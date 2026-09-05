"""End-to-end coverage for the voice and synthetic-media impersonation channels."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from tests.conftest import login


def _iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _first_employee(client: TestClient, headers: dict[str, str], index: int = 0) -> dict:
    """Pick a seeded employee. Tests that assert on risk deltas must use distinct
    indexes, because the test database is shared across the whole session and a
    clamped-to-zero score would hide a real change."""
    response = client.get("/api/v1/employees", headers=headers)
    assert response.status_code == 200, response.text
    employees = response.json()
    assert len(employees) > index, "seeded demo directory should not be empty"
    return employees[index]


def _register_persona(client: TestClient, headers: dict[str, str], **overrides) -> dict:
    payload = {
        "display_name": "Finance Director",
        "role_title": "Director of Finance",
        "relationship_to_targets": "senior leadership",
        "modality": "voice_note",
        "is_real_person": False,
        "detection_tells": ["Recognition is not verification."],
    }
    payload.update(overrides)
    response = client.post("/api/v1/personas", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _approve_persona(client: TestClient, persona_id: str) -> dict:
    # Approval must come from a different admin than the one who registered it.
    reviewer = login(client, "reviewer@breachsim-lab.com", "Reviewer123!")
    response = client.post(f"/api/v1/personas/{persona_id}/approve", headers=reviewer)
    assert response.status_code == 200, response.text
    return response.json()


def _enable_impersonation(client: TestClient, headers: dict[str, str]) -> None:
    response = client.put(
        "/api/v1/integrations/impersonation",
        json={"impersonation_enabled": True, "voice_provider_enabled": False, "voice_provider_mode": "simulator"},
        headers=headers,
    )
    assert response.status_code == 200, response.text


# --------------------------------------------------------------------------------------
# Persona governance
# --------------------------------------------------------------------------------------

def test_real_person_persona_requires_consent_reference(client: TestClient, admin_headers):
    response = client.post(
        "/api/v1/personas",
        json={
            "display_name": "Ayesha Malik",
            "role_title": "Chief Financial Officer",
            "is_real_person": True,
        },
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "consent reference" in response.text.lower()


def test_persona_cannot_be_approved_by_its_own_creator(client: TestClient, admin_headers):
    persona = _register_persona(client, admin_headers, display_name="Self Approval Test")
    response = client.post(f"/api/v1/personas/{persona['id']}/approve", headers=admin_headers)
    assert response.status_code == 400
    assert "second admin" in response.text.lower()


def test_expired_consent_blocks_scenario_generation(client: TestClient, admin_headers, manager_headers):
    _enable_impersonation(client, admin_headers)
    employee = _first_employee(client, manager_headers)

    persona = _register_persona(
        client,
        admin_headers,
        display_name="Lapsed Consent Persona",
        is_real_person=True,
        consent_reference="HR-AUTH-2026-014",
        consent_expires_at=_iso(days=2),
    )
    _approve_persona(client, persona["id"])

    # Force the consent window shut, then confirm generation is refused.
    from app.db.session import SessionLocal
    from app.models.entities import ImpersonationPersona

    session = SessionLocal()
    try:
        row = (
            session.query(ImpersonationPersona)
            .filter(ImpersonationPersona.id == uuid.UUID(persona["id"]))
            .first()
        )
        row.consent_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        session.commit()
    finally:
        session.close()

    response = client.post(
        "/api/v1/scenarios/generate",
        json={
            "employee_id": employee["id"],
            "channel": "deepfake",
            "theme": "executive approval request",
            "difficulty_level": "high",
            "persona_id": persona["id"],
        },
        headers=manager_headers,
    )
    assert response.status_code == 400
    assert "expired" in response.text.lower()


def test_deepfake_requires_a_persona(client: TestClient, admin_headers, manager_headers):
    _enable_impersonation(client, admin_headers)
    employee = _first_employee(client, manager_headers)
    response = client.post(
        "/api/v1/scenarios/generate",
        json={
            "employee_id": employee["id"],
            "channel": "deepfake",
            "theme": "executive approval request",
            "difficulty_level": "medium",
        },
        headers=manager_headers,
    )
    assert response.status_code == 400
    assert "persona" in response.text.lower()


def test_revoked_persona_cannot_be_used(client: TestClient, admin_headers, manager_headers):
    _enable_impersonation(client, admin_headers)
    employee = _first_employee(client, manager_headers)
    persona = _register_persona(client, admin_headers, display_name="Revocation Test Persona")
    _approve_persona(client, persona["id"])

    revoke = client.post(
        f"/api/v1/personas/{persona['id']}/revoke",
        json={"reason": "Authorization withdrawn"},
        headers=admin_headers,
    )
    assert revoke.status_code == 200
    assert revoke.json()["status"] == "revoked"

    response = client.post(
        "/api/v1/scenarios/generate",
        json={
            "employee_id": employee["id"],
            "channel": "deepfake",
            "theme": "executive approval request",
            "difficulty_level": "medium",
            "persona_id": persona["id"],
        },
        headers=manager_headers,
    )
    assert response.status_code == 400
    assert "revoked" in response.text.lower()


# --------------------------------------------------------------------------------------
# Full simulation flow
# --------------------------------------------------------------------------------------

def _build_campaign(
    client: TestClient,
    admin_headers,
    manager_headers,
    *,
    channel: str,
    theme: str,
    persona_id: str,
    employee_index: int = 0,
):
    employee = _first_employee(client, manager_headers, employee_index)

    scenario = client.post(
        "/api/v1/scenarios/generate",
        json={
            "employee_id": employee["id"],
            "channel": channel,
            "theme": theme,
            "difficulty_level": "high",
            "persona_id": persona_id,
        },
        headers=manager_headers,
    )
    assert scenario.status_code == 201, scenario.text
    scenario_body = scenario.json()
    assert scenario_body["latest_version"]["channel_payload"]["script"], "interactive channels need a script"

    approved = client.post(f"/api/v1/scenarios/{scenario_body['id']}/approve", headers=admin_headers)
    assert approved.status_code == 200, approved.text

    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "name": f"{channel} drill",
            "channel": channel,
            "target_employee_ids": [employee["id"]],
            "scenario_ids": [scenario_body["id"]],
            "requires_second_approval": False,
            "sandbox_mode": True,
        },
        headers=manager_headers,
    )
    assert campaign.status_code == 201, campaign.text
    campaign_id = campaign.json()["id"]

    assert client.post(f"/api/v1/campaigns/{campaign_id}/request-approval", headers=manager_headers).status_code == 200
    assert client.post(f"/api/v1/campaigns/{campaign_id}/approve", headers=admin_headers).status_code == 200

    launched = client.post(f"/api/v1/campaigns/{campaign_id}/deliver", headers=manager_headers)
    assert launched.status_code == 200, launched.text
    attempts = launched.json()
    assert attempts, "delivery should produce at least one attempt"
    return employee, scenario_body, attempts[0]


def test_vishing_call_records_each_decision_and_rewards_verification(client: TestClient, admin_headers, manager_headers):
    _enable_impersonation(client, admin_headers)
    persona = _register_persona(client, admin_headers, display_name="IT Service Desk Lead")
    _approve_persona(client, persona["id"])

    _, _, attempt = _build_campaign(
        client,
        admin_headers,
        manager_headers,
        channel="vishing",
        theme="password reset",
        persona_id=persona["id"],
    )

    assert attempt["preview_payload"]["module"] == "voice_simulation"
    assert attempt["preview_payload"]["caller_id_display"]
    call_url = attempt["preview_payload"]["call_url"]
    token = call_url.rstrip("/").split("/")[-1]

    simulation = client.get(f"/api/v1/public/simulation/{token}")
    assert simulation.status_code == 200, simulation.text
    body = simulation.json()
    assert body["module"] == "voice_simulation"
    assert body["current_step"]["key"] == "opening"
    # The safe answer must not be discoverable from the payload.
    assert all("risk_weight" not in option for option in body["current_step"]["options"])

    first = client.post(
        f"/api/v1/public/simulation/{token}/respond",
        json={"step_key": "opening", "response_key": "engage", "elapsed_ms": 3200},
    )
    assert first.status_code == 200, first.text
    assert first.json()["safe"] is False
    assert first.json()["next_step"]["key"] == "pretext"

    # Replaying the same step must be rejected.
    replay = client.post(
        f"/api/v1/public/simulation/{token}/respond",
        json={"step_key": "opening", "response_key": "verify_identity"},
    )
    assert replay.status_code == 409

    second = client.post(
        f"/api/v1/public/simulation/{token}/respond",
        json={"step_key": "pretext", "response_key": "refuse_details"},
    )
    assert second.status_code == 200, second.text
    assert second.json()["safe"] is True
    assert second.json()["coaching"]

    third = client.post(
        f"/api/v1/public/simulation/{token}/respond",
        json={"step_key": "ask", "response_key": "report_call"},
    )
    assert third.status_code == 200, third.text
    assert third.json()["terminal"] is True

    summary = client.post(f"/api/v1/public/simulation/{token}/complete")
    assert summary.status_code == 200, summary.text
    result = summary.json()
    assert result["outcome"] == "recovered"
    assert result["steps_taken"] == 3
    assert result["breaking_point"]["step_key"] == "opening"
    assert result["verification_procedure"]
    assert len(result["decision_trail"]) == 3


def test_deepfake_compliance_raises_risk_and_assigns_training(client: TestClient, admin_headers, manager_headers):
    _enable_impersonation(client, admin_headers)
    persona = _register_persona(
        client,
        admin_headers,
        display_name="Group CFO",
        modality="video_message",
        detection_tells=["Lip-sync drift on plosive sounds."],
    )
    _approve_persona(client, persona["id"])

    employee, _, attempt = _build_campaign(
        client,
        admin_headers,
        manager_headers,
        channel="deepfake",
        theme="executive approval request",
        persona_id=persona["id"],
        employee_index=1,
    )

    payload = attempt["preview_payload"]
    assert payload["module"] == "synthetic_media_simulation"
    assert payload["modality"] == "video_message"
    assert "no media file is generated" in payload["delivery_note"].lower()

    token = payload["media_url"].rstrip("/").split("/")[-1]
    before = client.get(f"/api/v1/employees/{employee['id']}", headers=manager_headers).json()["risk_score"]

    client.post(
        f"/api/v1/public/simulation/{token}/respond",
        json={"step_key": "receipt", "response_key": "play_media"},
    )
    complied = client.post(
        f"/api/v1/public/simulation/{token}/respond",
        json={"step_key": "request", "response_key": "comply_now"},
    )
    assert complied.status_code == 200, complied.text
    assert complied.json()["safe"] is False
    assert complied.json()["assignment_id"], "acting on synthetic media must assign remediation"

    after = client.get(f"/api/v1/employees/{employee['id']}", headers=manager_headers).json()["risk_score"]
    assert after > before

    summary = client.post(f"/api/v1/public/simulation/{token}/complete").json()
    assert summary["outcome"] == "compromised"
    assert summary["synthetic_artifacts"], "the debrief must show the tells that were present"
    assert summary["detection_tells"]


def test_unknown_response_key_is_rejected(client: TestClient, admin_headers, manager_headers):
    _enable_impersonation(client, admin_headers)
    persona = _register_persona(client, admin_headers, display_name="Validation Persona")
    _approve_persona(client, persona["id"])

    _, _, attempt = _build_campaign(
        client,
        admin_headers,
        manager_headers,
        channel="vishing",
        theme="document review",
        persona_id=persona["id"],
    )
    token = attempt["preview_payload"]["call_url"].rstrip("/").split("/")[-1]

    response = client.post(
        f"/api/v1/public/simulation/{token}/respond",
        json={"step_key": "opening", "response_key": "not-a-real-option"},
    )
    assert response.status_code == 400
