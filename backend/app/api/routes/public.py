from __future__ import annotations

import hmac
import json
from datetime import datetime, timezone
from io import BytesIO
from typing import Annotated, Any
from urllib.parse import urlparse

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.core.config import is_production_environment, settings
from app.db.session import get_db
from app.models.entities import Campaign, DeliveryAttempt, Employee, EventLog, LandingToken, QrAssetToken
from app.models.enums import EventType
from app.services.domains import public_origin
from app.services.events import classify_failure_reasons, create_event, resolve_scenario_for_token
from app.services.public_tokens import parse_public_token, token_secret_matches
from app.services.scoring import recalculate_employee_risk
from app.services.simulation import complete_simulation, load_simulation, record_response
from app.services.training import assign_micro_training

router = APIRouter()


class SimulationResponseRequest(BaseModel):
    step_key: str = Field(min_length=1, max_length=64)
    response_key: str = Field(min_length=1, max_length=64)
    elapsed_ms: int = 0


class TrainingEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: EventType
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def metadata_must_be_bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, default=str).encode("utf-8")) > 4096:
            raise ValueError("metadata must be 4 KB or smaller")
        # Only a categorical answer can come from a public browser. Ignore legacy
        # source/channel hints and reject all other fields before event persistence.
        # The server resolves the channel and recipient from the opaque token.
        unsupported = set(value) - {"source", "channel", "simulation_choice"}
        if unsupported:
            raise ValueError("metadata contains unsupported fields")
        choice = value.get("simulation_choice")
        if choice is not None and (
            not isinstance(choice, str)
            or choice not in {"would_provide_details", "verify_independently"}
        ):
            raise ValueError("simulation_choice is not supported")
        return {"simulation_choice": choice} if choice is not None else {}


class TrackEventRequest(TrainingEventRequest):
    token: str = Field(min_length=20, max_length=255)


def _load_valid_landing_token(db: Session, token: str) -> LandingToken:
    parsed = parse_public_token(token)
    if parsed:
        public_id, secret = parsed
        landing_token = db.query(LandingToken).filter(LandingToken.token_public_id == public_id).first()
        if landing_token and not token_secret_matches(secret, landing_token.token_secret_hash):
            landing_token = None
    else:
        # Compatibility for links issued before the two-part token migration.
        landing_token = db.query(LandingToken).filter(LandingToken.token == token).first()
    if not landing_token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid token")
    if landing_token.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This training link has been revoked")
    expires_at = landing_token.expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="This training link has expired")
    return landing_token


def _validate_expected_host(request: Request, expected_hostname: str | None) -> None:
    if not is_production_environment(settings.environment) or not expected_hostname:
        return
    if not hmac.compare_digest(request.headers.get("X-Azure-FDID", ""), settings.front_door_id or ""):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid token host")
    forwarded = request.headers.get("X-Forwarded-Host", "").split(",", 1)[0].strip()
    requested_host = (forwarded.partition(":")[0] or request.url.hostname or "").casefold().rstrip(".")
    if requested_host != expected_hostname.casefold().rstrip("."):
        # A token copied to the platform API hostname must not bypass a customer's
        # snapshotted custom-domain boundary.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid token host")


def _validate_landing_host(request: Request, landing_token: LandingToken) -> None:
    _validate_expected_host(request, landing_token.landing_hostname)


def _training_redirect(landing_token: LandingToken, token: str, *, entry: str) -> str:
    if is_production_environment(settings.environment) and landing_token.landing_hostname:
        origin = public_origin(landing_token.landing_hostname)
    else:
        origin = settings.frontend_base_url.rstrip("/")
    return f"{origin}/training/{token}?entry={entry}"


def _record_entry_event(db: Session, landing_token: LandingToken, event_type: EventType) -> None:
    existing = db.query(EventLog).filter(
        EventLog.landing_token_id == landing_token.id,
        EventLog.event_type == event_type,
    ).first()
    if existing:
        return
    employee = db.query(Employee).filter(Employee.id == landing_token.employee_id).first()
    if not employee:
        return
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
        metadata={"source": "server_redirect"},
    )
    reason_codes = classify_failure_reasons(event_type, scenario)
    if event_type in {EventType.CLICKED_LINK, EventType.SCANNED_QR}:
        assign_micro_training(
            db,
            employee=employee,
            campaign_id=landing_token.campaign_id,
            source_event=event,
            channel=scenario.channel.value if scenario else landing_token.landing_type,
            reason_codes=reason_codes,
        )
    if event_type == EventType.SCANNED_QR:
        landing_token.first_scanned_at = landing_token.first_scanned_at or datetime.now(timezone.utc)
    recalculate_employee_risk(db, employee)


@router.get("/qr-assets/{token}.png", include_in_schema=False)
def get_qr_asset(token: str, request: Request, db: Annotated[Session, Depends(get_db)]) -> Response:
    parsed = parse_public_token(token)
    if not parsed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid QR asset")
    public_id, secret = parsed
    asset = db.query(QrAssetToken).filter(QrAssetToken.public_id == public_id).first()
    if not asset or not token_secret_matches(secret, asset.secret_hash):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid QR asset")
    expires_at = asset.expires_at if asset.expires_at.tzinfo else asset.expires_at.replace(tzinfo=timezone.utc)
    if asset.revoked_at is not None or expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="QR asset has expired")
    _validate_expected_host(request, urlparse(asset.qr_payload_ciphertext).hostname)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_Q,
        box_size=10,
        border=4,
    )
    qr.add_data(asset.qr_payload_ciphertext)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return Response(
        content=buffer.getvalue(),
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=86400, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/q/{token}", include_in_schema=False)
def open_qr_link(token: str, request: Request, db: Annotated[Session, Depends(get_db)]):
    landing_token = _load_valid_landing_token(db, token)
    _validate_landing_host(request, landing_token)
    if landing_token.landing_type != "qr":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid QR link")
    _record_entry_event(db, landing_token, EventType.SCANNED_QR)
    db.commit()
    return RedirectResponse(_training_redirect(landing_token, token, entry="qr"), status_code=302)


@router.get("/l/{token}", include_in_schema=False)
def open_email_link(token: str, request: Request, db: Annotated[Session, Depends(get_db)]):
    landing_token = _load_valid_landing_token(db, token)
    _validate_landing_host(request, landing_token)
    if landing_token.landing_type != "email":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid email link")
    _record_entry_event(db, landing_token, EventType.CLICKED_LINK)
    db.commit()
    return RedirectResponse(_training_redirect(landing_token, token, entry="email"), status_code=302)


@router.get("/training/{token}")
def get_training_page(token: str, request: Request, db: Annotated[Session, Depends(get_db)]):
    landing_token = _load_valid_landing_token(db, token)
    _validate_landing_host(request, landing_token)
    delivery_attempt = db.query(DeliveryAttempt).filter(DeliveryAttempt.id == landing_token.delivery_attempt_id).first()
    campaign = db.query(Campaign).filter(Campaign.id == landing_token.campaign_id).first()
    scenario = resolve_scenario_for_token(db, landing_token)
    latest_version = None
    if scenario and scenario.versions:
        latest_version = max(scenario.versions, key=lambda version: version.version_number)

    return {
        "token": token,
        "landing_type": landing_token.landing_type,
        "campaign_id": str(landing_token.campaign_id),
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
def track_training_event(
    token: str,
    payload: TrainingEventRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    landing_token = _load_valid_landing_token(db, token)
    _validate_landing_host(request, landing_token)
    event_type = payload.event_type
    if landing_token.token_public_id and event_type in {
        EventType.DELIVERED,
        EventType.BOUNCED,
        EventType.PROVIDER_ACCEPTED,
        EventType.CLICKED_LINK,
        EventType.SCANNED_QR,
        EventType.OPENED_EMAIL,
    }:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This event is recorded only by a trusted server-side source",
        )
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
        metadata=payload.metadata,
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
def track_event(payload: TrackEventRequest, request: Request, db: Annotated[Session, Depends(get_db)]):
    return track_training_event(payload.token, payload, request, db)


@router.get("/simulation/{token}")
def get_simulation(token: str, request: Request, db: Annotated[Session, Depends(get_db)]):
    """Framing plus the single step the employee is currently on."""
    _validate_landing_host(request, _load_valid_landing_token(db, token))
    return load_simulation(db, token)


@router.post("/simulation/{token}/respond")
def post_simulation_response(
    token: str,
    payload: SimulationResponseRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    _validate_landing_host(request, _load_valid_landing_token(db, token))
    return record_response(
        db,
        token=token,
        step_key=payload.step_key,
        response_key=payload.response_key,
        elapsed_ms=payload.elapsed_ms,
    )


@router.post("/simulation/{token}/complete")
def post_simulation_complete(token: str, request: Request, db: Annotated[Session, Depends(get_db)]):
    _validate_landing_host(request, _load_valid_landing_token(db, token))
    return complete_simulation(db, token)
