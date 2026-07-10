from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.entities import AccessLog, AuditLog


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
    db.add(
        AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
        )
    )


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
