"""Erasure and purge after a real enterprise QR run.

The test database enforces foreign keys (see conftest), as PostgreSQL does. Before the fix,
QR asset tokens, provider receipts and campaign runs were left behind and these deletes failed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.models.entities import DeliveryAttempt, EmailConnection, LandingToken, QrAssetToken
from app.models.enums import ConnectionStatus
from tests.test_enterprise_email_qr import _verify_domain


def _qr_run_for_new_employee(client, admin_headers, manager_headers, *, domain, connection_id, landing_id, local):
    department = client.get("/api/v1/departments", headers=admin_headers).json()[0]
    employee = client.post(
        "/api/v1/employees",
        headers=admin_headers,
        json={
            "employee_id": f"ERASE-{uuid.uuid4().hex[:6]}",
            "full_name": f"{local.title()} Erasure",
            "email": f"{local}@{domain}",
            "role_title": "Analyst",
            "department_id": department["id"],
            "consent_status": "consented",
        },
    ).json()
    scenario = client.post(
        "/api/v1/scenarios/generate",
        headers=manager_headers,
        json={"employee_id": employee["id"], "channel": "qr", "theme": "qr verification", "difficulty_level": "medium"},
    ).json()
    assert client.post(f"/api/v1/scenarios/{scenario['id']}/approve", headers=admin_headers).status_code == 200
    campaign = client.post(
        "/api/v1/campaigns",
        headers=manager_headers,
        json={
            "name": f"Erasure QR {local}",
            "channel": "qr",
            "target_employee_ids": [employee["id"]],
            "scenario_ids": [scenario["id"]],
            "requires_second_approval": False,
            "sandbox_mode": False,
            "landing_domain_id": landing_id,
            "email_connection_id": connection_id,
        },
    ).json()
    client.post(f"/api/v1/campaigns/{campaign['id']}/request-approval", headers=manager_headers)
    assert client.post(f"/api/v1/campaigns/{campaign['id']}/approve", headers=admin_headers).status_code == 200
    run = client.post(
        f"/api/v1/campaigns/{campaign['id']}/runs",
        headers={**admin_headers, "Idempotency-Key": f"erase-{uuid.uuid4()}"},
        json={"scheduled_for": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()},
    )
    assert run.status_code == 202, run.text
    with SessionLocal() as db:
        attempt = db.query(DeliveryAttempt).filter(DeliveryAttempt.employee_id == uuid.UUID(employee["id"])).one()
        token = db.query(LandingToken).filter(LandingToken.delivery_attempt_id == attempt.id).one()
        assert db.query(QrAssetToken).filter(QrAssetToken.landing_token_id == token.id).count() == 1
    return employee, campaign


def test_erasure_and_purge_succeed_after_an_enterprise_qr_run(client, admin_headers, manager_headers):
    domain = f"erase-{uuid.uuid4().hex[:10]}.example"
    _verify_domain(client, admin_headers, hostname=domain, purpose="recipient")
    _verify_domain(client, admin_headers, hostname=domain, purpose="sender")
    landing = next(
        row
        for row in client.get("/api/v1/orgs/current/domains", headers=admin_headers).json()
        if row["purpose"] == "landing" and row["status"] == "active"
    )
    sender = f"security-awareness@{domain}"
    connection = client.post(
        "/api/v1/email-connections",
        headers=admin_headers,
        json={
            "provider": "google_workspace",
            "display_name": "Erasure test sender",
            "sender_email": sender,
            "sender_name": "Security Awareness",
            "delegated_subject": sender,
            "rate_limit_per_minute": 120,
        },
    )
    assert connection.status_code == 201, connection.text
    with SessionLocal() as db:
        row = db.query(EmailConnection).filter(EmailConnection.id == uuid.UUID(connection.json()["id"])).one()
        row.status = ConnectionStatus.HEALTHY
        row.authorized_at = datetime.now(timezone.utc)
        db.commit()

    kwargs = {"domain": domain, "connection_id": connection.json()["id"], "landing_id": landing["id"]}
    _, purged_campaign = _qr_run_for_new_employee(client, admin_headers, manager_headers, local="purge", **kwargs)
    erased_employee, _ = _qr_run_for_new_employee(client, admin_headers, manager_headers, local="erase", **kwargs)

    purge = client.delete(f"/api/v1/campaigns/{purged_campaign['id']}?purge_evidence=true", headers=admin_headers)
    assert purge.status_code == 200, purge.text
    assert purge.json()["removed"].get("qr_assets") == 1
    assert purge.json()["removed"].get("campaign_runs") == 1

    erase = client.delete(f"/api/v1/employees/{erased_employee['id']}", headers=admin_headers)
    assert erase.status_code == 200, erase.text
    assert erase.json()["removed"].get("qr_assets") == 1
