from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.entities import ConsentRecord, Department, Employee, EventLog, RiskScore, TrainingAssignment
from app.models.enums import EventType
from app.models.enums import UserRole
from app.schemas.employees import (
    ConsentUpdate,
    ContextProfileRead,
    EmployeeCreate,
    EmployeeImportPayload,
    EmployeeImportResult,
    EmployeeRead,
    EmployeeUpdate,
)
from app.services.audit import access_log, audit_log
from app.services.profiling import build_context_profile, ensure_context_profile

router = APIRouter()


def serialize_employee(employee: Employee) -> EmployeeRead:
    latest_profile = sorted(employee.context_profiles, key=lambda profile: profile.created_at, reverse=True)[0] if employee.context_profiles else None
    return EmployeeRead(
        id=str(employee.id),
        employee_id=employee.employee_id,
        full_name=employee.full_name,
        email=employee.email,
        phone=employee.phone,
        role_title=employee.role_title,
        approved_context_summary=employee.approved_context_summary,
        approved_public_profile_summary=employee.approved_public_profile_summary,
        training_preferences=employee.training_preferences,
        consent_status=employee.consent_status,
        risk_score=employee.risk_score,
        status=employee.status,
        department_id=str(employee.department_id) if employee.department_id else None,
        department_name=employee.department.name if employee.department else None,
        latest_context_profile=ContextProfileRead.model_validate(latest_profile) if latest_profile else None,
    )


@router.get("/employees", response_model=list[EmployeeRead])
def list_employees(
    db: Annotated[Session, Depends(get_db)],
    user=Depends(get_current_user),
    department_id: str | None = Query(default=None),
    risk_band: str | None = Query(default=None),
) -> list[EmployeeRead]:
    query = (
        db.query(Employee)
        .options(joinedload(Employee.department), joinedload(Employee.context_profiles))
        .filter(Employee.organization_id == user.organization_id)
    )
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    employees = query.order_by(Employee.full_name.asc()).all()
    if risk_band == "high":
        employees = [employee for employee in employees if employee.risk_score >= 60]
    elif risk_band == "medium":
        employees = [employee for employee in employees if 30 <= employee.risk_score < 60]
    elif risk_band == "low":
        employees = [employee for employee in employees if employee.risk_score < 30]
    return [serialize_employee(employee) for employee in employees]


@router.post("/employees", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
def create_employee(
    payload: EmployeeCreate,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER)),
) -> EmployeeRead:
    employee = Employee(organization_id=user.organization_id, **payload.model_dump())
    db.add(employee)
    db.flush()
    db.add(ConsentRecord(employee_id=employee.id, status=employee.consent_status, source="manual"))
    build_context_profile(db, employee)
    audit_log(db, organization_id=user.organization_id, user_id=user.id, action="employee.create", resource_type="employee", resource_id=str(employee.id), details={"employee_id": employee.employee_id})
    db.commit()
    db.refresh(employee)
    return serialize_employee(employee)


@router.post("/employees/import", response_model=EmployeeImportResult)
def import_employees(
    payload: EmployeeImportPayload,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER)),
) -> EmployeeImportResult:
    created = 0
    updated = 0
    errors: list[dict] = []
    departments = {department.name.lower(): department for department in db.query(Department).filter(Department.organization_id == user.organization_id).all()}

    for index, row in enumerate(payload.rows, start=1):
        department = departments.get(row.department.lower())
        if not department:
            errors.append({"row": index, "error": f"Unknown department {row.department}"})
            continue
        employee = (
            db.query(Employee)
            .filter(Employee.organization_id == user.organization_id, Employee.employee_id == row.employee_id)
            .first()
        )
        data = row.model_dump(exclude={"department"})
        if employee:
            for key, value in data.items():
                setattr(employee, key, value)
            employee.department_id = department.id
            updated += 1
        else:
            employee = Employee(organization_id=user.organization_id, department_id=department.id, **data)
            db.add(employee)
            db.flush()
            db.add(ConsentRecord(employee_id=employee.id, status=employee.consent_status, source="csv_import"))
            created += 1
        build_context_profile(db, employee)

    audit_log(db, organization_id=user.organization_id, user_id=user.id, action="employee.import", resource_type="employee", details={"created": created, "updated": updated, "error_count": len(errors)})
    db.commit()
    return EmployeeImportResult(created=created, updated=updated, errors=errors)


@router.get("/employees/{employee_id}", response_model=EmployeeRead)
def get_employee(employee_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], user=Depends(get_current_user)) -> EmployeeRead:
    employee = (
        db.query(Employee)
        .options(joinedload(Employee.department), joinedload(Employee.context_profiles))
        .filter(Employee.id == employee_id, Employee.organization_id == user.organization_id)
        .first()
    )
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    access_log(db, organization_id=user.organization_id, user_id=user.id, resource_type="employee", resource_id=str(employee.id))
    db.commit()
    return serialize_employee(employee)


@router.get("/employees/{employee_id}/report")
def get_employee_report(
    employee_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER, UserRole.AUDITOR)),
):
    employee = (
        db.query(Employee)
        .options(joinedload(Employee.department), joinedload(Employee.context_profiles))
        .filter(Employee.id == employee_id, Employee.organization_id == user.organization_id)
        .first()
    )
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    risk_scores = (
        db.query(RiskScore)
        .filter(RiskScore.employee_id == employee.id)
        .order_by(RiskScore.calculated_at.asc())
        .all()
    )
    all_events = (
        db.query(EventLog)
        .filter(EventLog.employee_id == employee.id)
        .order_by(EventLog.occurred_at.desc())
        .all()
    )
    assignments = (
        db.query(TrainingAssignment)
        .options(joinedload(TrainingAssignment.module))
        .filter(TrainingAssignment.employee_id == employee.id)
        .order_by(TrainingAssignment.created_at.desc())
        .all()
    )

    latest_risk = risk_scores[-1] if risk_scores else None
    first_score = risk_scores[0].score if risk_scores else employee.risk_score
    last_score = latest_risk.score if latest_risk else employee.risk_score
    if last_score < first_score:
        trend = "improving"
    elif last_score > first_score:
        trend = "worsening"
    else:
        trend = "stable"

    behavior_summary = {
        "opened_emails": sum(1 for event in all_events if event.event_type == EventType.OPENED_EMAIL),
        "clicked_links": sum(1 for event in all_events if event.event_type == EventType.CLICKED_LINK),
        "visited_landing_pages": sum(1 for event in all_events if event.event_type == EventType.VISITED_LANDING_PAGE),
        "reported": sum(1 for event in all_events if event.event_type == EventType.CLICKED_REPORT),
        "submitted_forms": sum(1 for event in all_events if event.event_type == EventType.SUBMITTED_FORM_BOOLEAN),
        "training_completed": sum(1 for event in all_events if event.event_type == EventType.TRAINING_COMPLETED),
        "last_event_at": all_events[0].occurred_at.isoformat() if all_events else None,
    }

    access_log(db, organization_id=user.organization_id, user_id=user.id, resource_type="employee_report", resource_id=str(employee.id))
    db.commit()
    return {
        "employee": serialize_employee(employee).model_dump(mode="json"),
        "current_risk_score": employee.risk_score,
        "trend": trend,
        "latest_breakdown": latest_risk.reason_breakdown if latest_risk else {},
        "risk_history": [
            {
                "date": score.calculated_at.isoformat(),
                "score": score.score,
            }
            for score in risk_scores
        ],
        "behavior_summary": behavior_summary,
        "events": [
            {
                "id": str(event.id),
                "event_type": event.event_type.value,
                "channel": event.channel.value if event.channel else None,
                "occurred_at": event.occurred_at.isoformat(),
                "metadata": event.event_metadata,
            }
            for event in all_events[:20]
        ],
        "training_assignments": [
            {
                "id": str(assignment.id),
                "status": assignment.status.value,
                "assigned_reason_codes": assignment.assigned_reason_codes,
                "retest_scheduled_for": assignment.retest_scheduled_for.isoformat() if assignment.retest_scheduled_for else None,
                "module_title": assignment.module.title,
                "module_body": assignment.module.body,
                "guidance_points": assignment.module.guidance_points,
            }
            for assignment in assignments
        ],
    }


@router.patch("/employees/{employee_id}", response_model=EmployeeRead)
def update_employee(
    employee_id: uuid.UUID,
    payload: EmployeeUpdate,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER)),
) -> EmployeeRead:
    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.organization_id == user.organization_id).first()
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(employee, key, value)
    build_context_profile(db, employee)
    audit_log(db, organization_id=user.organization_id, user_id=user.id, action="employee.update", resource_type="employee", resource_id=str(employee.id), details=payload.model_dump(exclude_none=True))
    db.commit()
    db.refresh(employee)
    return serialize_employee(employee)


@router.post("/employees/{employee_id}/consent", response_model=EmployeeRead)
def update_consent(
    employee_id: uuid.UUID,
    payload: ConsentUpdate,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER)),
) -> EmployeeRead:
    employee = (
        db.query(Employee)
        .options(joinedload(Employee.department), joinedload(Employee.context_profiles))
        .filter(Employee.id == employee_id, Employee.organization_id == user.organization_id)
        .first()
    )
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    employee.consent_status = payload.status
    db.add(ConsentRecord(employee_id=employee.id, status=payload.status, source=payload.source, note=payload.note))
    audit_log(db, organization_id=user.organization_id, user_id=user.id, action="employee.consent", resource_type="employee", resource_id=str(employee.id), details=payload.model_dump())
    db.commit()
    return serialize_employee(employee)


@router.post("/employees/{employee_id}/profile", response_model=ContextProfileRead)
def generate_profile(
    employee_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER, UserRole.AUDITOR)),
) -> ContextProfileRead:
    employee = (
        db.query(Employee)
        .options(joinedload(Employee.department))
        .filter(Employee.id == employee_id, Employee.organization_id == user.organization_id)
        .first()
    )
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    profile = build_context_profile(db, employee)
    audit_log(db, organization_id=user.organization_id, user_id=user.id, action="profile.generate", resource_type="employee", resource_id=str(employee.id))
    db.commit()
    return ContextProfileRead.model_validate(profile)
