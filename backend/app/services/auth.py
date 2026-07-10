from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_role_names
from app.core.security import verify_password
from app.models.entities import User, UserRoleLink
from app.schemas.auth import UserSummary


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = (
        db.query(User)
        .options(selectinload(User.roles).selectinload(UserRoleLink.role))
        .filter(User.email == email, User.is_active.is_(True))
        .first()
    )
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def serialize_user(user: User) -> UserSummary:
    return UserSummary(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        roles=get_role_names(user),
        organization_id=str(user.organization_id),
    )
