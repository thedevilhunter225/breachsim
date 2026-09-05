"""Per-channel delivery adapters.

Every channel produces the same three things — a :class:`DeliveryAttempt`, a single-use
:class:`LandingToken`, and a ``delivered`` event — so analytics, scoring and reporting stay
channel-agnostic. What differs is the *payload* each adapter builds and whether anything
actually leaves the platform:

===============  =====================================  ==========================
Channel          Outbound action                        Employee entry point
===============  =====================================  ==========================
email            SMTP send to an allowlisted mailbox    ``/training/<token>``
sms              REST send to an allowlisted number     ``/training/<token>``
qr               SMTP email with an HTML-rendered QR    ``/qr/<token>``
vishing          none — the call runs in the browser    ``/call/<token>``
deepfake         none — the media runs in the browser   ``/impersonation/<token>``
===============  =====================================  ==========================

Voice and synthetic-media simulations are deliberately *pull* rather than *push*.
BreachSim never dials a real number and never publishes generated media. The simulation
is rendered locally in the target's browser, which keeps a convincing exercise inside a
boundary the organization fully controls.
"""

from __future__ import annotations

import base64
import secrets
from datetime import datetime, timedelta, timezone
from html import escape
from io import BytesIO

import qrcode
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.core.config import is_production_environment, settings
from app.models.entities import Campaign, DeliveryAttempt, Employee, LandingToken, Organization, Scenario
from app.models.enums import CampaignStatus, Channel, DeliveryStatus, EventType
from app.services.audit import audit_log
from app.services.email_integration import send_lab_email
from app.services.events import create_event
from app.services.sms_integration import send_lab_sms

TOKEN_TTL_DAYS = 30

#: Channels that never send anything outbound — the simulation runs in the browser.
SESSION_ONLY_CHANNELS = {Channel.VISHING, Channel.DEEPFAKE}

#: Which frontend route a token resolves to, per channel.
ENTRY_ROUTE_BY_CHANNEL = {
    Channel.EMAIL: "training",
    Channel.SMS: "training",
    Channel.QR: "qr",
    Channel.VISHING: "call",
    Channel.DEEPFAKE: "impersonation",
}


# --------------------------------------------------------------------------------------
# Shared plumbing
# --------------------------------------------------------------------------------------

def _load_campaign(db: Session, *, campaign_id, actor) -> Campaign:
    campaign = (
        db.query(Campaign)
        .options(selectinload(Campaign.targets), selectinload(Campaign.scenario_links))
        .filter(Campaign.id == campaign_id, Campaign.organization_id == actor.organization_id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if campaign.status not in {CampaignStatus.APPROVED, CampaignStatus.SCHEDULED, CampaignStatus.ACTIVE}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign must be approved, scheduled, or active before launch",
        )
    if not campaign.targets or not campaign.scenario_links:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign requires targets and scenarios")
    return campaign


def _scenario_for_campaign(db: Session, campaign: Campaign) -> tuple[Scenario, object]:
    scenario = db.query(Scenario).filter(Scenario.id == campaign.scenario_links[0].scenario_id).first()
    latest_version = max(scenario.versions, key=lambda version: version.version_number)
    return scenario, latest_version


def _qr_png_bytes(value: str) -> bytes:
    qr_image = qrcode.make(value)
    buffer = BytesIO()
    qr_image.save(buffer, format="PNG")
    return buffer.getvalue()


def _qr_image_data_url(value: str) -> str:
    encoded = base64.b64encode(_qr_png_bytes(value)).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _qr_html_table(value: str, *, module_size: int = 6) -> str:
    """Render a scannable QR as email-safe HTML without an image MIME part.

    Gmail exposes even correctly related CID images in its attachment tray for
    some recipients. A compact run-length table keeps every QR module inside
    the HTML body, so there is nothing for the client to present as a download.
    The QR library's matrix includes the required four-module quiet zone. Every
    row deliberately has the same number of cells: email clients calculate one
    shared column grid for a table, so run-length-compressed rows can distort
    into barcode-like vertical stripes after Gmail sanitizes the markup.
    """

    qr_code = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1,
        border=4,
    )
    qr_code.add_data(value)
    qr_code.make(fit=True)
    matrix = qr_code.get_matrix()
    pixel_size = len(matrix) * module_size

    rows = [
        f'<tr height="{module_size}">'
        + "".join(
            f'<td width="{module_size}" height="{module_size}" '
            f'bgcolor="{"#000000" if dark else "#ffffff"}"></td>'
            for dark in row
        )
        + "</tr>"
        for row in matrix
    ]

    return (
        f'<table role="img" aria-label="QR code" cellspacing="0" cellpadding="0" border="0" '
        f'width="{pixel_size}" style="width:{pixel_size}px;height:{pixel_size}px;'
        'table-layout:fixed;border-collapse:collapse;background:#ffffff;">'
        f'{"".join(rows)}</table>'
    )


def entry_url(channel: Channel, token_value: str) -> str:
    route = ENTRY_ROUTE_BY_CHANNEL.get(channel, "training")
    return f"{settings.frontend_base_url}/{route}/{token_value}"


def _issue_attempt_and_token(
    db: Session,
    *,
    campaign: Campaign,
    scenario: Scenario,
    employee_id,
    sandbox_mode: bool,
) -> tuple[DeliveryAttempt, LandingToken]:
    attempt = DeliveryAttempt(
        campaign_id=campaign.id,
        employee_id=employee_id,
        scenario_id=scenario.id,
        channel=campaign.channel,
        status=DeliveryStatus.SANDBOXED if sandbox_mode else DeliveryStatus.FAILED,
        sandbox_mode=sandbox_mode,
        preview_payload={},
    )
    db.add(attempt)
    db.flush()

    token = LandingToken(
        delivery_attempt_id=attempt.id,
        employee_id=employee_id,
        campaign_id=campaign.id,
        token=secrets.token_urlsafe(32),
        landing_type=campaign.channel.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=TOKEN_TTL_DAYS),
    )
    db.add(token)
    db.flush()
    return attempt, token


# --------------------------------------------------------------------------------------
# Payload builders — one per channel
# --------------------------------------------------------------------------------------

def build_attempt_payload(
    *,
    campaign: Campaign,
    latest_version,
    token: LandingToken,
    recipient: str | None = None,
    sender_name: str = "Workflow Notifications",
    from_email: str = "no-reply@workflow.local",
    organization: Organization | None = None,
) -> dict:
    """Assemble the admin-facing preview and the employee-facing entry point."""

    training_url = f"{settings.frontend_base_url}/training/{token.token}"
    channel_url = entry_url(campaign.channel, token.token)
    payload = {
        "channel": campaign.channel.value,
        "subject": latest_version.subject,
        "body_copy": latest_version.body_copy,
        "cta_text": latest_version.cta_text,
        "sender_name": sender_name,
        "from_email": from_email,
        "preview_url": training_url,
        "entry_url": channel_url,
        "landing_page_copy": latest_version.landing_page_copy,
    }
    if recipient:
        payload["recipient"] = recipient

    if campaign.channel == Channel.QR:
        payload.update(_qr_payload(latest_version, channel_url))
    elif campaign.channel == Channel.SMS:
        payload.update(_sms_payload(latest_version, channel_url))
    elif campaign.channel == Channel.VISHING:
        payload.update(_voice_payload(latest_version, channel_url))
    elif campaign.channel == Channel.DEEPFAKE:
        payload.update(_deepfake_payload(latest_version, channel_url, organization))

    return payload


def _qr_payload(latest_version, scan_url: str) -> dict:
    return {
        "scan_url": scan_url,
        "qr_payload_text": scan_url,
        "qr_image_data_url": _qr_image_data_url(scan_url),
        "email_subject": latest_version.subject,
        "email_body": latest_version.body_copy,
        # Retained for previews created before QR moved from print posters to email delivery.
        "poster_title": latest_version.subject,
        "poster_body": latest_version.body_copy,
        "delivery_format": "inline_email",
        "placement_context": "Embedded directly in the email body; no attachment or download required",
        "verification_note": (
            "Each recipient receives a unique QR. A scan is recorded as an awareness event "
            "before the employee reaches the training result page."
        ),
        "expected_events": ["delivered", "scanned_qr", "visited_landing_page", "clicked_report", "submitted_form_boolean"],
        "module": "qr_simulation",
    }


#: Characters representable in the GSM 03.38 default alphabet. Anything outside this set
#: forces the whole message into UCS-2, which more than halves the per-segment capacity.
GSM7_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
#: Extension-table characters occupy two GSM-7 septets each.
GSM7_EXTENDED = set("^{}\\[~]|€")


def sms_segments(text: str) -> tuple[int, str, int]:
    """Return (segment_count, encoding, billable_units) for one SMS body.

    Mirrors how a carrier actually meters the message so the admin preview does not
    understate cost or truncation risk.
    """
    if all(character in GSM7_BASIC or character in GSM7_EXTENDED for character in text):
        units = sum(2 if character in GSM7_EXTENDED else 1 for character in text)
        single, concatenated = 160, 153
        encoding = "GSM-7"
    else:
        units = len(text)
        single, concatenated = 70, 67
        encoding = "UCS-2"

    if units <= single:
        return 1, encoding, units
    return -(-units // concatenated), encoding, units


def _sms_payload(latest_version, training_url: str) -> dict:
    message_text = f"{latest_version.body_copy.strip()} {training_url}"
    segment_count, encoding, units = sms_segments(message_text)
    return {
        "module": "sms_simulation",
        "message_text": message_text,
        "character_count": len(message_text),
        "billable_units": units,
        "encoding": encoding,
        "segment_count": segment_count,
        "expected_events": ["delivered", "clicked_link", "replied_sms", "clicked_report"],
    }


def _voice_payload(latest_version, call_url: str) -> dict:
    script = latest_version.channel_payload or {}
    header = script.get("header", {})
    return {
        "module": "voice_simulation",
        "call_url": call_url,
        "caller_id_display": header.get("caller_id_display"),
        "caller_id_label": header.get("caller_id_label"),
        "spoofed_display_name": header.get("spoofed_display_name"),
        "call_reason": header.get("call_reason"),
        "script_step_count": len(script.get("script") or []),
        "persona": script.get("persona"),
        "delivery_note": (
            "No outbound call is placed. Send the call link to the target, or open it on their "
            "device during a supervised exercise."
        ),
        "expected_events": ["delivered", "answered_call", "disclosed_on_call", "verified_caller", "ended_call_safely"],
    }


def _deepfake_payload(latest_version, media_url: str, organization: Organization | None) -> dict:
    brief = latest_version.channel_payload or {}
    header = brief.get("header", {})
    return {
        "module": "synthetic_media_simulation",
        "media_url": media_url,
        "modality": header.get("modality"),
        "sender_display_name": header.get("sender_display_name"),
        "sender_role_title": header.get("sender_role_title"),
        "requested_action": header.get("requested_action"),
        "artifact_count": len(brief.get("synthetic_artifacts") or []),
        "persona": brief.get("persona"),
        "disclosure_text": (
            organization.impersonation_disclosure_text
            if organization
            else brief.get("safety_notice")
        ),
        "delivery_note": (
            "No media file is generated, stored or published. The impersonation is rendered "
            "in the target's browser from the approved script and discarded when the page closes."
        ),
        "expected_events": [
            "delivered",
            "played_synthetic_media",
            "trusted_synthetic_media",
            "flagged_synthetic_media",
            "verified_out_of_band",
        ],
    }


# --------------------------------------------------------------------------------------
# Sandbox launch — every channel, nothing outbound
# --------------------------------------------------------------------------------------

def launch_campaign_sandbox(db: Session, *, campaign_id, actor) -> list[DeliveryAttempt]:
    campaign = _load_campaign(db, campaign_id=campaign_id, actor=actor)
    organization = db.query(Organization).filter(Organization.id == actor.organization_id).first()
    scenario, latest_version = _scenario_for_campaign(db, campaign)
    attempts: list[DeliveryAttempt] = []

    for target in campaign.targets:
        attempt, token = _issue_attempt_and_token(
            db,
            campaign=campaign,
            scenario=scenario,
            employee_id=target.employee_id,
            sandbox_mode=True,
        )
        attempt.preview_payload = build_attempt_payload(
            campaign=campaign,
            latest_version=latest_version,
            token=token,
            organization=organization,
        )
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
            metadata={"sandbox_mode": True, "delivery_mode": f"{campaign.channel.value}_preview"},
        )

    campaign.status = CampaignStatus.ACTIVE
    audit_log(
        db,
        organization_id=actor.organization_id,
        user_id=actor.id,
        action="campaign.launch_sandbox",
        resource_type="campaign",
        resource_id=str(campaign.id),
        details={"attempt_count": len(attempts), "channel": campaign.channel.value},
    )
    db.commit()
    return attempts


# --------------------------------------------------------------------------------------
# Live delivery — dispatches to the channel adapter
# --------------------------------------------------------------------------------------

def deliver_campaign(db: Session, *, campaign_id, actor) -> list[DeliveryAttempt]:
    """Run the campaign for real: send outbound where the channel sends, activate sessions otherwise."""

    campaign = _load_campaign(db, campaign_id=campaign_id, actor=actor)
    organization = db.query(Organization).filter(Organization.id == actor.organization_id).first()
    scenario, latest_version = _scenario_for_campaign(db, campaign)

    dispatch = {
        Channel.EMAIL: _deliver_email_attempt,
        Channel.SMS: _deliver_sms_attempt,
        Channel.QR: _deliver_qr_email_attempt,
        Channel.VISHING: _activate_in_platform_attempt,
        Channel.DEEPFAKE: _activate_in_platform_attempt,
    }
    adapter = dispatch.get(campaign.channel)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No delivery adapter registered for channel '{campaign.channel.value}'",
        )

    # A provider that is switched off is not a failure — it means the organization has
    # not opted into outbound sending on this channel, so the campaign runs as a clearly
    # labelled sandbox preview instead of reporting a delivery error.
    outbound_available = _outbound_available(campaign.channel, organization)
    if not outbound_available:
        adapter = _activate_in_platform_attempt

    attempts: list[DeliveryAttempt] = []
    for target in campaign.targets:
        employee = target.employee
        attempt, token = _issue_attempt_and_token(
            db,
            campaign=campaign,
            scenario=scenario,
            employee_id=target.employee_id,
            sandbox_mode=campaign.channel in SESSION_ONLY_CHANNELS or not outbound_available,
        )
        attempt.preview_payload = build_attempt_payload(
            campaign=campaign,
            latest_version=latest_version,
            token=token,
            recipient=_recipient_for(campaign.channel, employee),
            sender_name=organization.smtp_sender_name or "BreachSim Delivery",
            from_email=organization.smtp_from_email or organization.smtp_username,
            organization=organization,
        )

        try:
            delivery_mode = adapter(
                db,
                campaign=campaign,
                organization=organization,
                employee=employee,
                attempt=attempt,
                token=token,
                latest_version=latest_version,
            )
            attempt.status = (
                DeliveryStatus.SANDBOXED if attempt.sandbox_mode else DeliveryStatus.DELIVERED
            )
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
                metadata={"sandbox_mode": attempt.sandbox_mode, "delivery_mode": delivery_mode},
            )
        except Exception as exc:  # noqa: BLE001 - one target failing must not abort the campaign
            attempt.status = DeliveryStatus.FAILED
            attempt.preview_payload = {**attempt.preview_payload, "error": _error_text(exc)}

        attempts.append(attempt)

    campaign.status = CampaignStatus.ACTIVE
    audit_log(
        db,
        organization_id=actor.organization_id,
        user_id=actor.id,
        action="campaign.deliver",
        resource_type="campaign",
        resource_id=str(campaign.id),
        details={
            "channel": campaign.channel.value,
            "attempt_count": len(attempts),
            "delivered": sum(1 for attempt in attempts if attempt.status == DeliveryStatus.DELIVERED),
        },
    )
    db.commit()
    return attempts


def _outbound_available(channel: Channel, organization: Organization | None) -> bool:
    """True when this channel is configured to actually send something outbound."""
    if channel in SESSION_ONLY_CHANNELS or organization is None:
        return False
    if is_production_environment(settings.environment):
        # Production delivery is handled only by the durable provider-neutral run
        # workers. The legacy SMTP/SMS path remains available to local demos.
        return False
    if channel in {Channel.EMAIL, Channel.QR}:
        return bool(organization.email_provider_enabled and organization.email_provider_mode == "lab")
    if channel == Channel.SMS:
        return bool(organization.sms_provider_enabled and organization.sms_provider_mode == "lab")
    return False


def _recipient_for(channel: Channel, employee: Employee) -> str | None:
    if channel == Channel.SMS:
        return employee.phone
    if channel in SESSION_ONLY_CHANNELS:
        return None
    return employee.email


def _error_text(exc: Exception) -> str:
    detail = getattr(exc, "detail", None)
    return str(detail) if detail else str(exc)


def _deliver_email_attempt(db: Session, *, organization, employee, token, latest_version, **_) -> str:
    send_lab_email(
        org=organization,
        recipient=employee.email,
        subject=latest_version.subject,
        body_text=latest_version.body_copy,
        cta_url=f"{settings.frontend_base_url}/training/{token.token}",
        cta_text=latest_version.cta_text or "clickhere",
    )
    return "lab_email"


def _deliver_qr_email_attempt(db: Session, *, organization, employee, token, latest_version, **_) -> str:
    scan_url = entry_url(Channel.QR, token.token)
    send_lab_email(
        org=organization,
        recipient=employee.email,
        subject=latest_version.subject,
        body_text=(
            f"Dear {employee.full_name.split()[0]},\n\n{latest_version.body_copy}\n\n"
            "1. Open your phone camera.\n"
            "2. Scan the QR code shown in this email.\n"
            "3. Review the page before taking any requested action."
        ),
        cta_url=scan_url,
        cta_text=latest_version.cta_text or "Open the secure page",
        html_body=_qr_email_html(
            organization=organization,
            employee=employee,
            latest_version=latest_version,
            scan_url=scan_url,
        ),
    )
    return "lab_qr_email"


def _qr_email_html(*, organization, employee, latest_version, scan_url: str) -> str:
    """Build an email-client-safe notice with a QR encoded in the HTML itself."""

    heading = escape(latest_version.subject)
    body = escape(latest_version.body_copy).replace("\n", "<br>")
    first_name = escape(employee.full_name.split()[0])
    company_name = escape(organization.name)
    safe_scan_url = escape(scan_url, quote=True)
    qr_table = _qr_html_table(scan_url)
    return f"""<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f4f6f8;color:#202124;font-family:Arial,Helvetica,sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f4f6f8;">
      <tr>
        <td align="center" style="padding:32px 12px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
                 style="max-width:680px;background:#ffffff;border:1px solid #dfe3e8;border-radius:8px;">
            <tr>
              <td style="padding:34px 38px 18px;text-align:center;border-bottom:1px solid #edf0f2;">
                <div style="font-size:12px;line-height:18px;letter-spacing:1.4px;text-transform:uppercase;color:#667085;">
                  {company_name} · Security notice
                </div>
                <h1 style="margin:10px 0 0;font-size:25px;line-height:34px;color:#173b73;font-weight:700;">
                  {heading}
                </h1>
              </td>
            </tr>
            <tr>
              <td style="padding:30px 38px 36px;font-size:16px;line-height:25px;">
                <p style="margin:0 0 22px;">Dear {first_name},</p>
                <p style="margin:0 0 25px;">{body}</p>
                <p style="margin:0 0 18px;font-weight:600;">Scan the QR code below with your phone camera to continue.</p>
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 24px;">
                  <tr>
                    <td style="padding:14px;border:1px solid #d8dde5;background:#ffffff;">
                      {qr_table}
                    </td>
                  </tr>
                </table>
                <ol style="margin:0 0 28px;padding-left:22px;color:#344054;">
                  <li style="margin:0 0 8px;">Open the camera on your mobile device.</li>
                  <li style="margin:0 0 8px;">Point it at the QR code in this email.</li>
                  <li style="margin:0;">Review the destination before completing any requested action.</li>
                </ol>
                <p style="margin:0;font-size:13px;line-height:20px;color:#667085;">
                  If your email client does not display the QR code, use this secure link:<br>
                  <a href="{safe_scan_url}" style="color:#175cd3;text-decoration:underline;word-break:break-all;">{safe_scan_url}</a>
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:18px 38px;background:#f8fafc;border-top:1px solid #edf0f2;border-radius:0 0 8px 8px;
                         font-size:12px;line-height:19px;color:#667085;">
                This automated notice was sent by {company_name}. Please follow your organization’s security and privacy policy.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def _deliver_sms_attempt(db: Session, *, organization, employee, attempt, token, latest_version, **_) -> str:
    provider_message_id = send_lab_sms(
        org=organization,
        recipient=employee.phone,
        body_text=latest_version.body_copy,
        cta_url=f"{settings.frontend_base_url}/training/{token.token}",
    )
    if provider_message_id:
        attempt.provider_message_id = provider_message_id
    return "lab_sms"


def _activate_in_platform_attempt(db: Session, *, campaign, attempt, token, **_) -> str:
    """Nothing is sent — the tokenized session simply goes live.

    This is the normal path for voice and deepfake, and also the fallback for email, QR
    or SMS when the organization has not enabled an outbound provider.
    """
    in_platform = campaign.channel in SESSION_ONLY_CHANNELS
    attempt.preview_payload = {
        **attempt.preview_payload,
        "session_state": "active",
        "session_url": entry_url(campaign.channel, token.token),
        "expires_at": token.expires_at.isoformat() if token.expires_at else None,
    }
    if not in_platform:
        attempt.preview_payload["sandbox_reason"] = (
            f"No outbound {campaign.channel.value} provider is enabled for this organization, so the "
            "campaign ran as a preview. Nothing was sent. Configure the provider under "
            "Workspace Settings to deliver for real."
        )
    return f"{campaign.channel.value}_session" if in_platform else f"{campaign.channel.value}_sandbox"


def deliver_campaign_email(db: Session, *, campaign_id, actor) -> list[DeliveryAttempt]:
    """Backwards-compatible entry point for the email-only delivery endpoint."""
    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.organization_id == actor.organization_id)
        .first()
    )
    if campaign and campaign.channel != Channel.EMAIL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use the generic deliver endpoint for non-email channels",
        )
    return deliver_campaign(db, campaign_id=campaign_id, actor=actor)
