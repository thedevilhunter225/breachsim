from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.entities import Department, Employee, EventLog, RiskScore, TrainingCompletion
from app.models.enums import PROTECTIVE_EVENT_TYPES, RISKY_EVENT_TYPES, EventType

#: Per-event contribution to an employee's risk score.
#:
#: Interactive-channel failures are weighted above a link click because disclosing on a
#: call or acting on synthetic media bypasses every technical control the organization
#: has — there is no gateway, filter or sandbox between the attacker and the decision.
WEIGHTS = {
    EventType.CLICKED_LINK: 20,
    EventType.SCANNED_QR: 15,
    EventType.SUBMITTED_FORM_BOOLEAN: 40,
    EventType.REPLIED_SMS: 18,
    EventType.DISCLOSED_ON_CALL: 35,
    EventType.TRUSTED_SYNTHETIC_MEDIA: 45,
    EventType.MARKED_SPAM: -10,
    EventType.CLICKED_REPORT: -25,
    EventType.TRAINING_COMPLETED: -10,
    EventType.VERIFIED_CALLER: -20,
    EventType.ENDED_CALL_SAFELY: -22,
    EventType.VERIFIED_OUT_OF_BAND: -25,
    EventType.FLAGGED_SYNTHETIC_MEDIA: -30,
}


def recalculate_employee_risk(db: Session, employee: Employee) -> RiskScore:
    events = db.query(EventLog).filter(EventLog.employee_id == employee.id).all()
    completions = db.query(TrainingCompletion).filter(TrainingCompletion.employee_id == employee.id).count()
    breakdown = defaultdict(int)
    score = 0
    failure_events = 0

    for event in events:
        weight = WEIGHTS.get(event.event_type, 0)
        score += weight
        breakdown[event.event_type.value] += weight
        if event.event_type in RISKY_EVENT_TYPES:
            failure_events += 1

    if failure_events >= 2:
        score += 10
        breakdown["repeated_failures"] += 10

    if completions:
        score -= min(completions * 3, 10)
        breakdown["completion_trend"] -= min(completions * 3, 10)

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)
    recent_reports = sum(
        1
        for event in events
        if event.event_type in PROTECTIVE_EVENT_TYPES
        and event.event_type != EventType.TRAINING_COMPLETED
        and (event.occurred_at.replace(tzinfo=None) if event.occurred_at.tzinfo else event.occurred_at) >= cutoff
    )
    if recent_reports:
        score -= 5
        breakdown["recent_improvement"] -= 5

    score = max(0, min(100, score))
    employee.risk_score = score

    risk = RiskScore(
        organization_id=employee.organization_id,
        employee_id=employee.id,
        department_id=employee.department_id,
        score=score,
        reason_breakdown=dict(breakdown),
    )
    db.add(risk)
    db.flush()
    return risk


def department_risk_rows(db: Session, organization_id) -> list[tuple[str, float]]:
    rows = (
        db.query(Department.name, func.avg(Employee.risk_score))
        .join(Employee, Employee.department_id == Department.id)
        .filter(Department.organization_id == organization_id)
        .group_by(Department.name)
        .all()
    )
    return [(name, float(avg or 0)) for name, avg in rows]
