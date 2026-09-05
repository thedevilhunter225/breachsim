from __future__ import annotations

from app.core.security import LEGACY_PASSWORD_ITERATIONS, hash_password
from app.db.session import SessionLocal
from app.models.entities import User


def test_admin_login_and_me(client):
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@breachsim-lab.com", "password": "Admin123!"},
        headers={"X-BreachSim-API-Client": "bearer"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert "admin" in me_response.json()["user"]["roles"]


def test_logout_revokes_server_session(client):
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@breachsim-lab.com", "password": "Admin123!"},
        headers={"X-BreachSim-API-Client": "bearer"},
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_legacy_password_hash_is_upgraded_on_login(client):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "admin@breachsim-lab.com").first()
        user.password_hash = hash_password("Admin123!", iterations=LEGACY_PASSWORD_ITERATIONS)
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@breachsim-lab.com", "password": "Admin123!"},
    )
    assert response.status_code == 200

    db = SessionLocal()
    try:
        upgraded = db.query(User).filter(User.email == "admin@breachsim-lab.com").first()
        assert upgraded.password_hash.startswith("pbkdf2_sha256$600000$")
    finally:
        db.close()


def test_browser_login_never_returns_bearer_value(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@breachsim-lab.com", "password": "Admin123!"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"] is None
    assert "httponly" in response.headers.get("set-cookie", "").casefold()
    assert client.get("/api/v1/auth/me").json()["access_token"] is None


def test_auditor_cannot_launch_campaign(client, auditor_headers):
    campaign_id = client.get("/api/v1/campaigns", headers=auditor_headers).json()[0]["id"]
    response = client.post(f"/api/v1/campaigns/{campaign_id}/launch-sandbox", headers=auditor_headers)
    assert response.status_code == 403
