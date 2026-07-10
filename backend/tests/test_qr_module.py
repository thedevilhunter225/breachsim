from __future__ import annotations


def test_qr_campaign_generates_scannable_preview_and_tracks_scan(client, admin_headers):
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

    approve_response = client.post(f"/api/v1/scenarios/{scenario_id}/approve", headers=admin_headers)
    assert approve_response.status_code == 200, approve_response.text

    campaign_response = client.post(
        "/api/v1/campaigns",
        headers=admin_headers,
        json={
            "name": "QR Module Test",
            "description": "QR phishing simulation preview test",
            "channel": "qr",
            "campaign_type": "one_time",
            "throttling_per_hour": 10,
            "target_employee_ids": [employee["id"]],
            "scenario_ids": [scenario_id],
            "requires_second_approval": False,
            "sandbox_mode": True,
            "learning_objective": "Verify QR codes before scanning.",
            "target_filters": {"source": "test_qr_module"},
        },
    )
    assert campaign_response.status_code == 201, campaign_response.text
    campaign_id = campaign_response.json()["id"]

    request_response = client.post(f"/api/v1/campaigns/{campaign_id}/request-approval", headers=admin_headers)
    assert request_response.status_code == 200, request_response.text

    approve_campaign_response = client.post(f"/api/v1/campaigns/{campaign_id}/approve", headers=admin_headers)
    assert approve_campaign_response.status_code == 200, approve_campaign_response.text

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
