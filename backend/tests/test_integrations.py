from __future__ import annotations


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
