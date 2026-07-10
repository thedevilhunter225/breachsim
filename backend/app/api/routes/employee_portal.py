from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.entities import ConsentRecord, Employee, TrainingAssignment
from app.models.enums import ConsentStatus
from app.services.audit import audit_log

router = APIRouter()


def _resolve_portal_employee(db: Session, user) -> Employee:
    employee = db.query(Employee).filter(Employee.portal_user_id == user.id).first()
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee portal is not linked for this user")
    return employee


@router.get("/employee-portal/me")
def portal_me(db: Annotated[Session, Depends(get_db)], user=Depends(get_current_user)):
    employee = _resolve_portal_employee(db, user)
    latest_profile = (
        db.query(Employee)
        .options(joinedload(Employee.context_profiles))
        .filter(Employee.id == employee.id)
        .first()
    )
    return {
        "employee_id": str(employee.id),
        "full_name": employee.full_name,
        "role_title": employee.role_title,
        "consent_status": employee.consent_status,
        "risk_score": employee.risk_score,
        "approved_context_summary": employee.approved_context_summary,
        "latest_profile": latest_profile.context_profiles[-1].employee_context_profile if latest_profile.context_profiles else None,
    }


@router.get("/employee-portal/history")
def portal_history(db: Annotated[Session, Depends(get_db)], user=Depends(get_current_user)):
    employee = _resolve_portal_employee(db, user)
    assignments = (
        db.query(TrainingAssignment)
        .options(joinedload(TrainingAssignment.module))
        .filter(TrainingAssignment.employee_id == employee.id)
        .order_by(TrainingAssignment.created_at.desc())
        .all()
    )
    return [
        {
            "id": str(assignment.id),
            "status": assignment.status,
            "assigned_reason_codes": assignment.assigned_reason_codes,
            "retest_scheduled_for": assignment.retest_scheduled_for,
            "module": {
                "id": str(assignment.module.id),
                "title": assignment.module.title,
                "vector": assignment.module.vector,
                "primary_reason_code": assignment.module.primary_reason_code,
                "guidance_points": assignment.module.guidance_points,
                "body": assignment.module.body,
            },
        }
        for assignment in assignments
    ]


@router.post("/employee-portal/opt-out")
def portal_opt_out(db: Annotated[Session, Depends(get_db)], user=Depends(get_current_user)):
    employee = _resolve_portal_employee(db, user)
    employee.consent_status = ConsentStatus.OPTED_OUT
    db.add(ConsentRecord(employee_id=employee.id, status=ConsentStatus.OPTED_OUT, source="employee_portal"))
    audit_log(db, organization_id=employee.organization_id, user_id=user.id, action="employee.opt_out", resource_type="employee", resource_id=str(employee.id))
    db.commit()
    return {"status": "opted_out"}


@router.post("/employee-portal/redaction-request")
def portal_redaction_request(db: Annotated[Session, Depends(get_db)], user=Depends(get_current_user)):
    employee = _resolve_portal_employee(db, user)
    employee.consent_status = ConsentStatus.REDACTION_REQUESTED
    db.add(ConsentRecord(employee_id=employee.id, status=ConsentStatus.REDACTION_REQUESTED, source="employee_portal"))
    audit_log(db, organization_id=employee.organization_id, user_id=user.id, action="employee.redaction_request", resource_type="employee", resource_id=str(employee.id))
    db.commit()
    return {"status": "redaction_requested"}
