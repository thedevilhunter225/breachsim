from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.crypto import pseudonymous_id
from app.models.entities import Campaign, EventLog, LandingToken, Scenario
from app.models.enums import RISKY_EVENT_TYPES, Channel, EventType

FAILURE_REASON_BY_TRIGGER = {
    "authority": "authority",
    "curiosity": "curiosity",
    "urgency": "urgency",
    "reward": "reward",
    "fear": "fear",
    "qr lure": "qr_lure",
    "sms trust": "sms_trust",
    "voice pressure": "voice_pressure",
    "synthetic likeness": "synthetic_likeness",
    "habit/autopilot": "habit_autopilot",
    "role-relevance": "role_relevance",
}

#: Fallback reason when a scenario carries no persuasion triggers of its own.
DEFAULT_REASON_BY_EVENT = {
    EventType.SCANNED_QR: "qr_lure",
    EventType.CLICKED_LINK: "curiosity",
    EventType.REPLIED_SMS: "sms_trust",
    EventType.DISCLOSED_ON_CALL: "voice_pressure",
    EventType.TRUSTED_SYNTHETIC_MEDIA: "synthetic_likeness",
    EventType.SUBMITTED_FORM_BOOLEAN: "habit_autopilot",
}


def classify_failure_reasons(event_type: EventType, scenario: Scenario | None) -> list[str]:
    if event_type not in RISKY_EVENT_TYPES:
        return []
    fallback = DEFAULT_REASON_BY_EVENT.get(event_type, "habit_autopilot")
    if scenario and scenario.detected_persuasion_triggers:
        return [
            FAILURE_REASON_BY_TRIGGER.get(trigger, trigger)
            for trigger in scenario.detected_persuasion_triggers
        ]
    return [fallback]


def create_event(
    db: Session,
    *,
    organization_id,
    employee_id,
    event_type: EventType,
    channel: Channel | None,
    campaign_id=None,
    delivery_attempt_id=None,
    landing_token_id=None,
    metadata: dict | None = None,
    occurred_at: datetime | None = None,
) -> EventLog:
    now = occurred_at or datetime.now(timezone.utc)
    event = EventLog(
        organization_id=organization_id,
        employee_id=employee_id,
        campaign_id=campaign_id,
        delivery_attempt_id=delivery_attempt_id,
        landing_token_id=landing_token_id,
        event_type=event_type,
        channel=channel,
        event_metadata=metadata or {},
        pseudo_event_id=pseudonymous_id(str(organization_id), str(employee_id or ""), event_type.value, now.isoformat()),
        occurred_at=now,
    )
    db.add(event)
    db.flush()
    return event


def resolve_scenario_for_token(db: Session, token: LandingToken) -> Scenario | None:
    campaign = db.query(Campaign).filter(Campaign.id == token.campaign_id).first()
    if not campaign or not campaign.scenario_links:
        return None
    scenario_id = campaign.scenario_links[0].scenario_id
    return db.query(Scenario).filter(Scenario.id == scenario_id).first()
