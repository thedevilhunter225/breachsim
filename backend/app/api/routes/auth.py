from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.api.deps import bearer_scheme, get_current_user
from app.core.config import is_production_environment, settings
from app.core.security import decode_access_token, verify_password
from app.db.session import get_db
from app.models.entities import AuthSession
from app.models.enums import UserRole
from app.schemas.auth import LoginRequest, MfaEnrollRequest, MfaEnrollResponse, TokenResponse
from app.services.auth import authenticate_user, create_user_session, serialize_user
from app.services.mfa import issue_mfa_material, verify_mfa_code
from app.services.session_cookies import clear_session_cookies, set_session_cookies

router = APIRouter()


def _api_client_token(request: Request, token: str) -> str | None:
    return token if request.headers.get("X-BreachSim-API-Client") == "bearer" else None


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    roles = {link.role.name for link in user.roles}
    mfa_required = user.mfa_enabled or (
        is_production_environment(settings.environment)
        and bool(roles.intersection({UserRole.ADMIN, UserRole.PLATFORM_OPERATOR}))
    )
    if mfa_required and not user.mfa_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="MFA enrollment is required for this account")
    if mfa_required and (not payload.mfa_code or not verify_mfa_code(user, payload.mfa_code)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="A valid MFA code is required")
    session = create_user_session(db, user)
    set_session_cookies(response, session)
    return TokenResponse(access_token=_api_client_token(request, session.access_token), user=serialize_user(user))


@router.post("/mfa/enroll", response_model=MfaEnrollResponse)
def enroll_mfa(
    payload: MfaEnrollRequest,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(get_current_user),
):
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")
    secret, provisioning_uri, recovery_codes, recovery_hashes = issue_mfa_material(user.email)
    user.mfa_secret = secret
    user.mfa_recovery_hashes = recovery_hashes
    user.mfa_enabled = True
    db.commit()
    return MfaEnrollResponse(
        secret=secret,
        provisioning_uri=provisioning_uri,
        recovery_codes=recovery_codes,
    )


@router.get("/me", response_model=TokenResponse)
def me(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    user=Depends(get_current_user),
) -> TokenResponse:
    token = credentials.credentials if credentials else request.cookies.get(settings.session_cookie_name, "")
    return TokenResponse(access_token=_api_client_token(request, token), user=serialize_user(user))


@router.post("/refresh", response_model=TokenResponse)
def refresh_session(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(get_current_user),
) -> TokenResponse:
    # Revoking the previous server session makes rotation meaningful even if an older
    # browser token is copied before the refresh.
    for existing in db.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)):
        existing.revoked_at = datetime.now(timezone.utc)
    db.flush()
    session = create_user_session(db, user, auth_method="refresh")
    set_session_cookies(response, session)
    return TokenResponse(access_token=_api_client_token(request, session.access_token), user=serialize_user(user))


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
    _user=Depends(get_current_user),
) -> dict[str, str]:
    token = credentials.credentials if credentials else request.cookies.get(settings.session_cookie_name, "")
    payload = decode_access_token(token)
    session = db.query(AuthSession).filter(AuthSession.token_jti == payload["jti"]).first()
    if session and session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        db.commit()
    clear_session_cookies(response)
    return {"status": "ok"}
