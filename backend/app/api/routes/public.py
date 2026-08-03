from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Campaign, DeliveryAttempt, Employee, LandingToken, Scenario
from app.models.enums import EventType
from app.services.events import classify_failure_reasons, create_event, resolve_scenario_for_token
from app.services.scoring import recalculate_employee_risk
from app.services.simulation import complete_simulation, load_simulation, record_response
from app.services.training import assign_micro_training

router = APIRouter()


class SimulationResponseRequest(BaseModel):
    step_key: str = Field(min_length=1, max_length=64)
    response_key: str = Field(min_length=1, max_length=64)
    elapsed_ms: int = 0


@router.get("/training/{token}")
def get_training_page(token: str, db: Annotated[Session, Depends(get_db)]):
    landing_token = db.query(LandingToken).filter(LandingToken.token == token).first()
    if not landing_token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid token")
    delivery_attempt = db.query(DeliveryAttempt).filter(DeliveryAttempt.id == landing_token.delivery_attempt_id).first()
    campaign = db.query(Campaign).filter(Campaign.id == landing_token.campaign_id).first()
    scenario = resolve_scenario_for_token(db, landing_token)
    latest_version = None
    if scenario and scenario.versions:
        latest_version = max(scenario.versions, key=lambda version: version.version_number)

    return {
        "token": landing_token.token,
        "landing_type": landing_token.landing_type,
        "campaign_id": str(landing_token.campaign_id),
        "employee_id": str(landing_token.employee_id),
        "training_banner": "Training simulation. No real credentials are stored.",
        "campaign_name": campaign.name if campaign else None,
        "scenario": {
            "title": scenario.title if scenario else None,
            "channel": scenario.channel.value if scenario else landing_token.landing_type,
            "theme": scenario.theme if scenario else None,
            "difficulty_level": scenario.difficulty_level.value if scenario else None,
            "subject": latest_version.subject if latest_version else None,
            "body_copy": latest_version.body_copy if latest_version else None,
            "cta_text": latest_version.cta_text if latest_version else None,
            "landing_page_copy": latest_version.landing_page_copy if latest_version else None,
            "triggers": latest_version.detected_persuasion_triggers if latest_version else [],
        },
        "preview_payload": delivery_attempt.preview_payload if delivery_attempt else {},
    }


@router.post("/training/{token}/events")
def track_training_event(token: str, payload: dict, db: Annotated[Session, Depends(get_db)]):
    landing_token = db.query(LandingToken).filter(LandingToken.token == token).first()
    if not landing_token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid token")

    try:
        event_type = EventType(payload.get("event_type"))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported event_type") from exc
    employee = db.query(Employee).filter(Employee.id == landing_token.employee_id).first()
    scenario = resolve_scenario_for_token(db, landing_token)
    event = create_event(
        db,
        organization_id=employee.organization_id,
        employee_id=employee.id,
        campaign_id=landing_token.campaign_id,
        delivery_attempt_id=landing_token.delivery_attempt_id,
        landing_token_id=landing_token.id,
        event_type=event_type,
        channel=scenario.channel if scenario else None,
        metadata=payload.get("metadata") or {},
    )
    reason_codes = classify_failure_reasons(event_type, scenario)
    assignment_id = None
    if event_type in {EventType.CLICKED_LINK, EventType.SCANNED_QR, EventType.SUBMITTED_FORM_BOOLEAN}:
        assignment = assign_micro_training(
            db,
            employee=employee,
            campaign_id=landing_token.campaign_id,
            source_event=event,
            channel=scenario.channel.value if scenario else landing_token.landing_type,
            reason_codes=reason_codes,
        )
        assignment_id = assignment.id
    recalculate_employee_risk(db, employee)
    db.commit()
    return {
        "event_id": str(event.id),
        "assignment_id": str(assignment_id) if assignment_id else None,
        "reason_codes": reason_codes,
        "risk_score": employee.risk_score,
    }


@router.post("/events/track")
def track_event(payload: dict, db: Annotated[Session, Depends(get_db)]):
    token = payload.get("token")
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="token is required")
    return track_training_event(token, payload, db)


@router.get("/simulation/{token}")
def get_simulation(token: str, db: Annotated[Session, Depends(get_db)]):
    """Framing plus the single step the employee is currently on."""
    return load_simulation(db, token)


@router.post("/simulation/{token}/respond")
def post_simulation_response(
    token: str,
    payload: SimulationResponseRequest,
    db: Annotated[Session, Depends(get_db)],
):
    return record_response(
        db,
        token=token,
        step_key=payload.step_key,
        response_key=payload.response_key,
        elapsed_ms=payload.elapsed_ms,
    )


@router.post("/simulation/{token}/complete")
def post_simulation_complete(token: str, db: Annotated[Session, Depends(get_db)]):
    return complete_simulation(db, token)
