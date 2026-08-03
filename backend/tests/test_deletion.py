"""Coverage for guarded deletion.

Deletion in this platform is not a plain cascade — each entity has referential and
evidence guardrails. These tests pin every guardrail plus the success path behind it,
because a regression here silently destroys audit evidence.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from tests.conftest import login


def _employee(client: TestClient, headers, index: int = 0) -> dict:
    rows = client.get("/api/v1/employees", headers=headers).json()
    assert len(rows) > index
    return rows[index]


def _scenario(client: TestClient, admin, manager, *, approve: bool = True) -> dict:
    employee = _employee(client, manager)
    response = client.post(
        "/api/v1/scenarios/generate",
        json={
            "employee_id": employee["id"],
            "channel": "email",
            "theme": "document review",
            "difficulty_level": "low",
        },
        headers=manager,
    )
    assert response.status_code == 201, response.text
    scenario = response.json()
    if approve:
        client.post(f"/api/v1/scenarios/{scenario['id']}/approve", headers=admin)
    return scenario


def _campaign(client: TestClient, admin, manager, scenario_id: str, *, approve: bool = False) -> str:
    employee = _employee(client, manager)
    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "name": f"del-test-{uuid.uuid4().hex[:6]}",
            "channel": "email",
            "target_employee_ids": [employee["id"]],
            "scenario_ids": [scenario_id],
            "requires_second_approval": False,
        },
        headers=manager,
    ).json()
    if approve:
        client.post(f"/api/v1/campaigns/{campaign['id']}/request-approval", headers=manager)
        client.post(f"/api/v1/campaigns/{campaign['id']}/approve", headers=admin)
    return campaign["id"]


# --------------------------------------------------------------------------------------
# Referential guardrails
# --------------------------------------------------------------------------------------

def test_scenario_linked_to_campaign_cannot_be_deleted(client: TestClient, admin_headers, manager_headers):
    scenario = _scenario(client, admin_headers, manager_headers)
    campaign_id = _campaign(client, admin_headers, manager_headers, scenario["id"])

    blocked = client.delete(f"/api/v1/scenarios/{scenario['id']}", headers=manager_headers)
    assert blocked.status_code == 409
    assert "campaign" in blocked.text.lower()

    # Removing the campaign releases the scenario.
    assert client.delete(f"/api/v1/campaigns/{campaign_id}", headers=admin_headers).status_code == 200
    freed = client.delete(f"/api/v1/scenarios/{scenario['id']}", headers=manager_headers)
    assert freed.status_code == 200, freed.text
    assert freed.json()["removed"]["scenario_versions"] >= 1

    remaining = {row["id"] for row in client.get("/api/v1/scenarios", headers=manager_headers).json()}
    assert scenario["id"] not in remaining


def test_campaign_with_evidence_requires_explicit_purge(client: TestClient, admin_headers, manager_headers):
    scenario = _scenario(client, admin_headers, manager_headers)
    campaign_id = _campaign(client, admin_headers, manager_headers, scenario["id"], approve=True)

    attempts = client.post(f"/api/v1/campaigns/{campaign_id}/deliver", headers=manager_headers)
    assert attempts.status_code == 200, attempts.text
    # Pause so the ACTIVE guardrail is not what we are measuring.
    client.post(f"/api/v1/campaigns/{campaign_id}/pause", headers=manager_headers)

    blocked = client.delete(f"/api/v1/campaigns/{campaign_id}", headers=admin_headers)
    assert blocked.status_code == 409
    assert "purge_evidence" in blocked.text

    purged = client.delete(f"/api/v1/campaigns/{campaign_id}?purge_evidence=true", headers=admin_headers)
    assert purged.status_code == 200, purged.text
    assert purged.json()["removed"].get("events", 0) >= 1


def test_active_campaign_must_be_paused_first(client: TestClient, admin_headers, manager_headers):
    scenario = _scenario(client, admin_headers, manager_headers)
    campaign_id = _campaign(client, admin_headers, manager_headers, scenario["id"], approve=True)
    client.post(f"/api/v1/campaigns/{campaign_id}/deliver", headers=manager_headers)  # -> ACTIVE

    blocked = client.delete(f"/api/v1/campaigns/{campaign_id}?purge_evidence=true", headers=admin_headers)
    assert blocked.status_code == 409
    assert "pause" in blocked.text.lower()


def test_department_with_employees_cannot_be_deleted(client: TestClient, admin_headers, manager_headers):
    department = client.post(
        "/api/v1/departments",
        json={"name": f"Deletable {uuid.uuid4().hex[:4]}", "code": f"D{uuid.uuid4().hex[:4].upper()}"},
        headers=admin_headers,
    ).json()

    employee = client.post(
        "/api/v1/employees",
        json={
            "employee_id": f"DEL-{uuid.uuid4().hex[:6]}",
            "full_name": "Dept Delete Probe",
            "email": f"probe-{uuid.uuid4().hex[:6]}@example.com",
            "role_title": "Analyst",
            "department_id": department["id"],
        },
        headers=admin_headers,
    )
    assert employee.status_code == 201, employee.text

    blocked = client.delete(f"/api/v1/departments/{department['id']}", headers=admin_headers)
    assert blocked.status_code == 409
    assert "employee" in blocked.text.lower()

    assert client.delete(f"/api/v1/employees/{employee.json()['id']}", headers=admin_headers).status_code == 200
    assert client.delete(f"/api/v1/departments/{department['id']}", headers=admin_headers).status_code == 200


def test_unused_persona_deletes_but_used_one_must_be_revoked(client: TestClient, admin_headers, manager_headers):
    unused = client.post(
        "/api/v1/personas",
        json={"display_name": f"Unused {uuid.uuid4().hex[:4]}", "role_title": "Ops Lead"},
        headers=admin_headers,
    ).json()
    assert client.delete(f"/api/v1/personas/{unused['id']}", headers=admin_headers).status_code == 200

    # A persona that has backed a scenario must be revoked, not deleted.
    client.put(
        "/api/v1/integrations/impersonation",
        json={"impersonation_enabled": True, "voice_provider_enabled": False, "voice_provider_mode": "simulator"},
        headers=admin_headers,
    )
    used = client.post(
        "/api/v1/personas",
        json={"display_name": f"Used {uuid.uuid4().hex[:4]}", "role_title": "Service Desk"},
        headers=admin_headers,
    ).json()
    reviewer = login(client, "reviewer@breachsim-lab.com", "Reviewer123!")
    client.post(f"/api/v1/personas/{used['id']}/approve", headers=reviewer)

    generated = client.post(
        "/api/v1/scenarios/generate",
        json={
            "employee_id": _employee(client, manager_headers)["id"],
            "channel": "vishing",
            "theme": "password reset",
            "difficulty_level": "low",
            "persona_id": used["id"],
        },
        headers=manager_headers,
    )
    assert generated.status_code == 201, generated.text

    blocked = client.delete(f"/api/v1/personas/{used['id']}", headers=admin_headers)
    assert blocked.status_code == 409
    assert "revoke" in blocked.text.lower()


def test_missing_resource_returns_404_not_500(client: TestClient, admin_headers):
    ghost = uuid.uuid4()
    for path in ("scenarios", "campaigns", "employees", "departments", "personas"):
        response = client.delete(f"/api/v1/{path}/{ghost}", headers=admin_headers)
        assert response.status_code == 404, f"{path} returned {response.status_code}"


# --------------------------------------------------------------------------------------
# Authorization
# --------------------------------------------------------------------------------------

def test_auditor_cannot_delete_anything(client: TestClient, admin_headers, manager_headers):
    auditor = login(client, "auditor@breachsim-lab.com", "Auditor123!")
    scenario = _scenario(client, admin_headers, manager_headers)
    ghost = uuid.uuid4()

    assert client.delete(f"/api/v1/scenarios/{scenario['id']}", headers=auditor).status_code == 403
    for path in ("campaigns", "employees", "departments", "personas"):
        assert client.delete(f"/api/v1/{path}/{ghost}", headers=auditor).status_code == 403


def test_manager_cannot_delete_admin_only_resources(client: TestClient, manager_headers):
    ghost = uuid.uuid4()
    for path in ("campaigns", "employees", "departments", "personas"):
        response = client.delete(f"/api/v1/{path}/{ghost}", headers=manager_headers)
        assert response.status_code == 403, f"{path} allowed a manager: {response.status_code}"


def test_unauthenticated_delete_is_rejected(client: TestClient):
    ghost = uuid.uuid4()
    for path in ("scenarios", "campaigns", "employees", "departments", "personas"):
        response = client.delete(f"/api/v1/{path}/{ghost}")
        assert response.status_code in (401, 403), f"{path} returned {response.status_code}"


# --------------------------------------------------------------------------------------
# Audit + integrity
# --------------------------------------------------------------------------------------

def test_deletions_are_audited(client: TestClient, admin_headers, manager_headers):
    scenario = _scenario(client, admin_headers, manager_headers)
    assert client.delete(f"/api/v1/scenarios/{scenario['id']}", headers=manager_headers).status_code == 200

    actions = [row["action"] for row in client.get("/api/v1/audit-logs", headers=admin_headers).json()]
    assert "scenario.delete" in actions


def test_analytics_survive_deletion(client: TestClient, admin_headers, manager_headers):
    """A deletion must not leave the dashboard unable to render."""
    scenario = _scenario(client, admin_headers, manager_headers)
    campaign_id = _campaign(client, admin_headers, manager_headers, scenario["id"], approve=True)
    client.post(f"/api/v1/campaigns/{campaign_id}/deliver", headers=manager_headers)
    client.post(f"/api/v1/campaigns/{campaign_id}/pause", headers=manager_headers)
    client.delete(f"/api/v1/campaigns/{campaign_id}?purge_evidence=true", headers=admin_headers)

    dashboard = client.get("/api/v1/analytics/dashboard", headers=admin_headers)
    assert dashboard.status_code == 200
    for row in dashboard.json()["channel_performance"]:
        assert 0 <= row["failure_rate"] <= 100
        assert 0 <= row["resilience_rate"] <= 100

    assert client.get("/api/v1/analytics/risk-intelligence", headers=admin_headers).status_code == 200


# --------------------------------------------------------------------------------------
# Regressions found by the multi-agent test sweep
# --------------------------------------------------------------------------------------

def test_employee_delete_leaves_no_dangling_foreign_keys(client: TestClient, admin_headers, manager_headers):
    """Postgres enforces FKs even though local SQLite does not, so orphaned pointers
    would turn right-to-erasure into a 500 in production."""
    from app.db.session import SessionLocal
    from app.models.entities import ContextProfile, ImpersonationPersona, Scenario

    employee = client.post(
        "/api/v1/employees",
        json={
            "employee_id": f"FK-{uuid.uuid4().hex[:6]}",
            "full_name": "Dangling Reference Probe",
            "email": f"fk-{uuid.uuid4().hex[:6]}@example.com",
            "role_title": "Analyst",
        },
        headers=admin_headers,
    ).json()

    # A scenario stamps scenarios.profile_id with this employee's context profile.
    generated = client.post(
        "/api/v1/scenarios/generate",
        json={
            "employee_id": employee["id"],
            "channel": "email",
            "theme": "document review",
            "difficulty_level": "low",
        },
        headers=manager_headers,
    )
    assert generated.status_code == 201, generated.text

    deleted = client.delete(f"/api/v1/employees/{employee['id']}", headers=admin_headers)
    assert deleted.status_code == 200, deleted.text

    session = SessionLocal()
    try:
        profile_ids = {
            row.id for row in session.query(ContextProfile).all()
        }
        dangling_scenarios = [
            row.id
            for row in session.query(Scenario).filter(Scenario.profile_id.isnot(None)).all()
            if row.profile_id not in profile_ids
        ]
        assert not dangling_scenarios, f"scenarios.profile_id dangling: {dangling_scenarios}"

        orphan_personas = (
            session.query(ImpersonationPersona)
            .filter(ImpersonationPersona.linked_employee_id == uuid.UUID(employee["id"]))
            .count()
        )
        assert orphan_personas == 0
    finally:
        session.close()


def test_employee_delete_scrubs_their_name_from_generated_copy(client: TestClient, admin_headers, manager_headers):
    """Generated copy embeds the target's name, so erasure must reach it — the training
    landing page serves that copy unauthenticated."""
    from app.db.session import SessionLocal
    from app.models.entities import ScenarioVersion

    unique_name = f"Zephyrine Quillfeather{uuid.uuid4().hex[:4]}"
    employee = client.post(
        "/api/v1/employees",
        json={
            "employee_id": f"ERA-{uuid.uuid4().hex[:6]}",
            "full_name": unique_name,
            "email": f"erasure-{uuid.uuid4().hex[:6]}@example.com",
            "role_title": "Finance Analyst",
        },
        headers=admin_headers,
    ).json()

    generated = client.post(
        "/api/v1/scenarios/generate",
        json={
            "employee_id": employee["id"],
            "channel": "email",
            "theme": "invoice/payment approval",
            "difficulty_level": "low",
        },
        headers=manager_headers,
    )
    assert generated.status_code == 201, generated.text
    # The generator personalises the body with the real name.
    assert unique_name.split()[0] in generated.json()["latest_version"]["body_copy"]

    assert client.delete(f"/api/v1/employees/{employee['id']}", headers=admin_headers).status_code == 200

    session = SessionLocal()
    try:
        leaked = [
            version.id
            for version in session.query(ScenarioVersion).all()
            if unique_name in (version.body_copy or "")
            or unique_name in (version.subject or "")
            or unique_name in (version.landing_page_copy or "")
        ]
        assert not leaked, f"erased employee name still present in scenario_versions: {leaked}"
    finally:
        session.close()


def test_patch_employee_department_does_not_500(client: TestClient, admin_headers):
    """A UUID in the audit payload used to break JSON serialization, 500-ing every
    employee edit in the UI."""
    dept_a = client.post(
        "/api/v1/departments",
        json={"name": f"PatchA {uuid.uuid4().hex[:4]}", "code": f"PA{uuid.uuid4().hex[:4].upper()}"},
        headers=admin_headers,
    ).json()
    dept_b = client.post(
        "/api/v1/departments",
        json={"name": f"PatchB {uuid.uuid4().hex[:4]}", "code": f"PB{uuid.uuid4().hex[:4].upper()}"},
        headers=admin_headers,
    ).json()
    employee = client.post(
        "/api/v1/employees",
        json={
            "employee_id": f"PCH-{uuid.uuid4().hex[:6]}",
            "full_name": "Patch Probe",
            "email": f"patch-{uuid.uuid4().hex[:6]}@example.com",
            "role_title": "Analyst",
            "department_id": dept_a["id"],
        },
        headers=admin_headers,
    ).json()

    moved = client.patch(
        f"/api/v1/employees/{employee['id']}",
        json={"department_id": dept_b["id"]},
        headers=admin_headers,
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["department_id"] == dept_b["id"]


def test_employees_filter_by_department_does_not_500(client: TestClient, admin_headers):
    departments = client.get("/api/v1/departments", headers=admin_headers).json()
    if departments:
        ok = client.get(
            f"/api/v1/employees?department_id={departments[0]['id']}", headers=admin_headers
        )
        assert ok.status_code == 200, ok.text

    # A malformed id must be a validation error, not a server crash.
    bad = client.get("/api/v1/employees?department_id=not-a-uuid", headers=admin_headers)
    assert bad.status_code == 422, f"expected 422, got {bad.status_code}"
