from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_role_names
from app.core.config import settings
from app.core.security import create_access_token, hash_password, password_needs_rehash, verify_password
from app.models.entities import AuthSession, User, UserRoleLink
from app.schemas.auth import UserSummary
from app.services.public_tokens import hash_token_secret

DUMMY_PASSWORD_HASH = hash_password("not-the-user-password")


@dataclass(frozen=True)
class SessionMaterial:
    access_token: str
    csrf_token: str


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = (
        db.query(User)
        .options(selectinload(User.roles).selectinload(UserRoleLink.role))
        .filter(User.email == email, User.is_active.is_(True))
        .first()
    )
    if not user:
        verify_password(password, DUMMY_PASSWORD_HASH)
        return None
    if not verify_password(password, user.password_hash):
        return None
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        db.flush()
    return user


def create_user_session(db: Session, user: User, *, auth_method: str = "password") -> SessionMaterial:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=settings.session_absolute_hours)
    idle_expires_at = now + timedelta(minutes=settings.session_idle_minutes)
    prune_before = now - timedelta(days=7)
    db.query(AuthSession).filter(
        or_(
            AuthSession.expires_at < now,
            AuthSession.revoked_at < prune_before,
        )
    ).delete(synchronize_session=False)
    token_jti = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            user_id=user.id,
            token_jti=token_jti,
            expires_at=expires_at,
            idle_expires_at=idle_expires_at,
            last_seen_at=now,
            csrf_token_hash=hash_token_secret(csrf_token),
            auth_method=auth_method,
        )
    )
    db.commit()
    return SessionMaterial(
        access_token=create_access_token(
            str(user.id),
            token_id=token_jti,
            expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        ),
        csrf_token=csrf_token,
    )


def serialize_user(user: User) -> UserSummary:
    return UserSummary(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        roles=get_role_names(user),
        organization_id=str(user.organization_id),
    )
