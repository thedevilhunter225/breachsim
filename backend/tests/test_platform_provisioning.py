from __future__ import annotations

import uuid

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.entities import Organization, Role, User, UserRoleLink
from app.models.enums import UserRole
from tests.conftest import login

STRONG_PASSWORD = "Provision-Test-Passw0rd!"


def _platform_operator(client) -> dict[str, str]:
    """A platform operator in its own organization, as the production bootstrap creates."""
    email = f"platform-{uuid.uuid4().hex[:8]}@breachsim-lab.com"
    db = SessionLocal()
    try:
        org = Organization(name="BreachSim Platform", slug=f"platform-{uuid.uuid4().hex[:10]}", timezone="UTC")
        db.add(org)
        db.flush()
        role = db.query(Role).filter(Role.name == UserRole.PLATFORM_OPERATOR).first()
        if role is None:
            role = Role(name=UserRole.PLATFORM_OPERATOR)
            db.add(role)
            db.flush()
        user = User(organization_id=org.id, email=email, full_name="Platform Operator", password_hash=hash_password(STRONG_PASSWORD))
        db.add(user)
        db.flush()
        db.add(UserRoleLink(user_id=user.id, role_id=role.id))
        db.commit()
    finally:
        db.close()
    return login(client, email, STRONG_PASSWORD)


def _provision(client, operator_headers, slug: str, admin_email: str):
    return client.post(
        "/api/v1/platform/organizations",
        headers=operator_headers,
        json={"name": "Contoso Bank", "slug": slug, "timezone": "Asia/Karachi", "admin_email": admin_email, "admin_name": "Contoso Admin"},
    )


def test_only_platform_operators_can_provision_tenants(client, admin_headers):
    assert client.get("/api/v1/platform/organizations", headers=admin_headers).status_code == 403
    assert _provision(client, admin_headers, f"blocked-{uuid.uuid4().hex[:8]}", "x@contoso.example").status_code == 403


def test_tenant_onboarding_from_provisioning_to_first_admin_sign_in(client):
    operator = _platform_operator(client)
    slug = f"contoso-{uuid.uuid4().hex[:8]}"
    admin_email = f"admin-{uuid.uuid4().hex[:6]}@contoso.example"

    created = _provision(client, operator, slug, admin_email)
    assert created.status_code == 201, created.text
    tenant = created.json()
    assert tenant["invite_url"].startswith("http")
    assert tenant["onboarding"]["branding"] is True
    assert tenant["onboarding"]["email_connection"] is False

    assert _provision(client, operator, slug, f"other-{admin_email}").status_code == 409, "duplicate slug"
    assert _provision(client, operator, f"{slug}-2", admin_email).status_code == 409, "duplicate admin email"
    assert any(row["id"] == tenant["id"] for row in client.get("/api/v1/platform/organizations", headers=operator).json())

    token = tenant["invite_token"]
    weak = client.post("/api/v1/platform/invitations/accept", json={"token": token, "full_name": "Contoso Admin", "password": "weakweakweakweak"})
    assert weak.status_code == 422
    accepted = client.post(
        "/api/v1/platform/invitations/accept",
        json={"token": token, "full_name": "Contoso Admin", "password": STRONG_PASSWORD},
    )
    assert accepted.status_code == 201, accepted.text
    recovery_code = accepted.json()["mfa_recovery_codes"][0]
    reused = client.post(
        "/api/v1/platform/invitations/accept",
        json={"token": token, "full_name": "Contoso Admin", "password": STRONG_PASSWORD},
    )
    assert reused.status_code == 404, "an invitation works once"

    without_mfa = client.post("/api/v1/auth/login", json={"email": admin_email, "password": STRONG_PASSWORD})
    assert without_mfa.status_code == 401, "invited administrators are enrolled in MFA"
    signed_in = client.post(
        "/api/v1/auth/login",
        json={"email": admin_email, "password": STRONG_PASSWORD, "mfa_code": recovery_code},
        headers={"X-BreachSim-API-Client": "bearer"},
    )
    assert signed_in.status_code == 200, signed_in.text
    tenant_admin = {"Authorization": f"Bearer {signed_in.json()['access_token']}"}
    assert client.get("/api/v1/employees", headers=tenant_admin).json() == [], "a new tenant starts empty"

    suspended = client.post(f"/api/v1/platform/organizations/{tenant['id']}/suspend", headers=operator)
    assert suspended.status_code == 200
    assert suspended.json()["suspended_at"] is not None
    assert client.get("/api/v1/employees", headers=tenant_admin).status_code in {401, 403}

    reactivated = client.post(f"/api/v1/platform/organizations/{tenant['id']}/reactivate", headers=operator)
    assert reactivated.json()["suspended_at"] is None
    assert client.get("/api/v1/employees", headers=tenant_admin).status_code == 200

    assert client.post(f"/api/v1/platform/organizations/{uuid.uuid4()}/suspend", headers=operator).status_code == 404
    missing_domain = client.post(
        f"/api/v1/platform/organizations/{tenant['id']}/domains/{uuid.uuid4()}/activate-edge", headers=operator
    )
    assert missing_domain.status_code == 404


def test_invalid_invitation_tokens_are_refused(client):
    malformed = client.post(
        "/api/v1/platform/invitations/accept",
        json={"token": "not-a-two-part-token-at-all", "full_name": "Nobody", "password": STRONG_PASSWORD},
    )
    assert malformed.status_code == 404
    forged = client.post(
        "/api/v1/platform/invitations/accept",
        json={"token": f"{uuid.uuid4().hex[:16]}.{uuid.uuid4().hex}", "full_name": "Nobody", "password": STRONG_PASSWORD},
    )
    assert forged.status_code == 404
