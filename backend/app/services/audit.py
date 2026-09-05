from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import AccessLog, AuditLog

GENESIS_HASH = "0" * 64


def _entry_hash(*, previous_hash: str, organization_id, user_id, action: str, resource_type: str, resource_id, details: dict, occurred_at: datetime) -> str:
    payload = json.dumps(
        {
            "previous_hash": previous_hash,
            "organization_id": str(organization_id),
            "user_id": str(user_id) if user_id else None,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details,
            "occurred_at": occurred_at.isoformat(),
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hmac.new(settings.secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def audit_log(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
) -> None:
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        # Serialize each tenant's chain without blocking unrelated organizations.
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:organization_id))"),
            {"organization_id": str(organization_id)},
        )
    previous = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == organization_id, AuditLog.entry_hash.is_not(None))
        .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
        .first()
    )
    previous_hash = previous.entry_hash if previous and previous.entry_hash else GENESIS_HASH
    occurred_at = datetime.now(timezone.utc)
    normalized_details = details or {}
    db.add(
        AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=normalized_details,
            previous_hash=previous_hash,
            entry_hash=_entry_hash(
                previous_hash=previous_hash,
                organization_id=organization_id,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=normalized_details,
                occurred_at=occurred_at,
            ),
            occurred_at=occurred_at,
        )
    )


def verify_audit_chain(db: Session, organization_id) -> dict[str, int | bool | str | None]:
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == organization_id, AuditLog.entry_hash.is_not(None))
        .order_by(AuditLog.occurred_at.asc(), AuditLog.id.asc())
        .all()
    )
    previous_hash = GENESIS_HASH
    for index, row in enumerate(rows):
        expected = _entry_hash(
            previous_hash=previous_hash,
            organization_id=row.organization_id,
            user_id=row.user_id,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            details=row.details,
            occurred_at=row.occurred_at if row.occurred_at.tzinfo else row.occurred_at.replace(tzinfo=timezone.utc),
        )
        if row.previous_hash != previous_hash or not hmac.compare_digest(row.entry_hash or "", expected):
            return {"valid": False, "entries": len(rows), "invalid_index": index, "invalid_entry_id": str(row.id)}
        previous_hash = row.entry_hash or previous_hash
    return {"valid": True, "entries": len(rows), "invalid_index": None, "invalid_entry_id": None}


def access_log(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None,
    resource_type: str,
    resource_id: str,
    action: str = "read",
) -> None:
    db.add(
        AccessLog(
            organization_id=organization_id,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
        )
    )
