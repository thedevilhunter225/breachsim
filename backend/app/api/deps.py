from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.entities import AuthSession, Organization, User, UserRoleLink
from app.models.enums import UserRole
from app.services.public_tokens import token_secret_matches

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    bearer_token = credentials.credentials if credentials else None
    cookie_token = request.cookies.get(settings.session_cookie_name)
    token = bearer_token or cookie_token
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    session = db.query(AuthSession).filter(AuthSession.token_jti == payload["jti"]).first()
    if not session or session.user_id != user_id or session.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is no longer active")
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has expired")
    now = datetime.now(timezone.utc)
    idle_expires_at = session.idle_expires_at
    if idle_expires_at is not None:
        if idle_expires_at.tzinfo is None:
            idle_expires_at = idle_expires_at.replace(tzinfo=timezone.utc)
        if idle_expires_at <= now:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has been idle too long")

    if cookie_token and not bearer_token and request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
        csrf_token = request.headers.get("X-CSRF-Token")
        if not csrf_token or not token_secret_matches(csrf_token, session.csrf_token_hash):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")

    user = (
        db.query(User)
        .options(selectinload(User.roles).selectinload(UserRoleLink.role))
        .filter(User.id == user_id, User.is_active.is_(True))
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user")
    organization = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not organization or organization.suspended_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization is suspended")
    session.last_seen_at = now
    session.idle_expires_at = now + timedelta(minutes=settings.session_idle_minutes)
    db.flush()
    return user


def get_role_names(user: User) -> list[str]:
    return [link.role.name.value for link in user.roles]


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        role_names = set(get_role_names(user))
        if not role_names.intersection({role.value for role in roles}):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return dependency
