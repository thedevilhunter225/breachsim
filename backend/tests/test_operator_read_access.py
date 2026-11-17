"""Tenant data is for console operators, and exercise links only for the roles that launch."""

from __future__ import annotations

import json
import uuid

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.entities import Organization, Role, User, UserRoleLink
from app.models.enums import UserRole
from app.services.delivery import EXERCISE_LINK_FIELDS, HIDDEN_LINK_PLACEHOLDER, without_exercise_links
from tests.conftest import login

PASSWORD = "Read-Access-Test-Passw0rd!"
READ_PATHS = [
    "/employees",
    "/campaigns",
    "/scenarios",
    "/delivery-attempts",
    "/personas",
    "/policies/current",
    "/departments",
    "/training/assignments",
    "/training/modules",
]


def _account(client, admin_headers, role: str) -> dict[str, str]:
    email = f"{role.replace('_', '-')}-{uuid.uuid4().hex[:8]}@example.com"
    created = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"email": email, "full_name": f"Only {role}", "password": PASSWORD, "roles": [role]},
    )
    assert created.status_code == 201, created.text
    return login(client, email, PASSWORD)


def _sandbox_campaign(client, admin_headers, manager_headers, *, channel: str, theme: str) -> dict:
    """Generate, approve and deliver one sandbox campaign; return the manager's view of its attempt."""
    employee = client.get("/api/v1/employees", headers=manager_headers).json()[0]
    scenario = client.post(
        "/api/v1/scenarios/generate",
        headers=manager_headers,
        json={"employee_id": employee["id"], "channel": channel, "theme": theme, "difficulty_level": "low"},
    )
    assert scenario.status_code == 201, scenario.text
    scenario_id = scenario.json()["id"]
    assert client.post(f"/api/v1/scenarios/{scenario_id}/approve", headers=admin_headers).status_code == 200
    campaign = client.post(
        "/api/v1/campaigns",
        headers=manager_headers,
        json={
            "name": f"Read access {channel} {uuid.uuid4().hex[:6]}",
            "channel": channel,
            "target_employee_ids": [employee["id"]],
            "scenario_ids": [scenario_id],
            "requires_second_approval": False,
            "sandbox_mode": True,
        },
    )
    assert campaign.status_code == 201, campaign.text
    campaign_id = campaign.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/request-approval", headers=manager_headers).status_code == 200
    assert client.post(f"/api/v1/campaigns/{campaign_id}/approve", headers=admin_headers).status_code == 200
    delivered = client.post(f"/api/v1/campaigns/{campaign_id}/deliver", headers=manager_headers)
    assert delivered.status_code == 200, delivered.text
    return delivered.json()[0]


def _attempt(client, headers, attempt_id: str) -> dict:
    return next(row for row in client.get("/api/v1/delivery-attempts", headers=headers).json() if row["id"] == attempt_id)


def test_roles_without_console_duties_cannot_read_tenant_data(client, admin_headers):
    employee_id = client.get("/api/v1/employees", headers=admin_headers).json()[0]["id"]
    campaign_id = client.get("/api/v1/campaigns", headers=admin_headers).json()[0]["id"]
    detail_paths = [f"/employees/{employee_id}", f"/campaigns/{campaign_id}", f"/campaigns/{campaign_id}/runs"]

    for role in ("employee", "risk_identity_viewer"):
        headers = _account(client, admin_headers, role)
        # The session itself is valid; it simply carries no console role.
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
        assert client.get("/api/v1/orgs/current", headers=headers).status_code == 200
        for path in READ_PATHS + detail_paths:
            assert client.get(f"/api/v1{path}", headers=headers).status_code == 403, (role, path)


def test_console_roles_keep_their_read_access(client, admin_headers, manager_headers, auditor_headers):
    for label, headers in (("admin", admin_headers), ("manager", manager_headers), ("auditor", auditor_headers)):
        for path in READ_PATHS:
            assert client.get(f"/api/v1{path}", headers=headers).status_code == 200, (label, path)


def test_read_only_roles_do_not_receive_exercise_links(client, admin_headers, manager_headers, auditor_headers):
    delivered = _sandbox_campaign(client, admin_headers, manager_headers, channel="sms", theme="policy update")
    link = delivered["preview_payload"]["entry_url"]
    token = link.rsplit("/", 1)[-1]
    assert token in delivered["preview_payload"]["message_text"], "the SMS preview embeds the link"

    for headers in (admin_headers, manager_headers):
        launcher_view = _attempt(client, headers, delivered["id"])["preview_payload"]
        assert launcher_view["entry_url"] == link

    auditor_view = _attempt(client, auditor_headers, delivered["id"])["preview_payload"]
    assert not EXERCISE_LINK_FIELDS.intersection(auditor_view)
    assert token not in json.dumps(auditor_view)
    assert HIDDEN_LINK_PLACEHOLDER in auditor_view["message_text"]
    # Everything a reviewer needs is still there.
    assert auditor_view["channel"] == "sms"
    assert auditor_view["subject"] == delivered["preview_payload"]["subject"]
    assert auditor_view["segment_count"] == delivered["preview_payload"]["segment_count"]

    # The link an auditor cannot see is a working credential for that employee.
    assert client.get("/api/v1/public/portal", headers={"X-Portal-Token": token}).status_code == 200


def test_link_removal_handles_every_preview_shape():
    payload = {
        "channel": "qr",
        "subject": "Scan to verify",
        "entry_url": "https://breachsim.example/qr/abc_DEF-123",
        "scan_url": "https://breachsim.example/qr/abc_DEF-123",
        "qr_payload_text": "https://breachsim.example/qr/abc_DEF-123",
        "qr_image_data_url": "data:image/png;base64,AAAA",
        "call_url": "https://breachsim.example/call/abc_DEF-123",
        "media_url": "https://breachsim.example/impersonation/abc_DEF-123",
        "message_text": "Review today https://breachsim.example/training/abc_DEF-123 thanks",
        "nested": {"session_url": "x", "notes": ["see https://breachsim.example/l/pub1.sec-2 now"]},
        "expected_events": ["delivered", "scanned_qr"],
        "script_step_count": 3,
    }
    cleaned = without_exercise_links(payload)

    assert "abc_DEF-123" not in json.dumps(cleaned) and "pub1.sec-2" not in json.dumps(cleaned)
    assert cleaned == {
        "channel": "qr",
        "subject": "Scan to verify",
        "message_text": f"Review today {HIDDEN_LINK_PLACEHOLDER} thanks",
        "nested": {"notes": [f"see {HIDDEN_LINK_PLACEHOLDER} now"]},
        "expected_events": ["delivered", "scanned_qr"],
        "script_step_count": 3,
    }
    assert payload["entry_url"].endswith("abc_DEF-123"), "the stored payload is left untouched"
    assert without_exercise_links(None) == {}
    # A link to somewhere other than an exercise is ordinary content.
    assert without_exercise_links({"note": "Policy: https://intranet.example/policies/42"}) == {
        "note": "Policy: https://intranet.example/policies/42"
    }


def test_training_records_stay_inside_the_tenant(client, admin_headers, manager_headers):
    # Make sure the seeded tenant has at least one assignment to leak.
    delivered = _sandbox_campaign(client, admin_headers, manager_headers, channel="email", theme="document review")
    token = delivered["preview_payload"]["entry_url"].rsplit("/", 1)[-1]
    answered = client.post(
        f"/api/v1/public/training/{token}/events",
        json={"event_type": "submitted_form_boolean", "metadata": {"simulation_choice": "would_provide_details"}},
    )
    assert answered.status_code == 200, answered.text
    own_assignments = client.get("/api/v1/training/assignments", headers=admin_headers).json()
    own_modules = client.get("/api/v1/training/modules", headers=admin_headers).json()
    assert own_assignments and own_modules

    suffix = uuid.uuid4().hex[:8]
    email = f"other-tenant-admin-{suffix}@example.com"
    db = SessionLocal()
    try:
        org = Organization(name="Other Tenant", slug=f"other-tenant-{suffix}", timezone="UTC")
        db.add(org)
        db.flush()
        user = User(organization_id=org.id, email=email, full_name="Other Admin", password_hash=hash_password(PASSWORD))
        db.add(user)
        db.flush()
        db.add(UserRoleLink(user_id=user.id, role_id=db.query(Role).filter(Role.name == UserRole.ADMIN).one().id))
        db.commit()
    finally:
        db.close()
    other_tenant = login(client, email, PASSWORD)

    assert client.get("/api/v1/training/assignments", headers=other_tenant).json() == []
    filtered = client.get(
        f"/api/v1/training/assignments?employee_id={own_assignments[0]['employee_id']}", headers=other_tenant
    )
    assert filtered.status_code == 200 and filtered.json() == [], "naming another tenant's employee returns nothing"
    foreign_module_ids = {module["id"] for module in own_modules}
    visible = client.get("/api/v1/training/modules", headers=other_tenant).json()
    assert not foreign_module_ids.intersection(module["id"] for module in visible)
    assert client.get("/api/v1/training/assignments?employee_id=not-a-uuid", headers=admin_headers).status_code == 422
