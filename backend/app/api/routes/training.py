from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.entities import Employee, TrainingAssignment, TrainingModule
from app.models.enums import UserRole
from app.schemas.training import TrainingAssignmentRead, TrainingCompleteRequest, TrainingModuleRead
from app.services.scoring import recalculate_employee_risk
from app.services.training import complete_assignment

router = APIRouter()


@router.get("/training/modules", response_model=list[TrainingModuleRead])
def list_modules(db: Annotated[Session, Depends(get_db)], user=Depends(get_current_user)):
    return db.query(TrainingModule).order_by(TrainingModule.title.asc()).all()


@router.get("/training/assignments", response_model=list[TrainingAssignmentRead])
def list_assignments(
    db: Annotated[Session, Depends(get_db)],
    user=Depends(get_current_user),
    employee_id: str | None = Query(default=None),
) -> list[TrainingAssignment]:
    query = db.query(TrainingAssignment).options(joinedload(TrainingAssignment.module))
    if employee_id:
        query = query.filter(TrainingAssignment.employee_id == employee_id)
    return query.order_by(TrainingAssignment.created_at.desc()).all()


@router.post("/training/assignments/{assignment_id}/complete", response_model=TrainingAssignmentRead)
def complete_training(
    assignment_id: uuid.UUID,
    payload: TrainingCompleteRequest,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(get_current_user),
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
