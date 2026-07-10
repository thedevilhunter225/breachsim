from __future__ import annotations

import csv
import html
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import AuditLog, Campaign, EventLog, ReportExport


def export_dir() -> Path:
    return Path(__file__).resolve().parents[3] / settings.report_export_dir


def export_audit_csv(db: Session, organization_id, user_id) -> ReportExport:
    export_dir().mkdir(parents=True, exist_ok=True)
    path = export_dir() / "audit-report.csv"
    rows = db.query(AuditLog).filter(AuditLog.organization_id == organization_id).order_by(AuditLog.occurred_at.desc()).all()
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["occurred_at", "action", "resource_type", "resource_id", "details"])
        for row in rows:
            writer.writerow([row.occurred_at.isoformat(), row.action, row.resource_type, row.resource_id, row.details])

    report = ReportExport(
        organization_id=organization_id,
        generated_by_user_id=user_id,
        report_type="audit",
        format="csv",
        path=str(path),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def export_campaign_html(db: Session, organization_id, user_id, campaign_id) -> ReportExport:
    export_dir().mkdir(parents=True, exist_ok=True)
    path = export_dir() / f"campaign-report-{campaign_id}.html"
    campaign = db.query(Campaign).filter(Campaign.organization_id == organization_id, Campaign.id == campaign_id).first()
    events = db.query(EventLog).filter(EventLog.campaign_id == campaign_id).all()
    html_body = f"""
    <html>
      <head><title>BreachSim Campaign Report</title></head>
      <body>
        <h1>{html.escape(campaign.name)}</h1>
        <p>Status: {html.escape(campaign.status.value)}</p>
        <p>Channel: {html.escape(campaign.channel.value)}</p>
        <h2>Events</h2>
        <table border="1" cellpadding="6" cellspacing="0">
          <tr><th>Type</th><th>Channel</th><th>Occurred At</th><th>Metadata</th></tr>
          {''.join(
              f"<tr><td>{html.escape(event.event_type.value)}</td><td>{html.escape(event.channel.value if event.channel else '-')}</td><td>{html.escape(event.occurred_at.isoformat())}</td><td>{html.escape(str(event.event_metadata))}</td></tr>"
              for event in events
          )}
        </table>
      </body>
    </html>
    """
    path.write_text(html_body.strip(), encoding="utf-8")

    report = ReportExport(
        organization_id=organization_id,
        generated_by_user_id=user_id,
        report_type="campaign",
        format="html",
        path=str(path),
        filters={"campaign_id": str(campaign_id)},
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
