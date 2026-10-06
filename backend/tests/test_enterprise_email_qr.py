from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
from urllib.parse import urlsplit

import pytest
import zxingcpp
from fastapi import HTTPException
from PIL import Image
from starlette.requests import Request

from app.api.routes import enterprise as enterprise_routes
from app.api.routes import public as public_routes
from app.db.session import SessionLocal
from app.models.entities import (
    DeliveryAttempt,
    DeliverySuppression,
    EmailConnection,
    EventLog,
    LandingToken,
    Policy,
    QrAssetToken,
)
from app.models.enums import ConnectionStatus, DeliveryStatus, EventType


def _approved_campaign(
    client,
    admin_headers,
    *,
    channel: str,
    sandbox_mode: bool,
    landing_domain_id: str | None = None,
    email_connection_id: str | None = None,
):
    employee = client.get("/api/v1/employees", headers=admin_headers).json()[0]
    scenario_response = client.post(
        "/api/v1/scenarios/generate",
        headers=admin_headers,
        json={
            "employee_id": employee["id"],
            "channel": channel,
            "theme": "qr verification" if channel == "qr" else "document review",
            "difficulty_level": "medium",
        },
    )
    assert scenario_response.status_code == 201, scenario_response.text
    scenario_id = scenario_response.json()["id"]
    assert client.post(f"/api/v1/scenarios/{scenario_id}/approve", headers=admin_headers).status_code == 200

    response = client.post(
        "/api/v1/campaigns",
        headers=admin_headers,
        json={
            "name": f"Enterprise {channel} {uuid.uuid4().hex[:8]}",
            "channel": channel,
            "campaign_type": "one_time",
            "throttling_per_hour": 100,
            "target_employee_ids": [employee["id"]],
            "scenario_ids": [scenario_id],
            "requires_second_approval": False,
            "sandbox_mode": sandbox_mode,
            "learning_objective": "Verify the destination before continuing.",
            "landing_domain_id": landing_domain_id,
            "email_connection_id": email_connection_id,
        },
    )
    assert response.status_code == 201, response.text
    campaign_id = response.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/request-approval", headers=admin_headers).status_code == 200
    approved = client.post(f"/api/v1/campaigns/{campaign_id}/approve", headers=admin_headers)
    assert approved.status_code == 200, approved.text
    return employee, campaign_id


def _verify_domain(client, admin_headers, *, hostname: str, purpose: str) -> dict:
    created = client.post(
        "/api/v1/orgs/current/domains",
        headers=admin_headers,
        json={"hostname": hostname, "purpose": purpose},
    )
    if created.status_code == 409:
        return next(
            domain
            for domain in client.get("/api/v1/orgs/current/domains", headers=admin_headers).json()
            if domain["hostname"] == hostname and domain["purpose"] == purpose
        )
    assert created.status_code == 201, created.text
    domain = created.json()
    verified = client.post(
        f"/api/v1/orgs/current/domains/{domain['id']}/verify",
        headers=admin_headers,
        json={"proof": domain["verification_value"]},
    )
    assert verified.status_code == 200, verified.text
    return verified.json()


def test_campaign_run_is_idempotent_and_preview_contains_no_recipient_pii(client, admin_headers):
    employee, campaign_id = _approved_campaign(
        client,
        admin_headers,
        channel="email",
        sandbox_mode=True,
    )
    headers = {**admin_headers, "Idempotency-Key": f"test-{uuid.uuid4()}"}
    first = client.post(f"/api/v1/campaigns/{campaign_id}/runs", headers=headers, json={})
    second = client.post(f"/api/v1/campaigns/{campaign_id}/runs", headers=headers, json={})
    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["target_count"] == 1

    with SessionLocal() as db:
        attempt = db.query(DeliveryAttempt).filter(
            DeliveryAttempt.campaign_run_id == uuid.UUID(first.json()["id"])
        ).one()
        serialized = str(attempt.preview_payload)
        assert employee["email"] not in serialized
        assert employee["full_name"] not in serialized
        assert "token" not in serialized.casefold()
        assert "http://" not in serialized and "https://" not in serialized


def test_email_link_tracking_records_one_click_without_claiming_an_open(client, admin_headers):
    employee = client.get("/api/v1/employees", headers=admin_headers).json()[0]
    employee_domain = employee["email"].rsplit("@", 1)[1]
    _verify_domain(client, admin_headers, hostname=employee_domain, purpose="recipient")
    _verify_domain(client, admin_headers, hostname=employee_domain, purpose="sender")
    landing_domain = next(
        domain
        for domain in client.get("/api/v1/orgs/current/domains", headers=admin_headers).json()
        if domain["purpose"] == "landing" and domain["status"] == "active"
    )
    sender = f"training@{employee_domain}"
    connection_response = client.post(
        "/api/v1/email-connections",
        headers=admin_headers,
        json={
            "provider": "google_workspace",
            "display_name": "Email tracking test",
            "sender_email": sender,
            "sender_name": "Security Awareness",
            "delegated_subject": sender,
            "rate_limit_per_minute": 120,
        },
    )
    assert connection_response.status_code == 201, connection_response.text
    connection_id = connection_response.json()["id"]
    with SessionLocal() as db:
        connection = db.query(EmailConnection).filter(EmailConnection.id == uuid.UUID(connection_id)).one()
        connection.status = ConnectionStatus.HEALTHY
        connection.authorized_at = datetime.now(timezone.utc)
        db.commit()

    _, campaign_id = _approved_campaign(
        client,
        admin_headers,
        channel="email",
        sandbox_mode=False,
        landing_domain_id=landing_domain["id"],
        email_connection_id=connection_id,
    )
    scheduled_for = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    run_response = client.post(
        f"/api/v1/campaigns/{campaign_id}/runs",
        headers={**admin_headers, "Idempotency-Key": f"email-track-{uuid.uuid4()}"},
        json={"scheduled_for": scheduled_for},
    )
    assert run_response.status_code == 202, run_response.text

    with SessionLocal() as db:
        attempt = db.query(DeliveryAttempt).filter(
            DeliveryAttempt.campaign_run_id == uuid.UUID(run_response.json()["id"])
        ).one()
        landing = db.query(LandingToken).filter(LandingToken.delivery_attempt_id == attempt.id).one()
        link = f"/api/v1/public/l/{landing.token_public_id}.{landing.token_secret_ciphertext}"
        landing_id = landing.id

    first = client.get(link, follow_redirects=False)
    second = client.get(link, follow_redirects=False)
    assert first.status_code == second.status_code == 302
    assert "/training/" in first.headers["location"]
    with SessionLocal() as db:
        events = db.query(EventLog).filter(EventLog.landing_token_id == landing_id).all()
        assert sum(event.event_type == EventType.CLICKED_LINK for event in events) == 1
        assert sum(event.event_type == EventType.OPENED_EMAIL for event in events) == 0


def test_remote_qr_asset_decodes_and_only_destination_open_records_scan(client, admin_headers):
    employee = client.get("/api/v1/employees", headers=admin_headers).json()[0]
    employee_domain = employee["email"].rsplit("@", 1)[1]
    _verify_domain(client, admin_headers, hostname=employee_domain, purpose="recipient")
    _verify_domain(client, admin_headers, hostname=employee_domain, purpose="sender")
    platform_domain = next(
        domain
        for domain in client.get("/api/v1/orgs/current/domains", headers=admin_headers).json()
        if domain["purpose"] == "landing" and domain["status"] == "active"
    )
    sender = f"security-awareness@{employee_domain}"
    connection_response = client.post(
        "/api/v1/email-connections",
        headers=admin_headers,
        json={
            "provider": "google_workspace",
            "display_name": "Enterprise QR test",
            "sender_email": sender,
            "sender_name": "Security Awareness",
            "delegated_subject": sender,
            "rate_limit_per_minute": 120,
        },
    )
    assert connection_response.status_code == 201, connection_response.text
    connection_id = connection_response.json()["id"]
    with SessionLocal() as db:
        connection = db.query(EmailConnection).filter(EmailConnection.id == uuid.UUID(connection_id)).one()
        connection.status = ConnectionStatus.HEALTHY
        connection.authorized_at = datetime.now(timezone.utc)
        db.commit()

    _, campaign_id = _approved_campaign(
        client,
        admin_headers,
        channel="qr",
        sandbox_mode=False,
        landing_domain_id=platform_domain["id"],
        email_connection_id=connection_id,
    )
    scheduled_for = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    run_response = client.post(
        f"/api/v1/campaigns/{campaign_id}/runs",
        headers={**admin_headers, "Idempotency-Key": f"qr-{uuid.uuid4()}"},
        json={"scheduled_for": scheduled_for},
    )
    assert run_response.status_code == 202, run_response.text
    assert run_response.json()["status"] == "scheduled"

    with SessionLocal() as db:
        attempt = db.query(DeliveryAttempt).filter(
            DeliveryAttempt.campaign_run_id == uuid.UUID(run_response.json()["id"])
        ).one()
        landing = db.query(LandingToken).filter(LandingToken.delivery_attempt_id == attempt.id).one()
        asset = db.query(QrAssetToken).filter(QrAssetToken.landing_token_id == landing.id).one()
        asset_token = f"{asset.public_id}.{asset.secret_ciphertext}"
        before = db.query(EventLog).filter(
            EventLog.landing_token_id == landing.id,
            EventLog.event_type == EventType.SCANNED_QR,
        ).count()
        assert before == 0

    image_response = client.get(f"/api/v1/public/qr-assets/{asset_token}.png")
    assert image_response.status_code == 200
    assert image_response.headers["content-type"] == "image/png"
    image = Image.open(BytesIO(image_response.content)).convert("RGB")
    assert image.width >= 320 and image.height >= 320
    decoded = zxingcpp.read_barcode(image)
    assert decoded is not None
    destination = decoded.text
    assert "/q/" in destination

    # Gmail and Outlook image proxies can fetch the asset repeatedly without
    # becoming engagement events. Only opening the encoded destination counts.
    assert client.get(f"/api/v1/public/qr-assets/{asset_token}.png").status_code == 200
    path = urlsplit(destination).path
    first_scan = client.get(path, follow_redirects=False)
    second_scan = client.get(path, follow_redirects=False)
    assert first_scan.status_code == 302
    assert second_scan.status_code == 302
    with SessionLocal() as db:
        scans = db.query(EventLog).filter(
            EventLog.landing_token_id == landing.id,
            EventLog.event_type == EventType.SCANNED_QR,
        ).count()
        assert scans == 1

    signing_secret = "enterprise-webhook-test-secret"
    os.environ["TEST_PROVIDER_WEBHOOK_SECRET"] = signing_secret
    with SessionLocal() as db:
        connection = db.query(EmailConnection).filter(EmailConnection.id == uuid.UUID(connection_id)).one()
        connection.reconciliation_secret_ref = "env://TEST_PROVIDER_WEBHOOK_SECRET"
        attempt = db.query(DeliveryAttempt).filter(DeliveryAttempt.id == attempt.id).one()
        attempt.status = DeliveryStatus.ACCEPTED
        db.commit()
        attempt_id = str(attempt.id)
    event = {
        "event_id": f"ndr-{uuid.uuid4()}",
        "attempt_id": attempt_id,
        "provider_message_id": "gmail-provider-message",
        "status": "bounced",
        "reason_code": "mailbox_not_found",
        "hard_bounce": True,
    }
    body = json.dumps(event, separators=(",", ":")).encode("utf-8")
    signed_at = int(time.time())
    signature = hmac.new(
        signing_secret.encode("utf-8"),
        str(signed_at).encode("ascii") + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    webhook_url = f"/api/v1/provider-webhooks/google_workspace/{connection_id}"
    webhook_headers = {
        "Content-Type": "application/json",
        "X-BreachSim-Timestamp": str(signed_at),
        "X-BreachSim-Signature": f"sha256={signature}",
    }
    reconciled = client.post(webhook_url, content=body, headers=webhook_headers)
    duplicate = client.post(webhook_url, content=body, headers=webhook_headers)
    assert reconciled.status_code == 200, reconciled.text
    assert reconciled.json()["status"] == "bounced"
    assert duplicate.json()["duplicate"] is True
    with SessionLocal() as db:
        assert db.query(DeliverySuppression).filter(DeliverySuppression.active.is_(True)).count() >= 1


def test_live_launch_enforces_rolling_employee_frequency_cap(client, admin_headers):
    employee = client.get("/api/v1/employees", headers=admin_headers).json()[0]
    employee_domain = employee["email"].rsplit("@", 1)[1]
    _verify_domain(client, admin_headers, hostname=employee_domain, purpose="recipient")
    _verify_domain(client, admin_headers, hostname=employee_domain, purpose="sender")
    platform_domain = next(
        domain
        for domain in client.get("/api/v1/orgs/current/domains", headers=admin_headers).json()
        if domain["purpose"] == "landing" and domain["status"] == "active"
    )
    sender = f"frequency-cap@{employee_domain}"
    connection_response = client.post(
        "/api/v1/email-connections",
        headers=admin_headers,
        json={
            "provider": "google_workspace",
            "display_name": "Frequency-cap test",
            "sender_email": sender,
            "sender_name": "Security Awareness",
            "delegated_subject": sender,
            "rate_limit_per_minute": 120,
        },
    )
    connection_id = connection_response.json()["id"]
    with SessionLocal() as db:
        connection = db.query(EmailConnection).filter(EmailConnection.id == uuid.UUID(connection_id)).one()
        organization_id = connection.organization_id
        connection.status = ConnectionStatus.HEALTHY
        connection.authorized_at = datetime.now(timezone.utc)
        policy = db.query(Policy).filter(Policy.organization_id == connection.organization_id).one()
        policy.maximum_frequency_per_employee = 1
        db.query(DeliveryAttempt).filter(
            DeliveryAttempt.employee_id == uuid.UUID(employee["id"])
        ).update(
            {DeliveryAttempt.created_at: datetime.now(timezone.utc) - timedelta(days=31)},
            synchronize_session=False,
        )
        db.query(DeliverySuppression).filter(
            DeliverySuppression.organization_id == connection.organization_id
        ).update({DeliverySuppression.active: False}, synchronize_session=False)
        db.commit()

    scheduled_for = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    first_employee, first_campaign_id = _approved_campaign(
        client,
        admin_headers,
        channel="email",
        sandbox_mode=False,
        landing_domain_id=platform_domain["id"],
        email_connection_id=connection_id,
    )
    first_run = client.post(
        f"/api/v1/campaigns/{first_campaign_id}/runs",
        headers={**admin_headers, "Idempotency-Key": f"frequency-first-{uuid.uuid4()}"},
        json={"scheduled_for": scheduled_for},
    )
    assert first_run.status_code == 202, first_run.text
    assert first_run.json()["queued_count"] == 1
    with SessionLocal() as db:
        first_attempt = db.query(DeliveryAttempt).filter(
            DeliveryAttempt.campaign_run_id == uuid.UUID(first_run.json()["id"])
        ).one()
        assert first_attempt.employee_id == uuid.UUID(first_employee["id"])
        assert first_attempt.sandbox_mode is False
        assert first_attempt.status == DeliveryStatus.QUEUED
        first_created_at = first_attempt.created_at.replace(tzinfo=timezone.utc)
        assert first_created_at >= datetime.now(timezone.utc) - timedelta(days=30)
        assert db.query(Policy).filter(Policy.organization_id == organization_id).one().maximum_frequency_per_employee == 1
        recent_attempt_count = db.query(DeliveryAttempt).filter(
            DeliveryAttempt.employee_id == uuid.UUID(first_employee["id"]),
            DeliveryAttempt.sandbox_mode.is_(False),
            DeliveryAttempt.created_at >= datetime.now(timezone.utc) - timedelta(days=30),
            DeliveryAttempt.status.in_(
                {
                    DeliveryStatus.QUEUED,
                    DeliveryStatus.PROCESSING,
                    DeliveryStatus.ACCEPTED,
                    DeliveryStatus.DELIVERED,
                    DeliveryStatus.UNKNOWN,
                }
            ),
        ).count()
        assert recent_attempt_count == 1

    _, second_campaign_id = _approved_campaign(
        client,
        admin_headers,
        channel="email",
        sandbox_mode=False,
        landing_domain_id=platform_domain["id"],
        email_connection_id=connection_id,
    )
    second_run = client.post(
        f"/api/v1/campaigns/{second_campaign_id}/runs",
        headers={**admin_headers, "Idempotency-Key": f"frequency-second-{uuid.uuid4()}"},
        json={"scheduled_for": scheduled_for},
    )
    assert second_run.status_code == 202, second_run.text
    with SessionLocal() as db:
        attempt = db.query(DeliveryAttempt).filter(
            DeliveryAttempt.campaign_run_id == uuid.UUID(second_run.json()["id"]),
            DeliveryAttempt.employee_id == uuid.UUID(first_employee["id"]),
        ).one()
        assert attempt.status == DeliveryStatus.SUPPRESSED, attempt.preview_payload
        assert attempt.preview_payload["suppression_code"] == "frequency_cap_reached"
    assert second_run.json()["suppressed_count"] == 1


def test_cookie_authenticated_mutations_require_csrf(client):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@breachsim-lab.com", "password": "Admin123!"},
    )
    assert login.status_code == 200
    assert "httponly" in login.headers.get("set-cookie", "").casefold()
    blocked = client.patch(
        "/api/v1/orgs/current",
        json={"privacy_notice": "This mutation must be CSRF protected."},
        headers={"X-CSRF-Token": "incorrect"},
    )
    assert blocked.status_code == 403

    csrf = client.cookies.get("breachsim_csrf")
    allowed = client.patch(
        "/api/v1/orgs/current",
        json={"privacy_notice": "Authorized, privacy-preserving simulations only."},
        headers={"X-CSRF-Token": csrf},
    )
    assert allowed.status_code == 200, allowed.text


def test_google_workspace_setup_exposes_only_non_secret_delegation_values(
    client,
    admin_headers,
    monkeypatch,
):
    sender = "workspace-setup@northwind.example.com"
    payload = {
        "provider": "google_workspace",
        "display_name": "Workspace setup test",
        "sender_email": sender,
        "sender_name": "Security Awareness",
        "delegated_subject": sender,
        "rate_limit_per_minute": 120,
    }
    created = client.post("/api/v1/email-connections", headers=admin_headers, json=payload)
    assert created.status_code == 201, created.text
    duplicate = client.post("/api/v1/email-connections", headers=admin_headers, json=payload)
    assert duplicate.status_code == 409

    monkeypatch.setattr(
        enterprise_routes.secret_store,
        "get",
        lambda _reference: json.dumps(
            {
                "client_id": "123456789012345678901",
                "private_key": "must-never-be-returned",
                "client_email": "delivery@project.iam.gserviceaccount.com",
            }
        ),
    )
    setup = client.get(
        f"/api/v1/email-connections/{created.json()['id']}/google-domain-wide-delegation",
        headers=admin_headers,
    )
    assert setup.status_code == 200, setup.text
    assert setup.json()["oauth_client_id"] == "123456789012345678901"
    assert setup.json()["oauth_scope"] == "https://www.googleapis.com/auth/gmail.send"
    assert setup.json()["delegated_subject"] == sender
    serialized = setup.text
    assert "private_key" not in serialized
    assert "must-never-be-returned" not in serialized


def test_manual_delivery_exclusion_is_opaque_and_enforced(client, admin_headers):
    employee = client.get("/api/v1/employees", headers=admin_headers).json()[0]
    created = client.post(
        "/api/v1/orgs/current/delivery-suppressions",
        headers=admin_headers,
        json={"email": employee["email"], "reason": "administrative", "note": "Approved exclusion"},
    )
    assert created.status_code == 201, created.text
    assert employee["email"] not in created.text
    assert created.json()["reference"].startswith("suppressed-")
    listed = client.get("/api/v1/orgs/current/delivery-suppressions", headers=admin_headers)
    assert listed.status_code == 200
    assert employee["email"] not in listed.text

    _, campaign_id = _approved_campaign(
        client,
        admin_headers,
        channel="email",
        sandbox_mode=True,
    )
    run_response = client.post(
        f"/api/v1/campaigns/{campaign_id}/runs",
        headers={**admin_headers, "Idempotency-Key": f"exclusion-{uuid.uuid4()}"},
        json={},
    )
    assert run_response.status_code == 202, run_response.text
    assert run_response.json()["suppressed_count"] == 1
    with SessionLocal() as db:
        attempt = db.query(DeliveryAttempt).filter(
            DeliveryAttempt.campaign_run_id == uuid.UUID(run_response.json()["id"])
        ).one()
        assert attempt.preview_payload["suppression_code"] == "recipient_suppressed"

    removed = client.delete(
        f"/api/v1/orgs/current/delivery-suppressions/{created.json()['id']}",
        headers=admin_headers,
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["active"] is False


def test_production_public_tokens_are_bound_to_front_door_and_landing_hostname(monkeypatch):
    monkeypatch.setattr(public_routes.settings, "environment", "production")
    monkeypatch.setattr(public_routes.settings, "front_door_id", "expected-front-door-id")

    def request_for(host: str, front_door_id: str = "expected-front-door-id") -> Request:
        return Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "GET",
                "scheme": "https",
                "path": "/q/token",
                "raw_path": b"/q/token",
                "query_string": b"",
                "headers": [
                    (b"host", b"private-origin.example"),
                    (b"x-forwarded-host", host.encode("ascii")),
                    (b"x-azure-fdid", front_door_id.encode("ascii")),
                ],
                "server": ("private-origin.example", 443),
                "client": ("127.0.0.1", 12345),
            }
        )

    public_routes._validate_expected_host(request_for("customer.training.example"), "customer.training.example")
    with pytest.raises(HTTPException) as wrong_host:
        public_routes._validate_expected_host(request_for("other.training.example"), "customer.training.example")
    assert wrong_host.value.status_code == 404
    with pytest.raises(HTTPException) as wrong_edge:
        public_routes._validate_expected_host(
            request_for("customer.training.example", front_door_id="attacker-edge"),
            "customer.training.example",
        )
    assert wrong_edge.value.status_code == 404
