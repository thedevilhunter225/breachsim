from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_role_names, require_roles
from app.core.security import hash_password, password_is_strong
from app.db.session import get_db
from app.models.entities import AuthSession, Role, User, UserRoleLink
from app.models.enums import UserRole
from app.schemas.users import UserAccountCreate, UserAccountRead, UserAccountUpdate, UserPasswordReset
from app.services.audit import audit_log

router = APIRouter()


def _serialize(user: User) -> UserAccountRead:
    return UserAccountRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=get_role_names(user),
        is_active=user.is_active,
        created_at=user.created_at,
    )


def _load_user(db: Session, organization_id, user_id: uuid.UUID) -> User:
    user = (
        db.query(User)
        .options(selectinload(User.roles).selectinload(UserRoleLink.role))
        .filter(User.id == user_id, User.organization_id == organization_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _role_rows(db: Session, roles: list[UserRole]) -> list[Role]:
    rows = db.query(Role).filter(Role.name.in_(roles)).all()
    if len(rows) != len(set(roles)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more roles are unavailable")
    return rows


def _active_admin_count(db: Session, organization_id) -> int:
    return (
        db.query(User)
        .join(UserRoleLink, UserRoleLink.user_id == User.id)
        .join(Role, Role.id == UserRoleLink.role_id)
        .filter(
            User.organization_id == organization_id,
            User.is_active.is_(True),
            Role.name == UserRole.ADMIN,
        )
        .count()
    )


@router.get("/users", response_model=list[UserAccountRead])
def list_users(
    db: Annotated[Session, Depends(get_db)],
    actor=Depends(require_roles(UserRole.ADMIN)),
):
    users = (
        db.query(User)
        .options(selectinload(User.roles).selectinload(UserRoleLink.role))
        .filter(User.organization_id == actor.organization_id)
        .order_by(User.full_name.asc())
        .all()
    )
    return [_serialize(user) for user in users]


@router.post("/users", response_model=UserAccountRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserAccountCreate,
    db: Annotated[Session, Depends(get_db)],
    actor=Depends(require_roles(UserRole.ADMIN)),
):
    if not password_is_strong(payload.password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain uppercase, lowercase, number, and symbol.",
        )
    email = str(payload.email).lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists")

    user = User(
        organization_id=actor.organization_id,
        email=email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.flush()
    for role in _role_rows(db, payload.roles):
        db.add(UserRoleLink(user_id=user.id, role_id=role.id))
    audit_log(
        db,
        organization_id=actor.organization_id,
        user_id=actor.id,
        action="user.create",
        resource_type="user",
        resource_id=str(user.id),
        details={"email": email, "roles": [role.value for role in payload.roles]},
    )
    db.commit()
    return _serialize(_load_user(db, actor.organization_id, user.id))


@router.patch("/users/{user_id}", response_model=UserAccountRead)
def update_user(
    user_id: uuid.UUID,
    payload: UserAccountUpdate,
    db: Annotated[Session, Depends(get_db)],
    actor=Depends(require_roles(UserRole.ADMIN)),
):
    user = _load_user(db, actor.organization_id, user_id)
    current_roles = set(get_role_names(user))
    next_roles = set(role.value for role in payload.roles) if payload.roles is not None else current_roles
    next_active = payload.is_active if payload.is_active is not None else user.is_active

    if user.id == actor.id and not next_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate your own account")
    removes_active_admin = (
        user.is_active
        and UserRole.ADMIN.value in current_roles
        and (not next_active or UserRole.ADMIN.value not in next_roles)
    )
    if removes_active_admin and _active_admin_count(db, actor.organization_id) <= 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least two active administrators are required for separation of duties",
        )

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.roles is not None:
        user.roles.clear()
        db.flush()
        for role in _role_rows(db, payload.roles):
            user.roles.append(UserRoleLink(role_id=role.id))

    audit_log(
        db,
        organization_id=actor.organization_id,
        user_id=actor.id,
        action="user.update",
        resource_type="user",
        resource_id=str(user.id),
        details={"is_active": user.is_active, "roles": sorted(next_roles)},
    )
    db.commit()
    return _serialize(_load_user(db, actor.organization_id, user.id))


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: uuid.UUID,
    payload: UserPasswordReset,
    db: Annotated[Session, Depends(get_db)],
    actor=Depends(require_roles(UserRole.ADMIN)),
) -> dict[str, str]:
    if not password_is_strong(payload.new_password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain uppercase, lowercase, number, and symbol.",
        )
    user = _load_user(db, actor.organization_id, user_id)
    user.password_hash = hash_password(payload.new_password)
    now = datetime.now(timezone.utc)
    db.query(AuthSession).filter(
        AuthSession.user_id == user.id,
        AuthSession.revoked_at.is_(None),
    ).update({AuthSession.revoked_at: now}, synchronize_session=False)
    audit_log(
        db,
        organization_id=actor.organization_id,
        user_id=actor.id,
        action="user.password_reset",
        resource_type="user",
        resource_id=str(user.id),
    )
    db.commit()
    return {"status": "password_reset"}
