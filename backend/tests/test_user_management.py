from __future__ import annotations

from app.db.session import SessionLocal
from app.models.entities import Organization, Role, User, UserRoleLink
from app.models.enums import ReportingIdentityMode, UserRole


def test_admin_can_create_operator_and_operator_can_login(client, admin_headers):
    response = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": "security.operator@example.com",
            "full_name": "Security Operator",
            "password": "UniqueOperator42!",
            "roles": ["auditor"],
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["roles"] == ["auditor"]

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "security.operator@example.com", "password": "UniqueOperator42!"},
    )
    assert login.status_code == 200


def test_non_admin_cannot_manage_operators(client, manager_headers):
    assert client.get("/api/v1/users", headers=manager_headers).status_code == 403


def test_password_reset_revokes_sessions_and_allows_new_password(client, admin_headers):
    created = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": "reset.target@example.com",
            "full_name": "Reset Target",
            "password": "InitialPassword42!",
            "roles": ["campaign_manager"],
        },
    ).json()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "reset.target@example.com", "password": "InitialPassword42!"},
        headers={"X-BreachSim-API-Client": "bearer"},
    ).json()
    old_headers = {"Authorization": f"Bearer {login['access_token']}"}

    reset = client.post(
        f"/api/v1/users/{created['id']}/reset-password",
        headers=admin_headers,
        json={"new_password": "ReplacementPassword84!"},
    )
    assert reset.status_code == 200
    assert client.get("/api/v1/auth/me", headers=old_headers).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "reset.target@example.com", "password": "ReplacementPassword84!"},
    ).status_code == 200


def test_two_active_administrators_are_preserved(client, admin_headers):
    users = client.get("/api/v1/users", headers=admin_headers).json()
    reviewer = next(user for user in users if user["email"] == "reviewer@breachsim-lab.com")
    response = client.patch(
        f"/api/v1/users/{reviewer['id']}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert response.status_code == 400
    assert "two active administrators" in response.text


def test_named_risk_recommendations_require_dedicated_identity_role(client, admin_headers):
    pseudonymous = client.get("/api/v1/analytics/risk-intelligence", headers=admin_headers)
    assert pseudonymous.status_code == 200
    recommendations = pseudonymous.json()["adaptive_recommendations"]
    assert recommendations
    assert recommendations[0]["employee_id"].startswith("anon-")
    assert recommendations[0]["employee_name"].startswith("Employee ")
    assert recommendations[0]["employee_email"] == ""

    db = SessionLocal()
    link_id = None
    organization_id = None
    try:
        admin = db.query(User).filter(User.email == "admin@breachsim-lab.com").one()
        organization_id = admin.organization_id
        organization = db.query(Organization).filter(Organization.id == organization_id).one()
        organization.reporting_identity_mode = ReportingIdentityMode.NAMED
        role = db.query(Role).filter(Role.name == UserRole.RISK_IDENTITY_VIEWER).one()
        link = UserRoleLink(user_id=admin.id, role_id=role.id)
        db.add(link)
        db.commit()
        db.refresh(link)
        link_id = link.id
    finally:
        db.close()

    try:
        named = client.get("/api/v1/analytics/risk-intelligence", headers=admin_headers)
        assert named.status_code == 200
        recommendation = named.json()["adaptive_recommendations"][0]
        assert not recommendation["employee_id"].startswith("anon-")
        assert "@" in recommendation["employee_email"]
    finally:
        db = SessionLocal()
        try:
            if link_id:
                link = db.query(UserRoleLink).filter(UserRoleLink.id == link_id).first()
                if link:
                    db.delete(link)
            if organization_id:
                organization = db.query(Organization).filter(Organization.id == organization_id).one()
                organization.reporting_identity_mode = ReportingIdentityMode.PSEUDONYMOUS
            db.commit()
        finally:
            db.close()
