from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import quote

import dns.resolver
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.config import settings
from app.core.crypto import blind_index
from app.core.security import hash_password, password_is_strong
from app.db.session import get_db
from app.models.entities import (
    EmailConnection,
    Organization,
    OrganizationBranding,
    OrganizationDomain,
    OrganizationInvitation,
    Role,
    ScimCredential,
    SsoConnection,
    User,
    UserRoleLink,
)
from app.models.enums import ConnectionStatus, DomainKind, DomainPurpose, UserRole, VerificationStatus
from app.schemas.enterprise import InvitationAccept, PlatformOrganizationCreate, PlatformOrganizationRead
from app.services.audit import audit_log
from app.services.domains import ensure_platform_landing_domain, public_origin
from app.services.mfa import issue_mfa_material
from app.services.public_tokens import hash_token_secret, issue_public_token, parse_public_token, token_secret_matches

router = APIRouter()


def _onboarding(db: Session, org: Organization) -> dict[str, bool]:
    verified_recipient = db.query(OrganizationDomain).filter(
        OrganizationDomain.organization_id == org.id,
        OrganizationDomain.purpose == DomainPurpose.RECIPIENT,
        OrganizationDomain.status == VerificationStatus.ACTIVE,
    ).first()
    landing = db.query(OrganizationDomain).filter(
        OrganizationDomain.organization_id == org.id,
        OrganizationDomain.purpose == DomainPurpose.LANDING,
        OrganizationDomain.status == VerificationStatus.ACTIVE,
    ).first()
    email = db.query(EmailConnection).filter(
        EmailConnection.organization_id == org.id,
        EmailConnection.status == ConnectionStatus.HEALTHY,
    ).first()
    return {
        "platform_domain": bool(landing),
        "recipient_domain": bool(verified_recipient),
        "branding": db.query(OrganizationBranding).filter(OrganizationBranding.organization_id == org.id).first()
        is not None,
        "email_connection": bool(email),
        "sso": db.query(SsoConnection).filter(SsoConnection.organization_id == org.id).first() is not None,
        "scim": db.query(ScimCredential).filter(
            ScimCredential.organization_id == org.id,
            ScimCredential.revoked_at.is_(None),
        ).first()
        is not None,
    }


def _serialize_org(db: Session, org: Organization, **updates) -> PlatformOrganizationRead:
    platform_domain = ensure_platform_landing_domain(db, org)
    return PlatformOrganizationRead(
        id=org.id,
        name=org.name,
        slug=org.slug,
        timezone=org.timezone,
        reporting_identity_mode=org.reporting_identity_mode,
        suspended_at=org.suspended_at,
        platform_url=public_origin(platform_domain.hostname),
        onboarding=_onboarding(db, org),
        **updates,
    )


@router.get("/organizations", response_model=list[PlatformOrganizationRead])
def list_organizations(
    db: Annotated[Session, Depends(get_db)],
    _user=Depends(require_roles(UserRole.PLATFORM_OPERATOR)),
):
    organizations = db.query(Organization).order_by(Organization.name.asc()).all()
    response = [_serialize_org(db, org) for org in organizations]
    db.commit()
    return response


@router.post("/organizations", response_model=PlatformOrganizationRead, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: PlatformOrganizationCreate,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.PLATFORM_OPERATOR)),
):
    if db.query(Organization).filter(Organization.slug == payload.slug).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Organization slug already exists")
    if db.query(User).filter(User.email == str(payload.admin_email).casefold()).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Administrator email is already registered")

    org = Organization(name=payload.name, slug=payload.slug, timezone=payload.timezone)
    db.add(org)
    db.flush()
    db.add(OrganizationBranding(organization_id=org.id, sender_name=payload.name))
    ensure_platform_landing_domain(db, org)

    issued = issue_public_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=72)
    invitation = OrganizationInvitation(
        organization_id=org.id,
        invited_by_user_id=user.id,
        email_ciphertext=str(payload.admin_email).casefold(),
        email_hash=blind_index(str(payload.admin_email), namespace="user-email"),
        invitee_name=payload.admin_name,
        role=UserRole.ADMIN,
        token_public_id=issued.public_id,
        token_secret_hash=hash_token_secret(issued.secret),
        expires_at=expires_at,
    )
    db.add(invitation)
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="platform.organization.create",
        resource_type="organization",
        resource_id=str(org.id),
        details={"name": org.name, "slug": org.slug, "admin_email_hash": invitation.email_hash},
    )
    db.commit()
    db.refresh(org)
    invite_url = f"{settings.frontend_base_url.rstrip('/')}/accept-invite?token={quote(issued.value, safe='')}"
    return _serialize_org(
        db,
        org,
        invite_token=issued.value,
        invite_url=invite_url,
        invite_expires_at=expires_at,
    )


@router.post("/organizations/{organization_id}/suspend", response_model=PlatformOrganizationRead)
def suspend_organization(
    organization_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.PLATFORM_OPERATOR)),
):
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    if org.id == user.organization_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot suspend your own platform organization")
    org.suspended_at = datetime.now(timezone.utc)
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="platform.organization.suspend",
        resource_type="organization",
        resource_id=str(org.id),
    )
    db.commit()
    return _serialize_org(db, org)


@router.post("/organizations/{organization_id}/reactivate", response_model=PlatformOrganizationRead)
def reactivate_organization(
    organization_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.PLATFORM_OPERATOR)),
):
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    org.suspended_at = None
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="platform.organization.reactivate",
        resource_type="organization",
        resource_id=str(org.id),
    )
    db.commit()
    return _serialize_org(db, org)


@router.post("/organizations/{organization_id}/domains/{domain_id}/activate-edge")
def activate_custom_landing_edge(
    organization_id: uuid.UUID,
    domain_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.PLATFORM_OPERATOR)),
):
    domain = db.query(OrganizationDomain).filter(
        OrganizationDomain.id == domain_id,
        OrganizationDomain.organization_id == organization_id,
        OrganizationDomain.purpose == DomainPurpose.LANDING,
        OrganizationDomain.kind == DomainKind.CUSTOM,
    ).first()
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom landing domain not found")
    if domain.status != VerificationStatus.VERIFIED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Domain ownership must be verified first")
    if not settings.front_door_endpoint_hostname:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Front Door is not configured")
    try:
        cname_targets = {
            str(answer.target).rstrip(".").casefold()
            for answer in dns.resolver.resolve(domain.hostname, "CNAME", lifetime=5)
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Landing CNAME was not found") from exc
    accepted_targets = {
        settings.front_door_endpoint_hostname.rstrip(".").casefold(),
        f"edge.{settings.platform_training_domain}".rstrip(".").casefold(),
    }
    if not cname_targets.intersection(accepted_targets):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Landing CNAME does not target this platform")
    try:
        probe = httpx.get(f"https://{domain.hostname}/health/ready", timeout=10, follow_redirects=False)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Managed TLS edge is not ready") from exc
    if probe.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Managed TLS edge is not ready")
    domain.status = VerificationStatus.ACTIVE
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="platform.domain.activate_edge",
        resource_type="organization_domain",
        resource_id=str(domain.id),
        details={"organization_id": str(organization_id), "hostname": domain.hostname},
    )
    db.commit()
    return {"status": "active", "hostname": domain.hostname}


@router.post("/invitations/accept", status_code=status.HTTP_201_CREATED)
def accept_invitation(payload: InvitationAccept, db: Annotated[Session, Depends(get_db)]):
    parsed = parse_public_token(payload.token)
    if not parsed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invitation")
    public_id, secret = parsed
    invitation = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.token_public_id == public_id,
        OrganizationInvitation.accepted_at.is_(None),
        OrganizationInvitation.revoked_at.is_(None),
    ).first()
    if not invitation or not token_secret_matches(secret, invitation.token_secret_hash):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invitation")
    expires_at = invitation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invitation has expired")
    if not password_is_strong(payload.password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 14 characters with upper, lower, number, and symbol",
        )
    email = invitation.email_ciphertext.casefold()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
    role = db.query(Role).filter(Role.name == invitation.role).first()
    if not role:
        role = Role(name=invitation.role)
        db.add(role)
        db.flush()
    mfa_secret, provisioning_uri, recovery_codes, recovery_hashes = issue_mfa_material(email)
    new_user = User(
        organization_id=invitation.organization_id,
        email=email,
        full_name=payload.full_name or invitation.invitee_name,
        password_hash=hash_password(payload.password),
        mfa_enabled=True,
        mfa_secret=mfa_secret,
        mfa_recovery_hashes=recovery_hashes,
    )
    db.add(new_user)
    db.flush()
    db.add(UserRoleLink(user_id=new_user.id, role_id=role.id))
    invitation.accepted_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "status": "accepted",
        "user_id": str(new_user.id),
        "login_url": f"{settings.frontend_base_url}/login",
        "mfa_provisioning_uri": provisioning_uri,
        "mfa_recovery_codes": recovery_codes,
    }
