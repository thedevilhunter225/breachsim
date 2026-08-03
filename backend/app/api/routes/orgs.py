from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.entities import Department, Organization
from app.models.enums import UserRole
from app.schemas.employees import DepartmentCreate, DepartmentRead
from app.services.audit import audit_log
from app.services.deletion import delete_department

router = APIRouter()


@router.get("/orgs/current")
def get_current_org(db: Annotated[Session, Depends(get_db)], user=Depends(get_current_user)) -> dict:
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "timezone": org.timezone,
        "retention_days": org.retention_days,
        "privacy_notice": org.privacy_notice,
    }


@router.patch("/orgs/current")
def update_current_org(
    payload: dict,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
) -> dict:
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    for field in ["name", "timezone", "retention_days", "privacy_notice"]:
        if field in payload:
            setattr(org, field, payload[field])
    audit_log(db, organization_id=user.organization_id, user_id=user.id, action="org.update", resource_type="organization", resource_id=str(org.id), details=payload)
    db.commit()
    db.refresh(org)
    return {"id": str(org.id), "name": org.name, "slug": org.slug, "timezone": org.timezone, "retention_days": org.retention_days, "privacy_notice": org.privacy_notice}


@router.get("/departments", response_model=list[DepartmentRead])
def list_departments(db: Annotated[Session, Depends(get_db)], user=Depends(get_current_user)) -> list[Department]:
    return db.query(Department).filter(Department.organization_id == user.organization_id).order_by(Department.name.asc()).all()


@router.post("/departments", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER)),
) -> Department:
    exists = (
        db.query(Department)
        .filter(Department.organization_id == user.organization_id, Department.code == payload.code)
        .first()
    )
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Department code already exists")
    department = Department(organization_id=user.organization_id, name=payload.name, code=payload.code)
    db.add(department)
    db.flush()
    audit_log(db, organization_id=user.organization_id, user_id=user.id, action="department.create", resource_type="department", resource_id=str(department.id), details=payload.model_dump(mode="json"))
    db.commit()
    db.refresh(department)
    return department


@router.delete("/departments/{department_id}")
def delete_department_route(
    department_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    """Delete a department. Refused while employees are still assigned to it."""
    result = delete_department(
        db, organization_id=user.organization_id, department_id=department_id, actor=user
    )
    return result.as_dict()
