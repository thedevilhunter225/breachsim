from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.crypto import blind_index
from app.db.session import get_db
from app.models.entities import (
    Campaign,
    DeliveryAttempt,
    DeliverySuppression,
    EmailConnection,
    Employee,
    EventLog,
    ProviderEventReceipt,
)
from app.models.enums import DeliveryStatus, EmailProviderKind, EventType, SuppressionReason, UserRole
from app.schemas.enterprise import ProviderReconciliationPayload
from app.services.audit import audit_log
from app.services.campaign_runs import _refresh_run_counts
from app.services.events import create_event
from app.services.secret_store import SecretStoreError, secret_store

router = APIRouter()
SIGNATURE_WINDOW_SECONDS = 300


def _tenant_connection(db: Session, *, connection_id: uuid.UUID, organization_id=None) -> EmailConnection:
    query = db.query(EmailConnection).filter(EmailConnection.id == connection_id)
    if organization_id is not None:
        query = query.filter(EmailConnection.organization_id == organization_id)
    connection = query.first()
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email connection not found")
    return connection


def _attempt_for_event(
    db: Session,
    *,
    connection: EmailConnection,
    payload: ProviderReconciliationPayload,
) -> DeliveryAttempt:
    query = db.query(DeliveryAttempt)
    if payload.attempt_id:
        query = query.filter(DeliveryAttempt.id == payload.attempt_id)
    else:
        query = query.filter(DeliveryAttempt.provider_message_id == payload.provider_message_id)
    for attempt in query.all():
        if attempt.campaign_run:
            snapshotted_connection = attempt.campaign_run.delivery_snapshot.get("email_connection_id")
            if (
                attempt.campaign_run.organization_id == connection.organization_id
                and snapshotted_connection == str(connection.id)
            ):
                return attempt
            continue
        # Compatibility for pre-run attempts issued before immutable run snapshots.
        campaign = db.query(Campaign).filter(
            Campaign.id == attempt.campaign_id,
            Campaign.organization_id == connection.organization_id,
            Campaign.email_connection_id == connection.id,
        ).first()
        if campaign:
            return attempt
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery attempt not found")


def _apply_reconciliation(
    db: Session,
    *,
    connection: EmailConnection,
    payload: ProviderReconciliationPayload,
    payload_hash: str,
    signature_timestamp: datetime | None,
) -> tuple[DeliveryAttempt, bool]:
    existing = db.query(ProviderEventReceipt).filter(
        ProviderEventReceipt.email_connection_id == connection.id,
        ProviderEventReceipt.provider_event_id == payload.event_id,
    ).first()
    if existing:
        attempt = db.query(DeliveryAttempt).filter(DeliveryAttempt.id == existing.delivery_attempt_id).one()
        return attempt, True

    attempt = _attempt_for_event(db, connection=connection, payload=payload)
    now = datetime.now(timezone.utc)
    mapped_status = DeliveryStatus(payload.status)
    if mapped_status == DeliveryStatus.ACCEPTED:
        attempt.accepted_at = attempt.accepted_at or now
        attempt.provider_message_id = payload.provider_message_id or attempt.provider_message_id
        attempt.last_error_code = None
        attempt.last_error_detail = None
        event_type = EventType.PROVIDER_ACCEPTED
    elif mapped_status == DeliveryStatus.BOUNCED:
        attempt.bounced_at = now
        attempt.last_error_code = payload.reason_code or "provider_bounce"
        attempt.last_error_detail = "Provider reported a non-delivery response"
        event_type = EventType.BOUNCED
        if payload.hard_bounce:
            employee = db.query(Employee).filter(Employee.id == attempt.employee_id).one()
            email_hash = employee.email_blind_index or blind_index(employee.email, namespace="employee-email")
            employee.email_blind_index = email_hash
            suppression = db.query(DeliverySuppression).filter(
                DeliverySuppression.organization_id == connection.organization_id,
                DeliverySuppression.email_hash == email_hash,
            ).first()
            if not suppression:
                suppression = DeliverySuppression(
                    organization_id=connection.organization_id,
                    email_hash=email_hash,
                    reason=SuppressionReason.HARD_BOUNCE,
                    provider=connection.provider,
                    active=True,
                )
                db.add(suppression)
            suppression.active = True
            suppression.details = {"attempt_id": str(attempt.id), "reason_code": payload.reason_code}
    else:
        attempt.last_error_code = payload.reason_code or f"provider_{payload.status}"
        attempt.last_error_detail = "Provider reconciliation did not confirm delivery"
        event_type = None

    attempt.status = mapped_status
    if event_type and not db.query(EventLog).filter(
        EventLog.delivery_attempt_id == attempt.id,
        EventLog.event_type == event_type,
    ).first():
        create_event(
            db,
            organization_id=connection.organization_id,
            employee_id=attempt.employee_id,
            campaign_id=attempt.campaign_id,
            delivery_attempt_id=attempt.id,
            landing_token_id=None,
            event_type=event_type,
            channel=attempt.channel,
            metadata={"provider": connection.provider.value, "reason_code": payload.reason_code},
        )
    db.add(
        ProviderEventReceipt(
            organization_id=connection.organization_id,
            email_connection_id=connection.id,
            delivery_attempt_id=attempt.id,
            provider_event_id=payload.event_id,
            payload_hash=payload_hash,
            reconciled_status=mapped_status,
            reason_code=payload.reason_code,
            signature_timestamp=signature_timestamp,
        )
    )
    if attempt.campaign_run:
        _refresh_run_counts(db, attempt.campaign_run)
    return attempt, False


@router.post("/provider-webhooks/{provider}/{connection_id}", include_in_schema=False)
async def receive_provider_reconciliation(
    provider: EmailProviderKind,
    connection_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    signature: Annotated[str, Header(alias="X-BreachSim-Signature")],
    timestamp: Annotated[int, Header(alias="X-BreachSim-Timestamp")],
):
    connection = _tenant_connection(db, connection_id=connection_id)
    if connection.provider != provider or provider == EmailProviderKind.SMTP_LAB:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email connection not found")
    if abs(int(time.time()) - timestamp) > SIGNATURE_WINDOW_SECONDS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook signature has expired")
    try:
        signing_secret = secret_store.get(connection.reconciliation_secret_ref)
    except SecretStoreError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Webhook signing is unavailable") from exc
    body = await request.body()
    expected = hmac.new(
        signing_secret.encode("utf-8"),
        str(timestamp).encode("ascii") + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    supplied = signature.removeprefix("sha256=")
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook signature is invalid")
    try:
        payload = ProviderReconciliationPayload.model_validate_json(body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Webhook payload is invalid") from exc
    attempt, duplicate = _apply_reconciliation(
        db,
        connection=connection,
        payload=payload,
        payload_hash=hashlib.sha256(body).hexdigest(),
        signature_timestamp=datetime.fromtimestamp(timestamp, tz=timezone.utc),
    )
    db.commit()
    return {"status": attempt.status.value, "attempt_id": str(attempt.id), "duplicate": duplicate}


@router.post("/email-connections/{connection_id}/reconcile")
def reconcile_delivery_manually(
    connection_id: uuid.UUID,
    payload: ProviderReconciliationPayload,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    connection = _tenant_connection(db, connection_id=connection_id, organization_id=user.organization_id)
    canonical = payload.model_dump_json().encode("utf-8")
    attempt, duplicate = _apply_reconciliation(
        db,
        connection=connection,
        payload=payload,
        payload_hash=hashlib.sha256(canonical).hexdigest(),
        signature_timestamp=None,
    )
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="delivery.reconcile",
        resource_type="delivery_attempt",
        resource_id=str(attempt.id),
        details={"status": attempt.status.value, "reason_code": payload.reason_code, "duplicate": duplicate},
    )
    db.commit()
    return {"status": attempt.status.value, "attempt_id": str(attempt.id), "duplicate": duplicate}
