from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import Annotated
from urllib.parse import urlencode, urlparse

import dns.resolver
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.config import settings
from app.core.crypto import blind_index
from app.core.security import create_access_token, decode_access_token
from app.db.session import get_db
from app.models.entities import (
    DeliverySuppression,
    EmailConnection,
    LandingToken,
    Organization,
    OrganizationBranding,
    OrganizationDomain,
    ScimCredential,
    SsoConnection,
)
from app.models.enums import (
    ConnectionStatus,
    DomainPurpose,
    EmailProviderKind,
    SuppressionReason,
    UserRole,
    VerificationStatus,
)
from app.schemas.enterprise import (
    DeliverySuppressionCreate,
    DeliverySuppressionRead,
    DomainVerificationRequest,
    EmailConnectionCreate,
    EmailConnectionRead,
    EmailConnectionTestRead,
    GoogleDomainWideDelegationRead,
    OrganizationBrandingRead,
    OrganizationBrandingUpdate,
    OrganizationDomainCreate,
    OrganizationDomainRead,
    ScimCredentialCreate,
    ScimCredentialRead,
    SsoConnectionCreate,
)
from app.services.audit import audit_log
from app.services.domains import create_custom_domain, ensure_platform_landing_domain, verify_custom_domain
from app.services.email_providers import EmailEnvelope, ProviderError, provider_for_connection
from app.services.public_tokens import hash_token_secret
from app.services.secret_store import SecretStoreError, secret_store

router = APIRouter()


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _domain_read(domain: OrganizationDomain, *, verification_value: str | None = None) -> OrganizationDomainRead:
    return OrganizationDomainRead.model_validate(domain).model_copy(update={"verification_value": verification_value})


@router.get("/orgs/current/domains", response_model=list[OrganizationDomainRead])
def list_domains(
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER)),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).one()
    ensure_platform_landing_domain(db, org)
    db.commit()
    return (
        db.query(OrganizationDomain)
        .filter(OrganizationDomain.organization_id == user.organization_id)
        .order_by(OrganizationDomain.purpose.asc(), OrganizationDomain.is_primary.desc(), OrganizationDomain.hostname.asc())
        .all()
    )


@router.post("/orgs/current/domains", response_model=OrganizationDomainRead, status_code=status.HTTP_201_CREATED)
def add_domain(
    payload: OrganizationDomainCreate,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).one()
    domain, verification_value = create_custom_domain(
        db,
        org=org,
        hostname=payload.hostname,
        purpose=payload.purpose,
    )
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="domain.create",
        resource_type="organization_domain",
        resource_id=str(domain.id),
        details={"hostname": domain.hostname, "purpose": domain.purpose.value},
    )
    db.commit()
    db.refresh(domain)
    return _domain_read(domain, verification_value=verification_value)


@router.post("/orgs/current/domains/{domain_id}/verify", response_model=OrganizationDomainRead)
def verify_domain(
    domain_id: uuid.UUID,
    payload: DomainVerificationRequest,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    domain = (
        db.query(OrganizationDomain)
        .filter(OrganizationDomain.id == domain_id, OrganizationDomain.organization_id == user.organization_id)
        .first()
    )
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    try:
        verify_custom_domain(domain, proof=payload.proof)
    except HTTPException:
        db.commit()
        raise
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="domain.verify",
        resource_type="organization_domain",
        resource_id=str(domain.id),
        details={"hostname": domain.hostname, "status": domain.status.value},
    )
    db.commit()
    db.refresh(domain)
    return domain


@router.post("/orgs/current/domains/{domain_id}/rotate-verification", response_model=OrganizationDomainRead)
def rotate_domain_verification(
    domain_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    domain = db.query(OrganizationDomain).filter(
        OrganizationDomain.id == domain_id,
        OrganizationDomain.organization_id == user.organization_id,
    ).first()
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    if domain.kind.value == "platform":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Managed domains do not require verification")
    raw = secrets.token_urlsafe(24)
    domain.verification_token_hash = hash_token_secret(raw)
    domain.status = VerificationStatus.PENDING
    domain.validation_error = None
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="domain.rotate_verification",
        resource_type="organization_domain",
        resource_id=str(domain.id),
    )
    db.commit()
    db.refresh(domain)
    return _domain_read(domain, verification_value=f"breachsim-verification={raw}")


@router.post("/orgs/current/domains/{domain_id}/set-primary", response_model=OrganizationDomainRead)
def set_primary_domain(
    domain_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    domain = (
        db.query(OrganizationDomain)
        .filter(OrganizationDomain.id == domain_id, OrganizationDomain.organization_id == user.organization_id)
        .first()
    )
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    if domain.status != VerificationStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only an active verified domain can be primary")
    db.query(OrganizationDomain).filter(
        OrganizationDomain.organization_id == user.organization_id,
        OrganizationDomain.purpose == domain.purpose,
    ).update({OrganizationDomain.is_primary: False}, synchronize_session=False)
    domain.is_primary = True
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="domain.set_primary",
        resource_type="organization_domain",
        resource_id=str(domain.id),
        details={"hostname": domain.hostname, "purpose": domain.purpose.value},
    )
    db.commit()
    db.refresh(domain)
    return domain


@router.delete("/orgs/current/domains/{domain_id}")
def deactivate_domain(
    domain_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    domain = (
        db.query(OrganizationDomain)
        .filter(OrganizationDomain.id == domain_id, OrganizationDomain.organization_id == user.organization_id)
        .first()
    )
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    if domain.kind.value == "platform":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The managed platform domain cannot be removed")
    active_token = (
        db.query(LandingToken)
        .filter(
            LandingToken.landing_hostname == domain.hostname,
            LandingToken.revoked_at.is_(None),
            LandingToken.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )
    if active_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Domain has active campaign links and can be removed after they expire",
        )
    domain.status = VerificationStatus.DEACTIVATED
    domain.deactivated_at = datetime.now(timezone.utc)
    domain.is_primary = False
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="domain.deactivate",
        resource_type="organization_domain",
        resource_id=str(domain.id),
    )
    db.commit()
    return {"status": "deactivated"}


def _get_or_create_branding(db: Session, organization_id) -> OrganizationBranding:
    branding = db.query(OrganizationBranding).filter(OrganizationBranding.organization_id == organization_id).first()
    if not branding:
        branding = OrganizationBranding(organization_id=organization_id)
        db.add(branding)
        db.flush()
    return branding


@router.get("/orgs/current/branding", response_model=OrganizationBrandingRead)
def get_branding(
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER)),
):
    branding = _get_or_create_branding(db, user.organization_id)
    db.commit()
    db.refresh(branding)
    return branding


@router.put("/orgs/current/branding", response_model=OrganizationBrandingRead)
def update_branding(
    payload: OrganizationBrandingUpdate,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    branding = _get_or_create_branding(db, user.organization_id)
    for key, value in payload.model_dump(mode="json").items():
        setattr(branding, key, value)
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="branding.update",
        resource_type="organization_branding",
        resource_id=str(branding.id),
        details={"primary_color": branding.primary_color, "sender_name": branding.sender_name},
    )
    db.commit()
    db.refresh(branding)
    return branding


@router.get("/email-connections", response_model=list[EmailConnectionRead])
def list_email_connections(
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER)),
):
    return (
        db.query(EmailConnection)
        .filter(EmailConnection.organization_id == user.organization_id)
        .order_by(EmailConnection.created_at.desc())
        .all()
    )


@router.post("/email-connections", response_model=EmailConnectionRead, status_code=status.HTTP_201_CREATED)
def create_email_connection(
    payload: EmailConnectionCreate,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    if payload.provider == EmailProviderKind.MICROSOFT_GRAPH and not payload.customer_tenant_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Microsoft tenant ID is required")
    if payload.provider == EmailProviderKind.MICROSOFT_GRAPH:
        try:
            uuid.UUID(str(payload.customer_tenant_id))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Microsoft tenant ID must be a tenant GUID",
            ) from exc
    if payload.provider == EmailProviderKind.GOOGLE_WORKSPACE and not payload.delegated_subject:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Google delegated subject is required")
    if (
        payload.provider == EmailProviderKind.GOOGLE_WORKSPACE
        and str(payload.delegated_subject).casefold() != str(payload.sender_email).casefold()
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Google delegated subject must match the configured sender mailbox",
        )

    scopes = (
        ["https://graph.microsoft.com/.default"]
        if payload.provider == EmailProviderKind.MICROSOFT_GRAPH
        else ["https://www.googleapis.com/auth/gmail.send"]
    )
    secret_ref = (
        settings.microsoft_graph_client_secret_ref
        if payload.provider == EmailProviderKind.MICROSOFT_GRAPH
        else settings.google_service_account_secret_ref
    )
    connection = EmailConnection(
        organization_id=user.organization_id,
        credential_secret_ref=secret_ref,
        scopes=scopes,
        status=ConnectionStatus.PENDING,
        **payload.model_dump(mode="python"),
    )
    db.add(connection)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This provider and sender mailbox are already configured",
        ) from exc
    connection.reconciliation_secret_ref = f"kv://email-reconciliation-{connection.id.hex}"
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="email_connection.create",
        resource_type="email_connection",
        resource_id=str(connection.id),
        details={"provider": connection.provider.value, "sender_email": connection.sender_email},
    )
    db.commit()
    db.refresh(connection)
    return connection


def _tenant_connection(db: Session, connection_id: uuid.UUID, organization_id) -> EmailConnection:
    connection = db.query(EmailConnection).filter(
        EmailConnection.id == connection_id,
        EmailConnection.organization_id == organization_id,
    ).first()
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email connection not found")
    return connection


@router.get(
    "/email-connections/{connection_id}/google-domain-wide-delegation",
    response_model=GoogleDomainWideDelegationRead,
)
def get_google_domain_wide_delegation_setup(
    connection_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    """Return the non-secret values a Workspace super admin must authorize.

    Google domain-wide delegation is an Admin Console grant, not an interactive
    OAuth callback. The service-account private key remains in Key Vault and is
    never returned to the tenant administrator or stored in SQL.
    """
    connection = _tenant_connection(db, connection_id, user.organization_id)
    if connection.provider != EmailProviderKind.GOOGLE_WORKSPACE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Connection is not Google Workspace")
    try:
        service_account_info = json.loads(secret_store.get(connection.credential_secret_ref))
        oauth_client_id = str(service_account_info["client_id"]).strip()
    except (SecretStoreError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google service-account credential is not available in the platform secret store",
        ) from exc
    if not oauth_client_id.isdigit():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google service-account credential does not contain a valid OAuth client ID",
        )
    return GoogleDomainWideDelegationRead(
        connection_id=connection.id,
        admin_console_url="https://admin.google.com/ac/owl/domainwidedelegation",
        oauth_client_id=oauth_client_id,
        oauth_scope="https://www.googleapis.com/auth/gmail.send",
        delegated_subject=connection.delegated_subject,
    )


def _suppression_read(row: DeliverySuppression) -> DeliverySuppressionRead:
    return DeliverySuppressionRead(
        id=row.id,
        reference=f"suppressed-{row.email_hash[:12]}",
        reason=row.reason,
        provider=row.provider,
        active=row.active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/orgs/current/delivery-suppressions", response_model=list[DeliverySuppressionRead])
def list_delivery_suppressions(
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER)),
):
    rows = (
        db.query(DeliverySuppression)
        .filter(DeliverySuppression.organization_id == user.organization_id)
        .order_by(DeliverySuppression.active.desc(), DeliverySuppression.created_at.desc())
        .all()
    )
    return [_suppression_read(row) for row in rows]


@router.post(
    "/orgs/current/delivery-suppressions",
    response_model=DeliverySuppressionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_delivery_suppression(
    payload: DeliverySuppressionCreate,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    if payload.reason not in {SuppressionReason.ADMINISTRATIVE, SuppressionReason.OPT_OUT}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Manual exclusions may use only administrative or opt_out reasons",
        )
    email_hash = blind_index(str(payload.email), namespace="employee-email")
    row = db.query(DeliverySuppression).filter(
        DeliverySuppression.organization_id == user.organization_id,
        DeliverySuppression.email_hash == email_hash,
    ).first()
    if row:
        row.reason = payload.reason
        row.active = True
        row.provider = None
        row.details = {"note": payload.note} if payload.note else {}
    else:
        row = DeliverySuppression(
            organization_id=user.organization_id,
            email_hash=email_hash,
            reason=payload.reason,
            provider=None,
            active=True,
            details={"note": payload.note} if payload.note else {},
        )
        db.add(row)
    db.flush()
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="delivery_suppression.create",
        resource_type="delivery_suppression",
        resource_id=str(row.id),
        details={"reference": f"suppressed-{email_hash[:12]}", "reason": payload.reason.value},
    )
    db.commit()
    db.refresh(row)
    return _suppression_read(row)


@router.delete("/orgs/current/delivery-suppressions/{suppression_id}", response_model=DeliverySuppressionRead)
def deactivate_delivery_suppression(
    suppression_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    row = db.query(DeliverySuppression).filter(
        DeliverySuppression.id == suppression_id,
        DeliverySuppression.organization_id == user.organization_id,
    ).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery exclusion not found")
    row.active = False
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="delivery_suppression.deactivate",
        resource_type="delivery_suppression",
        resource_id=str(row.id),
    )
    db.commit()
    db.refresh(row)
    return _suppression_read(row)


@router.post("/email-connections/{connection_id}/microsoft-admin-consent")
def start_microsoft_admin_consent(
    connection_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    connection = _tenant_connection(db, connection_id, user.organization_id)
    if connection.provider != EmailProviderKind.MICROSOFT_GRAPH:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Connection is not Microsoft Graph")
    if not settings.microsoft_graph_client_id or not settings.microsoft_graph_redirect_uri:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Microsoft OAuth is not configured")
    state = create_access_token(
        str(user.id),
        extra={
            "purpose": "microsoft_admin_consent",
            "organization_id": str(user.organization_id),
            "connection_id": str(connection.id),
        },
    )
    params = {
        "client_id": settings.microsoft_graph_client_id,
        "redirect_uri": settings.microsoft_graph_redirect_uri,
        "state": state,
    }
    return {
        "connection": EmailConnectionRead.model_validate(connection),
        "authorization_url": f"https://login.microsoftonline.com/organizations/v2.0/adminconsent?{urlencode(params)}",
    }


@router.get("/email-connections/microsoft/callback", include_in_schema=False)
def microsoft_admin_consent_callback(
    state: str,
    tenant: str | None,
    admin_consent: str | None,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        claims = decode_access_token(state)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state is invalid") from exc
    if claims.get("purpose") != "microsoft_admin_consent" or admin_consent != "True" or not tenant:
        return {"status": "denied"}
    try:
        connection_id = uuid.UUID(str(claims.get("connection_id")))
        organization_id = uuid.UUID(str(claims.get("organization_id")))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state is invalid") from exc
    connection = db.query(EmailConnection).filter(
        EmailConnection.id == connection_id,
        EmailConnection.organization_id == organization_id,
        EmailConnection.provider == EmailProviderKind.MICROSOFT_GRAPH,
    ).first()
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email connection not found")
    if connection.customer_tenant_id and connection.customer_tenant_id.casefold() != tenant.casefold():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Consented tenant does not match connection")
    connection.customer_tenant_id = tenant
    connection.authorized_at = datetime.now(timezone.utc)
    connection.status = ConnectionStatus.PENDING
    db.commit()
    return {"status": "authorized", "connection_id": str(connection.id)}


def _dns_txt(name: str) -> list[str]:
    try:
        return [b"".join(answer.strings).decode("utf-8") for answer in dns.resolver.resolve(name, "TXT", lifetime=4)]
    except Exception:
        return []


def _connection_readiness(db: Session, connection: EmailConnection) -> tuple[bool, bool, bool, bool]:
    sender_domain = connection.sender_email.rpartition("@")[2].casefold()
    verified = db.query(OrganizationDomain).filter(
        OrganizationDomain.organization_id == connection.organization_id,
        OrganizationDomain.purpose == DomainPurpose.SENDER,
        OrganizationDomain.status == VerificationStatus.ACTIVE,
        OrganizationDomain.hostname == sender_domain,
    ).first() is not None
    spf = any(value.casefold().startswith("v=spf1") for value in _dns_txt(sender_domain))
    dmarc = any(value.casefold().startswith("v=dmarc1") for value in _dns_txt(f"_dmarc.{sender_domain}"))
    selectors = ["selector1", "selector2"] if connection.provider == EmailProviderKind.MICROSOFT_GRAPH else ["google"]
    dkim = any(_dns_txt(f"{selector}._domainkey.{sender_domain}") for selector in selectors)
    return verified, spf, dmarc, dkim


@router.post("/email-connections/{connection_id}/health", response_model=EmailConnectionTestRead)
def check_email_connection(
    connection_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    connection = _tenant_connection(db, connection_id, user.organization_id)
    provider_authorized = False
    try:
        provider_for_connection(connection).health_check()
    except (ProviderError, ValueError) as exc:
        connection.status = ConnectionStatus.DEGRADED
        connection.last_error = str(exc)[:2000]
    else:
        provider_authorized = True
        connection.status = ConnectionStatus.HEALTHY
        connection.last_error = None
        connection.authorized_at = connection.authorized_at or datetime.now(timezone.utc)
    connection.last_health_check_at = datetime.now(timezone.utc)
    verified, spf, dmarc, dkim = _connection_readiness(db, connection)
    db.commit()
    db.refresh(connection)
    return EmailConnectionTestRead(
        connection=EmailConnectionRead.model_validate(connection),
        provider_authorized=provider_authorized,
        sender_domain_verified=verified,
        spf_present=spf,
        dmarc_present=dmarc,
        dkim_present=dkim,
    )


@router.post("/email-connections/{connection_id}/test", response_model=EmailConnectionTestRead)
def send_email_connection_test(
    connection_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    connection = _tenant_connection(db, connection_id, user.organization_id)
    verified, spf, dmarc, dkim = _connection_readiness(db, connection)
    if not verified:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Sender domain must be verified before test send")
    envelope = EmailEnvelope(
        recipient=connection.sender_email,
        sender_email=connection.sender_email,
        sender_name=connection.sender_name,
        subject="BreachSim connection verification",
        text_body="Your customer-owned email connection is working. This is an administrative test, not a campaign.",
        html_body=(
            "<p>Your customer-owned email connection is working.</p>"
            "<p>This is an administrative test, not a campaign.</p>"
        ),
        idempotency_key=f"connection-test:{connection.id}:{secrets.token_urlsafe(8)}",
    )
    try:
        result = provider_for_connection(connection).send(envelope)
    except (ProviderError, ValueError) as exc:
        connection.status = ConnectionStatus.DEGRADED
        connection.last_error = str(exc)[:2000]
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Provider rejected the test message") from exc
    connection.status = ConnectionStatus.HEALTHY
    connection.last_health_check_at = datetime.now(timezone.utc)
    connection.last_error = None
    db.commit()
    db.refresh(connection)
    return EmailConnectionTestRead(
        connection=EmailConnectionRead.model_validate(connection),
        provider_authorized=True,
        sender_domain_verified=verified,
        spf_present=spf,
        dmarc_present=dmarc,
        dkim_present=dkim,
        test_message_status=result.provider_status,
    )


@router.post("/email-connections/{connection_id}/revoke", response_model=EmailConnectionRead)
def revoke_email_connection(
    connection_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    connection = (
        db.query(EmailConnection)
        .filter(EmailConnection.id == connection_id, EmailConnection.organization_id == user.organization_id)
        .first()
    )
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email connection not found")
    connection.status = ConnectionStatus.REVOKED
    connection.revoked_at = datetime.now(timezone.utc)
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="email_connection.revoke",
        resource_type="email_connection",
        resource_id=str(connection.id),
    )
    db.commit()
    db.refresh(connection)
    return connection


@router.post("/orgs/current/scim-credentials", response_model=ScimCredentialRead, status_code=status.HTTP_201_CREATED)
def create_scim_credential(
    payload: ScimCredentialCreate,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    raw = secrets.token_urlsafe(36)
    credential = ScimCredential(
        organization_id=user.organization_id,
        token_prefix=raw[:12],
        token_hash=hash_token_secret(raw),
        description=payload.description,
    )
    db.add(credential)
    db.flush()
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="scim_credential.create",
        resource_type="scim_credential",
        resource_id=str(credential.id),
    )
    db.commit()
    db.refresh(credential)
    return ScimCredentialRead(
        id=credential.id,
        token_prefix=credential.token_prefix,
        description=credential.description,
        created_at=credential.created_at,
        last_used_at=credential.last_used_at,
        revoked_at=credential.revoked_at,
        token=raw,
    )


@router.get("/orgs/current/scim-credentials", response_model=list[ScimCredentialRead])
def list_scim_credentials(
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    return db.query(ScimCredential).filter(
        ScimCredential.organization_id == user.organization_id,
    ).order_by(ScimCredential.created_at.desc()).all()


@router.post("/orgs/current/scim-credentials/{credential_id}/revoke", response_model=ScimCredentialRead)
def revoke_scim_credential(
    credential_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    credential = db.query(ScimCredential).filter(
        ScimCredential.id == credential_id,
        ScimCredential.organization_id == user.organization_id,
    ).first()
    if not credential:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SCIM credential not found")
    credential.revoked_at = datetime.now(timezone.utc)
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="scim_credential.revoke",
        resource_type="scim_credential",
        resource_id=str(credential.id),
    )
    db.commit()
    db.refresh(credential)
    return credential


@router.post("/orgs/current/sso-connections", status_code=status.HTTP_201_CREATED)
def create_sso_connection(
    payload: SsoConnectionCreate,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    allowed_domains = sorted({domain.strip().casefold() for domain in payload.allowed_domains})
    if not allowed_domains:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one SSO domain is required")
    verified_domains = {
        row.hostname.casefold()
        for row in db.query(OrganizationDomain).filter(
            OrganizationDomain.organization_id == user.organization_id,
            OrganizationDomain.purpose == DomainPurpose.RECIPIENT,
            OrganizationDomain.status == VerificationStatus.ACTIVE,
        )
    }
    unverified = sorted(set(allowed_domains) - verified_domains)
    if unverified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Verify these recipient domains before enabling SSO: {', '.join(unverified)}",
        )
    issuer = str(payload.issuer).rstrip("/")
    parsed_issuer = urlparse(issuer)
    if payload.provider == "google" and issuer != "https://accounts.google.com":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Google issuer must be https://accounts.google.com",
        )
    if payload.provider == "entra":
        path_parts = [part for part in parsed_issuer.path.split("/") if part]
        tenant_is_uuid = bool(path_parts) and _is_uuid(path_parts[0])
        if (
            parsed_issuer.scheme != "https"
            or parsed_issuer.hostname != "login.microsoftonline.com"
            or len(path_parts) != 2
            or not tenant_is_uuid
            or path_parts[1] != "v2.0"
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Entra issuer must use the customer tenant GUID, not common or organizations",
            )
    connection = SsoConnection(
        organization_id=user.organization_id,
        provider=payload.provider,
        issuer=issuer,
        client_id=payload.client_id,
        client_secret_ref=payload.client_secret_ref,
        allowed_domains=allowed_domains,
        group_role_mappings={key: value.value for key, value in payload.group_role_mappings.items()},
        status=ConnectionStatus.PENDING,
    )
    db.add(connection)
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="sso_connection.create",
        resource_type="sso_connection",
        details={"provider": payload.provider, "allowed_domains": allowed_domains},
    )
    db.commit()
    db.refresh(connection)
    return {
        "id": str(connection.id),
        "provider": connection.provider,
        "issuer": connection.issuer,
        "allowed_domains": connection.allowed_domains,
        "status": connection.status.value,
    }


@router.get("/orgs/current/sso-connections")
def list_sso_connections(
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    connections = db.query(SsoConnection).filter(SsoConnection.organization_id == user.organization_id).all()
    return [
        {
            "id": str(connection.id),
            "provider": connection.provider,
            "issuer": connection.issuer,
            "client_id": connection.client_id,
            "allowed_domains": connection.allowed_domains,
            "group_role_mappings": connection.group_role_mappings,
            "status": connection.status.value,
        }
        for connection in connections
    ]
