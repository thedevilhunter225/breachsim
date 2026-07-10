from __future__ import annotations


def test_employee_report_returns_risk_history_and_behavior(client, admin_headers):
    employee = client.get("/api/v1/employees", headers=admin_headers).json()[0]
    scenario_response = client.post(
        "/api/v1/scenarios/generate",
        headers=admin_headers,
        json={
            "employee_id": employee["id"],
            "channel": "email",
            "theme": "invoice/payment approval",
            "difficulty_level": "medium",
        },
    )
    assert scenario_response.status_code == 201, scenario_response.text
    scenario_id = scenario_response.json()["id"]

    scenario_approve_response = client.post(f"/api/v1/scenarios/{scenario_id}/approve", headers=admin_headers)
    assert scenario_approve_response.status_code == 200, scenario_approve_response.text

    campaign_response = client.post(
        "/api/v1/campaigns",
        headers=admin_headers,
        json={
            "name": "Employee Report Test",
            "description": "Test campaign for employee reporting",
            "channel": "email",
            "campaign_type": "one_time",
            "throttling_per_hour": 10,
            "target_employee_ids": [employee["id"]],
            "scenario_ids": [scenario_id],
            "requires_second_approval": False,
            "sandbox_mode": True,
            "learning_objective": "Recognize urgent phishing language.",
            "target_filters": {"source": "test_employee_report"},
        },
    )
    assert campaign_response.status_code == 201, campaign_response.text
    campaign_id = campaign_response.json()["id"]

    request_response = client.post(f"/api/v1/campaigns/{campaign_id}/request-approval", headers=admin_headers)
    assert request_response.status_code == 200, request_response.text

    approve_response = client.post(f"/api/v1/campaigns/{campaign_id}/approve", headers=admin_headers)
    assert approve_response.status_code == 200, approve_response.text

    launch_response = client.post(f"/api/v1/campaigns/{campaign_id}/launch-sandbox", headers=admin_headers)
    assert launch_response.status_code == 200, launch_response.text

    attempt = launch_response.json()[0]
    preview_url = attempt["preview_payload"]["preview_url"]
    token = preview_url.rsplit("/", 1)[-1]
    event_response = client.post(
        f"/api/v1/public/training/{token}/events",
        json={"event_type": "clicked_link", "metadata": {"source": "employee-report-test"}},
    )
    assert event_response.status_code == 200, event_response.text

    report_response = client.get(f"/api/v1/employees/{attempt['employee_id']}/report", headers=admin_headers)
    assert report_response.status_code == 200, report_response.text

    payload = report_response.json()
    assert payload["employee"]["id"] == attempt["employee_id"]
    assert isinstance(payload["current_risk_score"], int)
    assert payload["risk_history"]
    assert payload["behavior_summary"]["clicked_links"] >= 1
    assert payload["events"]
