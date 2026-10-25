from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.api.routes.public import _load_valid_landing_token, _validate_landing_host
from app.db.session import get_db
from app.models.entities import ConsentRecord, Employee, Organization, TrainingAssignment
from app.models.enums import ConsentStatus
from app.services.audit import audit_log
from app.services.scoring import recalculate_employee_risk, risk_trend
from app.services.training import complete_assignment

router = APIRouter()


class PortalTrainingCompleteRequest(BaseModel):
    dwell_seconds: int = Field(default=45, ge=0, le=3600)


def _resolve_portal_employee(db: Session, user) -> Employee:
    employee = db.query(Employee).filter(Employee.portal_user_id == user.id).first()
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee portal is not linked for this user")
    return employee


def _employee_from_exercise_link(db: Session, request: Request, portal_token: str | None) -> Employee:
    """Employees have no operator account; their own exercise link identifies them.

    The token travels in a header rather than the URL so it never reaches access logs,
    browser history or a Referer header. Expired or revoked links stop working here too.
    """
    if not portal_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Open the portal from the link at the end of a BreachSim exercise.",
        )
    landing_token = _load_valid_landing_token(db, portal_token)
    _validate_landing_host(request, landing_token)
    employee = db.query(Employee).filter(Employee.id == landing_token.employee_id).first()
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee record not found")
    return employee


def _training_rows(db: Session, employee: Employee) -> list[TrainingAssignment]:
    return (
        db.query(TrainingAssignment)
        .options(joinedload(TrainingAssignment.module))
        .filter(TrainingAssignment.employee_id == employee.id)
        .order_by(TrainingAssignment.created_at.desc())
        .all()
    )


def _portal_summary(db: Session, employee: Employee) -> dict:
    organization = db.query(Organization).filter(Organization.id == employee.organization_id).first()
    names = employee.full_name.split()
    assignments = _training_rows(db, employee)
    return {
        "first_name": names[0] if names else "there",
        "organization_name": organization.name if organization else None,
        "privacy_notice": organization.privacy_notice if organization else None,
        "consent_status": employee.consent_status.value,
        # A direction, not the score: the portal explains progress without exposing a number
        # anyone holding a forwarded exercise link could read.
        "trend": risk_trend(db, employee),
        "training": [
            {
                "id": str(assignment.id),
                "status": assignment.status.value,
                "title": assignment.module.title,
                "body": assignment.module.body,
                "guidance_points": assignment.module.guidance_points,
                "assigned_at": assignment.created_at.isoformat() if assignment.created_at else None,
                "retest_scheduled_for": (
                    assignment.retest_scheduled_for.isoformat() if assignment.retest_scheduled_for else None
                ),
            }
            for assignment in assignments
        ],
    }


def _record_consent_change(db: Session, employee: Employee, consent: ConsentStatus, *, user_id, action: str) -> None:
    employee.consent_status = consent
    db.add(ConsentRecord(employee_id=employee.id, status=consent, source="employee_portal"))
    audit_log(
        db,
        organization_id=employee.organization_id,
        user_id=user_id,
        action=action,
        resource_type="employee",
        resource_id=str(employee.id),
    )
    db.commit()


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
    assignments = _training_rows(db, employee)
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
    _record_consent_change(db, employee, ConsentStatus.OPTED_OUT, user_id=user.id, action="employee.opt_out")
    return {"status": "opted_out"}


@router.post("/employee-portal/redaction-request")
def portal_redaction_request(db: Annotated[Session, Depends(get_db)], user=Depends(get_current_user)):
    employee = _resolve_portal_employee(db, user)
    _record_consent_change(
        db, employee, ConsentStatus.REDACTION_REQUESTED, user_id=user.id, action="employee.redaction_request"
    )
    return {"status": "redaction_requested"}


# ---------------------------------------------------------------------------------------
# Employee self-service through an exercise link (no operator account required)
# ---------------------------------------------------------------------------------------


@router.get("/public/portal")
def public_portal(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    x_portal_token: Annotated[str | None, Header()] = None,
):
    employee = _employee_from_exercise_link(db, request, x_portal_token)
    return _portal_summary(db, employee)


@router.post("/public/portal/opt-out")
def public_portal_opt_out(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    x_portal_token: Annotated[str | None, Header()] = None,
):
    employee = _employee_from_exercise_link(db, request, x_portal_token)
    _record_consent_change(db, employee, ConsentStatus.OPTED_OUT, user_id=None, action="employee.opt_out")
    return _portal_summary(db, employee)


@router.post("/public/portal/redaction-request")
def public_portal_redaction_request(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    x_portal_token: Annotated[str | None, Header()] = None,
):
    employee = _employee_from_exercise_link(db, request, x_portal_token)
    _record_consent_change(
        db, employee, ConsentStatus.REDACTION_REQUESTED, user_id=None, action="employee.redaction_request"
    )
    return _portal_summary(db, employee)


@router.post("/public/portal/training/{assignment_id}/complete")
def public_portal_complete_training(
    assignment_id: uuid.UUID,
    payload: PortalTrainingCompleteRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    x_portal_token: Annotated[str | None, Header()] = None,
):
    employee = _employee_from_exercise_link(db, request, x_portal_token)
    # complete_assignment only finds assignments that belong to this employee.
    complete_assignment(db, assignment_id=assignment_id, employee=employee, dwell_seconds=payload.dwell_seconds)
    recalculate_employee_risk(db, employee)
    db.commit()
    return _portal_summary(db, employee)
