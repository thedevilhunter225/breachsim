"""Platform operator is the one cross-tenant role, so a tenant must not be able to mint it."""

from __future__ import annotations

import uuid

from app.api.routes.sso import roles_from_group_claims
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.entities import Organization, Role, SsoConnection, User, UserRoleLink
from app.models.enums import ConnectionStatus, UserRole
from tests.conftest import login

PASSWORD = "Escalation-Test-Passw0rd!"


def _role(db, name: UserRole) -> Role:
    role = db.query(Role).filter(Role.name == name).first()
    if role is None:
        role = Role(name=name)
        db.add(role)
        db.flush()
    return role


def _platform_organization(*extra_admins: str) -> dict:
    """An organization shaped like the production bootstrap: one admin who is also the
    platform operator, plus any number of ordinary admins."""
    suffix = uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        org = Organization(name="BreachSim Platform", slug=f"platform-{suffix}", timezone="UTC")
        db.add(org)
        db.flush()

        def add_user(label: str, roles: tuple[UserRole, ...]) -> tuple[str, str]:
            email = f"{label}-{suffix}@breachsim-lab.com"
            user = User(organization_id=org.id, email=email, full_name=label.title(), password_hash=hash_password(PASSWORD))
            db.add(user)
            db.flush()
            for role in roles:
                db.add(UserRoleLink(user_id=user.id, role_id=_role(db, role).id))
            return email, str(user.id)

        operator_email, operator_id = add_user("operator", (UserRole.ADMIN, UserRole.PLATFORM_OPERATOR))
        admins = [add_user(label, (UserRole.ADMIN,)) for label in extra_admins]
        db.commit()
        return {
            "organization_id": org.id,
            "operator_email": operator_email,
            "operator_id": operator_id,
            "admins": admins,
        }
    finally:
        db.close()


def _own_id(client, headers) -> str:
    return client.get("/api/v1/auth/me", headers=headers).json()["user"]["id"]


def test_tenant_admin_cannot_create_a_platform_operator(client, admin_headers):
    for roles in (["platform_operator"], ["auditor", "platform_operator"]):
        email = f"minted-{uuid.uuid4().hex[:8]}@example.com"
        response = client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={"email": email, "full_name": "Minted Operator", "password": PASSWORD, "roles": roles},
        )
        assert response.status_code == 403, response.text
        assert all(user["email"] != email for user in client.get("/api/v1/users", headers=admin_headers).json())


def test_tenant_admin_cannot_grant_itself_platform_operator(client, admin_headers):
    own_id = _own_id(client, admin_headers)
    response = client.patch(
        f"/api/v1/users/{own_id}",
        headers=admin_headers,
        json={"roles": ["admin", "platform_operator"]},
    )
    assert response.status_code == 403, response.text

    me = client.get("/api/v1/auth/me", headers=admin_headers).json()["user"]
    assert "platform_operator" not in me["roles"]
    assert client.get("/api/v1/platform/organizations", headers=admin_headers).status_code == 403


def test_tenant_admin_cannot_map_an_sso_group_to_platform_operator(client, admin_headers):
    response = client.post(
        "/api/v1/orgs/current/sso-connections",
        headers=admin_headers,
        json={
            "provider": "entra",
            "issuer": f"https://login.microsoftonline.com/{uuid.uuid4()}/v2.0",
            "client_id": "client-id",
            "client_secret_ref": "env://SSO_CLIENT_SECRET",
            "allowed_domains": ["northwind.example.com"],
            "group_role_mappings": {"platform-team": "platform_operator"},
        },
    )
    assert response.status_code == 403, response.text
    assert "platform operator" in response.json()["detail"]


def test_platform_operator_can_grant_the_role_inside_its_own_organization(client):
    platform = _platform_organization()
    operator = login(client, platform["operator_email"], PASSWORD)
    email = f"second-operator-{uuid.uuid4().hex[:8]}@breachsim-lab.com"

    created = client.post(
        "/api/v1/users",
        headers=operator,
        json={"email": email, "full_name": "Second Operator", "password": PASSWORD, "roles": ["platform_operator"]},
    )
    assert created.status_code == 201, created.text
    assert created.json()["roles"] == ["platform_operator"]

    second_operator = login(client, email, PASSWORD)
    assert client.get("/api/v1/platform/organizations", headers=second_operator).status_code == 200


def test_only_a_platform_operator_can_change_a_platform_operator_account(client):
    platform = _platform_organization("plain-admin", "spare-admin")
    plain_admin = login(client, platform["admins"][0][0], PASSWORD)
    operator_id = platform["operator_id"]

    reset = client.post(
        f"/api/v1/users/{operator_id}/reset-password",
        headers=plain_admin,
        json={"new_password": "Replacement-Passw0rd!!"},
    )
    assert reset.status_code == 403, "an ordinary admin could otherwise sign in as the operator"
    for change in ({"roles": ["admin"]}, {"is_active": False}, {"full_name": "Renamed"}):
        assert client.patch(f"/api/v1/users/{operator_id}", headers=plain_admin, json=change).status_code == 403, change

    # The original password still works, so nothing above took effect.
    operator = login(client, platform["operator_email"], PASSWORD)
    assert client.get("/api/v1/platform/organizations", headers=operator).status_code == 200
    # Ordinary accounts in the same organization are still managed as before.
    spare_id = platform["admins"][1][1]
    renamed = client.patch(f"/api/v1/users/{spare_id}", headers=plain_admin, json={"full_name": "Spare Renamed"})
    assert renamed.status_code == 200, renamed.text


def test_sso_group_mapping_cannot_introduce_platform_operator(client, admin_headers):
    """Covers a mapping stored before the connection API refused it."""
    mappings = {"platform-team": "platform_operator", "security-team": "auditor"}
    groups = {"platform-team", "security-team", "unmapped"}
    platform = _platform_organization()

    db = SessionLocal()
    try:
        tenant_org_id = db.query(User).filter(User.email == "admin@breachsim-lab.com").one().organization_id

        def connection_for(organization_id) -> SsoConnection:
            return SsoConnection(
                organization_id=organization_id,
                provider="entra",
                issuer="https://login.microsoftonline.com/tenant/v2.0",
                client_id="client-id",
                client_secret_ref="env://SSO_CLIENT_SECRET",
                allowed_domains=["northwind.example.com"],
                group_role_mappings=mappings,
                status=ConnectionStatus.PENDING,
            )

        assert roles_from_group_claims(db, connection_for(tenant_org_id), groups) == {UserRole.AUDITOR}
        assert roles_from_group_claims(db, connection_for(platform["organization_id"]), groups) == {
            UserRole.AUDITOR,
            UserRole.PLATFORM_OPERATOR,
        }
        assert roles_from_group_claims(db, connection_for(tenant_org_id), {"unmapped"}) == set()
    finally:
        db.close()
