from __future__ import annotations


def test_admin_login_and_me(client):
    login_response = client.post("/api/v1/auth/login", json={"email": "admin@breachsim-lab.com", "password": "Admin123!"})
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert "admin" in me_response.json()["user"]["roles"]


def test_auditor_cannot_launch_campaign(client, auditor_headers):
    campaign_id = client.get("/api/v1/campaigns", headers=auditor_headers).json()[0]["id"]
    response = client.post(f"/api/v1/campaigns/{campaign_id}/launch-sandbox", headers=auditor_headers)
    assert response.status_code == 403
