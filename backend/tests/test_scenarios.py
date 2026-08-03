from __future__ import annotations

from app.services.llm import LLMProviderError


def test_generate_and_approve_scenario(client, admin_headers):
    employee_id = client.get("/api/v1/employees", headers=admin_headers).json()[0]["id"]
    generate_response = client.post(
        "/api/v1/scenarios/generate",
        headers=admin_headers,
        json={
            "employee_id": employee_id,
            "channel": "email",
            "theme": "invoice/payment approval",
            "difficulty_level": "medium",
        },
    )
    assert generate_response.status_code == 201, generate_response.text
    scenario_id = generate_response.json()["id"]

    approve_response = client.post(f"/api/v1/scenarios/{scenario_id}/approve", headers=admin_headers)
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"


def test_edit_scenario_creates_new_version(client, admin_headers):
    employee_id = client.get("/api/v1/employees", headers=admin_headers).json()[0]["id"]
    generate_response = client.post(
        "/api/v1/scenarios/generate",
        headers=admin_headers,
        json={
            "employee_id": employee_id,
            "channel": "email",
            "theme": "invoice/payment approval",
            "difficulty_level": "medium",
        },
    )
    assert generate_response.status_code == 201, generate_response.text
    scenario_id = generate_response.json()["id"]

    edit_response = client.patch(
        f"/api/v1/scenarios/{scenario_id}",
        headers=admin_headers,
        json={
            "subject": "Updated invoice review request",
            "body_copy": "Please review the updated invoice request and confirm the payment workflow.",
            "cta_text": "Review Request",
            "landing_page_copy": "Training login page for the updated invoice review scenario.",
            "notes": "Adjusted tone for finance team demo.",
        },
    )
    assert edit_response.status_code == 200, edit_response.text
    assert edit_response.json()["status"] == "pending_approval"
    assert edit_response.json()["latest_version"]["subject"] == "Updated invoice review request"
    assert edit_response.json()["latest_version"]["version_number"] == 2


def test_policy_blocks_disallowed_theme(client, admin_headers):
    employee_id = client.get("/api/v1/employees", headers=admin_headers).json()[0]["id"]
    response = client.post(
        "/api/v1/scenarios/generate",
        headers=admin_headers,
        json={
            "employee_id": employee_id,
            "channel": "email",
            "theme": "celebrity giveaway",
            "difficulty_level": "medium",
        },
    )
    assert response.status_code == 400


def test_generation_falls_back_when_provider_output_is_invalid(client, admin_headers, monkeypatch):
    class InvalidProvider:
        def generate(self, _prompt):
            raise LLMProviderError("invalid provider response")

    monkeypatch.setattr(
        "app.services.scenario_service.get_default_llm_provider",
        lambda: InvalidProvider(),
    )
    employee_id = client.get("/api/v1/employees", headers=admin_headers).json()[0]["id"]

    response = client.post(
        "/api/v1/scenarios/generate",
        headers=admin_headers,
        json={
            "employee_id": employee_id,
            "channel": "email",
            "theme": "invoice/payment approval",
            "difficulty_level": "medium",
        },
    )

    assert response.status_code == 201, response.text
    metadata = response.json()["latest_version"]["rationale_metadata"]
    assert metadata["provider"] == "rule-based"
    assert metadata["provider_status"] == "fallback"
    assert metadata["fallback_from"] == "InvalidProvider"
