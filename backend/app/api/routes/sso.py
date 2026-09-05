from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from joserfc import jwt
from joserfc.jwk import KeySet
from joserfc.jwt import JWTClaimsRegistry
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.session import get_db
from app.models.entities import OidcTransaction, Organization, Role, SsoConnection, User, UserRoleLink
from app.models.enums import ConnectionStatus, UserRole
from app.services.auth import create_user_session
from app.services.public_tokens import hash_token_secret, token_secret_matches
from app.services.secret_store import SecretStoreError, secret_store
from app.services.session_cookies import set_session_cookies

router = APIRouter()


def _discovery(connection: SsoConnection) -> dict:
    try:
        response = httpx.get(
            f"{connection.issuer.rstrip('/')}/.well-known/openid-configuration",
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Identity provider is unavailable") from exc
    required = {"authorization_endpoint", "token_endpoint", "jwks_uri", "issuer"}
    if not required.issubset(payload):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Identity provider metadata is invalid")
    if str(payload["issuer"]).rstrip("/") != connection.issuer.rstrip("/"):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Identity provider issuer mismatch")
    return payload


@router.get("/sso/{organization_slug}/{provider}/start", include_in_schema=False)
def start_sso(
    organization_slug: str,
    provider: str,
    db: Annotated[Session, Depends(get_db)],
):
    org = db.query(Organization).filter(
        Organization.slug == organization_slug,
        Organization.suspended_at.is_(None),
    ).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    connection = db.query(SsoConnection).filter(
        SsoConnection.organization_id == org.id,
        SsoConnection.provider == provider,
        SsoConnection.status != ConnectionStatus.REVOKED,
    ).first()
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SSO connection not found")
    metadata = _discovery(connection)
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    db.add(
        OidcTransaction(
            organization_id=org.id,
            sso_connection_id=connection.id,
            state_hash=hash_token_secret(state),
            code_verifier=verifier,
            nonce=nonce,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
    )
    db.commit()
    params = {
        "client_id": connection.client_id,
        "response_type": "code",
        "redirect_uri": settings.sso_callback_url,
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return RedirectResponse(f"{metadata['authorization_endpoint']}?{urlencode(params)}", status_code=302)


@router.get("/sso/callback", include_in_schema=False)
def sso_callback(
    db: Annotated[Session, Depends(get_db)],
    state: str = Query(min_length=20, max_length=255),
    code: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    if error or not code:
        return RedirectResponse(f"{settings.frontend_base_url}/login?sso_error=authorization_denied", status_code=302)
    transactions = db.query(OidcTransaction).filter(
        OidcTransaction.used_at.is_(None),
        OidcTransaction.expires_at > datetime.now(timezone.utc),
    ).all()
    transaction = next((row for row in transactions if token_secret_matches(state, row.state_hash)), None)
    if not transaction:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SSO transaction is invalid or expired")
    connection = db.query(SsoConnection).filter(SsoConnection.id == transaction.sso_connection_id).one()
    metadata = _discovery(connection)
    try:
        client_secret = secret_store.get(connection.client_secret_ref)
    except SecretStoreError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="SSO secret is unavailable") from exc
    try:
        token_response = httpx.post(
            metadata["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.sso_callback_url,
                "client_id": connection.client_id,
                "client_secret": client_secret,
                "code_verifier": transaction.code_verifier,
            },
            timeout=15,
        )
        token_response.raise_for_status()
        id_token = token_response.json()["id_token"]
        jwks = httpx.get(metadata["jwks_uri"], timeout=10).json()
        token = jwt.decode(
            id_token,
            KeySet.import_key_set(jwks),
            algorithms=["RS256"],
        )
        claims = token.claims
        JWTClaimsRegistry(
            iss={"essential": True, "value": metadata["issuer"]},
            aud={"essential": True, "value": connection.client_id},
            exp={"essential": True},
        ).validate(claims)
        claim_nonce = str(claims.get("nonce") or "")
        if not claim_nonce or not secrets.compare_digest(claim_nonce, transaction.nonce):
            raise ValueError("OIDC nonce mismatch")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="SSO token validation failed") from exc

    email = str(claims.get("email") or claims.get("preferred_username") or "").casefold()
    subject = str(claims.get("sub") or "")
    email_domain = email.rpartition("@")[2]
    if connection.provider == "google" and claims.get("email_verified") is not True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Google email address is not verified")
    if not email or not subject or email_domain not in {domain.casefold() for domain in connection.allowed_domains}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SSO identity is outside the allowed domains")
    user = (
        db.query(User)
        .options(selectinload(User.roles).selectinload(UserRoleLink.role))
        .filter(
            User.organization_id == connection.organization_id,
            User.email == email,
            User.is_active.is_(True),
        )
        .first()
    )
    if not user:
        # Users are provisioned through a reviewed invitation or SCIM workflow; SSO
        # alone never creates an administrator account.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not provisioned")
    if user.external_subject and user.external_subject != subject:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SSO subject does not match the provisioned user")
    user.external_subject = subject

    groups = {str(group) for group in claims.get("groups", [])}
    mapped_roles = {
        UserRole(role_name)
        for group, role_name in connection.group_role_mappings.items()
        if group in groups
    }
    for role_name in mapped_roles:
        role = db.query(Role).filter(Role.name == role_name).first()
        if role and not any(link.role_id == role.id for link in user.roles):
            db.add(UserRoleLink(user_id=user.id, role_id=role.id))
    transaction.used_at = datetime.now(timezone.utc)
    connection.status = ConnectionStatus.HEALTHY
    connection.last_health_check_at = datetime.now(timezone.utc)
    db.flush()
    session = create_user_session(db, user, auth_method="oidc")
    response = RedirectResponse(f"{settings.frontend_base_url}/dashboard", status_code=302)
    set_session_cookies(response, session)
    return response
