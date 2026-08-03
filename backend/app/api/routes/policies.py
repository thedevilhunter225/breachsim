from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.entities import PolicyVersion
from app.models.enums import UserRole
from app.schemas.policies import PolicyRead, PolicyUpdate
from app.services.audit import audit_log
from app.services.policy_engine import get_or_create_policy, snapshot_policy

router = APIRouter()


@router.get("/policies/current", response_model=PolicyRead)
def get_policy(db: Annotated[Session, Depends(get_db)], user=Depends(get_current_user)):
    return get_or_create_policy(db, user.organization_id)


@router.put("/policies/current", response_model=PolicyRead)
def update_policy(
    payload: PolicyUpdate,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    policy = get_or_create_policy(db, user.organization_id)
    for key, value in payload.model_dump().items():
        setattr(policy, key, value)
    db.add(PolicyVersion(policy_id=policy.id, changed_by_user_id=user.id, snapshot=snapshot_policy(policy)))
    audit_log(db, organization_id=user.organization_id, user_id=user.id, action="policy.update", resource_type="policy", resource_id=str(policy.id), details=payload.model_dump(mode="json"))
    db.commit()
    db.refresh(policy)
    return policy
