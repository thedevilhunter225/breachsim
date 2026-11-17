"""Mandatory MFA for administrators outside production, and the first-sign-in setup step."""

from __future__ import annotations

import uuid

import pyotp
import pytest

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.entities import Role, User, UserRoleLink
from app.models.enums import UserRole

PASSWORD = "Mfa-Setup-Test-Passw0rd!"
LOGIN = "/api/v1/auth/login"
SETUP = "/api/v1/auth/mfa/setup"
BEARER = {"X-BreachSim-API-Client": "bearer"}


@pytest.fixture()
def temporary_admin():
    """A throwaway admin in the seeded tenant, so the shared seeded admin never gains MFA.

    It is deactivated afterwards: other tests count the tenant's active administrators.
    """
    email = f"mfa-admin-{uuid.uuid4().hex[:8]}@example.com"
    db = SessionLocal()
    try:
        organization_id = db.query(User).filter(User.email == "admin@breachsim-lab.com").one().organization_id
        user = User(organization_id=organization_id, email=email, full_name="MFA Admin", password_hash=hash_password(PASSWORD))
        db.add(user)
        db.flush()
        db.add(UserRoleLink(user_id=user.id, role_id=db.query(Role).filter(Role.name == UserRole.ADMIN).one().id))
        db.commit()
        user_id = user.id
    finally:
        db.close()

    yield email

    db = SessionLocal()
    try:
        db.query(User).filter(User.id == user_id).update({User.is_active: False})
        db.commit()
    finally:
        db.close()


def _sign_in(client, email: str, code: str | None = None, password: str = PASSWORD):
    body = {"email": email, "password": password}
    if code is not None:
        body["mfa_code"] = code
    return client.post(LOGIN, json=body, headers=BEARER)


def _stored(email: str) -> User:
    db = SessionLocal()
    try:
        return db.query(User).filter(User.email == email).one()
    finally:
        db.close()


def test_mfa_is_optional_for_administrators_by_default(client, temporary_admin):
    assert _sign_in(client, temporary_admin).status_code == 200
    refused = client.post(SETUP, json={"email": temporary_admin, "password": PASSWORD})
    assert refused.status_code == 409, "the setup route exists only for accounts that are required to enrol"


def test_requiring_mfa_stops_password_only_sign_in_for_administrators(client, monkeypatch, temporary_admin):
    monkeypatch.setattr(settings, "require_privileged_mfa", True)

    refused = _sign_in(client, temporary_admin)
    assert refused.status_code == 403
    assert refused.json()["detail"] == {
        "code": "mfa_setup_required",
        "message": "MFA enrollment is required for this account",
    }
    assert "set-cookie" not in refused.headers, "no session is issued before MFA is in place"

    # Roles that cannot approve or administer are not affected.
    manager = client.post(LOGIN, json={"email": "manager@breachsim-lab.com", "password": "Manager123!"})
    assert manager.status_code == 200
    not_eligible = client.post(SETUP, json={"email": "manager@breachsim-lab.com", "password": "Manager123!"})
    assert not_eligible.status_code == 409


def test_first_sign_in_sets_up_mfa_and_the_first_code_switches_it_on(client, monkeypatch, admin_headers, temporary_admin):
    monkeypatch.setattr(settings, "require_privileged_mfa", True)

    assert client.post(SETUP, json={"email": temporary_admin, "password": "not-the-password"}).status_code == 401
    assert client.post(SETUP, json={"email": "nobody@example.com", "password": PASSWORD}).status_code == 401

    setup = client.post(SETUP, json={"email": temporary_admin, "password": PASSWORD})
    assert setup.status_code == 200, setup.text
    material = setup.json()
    assert len(material["recovery_codes"]) == 10
    assert material["provisioning_uri"].startswith("otpauth://totp/")
    assert material["qr_image_data_url"].startswith("data:image/png;base64,")
    assert _stored(temporary_admin).mfa_enabled is False, "issuing the secret switches nothing on"

    # Until the authenticator proves it works, the account is still waiting for setup.
    assert _sign_in(client, temporary_admin).status_code == 403
    assert _sign_in(client, temporary_admin, "000000").status_code == 403
    assert _sign_in(client, temporary_admin, material["recovery_codes"][0]).status_code == 403
    assert _stored(temporary_admin).mfa_enabled is False

    confirmed = _sign_in(client, temporary_admin, pyotp.TOTP(material["secret"]).now())
    assert confirmed.status_code == 200, confirmed.text
    assert "admin" in confirmed.json()["user"]["roles"]
    assert _stored(temporary_admin).mfa_enabled is True

    # From here on it is an ordinary MFA account.
    assert _sign_in(client, temporary_admin).status_code == 401
    assert _sign_in(client, temporary_admin, "000000").status_code == 401
    assert _sign_in(client, temporary_admin, material["recovery_codes"][0]).status_code == 200
    assert _sign_in(client, temporary_admin, material["recovery_codes"][0]).status_code == 401, "recovery codes are single use"
    assert client.post(SETUP, json={"email": temporary_admin, "password": PASSWORD}).status_code == 409

    actions = [row["action"] for row in client.get("/api/v1/audit-logs", headers=admin_headers).json()]
    assert "user.mfa_enabled" in actions
    assert client.get("/api/v1/audit-logs/verify", headers=admin_headers).json()["valid"] is True


def test_an_interrupted_setup_can_be_started_again(client, monkeypatch, temporary_admin):
    monkeypatch.setattr(settings, "require_privileged_mfa", True)

    first = client.post(SETUP, json={"email": temporary_admin, "password": PASSWORD}).json()
    second = client.post(SETUP, json={"email": temporary_admin, "password": PASSWORD}).json()
    assert first["secret"] != second["secret"]

    stale = _sign_in(client, temporary_admin, pyotp.TOTP(first["secret"]).now())
    assert stale.status_code == 403, "only the latest secret can finish setup"
    assert _sign_in(client, temporary_admin, pyotp.TOTP(second["secret"]).now()).status_code == 200


def test_enrolled_accounts_keep_using_mfa_when_the_requirement_is_off(client, monkeypatch, temporary_admin):
    monkeypatch.setattr(settings, "require_privileged_mfa", True)
    material = client.post(SETUP, json={"email": temporary_admin, "password": PASSWORD}).json()
    assert _sign_in(client, temporary_admin, pyotp.TOTP(material["secret"]).now()).status_code == 200

    monkeypatch.setattr(settings, "require_privileged_mfa", False)
    assert _sign_in(client, temporary_admin).status_code == 401
    assert _sign_in(client, temporary_admin, pyotp.TOTP(material["secret"]).now()).status_code == 200


def test_readiness_covers_redis_whenever_sign_in_is_throttled(client, monkeypatch):
    ready = client.get("/health/ready")
    assert ready.status_code == 200 and "redis" not in ready.json()["checks"]

    # The limiter fails closed without Redis, so the instance must not report ready.
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:1/0")
    not_ready = client.get("/health/ready")
    assert not_ready.status_code == 503
    assert not_ready.json()["checks"] == {"database": "ok", "redis": "unavailable"}
