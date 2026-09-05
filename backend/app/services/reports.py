"""Evidence exports.

A campaign report has to stand up as evidence: an assessor should be able to read one
document and follow the whole chain — who approved the simulation, what was sent, who
interacted, where in the pressure sequence they complied or verified, what remediation
was assigned, and how the risk score moved as a result.

Exports are written to disk *and* returned inline so the console can stream a download
without a second round trip to the filesystem.
"""

from __future__ import annotations

import csv
import html
import io
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.crypto import pseudonymous_id
from app.models.entities import (
    AuditLog,
    Campaign,
    DeliveryAttempt,
    Employee,
    EventLog,
    ImpersonationPersona,
    Organization,
    ReportExport,
    Scenario,
    SimulationResponse,
    TrainingAssignment,
    User,
)
from app.models.enums import PROTECTIVE_EVENT_TYPES, RISKY_EVENT_TYPES, EventType, UserRole
from app.services.evidence_store import persist_evidence

CHANNEL_LABELS = {
    "email": "Email phishing",
    "sms": "SMS / smishing",
    "qr": "QR phishing",
    "vishing": "Voice / vishing",
    "deepfake": "Synthetic media impersonation",
}


def _fmt(value: datetime | None) -> str:
    if not value:
        return "-"
    moment = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return moment.strftime("%Y-%m-%d %H:%M UTC")


def _record(db: Session, *, organization_id, user_id, report_type: str, fmt: str, path: str, filters: dict) -> ReportExport:
    report = ReportExport(
        organization_id=organization_id,
        generated_by_user_id=user_id,
        report_type=report_type,
        format=fmt,
        path=path,
        filters=filters,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


# --------------------------------------------------------------------------------------
# Audit CSV
# --------------------------------------------------------------------------------------

def build_audit_csv(db: Session, organization_id) -> str:
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == organization_id)
        .order_by(AuditLog.occurred_at.desc())
        .all()
    )
    actor_names = {
        str(user.id): user.full_name
        for user in db.query(User).filter(User.organization_id == organization_id).all()
    }

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["occurred_at", "actor", "action", "resource_type", "resource_id", "details"])
    for row in rows:
        writer.writerow(
            [
                _fmt(row.occurred_at),
                actor_names.get(str(row.user_id), "system"),
                row.action,
                row.resource_type,
                row.resource_id or "",
                row.details,
            ]
        )
    return buffer.getvalue()


def export_audit_csv(db: Session, organization_id, user_id) -> ReportExport:
    path = persist_evidence(
        build_audit_csv(db, organization_id).encode("utf-8"),
        organization_id=organization_id,
        report_type="audit",
        extension="csv",
        content_type="text/csv; charset=utf-8",
    )
    return _record(
        db,
        organization_id=organization_id,
        user_id=user_id,
        report_type="audit",
        fmt="csv",
        path=path,
        filters={},
    )


# --------------------------------------------------------------------------------------
# Campaign evidence pack
# --------------------------------------------------------------------------------------

def gather_campaign_evidence(db: Session, organization_id, campaign_id) -> dict[str, Any]:
    """Assemble everything the campaign report needs, in one place."""

    campaign = (
        db.query(Campaign)
        .filter(Campaign.organization_id == organization_id, Campaign.id == campaign_id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    attempts = db.query(DeliveryAttempt).filter(DeliveryAttempt.campaign_id == campaign_id).all()
    events = (
        db.query(EventLog)
        .filter(EventLog.campaign_id == campaign_id)
        .order_by(EventLog.occurred_at.asc())
        .all()
    )
    responses = (
        db.query(SimulationResponse)
        .filter(SimulationResponse.campaign_id == campaign_id)
        .order_by(SimulationResponse.occurred_at.asc())
        .all()
    )
    assignments = db.query(TrainingAssignment).filter(TrainingAssignment.campaign_id == campaign_id).all()

    employee_ids = {attempt.employee_id for attempt in attempts} | {
        event.employee_id for event in events if event.employee_id
    }
    employees = {
        employee.id: employee
        for employee in db.query(Employee).filter(Employee.id.in_(employee_ids)).all()
    } if employee_ids else {}

    scenario = None
    persona = None
    if campaign.scenario_links:
        scenario = db.query(Scenario).filter(Scenario.id == campaign.scenario_links[0].scenario_id).first()
        if scenario and scenario.persona_id:
            persona = (
                db.query(ImpersonationPersona)
                .filter(ImpersonationPersona.id == scenario.persona_id)
                .first()
            )

    users = {
        str(user.id): user.full_name
        for user in db.query(User).filter(User.organization_id == organization_id).all()
    }

    delivered = sum(1 for event in events if event.event_type == EventType.DELIVERED)
    risky = [event for event in events if event.event_type in RISKY_EVENT_TYPES]
    protective = [
        event
        for event in events
        if event.event_type in PROTECTIVE_EVENT_TYPES and event.event_type != EventType.TRAINING_COMPLETED
    ]

    # Per-employee outcome, which is what an assessor actually reads.
    per_employee: dict[Any, dict[str, Any]] = defaultdict(
        lambda: {"risky": 0, "protective": 0, "steps": [], "training": 0}
    )
    for event in events:
        if not event.employee_id:
            continue
        if event.event_type in RISKY_EVENT_TYPES:
            per_employee[event.employee_id]["risky"] += 1
        elif event.event_type in PROTECTIVE_EVENT_TYPES and event.event_type != EventType.TRAINING_COMPLETED:
            per_employee[event.employee_id]["protective"] += 1
    for response in responses:
        per_employee[response.employee_id]["steps"].append(response)
    for assignment in assignments:
        per_employee[assignment.employee_id]["training"] += 1

    rows = []
    for employee_id, stats in per_employee.items():
        employee = employees.get(employee_id)
        if not employee:
            continue
        if stats["risky"] and stats["protective"]:
            outcome = "Recovered"
        elif stats["risky"]:
            outcome = "Compromised"
        elif stats["protective"]:
            outcome = "Resilient"
        else:
            outcome = "No interaction"
        first_unsafe = next((step for step in stats["steps"] if not step.is_safe_action and step.risk_weight > 0), None)
        rows.append(
            {
                "employee": employee,
                "outcome": outcome,
                "risky": stats["risky"],
                "protective": stats["protective"],
                "training": stats["training"],
                "steps": sorted(stats["steps"], key=lambda step: step.step_index),
                "breaking_point": first_unsafe.step_key if first_unsafe else None,
            }
        )
    rows.sort(key=lambda row: (row["outcome"] != "Compromised", row["employee"].full_name))

    # Rates are per *target*, not per event. An interactive simulation produces several
    # decisions per person, so dividing events by deliveries would exceed 100%.
    reached = len(rows) or metrics_targets(campaign)
    compromised_targets = sum(1 for row in rows if row["outcome"] == "Compromised")
    recovered_targets = sum(1 for row in rows if row["outcome"] == "Recovered")
    resilient_targets = sum(1 for row in rows if row["outcome"] == "Resilient")

    return {
        "campaign": campaign,
        "organization": organization,
        "scenario": scenario,
        "persona": persona,
        "attempts": attempts,
        "events": events,
        "responses": responses,
        "assignments": assignments,
        "employees": employees,
        "users": users,
        "rows": rows,
        "metrics": {
            "targets": len(campaign.targets),
            "delivered": delivered,
            "engaged_targets": reached,
            "risky_actions": len(risky),
            "protective_actions": len(protective),
            "training_assigned": len(assignments),
            "compromised_targets": compromised_targets,
            "recovered_targets": recovered_targets,
            "resilient_targets": resilient_targets,
            # Share of engaged targets who complied at least once.
            "failure_rate": round(compromised_targets / reached * 100, 1) if reached else 0.0,
            # Share who resisted without ever complying.
            "resilience_rate": round(resilient_targets / reached * 100, 1) if reached else 0.0,
            "event_breakdown": Counter(event.event_type.value for event in events),
        },
    }


def metrics_targets(campaign: Campaign) -> int:
    return len(campaign.targets)


def _can_view_named_identities(db: Session, organization_id, user_id) -> bool:
    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    if not organization or organization.reporting_identity_mode.value != "named":
        return False
    user = db.query(User).filter(User.id == user_id, User.organization_id == organization_id).first()
    return bool(user and any(link.role.name == UserRole.RISK_IDENTITY_VIEWER for link in user.roles))


def _report_identity(organization_id, employee: Employee, include_identities: bool) -> tuple[str, str]:
    if include_identities:
        return employee.full_name, employee.email
    label = pseudonymous_id(str(organization_id), str(employee.id))[:10].upper()
    return f"Employee {label}", ""


def build_campaign_html(db: Session, organization_id, campaign_id, *, include_identities: bool = False) -> str:
    data = gather_campaign_evidence(db, organization_id, campaign_id)
    campaign = data["campaign"]
    scenario = data["scenario"]
    persona = data["persona"]
    metrics = data["metrics"]
    users = data["users"]

    def esc(value: Any) -> str:
        return html.escape(str(value if value is not None else "-"))

    approvals = [
        ("Created by", users.get(str(campaign.created_by_user_id), "-")),
        ("First approval", users.get(str(campaign.approved_by_user_id), "Not recorded")),
        (
            "Second approval",
            users.get(str(campaign.second_approved_by_user_id), "Not required")
            if not campaign.requires_second_approval or campaign.second_approved_by_user_id
            else "Outstanding",
        ),
    ]

    persona_block = ""
    if persona:
        persona_block = f"""
        <section>
          <h2>Impersonation authorization</h2>
          <table class="kv">
            <tr><th>Persona</th><td>{esc(persona.display_name)} ({esc(persona.reference_code)})</td></tr>
            <tr><th>Role presented</th><td>{esc(persona.role_title)}</td></tr>
            <tr><th>Represents a real person</th><td>{"Yes" if persona.is_real_person else "No — synthetic composite role"}</td></tr>
            <tr><th>Consent reference</th><td>{esc(persona.consent_reference or "Not applicable")}</td></tr>
            <tr><th>Consent window</th><td>{_fmt(persona.consent_granted_at)} to {_fmt(persona.consent_expires_at)}</td></tr>
            <tr><th>Approved by</th><td>{esc(users.get(str(persona.approved_by_user_id), "-"))}</td></tr>
          </table>
        </section>
        """

    employee_rows = "".join(
        f"""
        <tr class="outcome-{row['outcome'].lower().replace(' ', '-')}">
          <td><strong>{esc(_report_identity(organization_id, row['employee'], include_identities)[0])}</strong><br><span class="muted">{esc(_report_identity(organization_id, row['employee'], include_identities)[1])}</span></td>
          <td><span class="pill pill-{row['outcome'].lower().replace(' ', '-')}">{esc(row['outcome'])}</span></td>
          <td class="num">{row['risky']}</td>
          <td class="num">{row['protective']}</td>
          <td class="num">{row['training']}</td>
          <td class="num">{row['employee'].risk_score}</td>
          <td>{esc(row['breaking_point'] or "-")}</td>
        </tr>
        """
        for row in data["rows"]
    ) or '<tr><td colspan="7" class="muted">No interactions recorded.</td></tr>'

    decision_rows = "".join(
        f"""
        <tr>
          <td>{esc(_report_identity(organization_id, data['employees'][step.employee_id], include_identities)[0] if data['employees'].get(step.employee_id) else '-')}</td>
          <td class="num">{step.step_index + 1}</td>
          <td>{esc(step.step_key)}</td>
          <td>{esc(step.response_label)}</td>
          <td>{"Safe" if step.is_safe_action else "Unsafe"}</td>
          <td class="num">{step.risk_weight:+d}</td>
          <td class="num">{step.elapsed_ms / 1000:.1f}s</td>
        </tr>
        """
        for step in data["responses"]
    )
    decision_section = (
        f"""
        <section>
          <h2>Interaction decision trail</h2>
          <p class="muted">Each decision the target made inside the {esc(CHANNEL_LABELS.get(campaign.channel.value, campaign.channel.value))} simulation, in order.</p>
          <table>
            <thead><tr><th>Employee</th><th>Step</th><th>Prompt</th><th>Response</th><th>Outcome</th><th>Weight</th><th>Time</th></tr></thead>
            <tbody>{decision_rows}</tbody>
          </table>
        </section>
        """
        if data["responses"]
        else ""
    )

    breakdown_rows = "".join(
        f"<tr><td>{esc(event_type.replace('_', ' ').title())}</td><td class='num'>{count}</td></tr>"
        for event_type, count in metrics["event_breakdown"].most_common()
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>BreachSim campaign report — {esc(campaign.name)}</title>
<style>
  :root {{ --navy:#0a1730; --brand:#2b8bff; --line:#dde5ef; --muted:#5c6c85; --breach:#e5484d; --signal:#12a594; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:40px 24px; background:#eef2f8; color:#0c1528;
         font:15px/1.6 -apple-system,Segoe UI,Roboto,sans-serif; }}
  .sheet {{ max-width:1000px; margin:0 auto; background:#fff; border:1px solid var(--line);
            border-radius:14px; overflow:hidden; box-shadow:0 18px 44px rgba(10,23,48,.09); }}
  header {{ background:linear-gradient(135deg,var(--navy),#12305e 60%,var(--brand)); color:#fff; padding:32px; }}
  header .eyebrow {{ font-size:11px; letter-spacing:.18em; text-transform:uppercase; opacity:.7; }}
  header h1 {{ margin:8px 0 4px; font-size:27px; letter-spacing:-.02em; }}
  header p {{ margin:0; opacity:.78; font-size:14px; }}
  section {{ padding:26px 32px; border-top:1px solid var(--line); }}
  h2 {{ margin:0 0 14px; font-size:16px; letter-spacing:.01em; }}
  .kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; }}
  .kpi {{ background:#f5f8fc; border:1px solid var(--line); border-radius:10px; padding:14px; }}
  .kpi .label {{ font-size:10.5px; letter-spacing:.11em; text-transform:uppercase; color:var(--muted); font-weight:700; }}
  .kpi .value {{ font-size:24px; font-weight:700; margin-top:4px; letter-spacing:-.02em; }}
  table {{ width:100%; border-collapse:collapse; font-size:13.5px; }}
  th,td {{ text-align:left; padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
  thead th {{ background:#f5f8fc; font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); }}
  table.kv th {{ width:220px; color:var(--muted); font-weight:600; background:transparent; text-transform:none;
                 font-size:13.5px; letter-spacing:0; }}
  .num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
  .muted {{ color:var(--muted); }}
  .pill {{ display:inline-block; padding:2px 9px; border-radius:999px; font-size:11.5px; font-weight:700; }}
  .pill-compromised {{ background:rgba(229,72,77,.12); color:var(--breach); }}
  .pill-recovered {{ background:rgba(43,139,255,.12); color:#1e6fe0; }}
  .pill-resilient {{ background:rgba(18,165,148,.13); color:var(--signal); }}
  .pill-no-interaction {{ background:#eef2f8; color:var(--muted); }}
  .note {{ background:#f5f8fc; border-left:3px solid var(--brand); padding:12px 14px; border-radius:0 8px 8px 0;
           font-size:13px; color:var(--muted); }}
  footer {{ padding:20px 32px; background:#f5f8fc; color:var(--muted); font-size:12px; }}
  @media print {{ body {{ background:#fff; padding:0; }} .sheet {{ box-shadow:none; border:0; }} }}
</style>
</head>
<body>
<div class="sheet">
  <header>
    <div class="eyebrow">BreachSim · Campaign evidence report</div>
    <h1>{esc(campaign.name)}</h1>
    <p>{esc(CHANNEL_LABELS.get(campaign.channel.value, campaign.channel.value))} · {esc(data['organization'].name if data['organization'] else '')} · generated {_fmt(datetime.now(timezone.utc))}</p>
  </header>

  <section>
    <h2>Outcome at a glance</h2>
    <p class="muted" style="margin-top:-6px">Rates are share of engaged targets, not share of events — one interactive simulation produces several decisions per person.</p>
    <div class="kpis">
      <div class="kpi"><div class="label">Targets</div><div class="value">{metrics['targets']}</div></div>
      <div class="kpi"><div class="label">Delivered</div><div class="value">{metrics['delivered']}</div></div>
      <div class="kpi"><div class="label">Compromised</div><div class="value">{metrics['compromised_targets']}</div></div>
      <div class="kpi"><div class="label">Failure rate</div><div class="value">{metrics['failure_rate']}%</div></div>
      <div class="kpi"><div class="label">Resilience rate</div><div class="value">{metrics['resilience_rate']}%</div></div>
      <div class="kpi"><div class="label">Training assigned</div><div class="value">{metrics['training_assigned']}</div></div>
    </div>
  </section>

  <section>
    <h2>Authorization chain</h2>
    <table class="kv">
      {''.join(f'<tr><th>{esc(label)}</th><td>{esc(value)}</td></tr>' for label, value in approvals)}
      <tr><th>Two-person rule</th><td>{"Required" if campaign.requires_second_approval else "Waived for this campaign"}</td></tr>
      <tr><th>Learning objective</th><td>{esc(campaign.learning_objective)}</td></tr>
      <tr><th>Scenario</th><td>{esc(scenario.title if scenario else "-")}</td></tr>
      <tr><th>Theme / difficulty</th><td>{esc(scenario.theme if scenario else "-")} · {esc(scenario.difficulty_level.value if scenario else "-")}</td></tr>
    </table>
  </section>

  {persona_block}

  <section>
    <h2>Per-employee outcome</h2>
    <table>
      <thead><tr><th>Employee</th><th>Outcome</th><th class="num">Risky</th><th class="num">Protective</th><th class="num">Training</th><th class="num">Risk</th><th>Broke at</th></tr></thead>
      <tbody>{employee_rows}</tbody>
    </table>
  </section>

  {decision_section}

  <section>
    <h2>Event breakdown</h2>
    <table>
      <thead><tr><th>Event</th><th class="num">Count</th></tr></thead>
      <tbody>{breakdown_rows or '<tr><td colspan="2" class="muted">No events recorded.</td></tr>'}</tbody>
    </table>
  </section>

  <section>
    <div class="note">
      This simulation was run under the organization's approved guardrails. No real credentials were
      captured, no real calls were placed, and no synthetic media was generated, stored or published.
      Analytics are keyed to pseudonymous event identifiers.
    </div>
  </section>

  <footer>Generated by BreachSim · Human Risk Intelligence · report id {esc(campaign.id)}</footer>
</div>
</body>
</html>"""


def export_campaign_html(db: Session, organization_id, user_id, campaign_id) -> ReportExport:
    path = persist_evidence(
        build_campaign_html(
            db,
            organization_id,
            campaign_id,
            include_identities=_can_view_named_identities(db, organization_id, user_id),
        ).encode("utf-8"),
        organization_id=organization_id,
        report_type=f"campaign-{campaign_id}",
        extension="html",
        content_type="text/html; charset=utf-8",
    )
    return _record(
        db,
        organization_id=organization_id,
        user_id=user_id,
        report_type="campaign",
        fmt="html",
        path=path,
        filters={"campaign_id": str(campaign_id)},
    )


def build_campaign_csv(db: Session, organization_id, campaign_id, *, include_identities: bool = False) -> str:
    """Flat per-employee outcome table, for import into a spreadsheet."""
    data = gather_campaign_evidence(db, organization_id, campaign_id)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        [
            "employee_name",
            "employee_email",
            "department",
            "channel",
            "outcome",
            "risky_actions",
            "protective_actions",
            "training_assigned",
            "breaking_point_step",
            "current_risk_score",
        ]
    )
    channel = data["campaign"].channel.value
    for row in data["rows"]:
        employee = row["employee"]
        identity_name, identity_email = _report_identity(organization_id, employee, include_identities)
        writer.writerow(
            [
                identity_name,
                identity_email,
                employee.department.name if employee.department else "",
                channel,
                row["outcome"],
                row["risky"],
                row["protective"],
                row["training"],
                row["breaking_point"] or "",
                employee.risk_score,
            ]
        )
    return buffer.getvalue()


def export_campaign_csv(db: Session, organization_id, user_id, campaign_id) -> ReportExport:
    path = persist_evidence(
        build_campaign_csv(
            db,
            organization_id,
            campaign_id,
            include_identities=_can_view_named_identities(db, organization_id, user_id),
        ).encode("utf-8"),
        organization_id=organization_id,
        report_type=f"campaign-{campaign_id}",
        extension="csv",
        content_type="text/csv; charset=utf-8",
    )
    return _record(
        db,
        organization_id=organization_id,
        user_id=user_id,
        report_type="campaign",
        fmt="csv",
        path=path,
        filters={"campaign_id": str(campaign_id)},
    )
