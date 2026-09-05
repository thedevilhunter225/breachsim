from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from redis import Redis
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import is_production_environment, settings
from app.core.crypto import blind_index
from app.db.session import SessionLocal
from app.models.entities import (
    Campaign,
    CampaignRun,
    DeliveryAttempt,
    DeliverySuppression,
    EmailConnection,
    Employee,
    LandingToken,
    Organization,
    OrganizationBranding,
    OrganizationDomain,
    OutboxEvent,
    Policy,
    QrAssetToken,
    Scenario,
    ScenarioVersion,
)
from app.models.enums import (
    CampaignRunStatus,
    CampaignStatus,
    Channel,
    ConnectionStatus,
    ConsentStatus,
    DeliveryStatus,
    DomainPurpose,
    EmployeeStatus,
    EventType,
    OutboxStatus,
    VerificationStatus,
)
from app.services.audit import audit_log
from app.services.domains import ensure_platform_landing_domain, public_origin
from app.services.email_providers import EmailEnvelope, ProviderError, provider_for_connection
from app.services.email_rendering import render_campaign_email
from app.services.events import create_event
from app.services.policy_engine import get_or_create_policy
from app.services.public_tokens import hash_token_secret, issue_public_token

TERMINAL_ATTEMPT_STATUSES = {
    DeliveryStatus.ACCEPTED,
    DeliveryStatus.BOUNCED,
    DeliveryStatus.SUPPRESSED,
    DeliveryStatus.FAILED,
    DeliveryStatus.CANCELLED,
    DeliveryStatus.UNKNOWN,
    DeliveryStatus.SANDBOXED,
    DeliveryStatus.DELIVERED,
}

# A policy frequency limit needs a bounded period; an unbounded lifetime cap
# would permanently exclude employees after a small number of campaigns. Keep
# the period in the immutable run snapshot so reporting can explain the launch
# decision even if this platform default changes later.
FREQUENCY_WINDOW_DAYS = 30
FREQUENCY_COUNTED_STATUSES = {
    DeliveryStatus.QUEUED,
    DeliveryStatus.PROCESSING,
    DeliveryStatus.ACCEPTED,
    DeliveryStatus.DELIVERED,
    DeliveryStatus.UNKNOWN,
}


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _scenario_snapshot(version: ScenarioVersion, scenario: Scenario) -> dict:
    return {
        "scenario_id": str(scenario.id),
        "scenario_version_id": str(version.id),
        "version_number": version.version_number,
        "channel": scenario.channel.value,
        "subject": version.subject,
        "body_copy": version.body_copy,
        "cta_text": version.cta_text,
        "landing_page_copy": version.landing_page_copy,
        "validation_result": version.validation_result,
    }


def _policy_snapshot(policy: Policy) -> dict:
    return {
        "policy_id": str(policy.id),
        "allowed_delivery_channels": policy.allowed_delivery_channels,
        "maximum_frequency_per_employee": policy.maximum_frequency_per_employee,
        "frequency_window_days": FREQUENCY_WINDOW_DAYS,
        "working_hours_start": policy.working_hours_start,
        "working_hours_end": policy.working_hours_end,
        "opt_out_respected": policy.opt_out_respected,
        "approved_training_domains": policy.approved_training_domains,
    }


def _branding_snapshot(branding: OrganizationBranding | None, org: Organization) -> dict:
    return {
        "logo_url": branding.logo_url if branding else None,
        "primary_color": branding.primary_color if branding else "#173B73",
        "accent_color": branding.accent_color if branding else "#175CD3",
        "sender_name": branding.sender_name if branding else org.name,
        "legal_footer": branding.legal_footer if branding else org.privacy_notice,
        "approved_template_ids": branding.approved_template_ids if branding else [],
    }


def _public_base(hostname: str) -> str:
    if not is_production_environment(settings.environment) and settings.public_dev_base_url:
        return settings.public_dev_base_url.rstrip("/")
    return public_origin(hostname)


def public_entry_url(*, hostname: str, channel: Channel, token: str) -> str:
    route = "q" if channel == Channel.QR else "l"
    return f"{_public_base(hostname)}/{route}/{token}"


def public_qr_asset_url(*, hostname: str, token: str) -> str:
    return f"{_public_base(hostname)}/qr-assets/{token}.png"


def _active_domains(db: Session, organization_id, purpose: DomainPurpose) -> list[OrganizationDomain]:
    return (
        db.query(OrganizationDomain)
        .filter(
            OrganizationDomain.organization_id == organization_id,
            OrganizationDomain.purpose == purpose,
            OrganizationDomain.status == VerificationStatus.ACTIVE,
        )
        .all()
    )


def _email_domain_allowed(email: str, verified_domains: list[OrganizationDomain]) -> bool:
    domain = email.rpartition("@")[2].casefold()
    return any(domain == row.hostname or domain.endswith(f".{row.hostname}") for row in verified_domains)


def _load_launch_components(db: Session, *, campaign_id, actor):
    campaign = (
        db.query(Campaign)
        .options(
            selectinload(Campaign.targets),
            selectinload(Campaign.scenario_links),
        )
        .filter(Campaign.id == campaign_id, Campaign.organization_id == actor.organization_id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if campaign.channel not in {Channel.EMAIL, Channel.QR}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Enterprise runs currently support Email and QR")
    if campaign.status not in {CampaignStatus.APPROVED, CampaignStatus.SCHEDULED}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Campaign must be approved before launch")
    if not campaign.targets or not campaign.scenario_links:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Campaign requires targets and a scenario")
    if len(campaign.targets) > settings.max_campaign_recipients:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Campaign exceeds the {settings.max_campaign_recipients}-recipient launch limit",
        )
    scenario = db.query(Scenario).filter(Scenario.id == campaign.scenario_links[0].scenario_id).first()
    if not scenario or scenario.status.value != "approved" or scenario.channel != campaign.channel:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Campaign scenario is not approved for this channel")
    version = None
    if scenario.current_version_id:
        version = db.query(ScenarioVersion).filter(ScenarioVersion.id == scenario.current_version_id).first()
    if not version:
        version = (
            db.query(ScenarioVersion)
            .filter(ScenarioVersion.scenario_id == scenario.id)
            .order_by(ScenarioVersion.version_number.desc())
            .first()
        )
    if not version or not version.validation_result.get("passed", True):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approved scenario version is unavailable")
    org = db.query(Organization).filter(Organization.id == actor.organization_id).one()
    return campaign, scenario, version, org


def create_campaign_run(
    db: Session,
    *,
    campaign_id,
    actor,
    idempotency_key: str,
    scheduled_for: datetime | None = None,
) -> CampaignRun:
    clean_key = idempotency_key.strip()
    if not 8 <= len(clean_key) <= 128:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Idempotency-Key must be 8-128 characters")
    existing = db.query(CampaignRun).filter(
        CampaignRun.organization_id == actor.organization_id,
        CampaignRun.idempotency_key == clean_key,
    ).first()
    if existing:
        if existing.campaign_id != campaign_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency-Key belongs to another campaign")
        return existing

    campaign, scenario, version, org = _load_launch_components(db, campaign_id=campaign_id, actor=actor)
    landing_domain = None
    if campaign.landing_domain_id:
        landing_domain = db.query(OrganizationDomain).filter(
            OrganizationDomain.id == campaign.landing_domain_id,
            OrganizationDomain.organization_id == org.id,
            OrganizationDomain.purpose == DomainPurpose.LANDING,
            OrganizationDomain.status == VerificationStatus.ACTIVE,
        ).first()
    if not landing_domain:
        landing_domain = ensure_platform_landing_domain(db, org)

    connection = None
    if not campaign.sandbox_mode:
        if not campaign.email_connection_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A healthy email connection is required")
        connection = db.query(EmailConnection).filter(
            EmailConnection.id == campaign.email_connection_id,
            EmailConnection.organization_id == org.id,
            EmailConnection.status == ConnectionStatus.HEALTHY,
            EmailConnection.revoked_at.is_(None),
        ).first()
        if not connection:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email connection is not healthy")
    recipient_domains = _active_domains(db, org.id, DomainPurpose.RECIPIENT)
    if not campaign.sandbox_mode and not recipient_domains:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A verified recipient domain is required")
    if connection:
        sender_domain = connection.sender_email.rpartition("@")[2].casefold()
        sender_domains = _active_domains(db, org.id, DomainPurpose.SENDER)
        if not any(row.hostname == sender_domain for row in sender_domains):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The selected sender domain is not verified")

    policy = get_or_create_policy(db, org.id)
    if policy.allowed_delivery_channels and campaign.channel.value not in policy.allowed_delivery_channels:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Channel is blocked by organization policy")
    branding = db.query(OrganizationBranding).filter(OrganizationBranding.organization_id == org.id).first()
    if branding and branding.approved_template_ids:
        approved_templates = {str(value) for value in branding.approved_template_ids}
        if str(scenario.id) not in approved_templates and str(version.id) not in approved_templates:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Scenario is not on the organization's approved email-template allowlist",
            )
    schedule = _utc(scheduled_for or campaign.schedule_at)
    now = datetime.now(timezone.utc)
    run_status = CampaignRunStatus.SCHEDULED if schedule and schedule > now else CampaignRunStatus.QUEUED
    run = CampaignRun(
        id=uuid.uuid4(),
        organization_id=org.id,
        campaign_id=campaign.id,
        created_by_user_id=actor.id,
        idempotency_key=clean_key,
        status=CampaignRunStatus.COMPLETED if campaign.sandbox_mode else run_status,
        scenario_snapshot=_scenario_snapshot(version, scenario),
        policy_snapshot=_policy_snapshot(policy),
        branding_snapshot=_branding_snapshot(branding, org),
        delivery_snapshot={
            "landing_hostname": landing_domain.hostname,
            "landing_domain_id": str(landing_domain.id),
            "email_connection_id": str(connection.id) if connection else None,
            "provider": connection.provider.value if connection else "sandbox",
            "sender_email": connection.sender_email if connection else None,
            "sender_name": connection.sender_name if connection else None,
            "throttling_per_hour": campaign.throttling_per_hour,
        },
        reporting_identity_mode=org.reporting_identity_mode,
        scheduled_for=schedule,
        target_count=0,
    )
    db.add(run)

    suppressions = {
        row.email_hash
        for row in db.query(DeliverySuppression).filter(
            DeliverySuppression.organization_id == org.id,
            DeliverySuppression.active.is_(True),
        )
    }
    employee_ids = [target.employee_id for target in campaign.targets]
    employees = {
        employee.id: employee
        for employee in db.query(Employee).filter(
            Employee.organization_id == org.id,
            Employee.id.in_(employee_ids),
        )
    }
    frequency_counts: dict[str, int] = {}
    if not campaign.sandbox_mode and policy.maximum_frequency_per_employee > 0:
        frequency_cutoff = now - timedelta(days=FREQUENCY_WINDOW_DAYS)
        frequency_counts = {
            str(employee_id): count
            for employee_id, count in (
                db.query(DeliveryAttempt.employee_id, func.count(DeliveryAttempt.id))
                .filter(
                    DeliveryAttempt.employee_id.in_(employee_ids),
                    DeliveryAttempt.sandbox_mode.is_(False),
                    DeliveryAttempt.created_at >= frequency_cutoff,
                    DeliveryAttempt.status.in_(FREQUENCY_COUNTED_STATUSES),
                )
                .group_by(DeliveryAttempt.employee_id)
                .all()
            )
        }
    queued_ids: list[str] = []
    suppressed_count = 0
    seen_employee_ids: set[uuid.UUID] = set()
    for target in campaign.targets:
        if target.employee_id in seen_employee_ids:
            continue
        seen_employee_ids.add(target.employee_id)
        employee = employees.get(target.employee_id)
        if not employee:
            continue
        email_hash = employee.email_blind_index or blind_index(employee.email, namespace="employee-email")
        employee.email_blind_index = email_hash
        suppression_code = None
        if employee.status != EmployeeStatus.ACTIVE:
            suppression_code = "employee_inactive"
        elif policy.opt_out_respected and employee.consent_status in {
            ConsentStatus.OPTED_OUT,
            ConsentStatus.REDACTION_REQUESTED,
        }:
            suppression_code = "employee_opted_out"
        elif not campaign.sandbox_mode and not _email_domain_allowed(employee.email, recipient_domains):
            suppression_code = "recipient_domain_unverified"
        elif email_hash in suppressions:
            suppression_code = "recipient_suppressed"
        elif frequency_counts.get(str(employee.id), 0) >= policy.maximum_frequency_per_employee:
            suppression_code = "frequency_cap_reached"

        attempt_status = (
            DeliveryStatus.SUPPRESSED
            if suppression_code
            else DeliveryStatus.SANDBOXED
            if campaign.sandbox_mode
            else DeliveryStatus.QUEUED
        )
        attempt = DeliveryAttempt(
            id=uuid.uuid4(),
            campaign_run_id=run.id,
            campaign_id=campaign.id,
            employee_id=employee.id,
            scenario_id=scenario.id,
            channel=campaign.channel,
            status=attempt_status,
            sandbox_mode=campaign.sandbox_mode,
            recipient_ciphertext=employee.email,
            idempotency_key=f"{run.id}:{employee.id}",
            preview_payload={
                "schema_version": 2,
                "subject": version.subject,
                "delivery_format": "remote_inline_qr" if campaign.channel == Channel.QR else "html_and_text",
                "landing_hostname": landing_domain.hostname,
                "suppression_code": suppression_code,
                "frequency_count": frequency_counts.get(str(employee.id), 0),
                "frequency_limit": policy.maximum_frequency_per_employee,
            },
        )
        db.add(attempt)
        run.target_count += 1
        if suppression_code or campaign.sandbox_mode:
            if suppression_code:
                suppressed_count += 1
            continue

        landing_issued = issue_public_token()
        expires_at = now + timedelta(days=settings.campaign_token_ttl_days)
        landing_token = LandingToken(
            id=uuid.uuid4(),
            delivery_attempt_id=attempt.id,
            employee_id=employee.id,
            campaign_id=campaign.id,
            token=None,
            token_public_id=landing_issued.public_id,
            token_secret_hash=hash_token_secret(landing_issued.secret),
            token_secret_ciphertext=landing_issued.secret,
            landing_hostname=landing_domain.hostname,
            landing_type=campaign.channel.value,
            expires_at=expires_at,
        )
        db.add(landing_token)
        landing_url = public_entry_url(
            hostname=landing_domain.hostname,
            channel=campaign.channel,
            token=landing_issued.value,
        )
        if campaign.channel == Channel.QR:
            asset_issued = issue_public_token()
            db.add(
                QrAssetToken(
                    id=uuid.uuid4(),
                    landing_token_id=landing_token.id,
                    public_id=asset_issued.public_id,
                    secret_hash=hash_token_secret(asset_issued.secret),
                    secret_ciphertext=asset_issued.secret,
                    qr_payload_ciphertext=landing_url,
                    expires_at=expires_at,
                )
            )
        queued_ids.append(str(attempt.id))

    run.queued_count = len(queued_ids)
    run.suppressed_count = suppressed_count
    available_at = schedule or now
    for offset in range(0, len(queued_ids), 100):
        batch = queued_ids[offset : offset + 100]
        db.add(
            OutboxEvent(
                organization_id=org.id,
                aggregate_type="campaign_run",
                aggregate_id=run.id,
                event_type="campaign.delivery_batch",
                payload={"run_id": str(run.id), "attempt_ids": batch},
                available_at=available_at,
            )
        )
    campaign.status = CampaignStatus.SCHEDULED if run_status == CampaignRunStatus.SCHEDULED else CampaignStatus.ACTIVE
    if campaign.sandbox_mode:
        campaign.status = CampaignStatus.COMPLETED
        run.completed_at = now
    audit_log(
        db,
        organization_id=org.id,
        user_id=actor.id,
        action="campaign_run.create",
        resource_type="campaign_run",
        resource_id=str(run.id),
        details={
            "campaign_id": str(campaign.id),
            "target_count": run.target_count,
            "queued_count": run.queued_count,
            "suppressed_count": run.suppressed_count,
            "landing_hostname": landing_domain.hostname,
            "provider": run.delivery_snapshot["provider"],
        },
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.query(CampaignRun).filter(
            CampaignRun.organization_id == actor.organization_id,
            CampaignRun.idempotency_key == clean_key,
        ).first()
        if existing and existing.campaign_id == campaign_id:
            return existing
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency-Key belongs to another campaign",
            ) from exc
        raise
    db.refresh(run)
    return run


def _enforce_rate_limit(db: Session, attempt: DeliveryAttempt, run: CampaignRun, connection: EmailConnection) -> bool:
    now = datetime.now(timezone.utc)
    try:
        redis = Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
        minute_key = f"delivery-rate:{run.organization_id}:{connection.id}:{now:%Y%m%d%H%M}"
        hour_key = f"campaign-rate:{run.id}:{now:%Y%m%d%H}"
        allowed, minute_count, hour_count = redis.eval(
            """
            local minute_count = tonumber(redis.call('GET', KEYS[1]) or '0')
            local hour_count = tonumber(redis.call('GET', KEYS[2]) or '0')
            if minute_count >= tonumber(ARGV[1]) or hour_count >= tonumber(ARGV[2]) then
              return {0, minute_count, hour_count}
            end
            minute_count = redis.call('INCR', KEYS[1])
            hour_count = redis.call('INCR', KEYS[2])
            if minute_count == 1 then redis.call('EXPIRE', KEYS[1], 120) end
            if hour_count == 1 then redis.call('EXPIRE', KEYS[2], 7200) end
            return {1, minute_count, hour_count}
            """,
            2,
            minute_key,
            hour_key,
            connection.rate_limit_per_minute,
            run.delivery_snapshot["throttling_per_hour"],
        )
        redis.close()
    except Exception:
        if is_production_environment(settings.environment):
            attempt.next_attempt_at = now + timedelta(seconds=60)
            attempt.last_error_code = "rate_limiter_unavailable"
            return False
        return True
    if not allowed:
        attempt.next_attempt_at = now + timedelta(seconds=60)
        attempt.last_error_code = "rate_limited_locally"
        return False
    return True


def _inside_working_hours(run: CampaignRun, org: Organization, attempt: DeliveryAttempt) -> bool:
    try:
        local_now = datetime.now(timezone.utc).astimezone(ZoneInfo(org.timezone))
    except Exception:
        local_now = datetime.now(timezone.utc)
    start = int(run.policy_snapshot.get("working_hours_start", 9))
    end = int(run.policy_snapshot.get("working_hours_end", 18))
    if start <= local_now.hour < end:
        return True
    next_day = local_now.date() if local_now.hour < start else local_now.date() + timedelta(days=1)
    next_local = datetime.combine(next_day, datetime.min.time(), tzinfo=local_now.tzinfo).replace(hour=start)
    attempt.next_attempt_at = next_local.astimezone(timezone.utc)
    attempt.last_error_code = "outside_working_hours"
    return False


def _schedule_deferred_attempt(db: Session, attempt: DeliveryAttempt, run: CampaignRun) -> None:
    """Publish a replacement message before the current Service Bus message is completed."""
    db.add(
        OutboxEvent(
            organization_id=run.organization_id,
            aggregate_type="delivery_attempt",
            aggregate_id=attempt.id,
            event_type="campaign.delivery_batch",
            payload={"run_id": str(run.id), "attempt_ids": [str(attempt.id)]},
            available_at=attempt.next_attempt_at or datetime.now(timezone.utc),
        )
    )


def process_delivery_attempt(db: Session, attempt_id: str | uuid.UUID) -> DeliveryAttempt | None:
    attempt = (
        db.query(DeliveryAttempt)
        .options(joinedload(DeliveryAttempt.campaign_run))
        .filter(DeliveryAttempt.id == attempt_id)
        .with_for_update(skip_locked=True)
        .first()
    )
    if not attempt or attempt.status != DeliveryStatus.QUEUED or not attempt.campaign_run:
        return attempt
    run = attempt.campaign_run
    if run.status in {CampaignRunStatus.PAUSED, CampaignRunStatus.CANCELLED, CampaignRunStatus.CANCELLING}:
        if run.status in {CampaignRunStatus.CANCELLED, CampaignRunStatus.CANCELLING}:
            attempt.status = DeliveryStatus.CANCELLED
        return attempt
    now = datetime.now(timezone.utc)
    if _utc(attempt.next_attempt_at) and _utc(attempt.next_attempt_at) > now:
        return attempt
    if _utc(run.scheduled_for) and _utc(run.scheduled_for) > now:
        attempt.next_attempt_at = run.scheduled_for
        return attempt

    org = db.query(Organization).filter(Organization.id == run.organization_id).one()
    if not _inside_working_hours(run, org, attempt):
        _schedule_deferred_attempt(db, attempt, run)
        return attempt
    connection_id = run.delivery_snapshot.get("email_connection_id")
    connection = db.query(EmailConnection).filter(
        EmailConnection.id == connection_id,
        EmailConnection.organization_id == run.organization_id,
        EmailConnection.status == ConnectionStatus.HEALTHY,
        EmailConnection.revoked_at.is_(None),
    ).first()
    if not connection:
        attempt.status = DeliveryStatus.FAILED
        attempt.last_error_code = "email_connection_unavailable"
        attempt.last_error_detail = "The selected email connection is no longer healthy"
        _refresh_run_counts(db, run)
        return attempt
    if not _enforce_rate_limit(db, attempt, run, connection):
        _schedule_deferred_attempt(db, attempt, run)
        return attempt

    employee = (
        db.query(Employee)
        .options(joinedload(Employee.department))
        .filter(Employee.id == attempt.employee_id, Employee.organization_id == run.organization_id)
        .first()
    )
    landing_token = db.query(LandingToken).filter(LandingToken.delivery_attempt_id == attempt.id).first()
    if not employee or not landing_token or not landing_token.token_secret_ciphertext:
        attempt.status = DeliveryStatus.FAILED
        attempt.last_error_code = "delivery_material_missing"
        _refresh_run_counts(db, run)
        return attempt
    landing_value = f"{landing_token.token_public_id}.{landing_token.token_secret_ciphertext}"
    landing_url = public_entry_url(
        hostname=landing_token.landing_hostname,
        channel=attempt.channel,
        token=landing_value,
    )
    qr_asset = db.query(QrAssetToken).filter(QrAssetToken.landing_token_id == landing_token.id).first()
    qr_image_url = None
    if qr_asset:
        if not qr_asset.secret_ciphertext:
            attempt.status = DeliveryStatus.FAILED
            attempt.last_error_code = "qr_asset_material_missing"
            _refresh_run_counts(db, run)
            return attempt
        qr_image_url = public_qr_asset_url(
            hostname=landing_token.landing_hostname,
            token=f"{qr_asset.public_id}.{qr_asset.secret_ciphertext}",
        )
    rendered = render_campaign_email(
        employee=employee,
        organization=org,
        branding_snapshot=run.branding_snapshot,
        scenario_snapshot=run.scenario_snapshot,
        landing_url=landing_url,
        qr_image_url=qr_image_url,
    )
    envelope = EmailEnvelope(
        recipient=attempt.recipient_ciphertext or employee.email,
        sender_email=connection.sender_email,
        sender_name=connection.sender_name,
        subject=rendered.subject,
        text_body=rendered.text_body,
        html_body=rendered.html_body,
        idempotency_key=attempt.idempotency_key or str(attempt.id),
        headers={"X-BreachSim-Run-ID": str(run.id)},
    )
    attempt.status = DeliveryStatus.PROCESSING
    run.status = CampaignRunStatus.RUNNING
    run.started_at = run.started_at or now
    try:
        result = provider_for_connection(connection).send(envelope)
    except ProviderError as exc:
        attempt.retry_count += 1
        attempt.last_error_code = exc.code
        attempt.last_error_detail = str(exc)[:2000]
        if exc.outcome_unknown:
            attempt.status = DeliveryStatus.UNKNOWN
        elif exc.retryable and attempt.retry_count <= settings.email_provider_max_retries:
            delay = exc.retry_after_seconds or min(900, int(math.pow(2, attempt.retry_count) * 15))
            # A small deterministic component avoids retry storms without relying on
            # process-global random state.
            delay += attempt.id.int % 11
            attempt.status = DeliveryStatus.QUEUED
            attempt.next_attempt_at = now + timedelta(seconds=delay)
            db.add(
                OutboxEvent(
                    organization_id=run.organization_id,
                    aggregate_type="delivery_attempt",
                    aggregate_id=attempt.id,
                    event_type="campaign.delivery_batch",
                    payload={"run_id": str(run.id), "attempt_ids": [str(attempt.id)]},
                    available_at=attempt.next_attempt_at,
                )
            )
        else:
            attempt.status = DeliveryStatus.FAILED
    else:
        attempt.status = DeliveryStatus.ACCEPTED
        attempt.provider_message_id = result.provider_message_id
        attempt.accepted_at = now
        attempt.delivered_at = now  # legacy compatibility; UI labels this provider-accepted
        attempt.last_error_code = None
        attempt.last_error_detail = None
        landing_token.token_secret_ciphertext = None
        if qr_asset:
            qr_asset.secret_ciphertext = None
        create_event(
            db,
            organization_id=run.organization_id,
            employee_id=employee.id,
            campaign_id=attempt.campaign_id,
            delivery_attempt_id=attempt.id,
            landing_token_id=landing_token.id,
            event_type=EventType.PROVIDER_ACCEPTED,
            channel=attempt.channel,
            metadata={"provider": connection.provider.value, "status": result.provider_status},
        )
    _refresh_run_counts(db, run)
    return attempt


def _refresh_run_counts(db: Session, run: CampaignRun) -> None:
    rows = dict(
        db.query(DeliveryAttempt.status, func.count(DeliveryAttempt.id))
        .filter(DeliveryAttempt.campaign_run_id == run.id)
        .group_by(DeliveryAttempt.status)
        .all()
    )
    run.queued_count = rows.get(DeliveryStatus.QUEUED, 0)
    run.processing_count = rows.get(DeliveryStatus.PROCESSING, 0)
    run.accepted_count = rows.get(DeliveryStatus.ACCEPTED, 0) + rows.get(DeliveryStatus.DELIVERED, 0)
    run.bounced_count = rows.get(DeliveryStatus.BOUNCED, 0)
    run.suppressed_count = rows.get(DeliveryStatus.SUPPRESSED, 0)
    run.failed_count = rows.get(DeliveryStatus.FAILED, 0)
    run.unknown_count = rows.get(DeliveryStatus.UNKNOWN, 0)
    terminal = sum(count for state, count in rows.items() if state in TERMINAL_ATTEMPT_STATUSES)
    if terminal >= run.target_count:
        run.status = CampaignRunStatus.COMPLETED
        run.completed_at = datetime.now(timezone.utc)
        campaign = db.query(Campaign).filter(Campaign.id == run.campaign_id).first()
        if campaign:
            campaign.status = CampaignStatus.COMPLETED


def process_delivery_batch(attempt_ids: list[str]) -> int:
    processed = 0
    for attempt_id in attempt_ids:
        db = SessionLocal()
        try:
            attempt = process_delivery_attempt(db, attempt_id)
            db.commit()
            if attempt:
                processed += 1
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    return processed


def dispatch_outbox(*, limit: int = 100) -> int:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        query = (
            db.query(OutboxEvent)
            .filter(OutboxEvent.status == OutboxStatus.PENDING)
            .order_by(OutboxEvent.available_at.asc())
        )
        if settings.email_delivery_backend == "database":
            query = query.filter(OutboxEvent.available_at <= now)
        events = query.with_for_update(skip_locked=True).limit(limit).all()
        if not events:
            return 0
        published = 0
        for event in events:
            try:
                _publish_event(event)
            except Exception as exc:
                event.publish_attempts += 1
                event.last_error = str(exc)[:2000]
                if event.publish_attempts >= 10:
                    event.status = OutboxStatus.FAILED
            else:
                event.status = OutboxStatus.PUBLISHED
                event.published_at = now
                event.publish_attempts += 1
                event.last_error = None
                published += 1
        db.commit()
        return published
    finally:
        db.close()


def _publish_event(event: OutboxEvent) -> None:
    backend = settings.email_delivery_backend
    if backend == "database":
        process_delivery_batch(event.payload["attempt_ids"])
        return
    if backend == "rq":
        from app.workers.queue import get_queue
        from app.workers.tasks import process_delivery_batch_job

        queue = get_queue("campaign-delivery")
        available_at = _utc(event.available_at)
        if available_at and available_at > datetime.now(timezone.utc):
            queue.enqueue_at(available_at, process_delivery_batch_job, event.payload["attempt_ids"])
        else:
            queue.enqueue(process_delivery_batch_job, event.payload["attempt_ids"])
        return
    if backend == "service_bus":
        if not settings.service_bus_fully_qualified_namespace:
            raise RuntimeError("SERVICE_BUS_FULLY_QUALIFIED_NAMESPACE is not configured")
        from azure.identity import DefaultAzureCredential
        from azure.servicebus import ServiceBusClient, ServiceBusMessage

        credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        with ServiceBusClient(
            fully_qualified_namespace=settings.service_bus_fully_qualified_namespace,
            credential=credential,
        ) as client:
            with client.get_queue_sender(settings.service_bus_campaign_queue) as sender:
                message = ServiceBusMessage(
                    json.dumps(event.payload, separators=(",", ":")),
                    message_id=str(event.id),
                    content_type="application/json",
                    application_properties={"event_type": event.event_type},
                )
                available_at = _utc(event.available_at)
                if available_at and available_at > datetime.now(timezone.utc):
                    sender.schedule_messages(message, available_at)
                else:
                    sender.send_messages(message)
        return
    raise RuntimeError(f"Unsupported EMAIL_DELIVERY_BACKEND: {backend}")


def update_run_state(db: Session, *, run: CampaignRun, action: str, actor) -> CampaignRun:
    allowed = {
        "pause": ({CampaignRunStatus.QUEUED, CampaignRunStatus.RUNNING, CampaignRunStatus.SCHEDULED}, CampaignRunStatus.PAUSED),
        "resume": ({CampaignRunStatus.PAUSED}, CampaignRunStatus.QUEUED),
        "cancel": (
            {CampaignRunStatus.QUEUED, CampaignRunStatus.RUNNING, CampaignRunStatus.SCHEDULED, CampaignRunStatus.PAUSED},
            CampaignRunStatus.CANCELLED,
        ),
    }
    if action not in allowed or run.status not in allowed[action][0]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Run cannot be {action}d from {run.status.value}")
    run.status = allowed[action][1]
    if action == "cancel":
        db.query(DeliveryAttempt).filter(
            DeliveryAttempt.campaign_run_id == run.id,
            DeliveryAttempt.status == DeliveryStatus.QUEUED,
        ).update({DeliveryAttempt.status: DeliveryStatus.CANCELLED}, synchronize_session=False)
        run.completed_at = datetime.now(timezone.utc)
    elif action == "resume":
        pending_ids = [
            str(row.id)
            for row in db.query(DeliveryAttempt).filter(
                DeliveryAttempt.campaign_run_id == run.id,
                DeliveryAttempt.status == DeliveryStatus.QUEUED,
            )
        ]
        for offset in range(0, len(pending_ids), 100):
            db.add(
                OutboxEvent(
                    organization_id=run.organization_id,
                    aggregate_type="campaign_run",
                    aggregate_id=run.id,
                    event_type="campaign.delivery_batch",
                    payload={"run_id": str(run.id), "attempt_ids": pending_ids[offset : offset + 100]},
                    available_at=datetime.now(timezone.utc),
                )
            )
    audit_log(
        db,
        organization_id=run.organization_id,
        user_id=actor.id,
        action=f"campaign_run.{action}",
        resource_type="campaign_run",
        resource_id=str(run.id),
    )
    db.commit()
    db.refresh(run)
    return run


def retry_failed_attempts(db: Session, *, run: CampaignRun, actor) -> CampaignRun:
    attempt_ids = [
        str(row.id)
        for row in db.query(DeliveryAttempt).filter(
            DeliveryAttempt.campaign_run_id == run.id,
            DeliveryAttempt.status == DeliveryStatus.FAILED,
        )
    ]
    if not attempt_ids:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Run has no retryable failed attempts")
    db.query(DeliveryAttempt).filter(
        DeliveryAttempt.id.in_(attempt_ids)
    ).update(
        {
            DeliveryAttempt.status: DeliveryStatus.QUEUED,
            DeliveryAttempt.next_attempt_at: None,
            DeliveryAttempt.last_error_code: None,
            DeliveryAttempt.last_error_detail: None,
            DeliveryAttempt.retry_count: 0,
        },
        synchronize_session=False,
    )
    run.status = CampaignRunStatus.QUEUED
    run.completed_at = None
    for offset in range(0, len(attempt_ids), 100):
        db.add(
            OutboxEvent(
                organization_id=run.organization_id,
                aggregate_type="campaign_run",
                aggregate_id=run.id,
                event_type="campaign.delivery_batch",
                payload={"run_id": str(run.id), "attempt_ids": attempt_ids[offset : offset + 100]},
            )
        )
    audit_log(
        db,
        organization_id=run.organization_id,
        user_id=actor.id,
        action="campaign_run.retry_failed",
        resource_type="campaign_run",
        resource_id=str(run.id),
        details={"attempt_count": len(attempt_ids)},
    )
    db.commit()
    db.refresh(run)
    return run
