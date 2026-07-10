from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from io import BytesIO

from fastapi import HTTPException, status
import qrcode
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.crypto import pseudonymous_id
from app.models.entities import Campaign, DeliveryAttempt, LandingToken, Organization, Scenario
from app.models.enums import CampaignStatus, Channel, DeliveryStatus, EventType
from app.services.audit import audit_log
from app.services.email_integration import send_lab_email
from app.services.events import create_event


def _load_campaign(db: Session, *, campaign_id, actor) -> Campaign:
    campaign = (
        db.query(Campaign)
        .options(selectinload(Campaign.targets), selectinload(Campaign.scenario_links))
        .filter(Campaign.id == campaign_id, Campaign.organization_id == actor.organization_id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if campaign.status not in {CampaignStatus.APPROVED, CampaignStatus.SCHEDULED}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign must be approved before launch")

    if not campaign.targets or not campaign.scenario_links:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign requires targets and scenarios")
    return campaign


def _scenario_for_campaign(db: Session, campaign: Campaign) -> tuple[Scenario, object]:
    scenario = db.query(Scenario).filter(Scenario.id == campaign.scenario_links[0].scenario_id).first()
    latest_version = max(scenario.versions, key=lambda version: version.version_number)
    return scenario, latest_version


def _qr_image_data_url(value: str) -> str:
    qr_image = qrcode.make(value)
    buffer = BytesIO()
    qr_image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _build_attempt_payload(
    *,
    campaign: Campaign,
    latest_version,
    token: LandingToken,
    recipient: str | None = None,
    sender_name: str = "Workflow Notifications",
    from_email: str = "no-reply@workflow.local",
) -> dict:
    training_url = f"{settings.frontend_base_url}/training/{token.token}"
    payload = {
        "subject": latest_version.subject,
        "body_copy": latest_version.body_copy,
        "cta_text": latest_version.cta_text,
        "sender_name": sender_name,
        "from_email": from_email,
        "preview_url": training_url,
        "landing_page_copy": latest_version.landing_page_copy,
    }
    if recipient:
        payload["recipient"] = recipient

    if campaign.channel == Channel.QR:
        scan_url = f"{settings.frontend_base_url}/qr/{token.token}"
        payload.update(
            {
                "scan_url": scan_url,
                "qr_payload_text": scan_url,
                "qr_image_data_url": _qr_image_data_url(scan_url),
                "poster_title": latest_version.subject,
                "poster_body": latest_version.body_copy,
                "placement_context": "Office noticeboard, reception desk, printer area, or meeting-room card",
                "verification_note": "Admin view: QR scans are logged as awareness events before the employee reaches the training result page.",
                "expected_events": ["delivered", "scanned_qr", "visited_landing_page", "clicked_report", "submitted_form_boolean"],
                "module": "qr_simulation",
            }
        )

    return payload


def launch_campaign_sandbox(db: Session, *, campaign_id, actor) -> list[DeliveryAttempt]:
    campaign = _load_campaign(db, campaign_id=campaign_id, actor=actor)

    scenario, latest_version = _scenario_for_campaign(db, campaign)
    attempts: list[DeliveryAttempt] = []

    for target in campaign.targets:
        attempt = DeliveryAttempt(
            campaign_id=campaign.id,
            employee_id=target.employee_id,
            scenario_id=scenario.id,
            channel=campaign.channel,
            status=DeliveryStatus.SANDBOXED,
            sandbox_mode=True,
            preview_payload={},
        )
        db.add(attempt)
        db.flush()
        token_value = pseudonymous_id(str(campaign.id), str(target.employee_id), str(attempt.id))[:32]
        token = LandingToken(
            delivery_attempt_id=attempt.id,
            employee_id=target.employee_id,
            campaign_id=campaign.id,
            token=token_value,
            landing_type=campaign.channel.value,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(token)
        db.flush()
        attempt.preview_payload = _build_attempt_payload(campaign=campaign, latest_version=latest_version, token=token)
        attempt.delivered_at = datetime.now(timezone.utc)
        attempts.append(attempt)
        create_event(
            db,
            organization_id=campaign.organization_id,
            employee_id=target.employee_id,
            campaign_id=campaign.id,
            delivery_attempt_id=attempt.id,
            landing_token_id=token.id,
            event_type=EventType.DELIVERED,
            channel=campaign.channel,
            metadata={"sandbox_mode": True, "delivery_mode": "qr_preview" if campaign.channel == Channel.QR else "sandbox_preview"},
        )

    campaign.status = CampaignStatus.ACTIVE
    audit_log(
        db,
        organization_id=actor.organization_id,
        user_id=actor.id,
        action="campaign.launch_sandbox",
        resource_type="campaign",
        resource_id=str(campaign.id),
        details={"attempt_count": len(attempts)},
    )
    db.commit()
    return attempts


def deliver_campaign_email(db: Session, *, campaign_id, actor) -> list[DeliveryAttempt]:
    campaign = _load_campaign(db, campaign_id=campaign_id, actor=actor)
    if campaign.channel.value != "email":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lab delivery is currently available only for email campaigns")

    org = db.query(Organization).filter(Organization.id == actor.organization_id).first()
    scenario, latest_version = _scenario_for_campaign(db, campaign)
    attempts: list[DeliveryAttempt] = []

    for target in campaign.targets:
        attempt = DeliveryAttempt(
            campaign_id=campaign.id,
            employee_id=target.employee_id,
            scenario_id=scenario.id,
            channel=campaign.channel,
            status=DeliveryStatus.FAILED,
            sandbox_mode=False,
            preview_payload={},
        )
        db.add(attempt)
        db.flush()

        token_value = pseudonymous_id(str(campaign.id), str(target.employee_id), str(attempt.id))[:32]
        token = LandingToken(
            delivery_attempt_id=attempt.id,
            employee_id=target.employee_id,
            campaign_id=campaign.id,
            token=token_value,
            landing_type=campaign.channel.value,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(token)
        db.flush()

        employee = target.employee
        preview_url = f"{settings.frontend_base_url}/training/{token.token}"
        attempt.preview_payload = _build_attempt_payload(
            campaign=campaign,
            latest_version=latest_version,
            token=token,
            recipient=employee.email,
            sender_name=org.smtp_sender_name or "BreachSim Delivery",
            from_email=org.smtp_from_email or org.smtp_username,
        )

        try:
            send_lab_email(
                org=org,
                recipient=employee.email,
                subject=latest_version.subject,
                body_text=latest_version.body_copy,
                cta_url=preview_url,
                cta_text=latest_version.cta_text or "clickhere",
            )
            attempt.status = DeliveryStatus.DELIVERED
            attempt.delivered_at = datetime.now(timezone.utc)
            create_event(
                db,
                organization_id=campaign.organization_id,
                employee_id=target.employee_id,
                campaign_id=campaign.id,
                delivery_attempt_id=attempt.id,
                landing_token_id=token.id,
                event_type=EventType.DELIVERED,
                channel=campaign.channel,
                metadata={"sandbox_mode": False, "delivery_mode": "lab_email"},
            )
        except Exception as exc:
            attempt.preview_payload = {**attempt.preview_payload, "error": str(exc)}

        attempts.append(attempt)

    campaign.status = CampaignStatus.ACTIVE
    audit_log(
        db,
        organization_id=actor.organization_id,
        user_id=actor.id,
        action="campaign.deliver_email",
        resource_type="campaign",
        resource_id=str(campaign.id),
        details={"attempt_count": len(attempts)},
    )
    db.commit()
    return attempts
