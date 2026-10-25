from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from app.services import email_integration, sms_integration


def test_update_email_integration(client, admin_headers):
    response = client.put(
        "/api/v1/integrations/email",
        headers=admin_headers,
        json={
            "email_provider_enabled": True,
            "email_provider_mode": "lab",
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_username": "admin@breachsim-lab.com",
            "smtp_password": "app-password",
            "smtp_from_email": "admin@breachsim-lab.com",
            "smtp_sender_name": "BreachSim Lab",
            "smtp_recipient_allowlist": ["sender@example.com"],
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["email_provider_enabled"] is True
    assert payload["email_provider_mode"] == "lab"
    assert payload["has_password"] is True


def test_lab_email_builds_inline_related_image(monkeypatch):
    captured = {}

    class FakeSmtp:
        def __init__(self, host, port, timeout):
            captured["connection"] = (host, port, timeout)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def starttls(self):
            captured["tls"] = True

        def login(self, username, password):
            captured["login"] = (username, password)

        def send_message(self, message):
            captured["message"] = message

    monkeypatch.setattr(email_integration.smtplib, "SMTP", FakeSmtp)
    org = SimpleNamespace(
        email_provider_enabled=True,
        email_provider_mode="lab",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="sender@example.com",
        smtp_password="app-password",
        smtp_from_email="sender@example.com",
        smtp_sender_name="Security Desk",
        smtp_recipient_allowlist=["recipient@example.com"],
    )

    email_integration.send_lab_email(
        org=org,
        recipient="recipient@example.com",
        subject="Security review",
        body_text="Review this notice.",
        cta_url="https://training.example/qr/token",
        html_body='<html><body><img src="cid:security-qr"></body></html>',
        inline_images=[(None, b"png-bytes", "image", "png", "security-qr@example.test")],
    )

    message = captured["message"]
    inline_part = next(part for part in message.walk() if part.get_content_type() == "image/png")
    assert inline_part["Content-ID"] == "<security-qr@example.test>"
    assert inline_part.get_content_disposition() == "inline"
    assert inline_part.get_filename() is None
    assert captured["tls"] is True


def test_twilio_lab_adapter_sends_only_to_an_allowlisted_number(monkeypatch):
    captured: dict = {}

    def fake_post(url, *, auth, data, timeout):
        captured.update({"url": url, "auth": auth, "data": data, "timeout": timeout})
        return httpx.Response(201, request=httpx.Request("POST", url), json={"sid": "SMsynthetic"})

    monkeypatch.setattr(sms_integration.httpx, "post", fake_post)
    org = SimpleNamespace(
        sms_provider_enabled=True,
        sms_provider_mode="lab",
        sms_api_base_url="https://api.twilio.com/2010-04-01",
        sms_account_sid="ACsynthetic",
        sms_auth_token="test-only-token",
        sms_from_number="+15550001111",
        sms_recipient_allowlist=["+15550002222"],
    )

    with pytest.raises(HTTPException, match="not in the lab SMS allowlist"):
        sms_integration.send_lab_sms(
            org=org,
            recipient="+15550003333",
            body_text="Synthetic test",
            cta_url="https://training.example.test/only-for-testing",
        )
    assert captured == {}

    message_id = sms_integration.send_lab_sms(
        org=org,
        recipient="+1 (555) 000-2222",
        body_text="Synthetic test",
        cta_url="https://training.example.test/only-for-testing",
    )
    assert message_id == "SMsynthetic"
    assert captured["url"].endswith("/Accounts/ACsynthetic/Messages.json")
    assert captured["data"]["To"] == "+15550002222"
    assert captured["auth"] == ("ACsynthetic", "test-only-token")


def test_android_demo_sends_fixed_link_free_sms_only_to_allowlist(monkeypatch):
    captured: dict = {}

    def fake_post(url, *, auth, json, timeout):
        captured.update({"url": url, "auth": auth, "json": json, "timeout": timeout})
        return httpx.Response(202, request=httpx.Request("POST", url), json={"id": "demo-123", "state": "Pending"})

    monkeypatch.setattr(sms_integration.httpx, "post", fake_post)
    org = SimpleNamespace(
        sms_provider_enabled=True,
        sms_provider_mode="android_demo",
        sms_api_base_url="http://192.168.1.20:8080",
        sms_account_sid="phone-user",
        sms_auth_token="test-only-password",
        sms_recipient_allowlist=["+923001234567"],
    )

    with pytest.raises(HTTPException, match="not in the lab SMS allowlist"):
        sms_integration.send_android_demo_sms(org=org, recipient="+923009999999")
    assert captured == {}

    message_id = sms_integration.send_android_demo_sms(org=org, recipient="+923001234567")
    assert message_id == "demo-123"
    assert captured["url"] == "http://192.168.1.20:8080/message"
    assert captured["auth"] == ("phone-user", "test-only-password")
    assert captured["json"] == {
        "textMessage": {"text": sms_integration.ANDROID_DEMO_MESSAGE},
        "phoneNumbers": ["+923001234567"],
    }
    assert "http" not in captured["json"]["textMessage"]["text"]


@pytest.mark.parametrize("url", [
    "https://api.example.com:8080",
    "http://127.0.0.1:8080",
    "http://169.254.169.254:8080",
    "http://192.168.1.20:8080/other",
    "http://192.168.1.20:80",
])
def test_android_demo_rejects_non_phone_gateway_urls(monkeypatch, url):
    def unexpected_post(*args, **kwargs):
        pytest.fail("Gateway must not be called for an unsafe URL")

    monkeypatch.setattr(sms_integration.httpx, "post", unexpected_post)
    org = SimpleNamespace(
        sms_provider_enabled=True,
        sms_provider_mode="android_demo",
        sms_api_base_url=url,
        sms_account_sid="phone-user",
        sms_auth_token="test-only-password",
        sms_recipient_allowlist=["+923001234567"],
    )
    with pytest.raises(HTTPException, match="Android gateway URL"):
        sms_integration.send_android_demo_sms(org=org, recipient="+923001234567")


def test_android_demo_endpoint_is_admin_only_and_queues_no_link(client, admin_headers, manager_headers, monkeypatch):
    captured: dict = {}

    def fake_post(url, *, auth, json, timeout):
        captured.update({"url": url, "json": json})
        return httpx.Response(202, request=httpx.Request("POST", url), json={"id": "demo-endpoint-1"})

    monkeypatch.setattr(sms_integration.httpx, "post", fake_post)
    response = client.put(
        "/api/v1/integrations/sms",
        headers=admin_headers,
        json={
            "sms_provider_enabled": True,
            "sms_provider_mode": "android_demo",
            "sms_api_base_url": "http://192.168.1.20:8080",
            "sms_account_sid": "phone-user",
            "sms_auth_token": "test-only-password",
            "sms_recipient_allowlist": ["+923001234567"],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["has_auth_token"] is True
    assert "sms_auth_token" not in response.json()

    denied = client.post(
        "/api/v1/integrations/sms/demo-send",
        headers=manager_headers,
        json={"recipient": "+923001234567"},
    )
    assert denied.status_code == 403
    assert captured == {}

    response = client.post(
        "/api/v1/integrations/sms/demo-send",
        headers=admin_headers,
        json={"recipient": "+923001234567"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"message_id": "demo-endpoint-1", "status": "queued"}
    assert captured["json"]["phoneNumbers"] == ["+923001234567"]
    assert "http" not in captured["json"]["textMessage"]["text"]

    for _ in range(3):
        response = client.post(
            "/api/v1/integrations/sms/demo-send",
            headers=admin_headers,
            json={"recipient": "+923001234567"},
        )
        assert response.status_code == 200
    fifth = client.post(
        "/api/v1/integrations/sms/demo-send",
        headers=admin_headers,
        json={"recipient": "+923001234567"},
    )
    assert fifth.status_code == 429
