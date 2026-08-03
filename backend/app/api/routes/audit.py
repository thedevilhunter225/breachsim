from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.entities import AccessLog, AuditLog, Campaign, ReportExport
from app.models.enums import UserRole
from app.services.reports import (
    build_audit_csv,
    build_campaign_csv,
    build_campaign_html,
    export_audit_csv,
    export_campaign_csv,
    export_campaign_html,
)

router = APIRouter()


def _attachment(content: str, *, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
        export_format = str(payload.get("format") or "html").lower()
        exporter = export_campaign_csv if export_format == "csv" else export_campaign_html
        report = exporter(db, user.organization_id, user.id, campaign_id)
        return {"report_id": str(report.id), "path": report.path, "format": report.format}
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported report type")


@router.get("/reports/campaigns")
def list_reportable_campaigns(
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR, UserRole.CAMPAIGN_MANAGER)),
):
    """Campaigns that have run, so the console can offer an evidence pack for each."""
    campaigns = (
        db.query(Campaign)
        .filter(Campaign.organization_id == user.organization_id)
        .order_by(Campaign.created_at.desc())
        .all()
    )
    return [
        {
            "id": str(campaign.id),
            "name": campaign.name,
            "channel": campaign.channel.value,
            "status": campaign.status.value,
            "target_count": len(campaign.targets),
            "created_at": campaign.created_at,
        }
        for campaign in campaigns
    ]


@router.get("/reports/audit/download")
def download_audit_csv(
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR)),
):
    return _attachment(
        build_audit_csv(db, user.organization_id),
        media_type="text/csv; charset=utf-8",
        filename="breachsim-audit-log.csv",
    )


@router.get("/reports/campaign/{campaign_id}/download")
def download_campaign_report(
    campaign_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    format: str = "html",
    user=Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR, UserRole.CAMPAIGN_MANAGER)),
):
    """Stream the campaign evidence pack straight to the browser."""
    if format.lower() == "csv":
        return _attachment(
            build_campaign_csv(db, user.organization_id, campaign_id),
            media_type="text/csv; charset=utf-8",
            filename=f"breachsim-campaign-{campaign_id}.csv",
        )
    return _attachment(
        build_campaign_html(db, user.organization_id, campaign_id),
        media_type="text/html; charset=utf-8",
        filename=f"breachsim-campaign-{campaign_id}.html",
    )
