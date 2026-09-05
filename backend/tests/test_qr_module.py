from __future__ import annotations

import re


def test_html_qr_uses_a_square_fixed_cell_grid():
    from app.services.delivery import _qr_html_table

    table = _qr_html_table("https://training.example/qr/example-token")
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table)
    cells_per_row = [row.count("<td ") for row in rows]

    assert rows
    assert len(rows) == cells_per_row[0]
    assert len(set(cells_per_row)) == 1
    assert 'table-layout:fixed' in table
    assert len(table.encode("utf-8")) < 90_000


def _approved_qr_campaign(client, admin_headers, *, name: str, sandbox_mode: bool = True):
    employee = client.get("/api/v1/employees", headers=admin_headers).json()[0]
    scenario_response = client.post(
        "/api/v1/scenarios/generate",
        headers=admin_headers,
        json={
            "employee_id": employee["id"],
            "channel": "qr",
            "theme": "qr verification",
            "difficulty_level": "medium",
        },
    )
    assert scenario_response.status_code == 201, scenario_response.text
    scenario_id = scenario_response.json()["id"]
    assert client.post(f"/api/v1/scenarios/{scenario_id}/approve", headers=admin_headers).status_code == 200

    campaign_response = client.post(
        "/api/v1/campaigns",
        headers=admin_headers,
        json={
            "name": name,
            "description": "QR phishing simulation email test",
            "channel": "qr",
            "campaign_type": "one_time",
            "throttling_per_hour": 10,
            "target_employee_ids": [employee["id"]],
            "scenario_ids": [scenario_id],
            "requires_second_approval": False,
            "sandbox_mode": sandbox_mode,
            "learning_objective": "Verify QR codes before scanning.",
            "target_filters": {"source": "test_qr_module"},
        },
    )
    assert campaign_response.status_code == 201, campaign_response.text
    campaign_id = campaign_response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/request-approval", headers=admin_headers).status_code == 200
    assert client.post(f"/api/v1/campaigns/{campaign_id}/approve", headers=admin_headers).status_code == 200
    return employee, campaign_id


def test_qr_campaign_generates_scannable_preview_and_tracks_scan(client, admin_headers):
    _employee, campaign_id = _approved_qr_campaign(client, admin_headers, name="QR Module Test")

    launch_response = client.post(f"/api/v1/campaigns/{campaign_id}/launch-sandbox", headers=admin_headers)
    assert launch_response.status_code == 200, launch_response.text

    attempt = launch_response.json()[0]
    payload = attempt["preview_payload"]
    assert payload["qr_image_data_url"].startswith("data:image/png;base64,")
    assert "/qr/" in payload["scan_url"]
    assert "/training/" in payload["preview_url"]

    token = payload["preview_url"].rsplit("/", 1)[-1]
    event_response = client.post(
        f"/api/v1/public/training/{token}/events",
        json={"event_type": "scanned_qr", "metadata": {"source": "test_qr_module"}},
    )
    assert event_response.status_code == 200, event_response.text
    assert event_response.json()["assignment_id"] is not None
    assert event_response.json()["risk_score"] >= 0


def test_live_qr_campaign_sends_html_embedded_qr_without_attachment(client, admin_headers, monkeypatch):
    from app.services import delivery

    employee, campaign_id = _approved_qr_campaign(
        client,
        admin_headers,
        name="QR Inline Email Test",
        sandbox_mode=False,
    )
    sent: dict = {}

    monkeypatch.setattr(delivery, "_outbound_available", lambda channel, organization: True)
    monkeypatch.setattr(delivery, "send_lab_email", lambda **kwargs: sent.update(kwargs))

    response = client.post(f"/api/v1/campaigns/{campaign_id}/deliver", headers=admin_headers)
    assert response.status_code == 200, response.text
    attempt = response.json()[0]
    payload = attempt["preview_payload"]

    assert attempt["status"] == "delivered"
    assert attempt["sandbox_mode"] is False
    assert payload["delivery_format"] == "inline_email"
    assert payload["recipient"] == employee["email"]
    assert 'role="img" aria-label="QR code"' in sent["html_body"]
    assert 'bgcolor="#000000"' in sent["html_body"]
    assert 'bgcolor="#ffffff"' in sent["html_body"]
    assert "cid:" not in sent["html_body"]
    assert "<img" not in sent["html_body"]
    assert "/qr/" in sent["cta_url"]
    assert "inline_images" not in sent
    assert "attachments" not in sent
