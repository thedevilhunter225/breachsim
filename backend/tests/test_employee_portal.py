from __future__ import annotations

import uuid

from app.db.session import SessionLocal
from app.models.entities import EventLog
from app.models.enums import EventType


def _portal_employee(client, admin_headers) -> dict:
    """A dedicated employee, so opting out cannot affect tests that share the database."""
    department = client.get("/api/v1/departments", headers=admin_headers).json()[0]
    response = client.post(
        "/api/v1/employees",
        json={
            "employee_id": f"PORTAL-{uuid.uuid4().hex[:6]}",
            "full_name": "Portal Probe",
            "email": f"portal-{uuid.uuid4().hex[:6]}@example.com",
            "role_title": "Analyst",
            "department_id": department["id"],
            "consent_status": "consented",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _sandbox_attempts(client, admin_headers, manager_headers, employee_id: str) -> list[dict]:
    scenario = client.post(
        "/api/v1/scenarios/generate",
        json={"employee_id": employee_id, "channel": "email", "theme": "document review", "difficulty_level": "low"},
        headers=manager_headers,
    ).json()
    client.post(f"/api/v1/scenarios/{scenario['id']}/approve", headers=admin_headers)
    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "name": f"Portal {uuid.uuid4().hex[:4]}",
            "channel": "email",
            "target_employee_ids": [employee_id],
            "scenario_ids": [scenario["id"]],
            "requires_second_approval": False,
        },
        headers=manager_headers,
    ).json()
    client.post(f"/api/v1/campaigns/{campaign['id']}/request-approval", headers=manager_headers)
    client.post(f"/api/v1/campaigns/{campaign['id']}/approve", headers=admin_headers)
    response = client.post(f"/api/v1/campaigns/{campaign['id']}/launch-sandbox", headers=admin_headers)
    assert response.status_code == 200, response.text
    return response.json()


def _token(attempt: dict) -> str:
    return attempt["preview_payload"]["preview_url"].rstrip("/").split("/")[-1]


def test_portal_requires_an_exercise_link(client):
    assert client.get("/api/v1/public/portal").status_code == 401
    assert client.get("/api/v1/public/portal", headers={"X-Portal-Token": "not-a-real-link"}).status_code == 404


def test_employee_sees_and_completes_own_training_once(client, admin_headers, manager_headers):
    employee = _portal_employee(client, admin_headers)
    token = _token(_sandbox_attempts(client, admin_headers, manager_headers, employee["id"])[0])
    headers = {"X-Portal-Token": token}

    answer = client.post(
        f"/api/v1/public/training/{token}/events",
        json={"event_type": "submitted_form_boolean", "metadata": {"simulation_choice": "would_provide_details"}},
    )
    assert answer.status_code == 200, answer.text

    portal = client.get("/api/v1/public/portal", headers=headers)
    assert portal.status_code == 200, portal.text
    body = portal.json()
    assert body["first_name"] == "Portal"
    assert body["consent_status"] == "consented"
    assert "risk_score" not in body
    assignment = body["training"][0]
    assert assignment["status"] == "assigned"

    for _ in range(2):
        done = client.post(
            f"/api/v1/public/portal/training/{assignment['id']}/complete",
            json={"dwell_seconds": 60},
            headers=headers,
        )
        assert done.status_code == 200, done.text
    assert done.json()["training"][0]["status"] == "completed"

    session = SessionLocal()
    try:
        completions = (
            session.query(EventLog)
            .filter(
                EventLog.employee_id == uuid.UUID(employee["id"]),
                EventLog.event_type == EventType.TRAINING_COMPLETED,
            )
            .count()
        )
    finally:
        session.close()
    assert completions == 1, "completing twice must not lower the score twice"


def test_portal_opt_out_excludes_employee_from_later_campaigns(client, admin_headers, manager_headers):
    employee = _portal_employee(client, admin_headers)
    token = _token(_sandbox_attempts(client, admin_headers, manager_headers, employee["id"])[0])

    opted_out = client.post("/api/v1/public/portal/opt-out", headers={"X-Portal-Token": token})
    assert opted_out.status_code == 200, opted_out.text
    assert opted_out.json()["consent_status"] == "opted_out"

    later = _sandbox_attempts(client, admin_headers, manager_headers, employee["id"])
    assert later == []

    audit = client.get("/api/v1/audit-logs", headers=admin_headers)
    if audit.status_code == 200:
        assert any(row["action"] == "employee.opt_out" for row in audit.json())


def test_portal_redaction_request_is_recorded(client, admin_headers, manager_headers):
    employee = _portal_employee(client, admin_headers)
    token = _token(_sandbox_attempts(client, admin_headers, manager_headers, employee["id"])[0])

    response = client.post("/api/v1/public/portal/redaction-request", headers={"X-Portal-Token": token})
    assert response.status_code == 200, response.text
    assert response.json()["consent_status"] == "redaction_requested"
    record = client.get(f"/api/v1/employees/{employee['id']}", headers=admin_headers).json()
    assert record["consent_status"] == "redaction_requested"


def test_read_only_operators_cannot_complete_training(client, auditor_headers):
    response = client.post(
        f"/api/v1/training/assignments/{uuid.uuid4()}/complete",
        json={"dwell_seconds": 30},
        headers=auditor_headers,
    )
    assert response.status_code == 403


def test_read_only_operators_cannot_regenerate_context_profiles(client, admin_headers, auditor_headers):
    employee = client.get("/api/v1/employees", headers=admin_headers).json()[0]
    response = client.post(f"/api/v1/employees/{employee['id']}/profile", headers=auditor_headers)
    assert response.status_code == 403


def test_employee_edits_audit_field_names_not_personal_values(client, admin_headers):
    employee = _portal_employee(client, admin_headers)
    response = client.patch(
        f"/api/v1/employees/{employee['id']}",
        json={"full_name": "Renamed Person", "phone": "+923001112223"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    entries = [
        row
        for row in client.get("/api/v1/audit-logs", headers=admin_headers).json()
        if row["action"] == "employee.update" and row["resource_id"] == employee["id"]
    ]
    assert entries[0]["details"] == {"changed_fields": ["full_name", "phone"]}
    assert "Renamed Person" not in str(entries[0]["details"])
