from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.entities import AccessLog, AuditLog, ReportExport
from app.models.enums import UserRole
from app.services.reports import export_audit_csv, export_campaign_html

router = APIRouter()


@router.get("/audit-logs")
def list_audit_logs(db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR))):
    rows = db.query(AuditLog).filter(AuditLog.organization_id == user.organization_id).order_by(AuditLog.occurred_at.desc()).all()
    return [
        {
            "id": str(row.id),
            "action": row.action,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "details": row.details,
            "occurred_at": row.occurred_at,
        }
        for row in rows
    ]


@router.get("/access-logs")
def list_access_logs(db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR))):
    rows = db.query(AccessLog).filter(AccessLog.organization_id == user.organization_id).order_by(AccessLog.occurred_at.desc()).all()
    return [
        {
            "id": str(row.id),
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "action": row.action,
            "occurred_at": row.occurred_at,
        }
        for row in rows
    ]


@router.get("/reports/audit")
def get_audit_report(db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR))):
    report = export_audit_csv(db, user.organization_id, user.id)
    return {"report_id": str(report.id), "path": report.path}


@router.get("/reports/campaign/{campaign_id}")
def get_campaign_report(campaign_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR))):
    report = export_campaign_html(db, user.organization_id, user.id, campaign_id)
    return {"report_id": str(report.id), "path": report.path}


@router.post("/reports/export")
def export_report(payload: dict, db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR))):
    report_type = payload.get("report_type")
    if report_type == "audit":
        report = export_audit_csv(db, user.organization_id, user.id)
        return {"report_id": str(report.id), "path": report.path}
    if report_type == "campaign":
        campaign_id = payload.get("campaign_id")
        if not campaign_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="campaign_id is required")
        report = export_campaign_html(db, user.organization_id, user.id, campaign_id)
        return {"report_id": str(report.id), "path": report.path}
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported report type")
