from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.entities import EventLog, TrainingAssignment, TrainingCompletion, TrainingModule
from app.models.enums import EventType, TrainingAssignmentStatus
from app.services.events import create_event


def assign_micro_training(
    db: Session,
    *,
    employee,
    campaign_id,
    source_event: EventLog,
    channel: str,
    reason_codes: list[str],
) -> TrainingAssignment:
    module = (
        db.query(TrainingModule)
        .filter(TrainingModule.vector == channel)
        .filter(TrainingModule.primary_reason_code.in_(reason_codes or ["habit_autopilot"]))
        .first()
    )
    if not module:
        module = db.query(TrainingModule).filter(TrainingModule.vector == "general").first()
    assignment = TrainingAssignment(
        employee_id=employee.id,
        module_id=module.id,
        campaign_id=campaign_id,
        source_event_id=source_event.id,
        assigned_reason_codes=reason_codes,
        retest_scheduled_for=datetime.now(timezone.utc) + timedelta(days=14),
    )
    db.add(assignment)
    db.flush()
    return assignment


def complete_assignment(db: Session, *, assignment_id: str, employee, dwell_seconds: int) -> TrainingAssignment:
    assignment = (
        db.query(TrainingAssignment)
        .options(joinedload(TrainingAssignment.module))
        .filter(TrainingAssignment.id == assignment_id, TrainingAssignment.employee_id == employee.id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training assignment not found")

    assignment.status = TrainingAssignmentStatus.COMPLETED
    completion = TrainingCompletion(assignment_id=assignment.id, employee_id=employee.id, dwell_seconds=dwell_seconds)
    db.add(completion)
    create_event(
        db,
        organization_id=employee.organization_id,
        employee_id=employee.id,
        campaign_id=assignment.campaign_id,
        event_type=EventType.TRAINING_COMPLETED,
        channel=None,
        metadata={"assignment_id": str(assignment.id), "dwell_seconds": dwell_seconds},
    )
    db.commit()
    db.refresh(assignment)
    return assignment
