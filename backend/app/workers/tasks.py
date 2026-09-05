from __future__ import annotations

from app.db.session import SessionLocal
from app.services.delivery import launch_campaign_sandbox
from app.services.reports import export_audit_csv, export_campaign_html


def launch_campaign_job(campaign_id: str, actor_id: str) -> int:
    db = SessionLocal()
    try:
      from app.models.entities import User

      actor = db.query(User).filter(User.id == actor_id).first()
      attempts = launch_campaign_sandbox(db, campaign_id=campaign_id, actor=actor)
      return len(attempts)
    finally:
      db.close()


def export_report_job(report_type: str, organization_id: str, user_id: str, campaign_id: str | None = None) -> str:
    db = SessionLocal()
    try:
      if report_type == "audit":
          report = export_audit_csv(db, organization_id, user_id)
      else:
          report = export_campaign_html(db, organization_id, user_id, campaign_id)
      return report.path
    finally:
      db.close()


def process_delivery_batch_job(attempt_ids: list[str]) -> int:
    from app.services.campaign_runs import process_delivery_batch

    return process_delivery_batch(attempt_ids)


def dispatch_outbox_job(limit: int = 100) -> int:
    from app.services.campaign_runs import dispatch_outbox

    return dispatch_outbox(limit=limit)
