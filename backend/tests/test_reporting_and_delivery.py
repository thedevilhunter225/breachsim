"""Coverage for the evidence exports, rate metrics and channel delivery semantics."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.models.entities import Campaign
from app.services.delivery import sms_segments
from tests.conftest import login

# --------------------------------------------------------------------------------------
# SMS encoding / segmentation
# --------------------------------------------------------------------------------------

def test_plain_ascii_message_is_a_single_gsm7_segment():
    segments, encoding, units = sms_segments("Please review the pending approval item.")
    assert (segments, encoding) == (1, "GSM-7")
    assert units == len("Please review the pending approval item.")


def test_gsm7_extension_characters_cost_two_units():
    # '[' lives in the GSM-7 extension table and is billed as two septets.
    _, encoding, units = sms_segments("[")
    assert encoding == "GSM-7"
    assert units == 2


def test_non_gsm_character_forces_ucs2_and_halves_capacity():
    # An em dash is outside GSM-7, so the whole message becomes UCS-2.
    ascii_only = "a" * 100
    with_em_dash = "a" * 99 + "—"

    assert sms_segments(ascii_only) == (1, "GSM-7", 100)
    segments, encoding, _ = sms_segments(with_em_dash)
    assert encoding == "UCS-2"
    assert segments == 2, "100 UCS-2 characters no longer fit in one 70-character segment"


def test_long_gsm7_message_splits_on_concatenated_boundary():
    segments, encoding, _ = sms_segments("a" * 161)
    assert (segments, encoding) == (2, "GSM-7")


# --------------------------------------------------------------------------------------
# Delivery semantics
# --------------------------------------------------------------------------------------

def _approved_email_campaign(client: TestClient, admin_headers, manager_headers) -> tuple[str, str]:
    employee = client.get("/api/v1/employees", headers=manager_headers).json()[0]
    scenario = client.post(
        "/api/v1/scenarios/generate",
        json={
            "employee_id": employee["id"],
            "channel": "email",
            "theme": "document review",
            "difficulty_level": "low",
        },
        headers=manager_headers,
    ).json()
    client.post(f"/api/v1/scenarios/{scenario['id']}/approve", headers=admin_headers)

    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "name": "Reporting fixture campaign",
            "channel": "email",
            "target_employee_ids": [employee["id"]],
            "scenario_ids": [scenario["id"]],
            "requires_second_approval": False,
        },
        headers=manager_headers,
    ).json()
    client.post(f"/api/v1/campaigns/{campaign['id']}/request-approval", headers=manager_headers)
    client.post(f"/api/v1/campaigns/{campaign['id']}/approve", headers=admin_headers)
    return campaign["id"], employee["id"]


def test_delivery_without_a_provider_is_sandboxed_not_failed(client: TestClient, admin_headers, manager_headers):
    """An organization that never enabled SMTP has not failed to send — it opted out."""
    # The test database is shared across the session, so state the precondition explicitly
    # rather than relying on the seeded default.
    disabled = client.put(
        "/api/v1/integrations/email",
        json={"email_provider_enabled": False, "email_provider_mode": "sandbox"},
        headers=admin_headers,
    )
    assert disabled.status_code == 200, disabled.text

    campaign_id, _ = _approved_email_campaign(client, admin_headers, manager_headers)

    response = client.post(f"/api/v1/campaigns/{campaign_id}/deliver", headers=manager_headers)
    assert response.status_code == 200, response.text
    attempt = response.json()[0]

    assert attempt["status"] == "sandboxed"
    assert attempt["sandbox_mode"] is True
    assert "sandbox_reason" in attempt["preview_payload"]
    assert "error" not in attempt["preview_payload"]


def test_every_channel_reports_its_own_entry_route(client: TestClient, admin_headers, manager_headers):
    from app.models.enums import Channel
    from app.services.delivery import ENTRY_ROUTE_BY_CHANNEL

    # Every channel in the enum must have a landing route, or its tokens are unreachable.
    for channel in Channel:
        assert channel in ENTRY_ROUTE_BY_CHANNEL, f"{channel.value} has no entry route"


# --------------------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------------------

def test_campaign_report_rates_stay_within_bounds(client: TestClient, admin_headers, manager_headers):
    """Interactive channels emit several events per person; rates must stay per-target."""
    from app.db.session import SessionLocal
    from app.services.reports import gather_campaign_evidence

    campaign_id, _ = _approved_email_campaign(client, admin_headers, manager_headers)
    client.post(f"/api/v1/campaigns/{campaign_id}/deliver", headers=manager_headers)

    attempts = client.get("/api/v1/delivery-attempts", headers=manager_headers).json()
    attempt = next(row for row in attempts if row["campaign_id"] == campaign_id)
    token = attempt["preview_payload"]["preview_url"].rstrip("/").split("/")[-1]

    # Multiple protective events from one target used to push resilience above 100%.
    for event_type in ["clicked_report", "marked_spam", "clicked_report"]:
        client.post(f"/api/v1/public/training/{token}/events", json={"event_type": event_type})

    session = SessionLocal()
    try:
        campaign = session.query(Campaign).filter(Campaign.id == uuid.UUID(campaign_id)).one()
        evidence = gather_campaign_evidence(session, campaign.organization_id, campaign.id)
    finally:
        session.close()

    metrics = evidence["metrics"]
    assert 0 <= metrics["failure_rate"] <= 100
    assert 0 <= metrics["resilience_rate"] <= 100
    assert metrics["protective_actions"] >= 3, "the extra events should still be counted"


def test_campaign_report_downloads_as_html_and_csv(client: TestClient, admin_headers, manager_headers):
    campaign_id, _ = _approved_email_campaign(client, admin_headers, manager_headers)
    client.post(f"/api/v1/campaigns/{campaign_id}/deliver", headers=manager_headers)

    html_response = client.get(
        f"/api/v1/reports/campaign/{campaign_id}/download?format=html", headers=admin_headers
    )
    assert html_response.status_code == 200, html_response.text
    assert html_response.headers["content-type"].startswith("text/html")
    assert "attachment" in html_response.headers["content-disposition"]
    body = html_response.text
    assert "Authorization chain" in body
    assert "Per-employee outcome" in body

    csv_response = client.get(
        f"/api/v1/reports/campaign/{campaign_id}/download?format=csv", headers=admin_headers
    )
    assert csv_response.status_code == 200
    assert csv_response.text.splitlines()[0].startswith("employee_name,employee_email")


def test_audit_log_downloads_as_csv(client: TestClient, admin_headers):
    response = client.get("/api/v1/reports/audit/download", headers=admin_headers)
    assert response.status_code == 200
    header = response.text.splitlines()[0]
    assert header == "occurred_at,actor,action,resource_type,resource_id,details"


def test_auditor_can_export_but_not_launch(client: TestClient, admin_headers, manager_headers):
    auditor = login(client, "auditor@breachsim-lab.com", "Auditor123!")
    campaign_id, _ = _approved_email_campaign(client, admin_headers, manager_headers)

    assert client.get("/api/v1/reports/audit/download", headers=auditor).status_code == 200
    assert client.post(f"/api/v1/campaigns/{campaign_id}/deliver", headers=auditor).status_code == 403


def test_dashboard_channel_rates_never_exceed_one_hundred(client: TestClient, admin_headers):
    dashboard = client.get("/api/v1/analytics/dashboard", headers=admin_headers).json()
    channels = {row["channel"] for row in dashboard["channel_performance"]}
    assert {"email", "sms", "qr", "vishing", "deepfake"} <= channels

    for row in dashboard["channel_performance"]:
        assert 0 <= row["failure_rate"] <= 100, row
        assert 0 <= row["resilience_rate"] <= 100, row
