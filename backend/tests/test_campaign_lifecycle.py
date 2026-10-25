from __future__ import annotations

import uuid


def _approved_scenario(client, manager_headers, admin_headers) -> tuple[str, str]:
    employee = client.get("/api/v1/employees", headers=manager_headers).json()[0]
    scenario = client.post(
        "/api/v1/scenarios/generate",
        json={"employee_id": employee["id"], "channel": "email", "theme": "document review", "difficulty_level": "low"},
        headers=manager_headers,
    ).json()
    assert client.post(f"/api/v1/scenarios/{scenario['id']}/approve", headers=admin_headers).status_code == 200
    return employee["id"], scenario["id"]


def _campaign(client, manager_headers, employee_id: str, scenario_id: str, *, second_approval: bool) -> dict:
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": f"Lifecycle {uuid.uuid4().hex[:6]}",
            "channel": "email",
            "target_employee_ids": [employee_id],
            "scenario_ids": [scenario_id],
            "requires_second_approval": second_approval,
        },
        headers=manager_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_active_campaign_can_be_completed_and_not_relaunched(client, admin_headers, manager_headers, auditor_headers):
    employee_id, scenario_id = _approved_scenario(client, manager_headers, admin_headers)
    campaign = _campaign(client, manager_headers, employee_id, scenario_id, second_approval=False)
    campaign_id = campaign["id"]

    early = client.post(f"/api/v1/campaigns/{campaign_id}/complete", headers=manager_headers)
    assert early.status_code == 409, "a draft cannot be completed"

    client.post(f"/api/v1/campaigns/{campaign_id}/request-approval", headers=manager_headers)
    client.post(f"/api/v1/campaigns/{campaign_id}/approve", headers=admin_headers)
    assert client.post(f"/api/v1/campaigns/{campaign_id}/launch-sandbox", headers=manager_headers).status_code == 200

    assert client.post(f"/api/v1/campaigns/{campaign_id}/complete", headers=auditor_headers).status_code == 403

    completed = client.post(f"/api/v1/campaigns/{campaign_id}/complete", headers=manager_headers)
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"

    relaunch = client.post(f"/api/v1/campaigns/{campaign_id}/launch-sandbox", headers=manager_headers)
    assert relaunch.status_code == 400


def test_first_approval_is_visible_until_a_second_admin_approves(
    client, admin_headers, manager_headers, reviewer_headers
):
    employee_id, scenario_id = _approved_scenario(client, manager_headers, admin_headers)
    campaign = _campaign(client, manager_headers, employee_id, scenario_id, second_approval=True)
    campaign_id = campaign["id"]
    client.post(f"/api/v1/campaigns/{campaign_id}/request-approval", headers=manager_headers)

    first = client.post(f"/api/v1/campaigns/{campaign_id}/approve", headers=admin_headers).json()
    assert first["status"] == "pending_approval"
    assert first["approved_by_user_id"] is not None
    assert first["second_approved_by_user_id"] is None

    second = client.post(f"/api/v1/campaigns/{campaign_id}/approve", headers=reviewer_headers).json()
    assert second["status"] == "approved"
    assert second["second_approved_by_user_id"] is not None
