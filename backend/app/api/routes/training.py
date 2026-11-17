from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_operator, require_roles
from app.db.session import get_db
from app.models.entities import Employee, TrainingAssignment, TrainingModule
from app.models.enums import UserRole
from app.schemas.training import TrainingAssignmentRead, TrainingCompleteRequest, TrainingModuleRead
from app.services.scoring import recalculate_employee_risk
from app.services.training import complete_assignment

router = APIRouter()


@router.get("/training/modules", response_model=list[TrainingModuleRead])
def list_modules(db: Annotated[Session, Depends(get_db)], user=Depends(require_operator)):
    # A module belongs to one organization, or to none when it is shared platform content.
    return (
        db.query(TrainingModule)
        .filter(or_(TrainingModule.organization_id == user.organization_id, TrainingModule.organization_id.is_(None)))
        .order_by(TrainingModule.title.asc())
        .all()
    )


@router.get("/training/assignments", response_model=list[TrainingAssignmentRead])
def list_assignments(
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_operator),
    employee_id: uuid.UUID | None = Query(default=None),
) -> list[TrainingAssignment]:
    # Assignments carry no organization column of their own, so the tenant boundary is
    # the employee they belong to. Without this join every tenant's rows are returned.
    query = (
        db.query(TrainingAssignment)
        .join(Employee, Employee.id == TrainingAssignment.employee_id)
        .options(joinedload(TrainingAssignment.module))
        .filter(Employee.organization_id == user.organization_id)
    )
    if employee_id:
        query = query.filter(TrainingAssignment.employee_id == employee_id)
    return query.order_by(TrainingAssignment.created_at.desc()).all()


@router.post("/training/assignments/{assignment_id}/complete", response_model=TrainingAssignmentRead)
def complete_training(
    assignment_id: uuid.UUID,
    payload: TrainingCompleteRequest,
    db: Annotated[Session, Depends(get_db)],
    # Employees complete their own training through the employee portal. Operators may
    # record an offline completion, but read-only roles must not change risk scores.
    user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER)),
):
    assignment = (
        db.query(TrainingAssignment)
        .options(joinedload(TrainingAssignment.employee), joinedload(TrainingAssignment.module))
        .filter(TrainingAssignment.id == assignment_id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="Training assignment not found")
    employee = db.query(Employee).filter(Employee.id == assignment.employee_id).first()
    if user.organization_id != employee.organization_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    assignment = complete_assignment(db, assignment_id=assignment_id, employee=employee, dwell_seconds=payload.dwell_seconds)
    recalculate_employee_risk(db, employee)
    db.commit()
    db.refresh(assignment)
    return assignment
