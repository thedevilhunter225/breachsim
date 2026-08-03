"""Runtime for the interactive (voice and synthetic-media) simulations.

The employee walks a branching script one step at a time. Every choice is persisted as a
:class:`SimulationResponse` so the campaign report can show exactly where in the pressure
sequence the person complied or verified — not just a binary pass/fail.

The script itself is never sent to the browser wholesale: :func:`load_simulation` returns
only the step the employee is currently on, so the safe answer cannot be read out of the
network response before the decision is made.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.entities import (
    Campaign,
    DeliveryAttempt,
    Employee,
    EventLog,
    LandingToken,
    Scenario,
    ScenarioVersion,
    SimulationResponse,
)
from app.models.enums import Channel, EventType
from app.services.channel_content import find_option, find_step
from app.services.events import classify_failure_reasons, create_event, resolve_scenario_for_token
from app.services.media_generation import media_for_version
from app.services.scoring import recalculate_employee_risk
from app.services.training import assign_micro_training

INTERACTIVE_LANDING_TYPES = {Channel.VISHING.value, Channel.DEEPFAKE.value}


def _load_token(db: Session, token: str) -> LandingToken:
    landing_token = db.query(LandingToken).filter(LandingToken.token == token).first()
    if not landing_token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid token")
    expires_at = landing_token.expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="This simulation link has expired")
    return landing_token


def _latest_version(db: Session, scenario: Scenario | None) -> ScenarioVersion | None:
    if not scenario or not scenario.versions:
        return None
    return max(scenario.versions, key=lambda version: version.version_number)


def _channel_payload(db: Session, landing_token: LandingToken) -> tuple[Scenario | None, dict[str, Any]]:
    scenario = resolve_scenario_for_token(db, landing_token)
    version = _latest_version(db, scenario)
    return scenario, (version.channel_payload if version else {}) or {}


def _public_step(step: dict[str, Any]) -> dict[str, Any]:
    """Strip the answer key before the step reaches the browser."""
    return {
        "key": step.get("key"),
        "index": step.get("index", 0),
        "speaker_line": step.get("speaker_line"),
        "pressure_tactic": step.get("pressure_tactic"),
        "hint": step.get("hint"),
        "options": [
            {"key": option.get("key"), "label": option.get("label")}
            for option in step.get("options") or []
        ],
    }


def _answered_step_keys(db: Session, landing_token: LandingToken) -> list[str]:
    rows = (
        db.query(SimulationResponse.step_key)
        .filter(SimulationResponse.landing_token_id == landing_token.id)
        .order_by(SimulationResponse.occurred_at.asc())
        .all()
    )
    return [row[0] for row in rows]


def _next_step(payload: dict[str, Any], answered: list[str]) -> dict[str, Any] | None:
    for step in payload.get("script") or []:
        if step.get("key") not in answered:
            return step
    return None


def load_simulation(db: Session, token: str) -> dict[str, Any]:
    """Return the framing plus the single step the employee is currently on."""
    landing_token = _load_token(db, token)
    scenario, payload = _channel_payload(db, landing_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This token does not belong to an interactive simulation",
        )

    campaign = db.query(Campaign).filter(Campaign.id == landing_token.campaign_id).first()
    attempt = db.query(DeliveryAttempt).filter(DeliveryAttempt.id == landing_token.delivery_attempt_id).first()
    employee = db.query(Employee).filter(Employee.id == landing_token.employee_id).first()

    answered = _answered_step_keys(db, landing_token)
    current = _next_step(payload, answered)
    finished = current is None or _has_terminal_response(db, landing_token, payload)

    # Real cloned media, if it was rendered for this scenario version. The simulator plays
    # these when present and falls back to the browser speech engine when they are not.
    version = _latest_version(db, scenario)
    media = media_for_version(db, version.id) if version else {}

    return {
        "token": landing_token.token,
        "module": payload.get("module"),
        "channel": payload.get("channel", landing_token.landing_type),
        "media": media,
        "campaign_name": campaign.name if campaign else None,
        "employee_first_name": employee.full_name.split()[0] if employee else None,
        "header": payload.get("header", {}),
        "persona": payload.get("persona", {}),
        "voice_profile": payload.get("voice_profile", {}),
        "transcript": payload.get("transcript"),
        "safety_notice": payload.get("safety_notice"),
        "total_steps": len(payload.get("script") or []),
        "completed_steps": len(answered),
        "current_step": _public_step(current) if current and not finished else None,
        "finished": finished,
        "scenario_title": scenario.title if scenario else None,
        "delivery_channel": attempt.channel.value if attempt else landing_token.landing_type,
        # Artifacts are only revealed for the deepfake module, and only the ones the
        # scenario difficulty allows to be visible before the decision is made.
        "visible_artifacts": [
            artifact
            for artifact in payload.get("synthetic_artifacts") or []
            if artifact.get("revealed_upfront")
        ],
    }


def _has_terminal_response(db: Session, landing_token: LandingToken, payload: dict[str, Any]) -> bool:
    rows = (
        db.query(SimulationResponse.step_key, SimulationResponse.response_key)
        .filter(SimulationResponse.landing_token_id == landing_token.id)
        .all()
    )
    for step_key, response_key in rows:
        step = find_step(payload, step_key)
        option = find_option(step, response_key) if step else None
        if option and option.get("terminal"):
            return True
    return False


def record_response(
    db: Session,
    *,
    token: str,
    step_key: str,
    response_key: str,
    elapsed_ms: int = 0,
) -> dict[str, Any]:
    """Persist one decision, emit its event, and hand back the follow-up."""

    landing_token = _load_token(db, token)
    scenario, payload = _channel_payload(db, landing_token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No interactive script for this token")

    step = find_step(payload, step_key)
    if not step:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown step '{step_key}'")
    option = find_option(step, response_key)
    if not option:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown response '{response_key}'")

    already = (
        db.query(SimulationResponse)
        .filter(
            SimulationResponse.landing_token_id == landing_token.id,
            SimulationResponse.step_key == step_key,
        )
        .first()
    )
    if already:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This step has already been answered")

    employee = db.query(Employee).filter(Employee.id == landing_token.employee_id).first()
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found for this token")

    channel = scenario.channel if scenario else Channel(landing_token.landing_type)

    event: EventLog | None = None
    if option.get("event_type"):
        event = create_event(
            db,
            organization_id=employee.organization_id,
            employee_id=employee.id,
            campaign_id=landing_token.campaign_id,
            delivery_attempt_id=landing_token.delivery_attempt_id,
            landing_token_id=landing_token.id,
            event_type=EventType(option["event_type"]),
            channel=channel,
            metadata={
                "step_key": step_key,
                "response_key": response_key,
                "pressure_tactic": step.get("pressure_tactic"),
                "outcome": option.get("outcome"),
                "elapsed_ms": elapsed_ms,
            },
        )

    db.add(
        SimulationResponse(
            organization_id=employee.organization_id,
            employee_id=employee.id,
            campaign_id=landing_token.campaign_id,
            delivery_attempt_id=landing_token.delivery_attempt_id,
            landing_token_id=landing_token.id,
            event_id=event.id if event else None,
            channel=channel,
            step_index=step.get("index", 0),
            step_key=step_key,
            step_prompt=step.get("speaker_line") or "",
            response_key=response_key,
            response_label=option.get("label") or "",
            is_safe_action=bool(option.get("safe")),
            risk_weight=int(option.get("risk_weight") or 0),
            elapsed_ms=max(0, int(elapsed_ms or 0)),
        )
    )
    db.flush()

    assignment_id = None
    if event and event.event_type in {
        EventType.DISCLOSED_ON_CALL,
        EventType.TRUSTED_SYNTHETIC_MEDIA,
    }:
        assignment = assign_micro_training(
            db,
            employee=employee,
            campaign_id=landing_token.campaign_id,
            source_event=event,
            channel=channel.value,
            reason_codes=classify_failure_reasons(event.event_type, scenario),
        )
        assignment_id = assignment.id

    recalculate_employee_risk(db, employee)
    db.commit()

    answered = _answered_step_keys(db, landing_token)
    upcoming = None if option.get("terminal") else _next_step(payload, answered)

    return {
        "recorded": True,
        "outcome": option.get("outcome"),
        "safe": bool(option.get("safe")),
        "followup_line": option.get("followup_line"),
        "coaching": option.get("coaching"),
        "terminal": bool(option.get("terminal")),
        "next_step": _public_step(upcoming) if upcoming else None,
        "finished": upcoming is None,
        "assignment_id": str(assignment_id) if assignment_id else None,
        "risk_score": employee.risk_score,
    }


def complete_simulation(db: Session, token: str) -> dict[str, Any]:
    """Close the simulation and return the debrief the employee has now earned."""

    landing_token = _load_token(db, token)
    scenario, payload = _channel_payload(db, landing_token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No interactive script for this token")

    employee = db.query(Employee).filter(Employee.id == landing_token.employee_id).first()
    responses = (
        db.query(SimulationResponse)
        .filter(SimulationResponse.landing_token_id == landing_token.id)
        .order_by(SimulationResponse.step_index.asc())
        .all()
    )

    unsafe = [row for row in responses if not row.is_safe_action and row.risk_weight > 0]
    safe = [row for row in responses if row.is_safe_action]
    net_weight = sum(row.risk_weight for row in responses)

    if not responses:
        outcome = "abandoned"
        headline = "Simulation not completed."
    elif not unsafe and safe:
        outcome = "resilient"
        headline = "You verified instead of complying. That is exactly the right response."
    elif safe and unsafe:
        outcome = "recovered"
        headline = "You engaged first, then caught it. Catching it later still prevents the loss."
    else:
        outcome = "compromised"
        headline = "The pretext worked. Here is the point where verification would have stopped it."

    first_unsafe = unsafe[0] if unsafe else None
    if not landing_token.used_at:
        landing_token.used_at = datetime.now(timezone.utc)
        db.commit()

    return {
        "token": landing_token.token,
        "outcome": outcome,
        "headline": headline,
        "net_risk_weight": net_weight,
        "current_risk_score": employee.risk_score if employee else None,
        "steps_taken": len(responses),
        "safe_actions": len(safe),
        "unsafe_actions": len(unsafe),
        "decision_trail": [
            {
                "step_key": row.step_key,
                "step_prompt": row.step_prompt,
                "response_label": row.response_label,
                "safe": row.is_safe_action,
                "risk_weight": row.risk_weight,
                "elapsed_ms": row.elapsed_ms,
            }
            for row in responses
        ],
        "breaking_point": (
            {"step_key": first_unsafe.step_key, "response_label": first_unsafe.response_label}
            if first_unsafe
            else None
        ),
        "red_flags": payload.get("red_flags", []),
        "detection_tells": payload.get("detection_tells", []),
        "synthetic_artifacts": payload.get("synthetic_artifacts", []),
        "verification_procedure": payload.get("verification_procedure"),
        "debrief": payload.get("debrief"),
        "safety_notice": payload.get("safety_notice"),
        "scenario_title": scenario.title if scenario else None,
        "channel": payload.get("channel", landing_token.landing_type),
    }
