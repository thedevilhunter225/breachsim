from __future__ import annotations

import secrets
import uuid

from app.db.session import SessionLocal
from app.models.entities import Organization, OrganizationDomain, ScimCredential
from app.models.enums import DomainKind, DomainPurpose, VerificationStatus
from app.services.public_tokens import hash_token_secret


def _verify_recipient_domain(client, admin_headers, hostname: str) -> None:
    created = client.post(
        "/api/v1/orgs/current/domains",
        headers=admin_headers,
        json={"hostname": hostname, "purpose": "recipient"},
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    verified = client.post(
        f"/api/v1/orgs/current/domains/{payload['id']}/verify",
        headers=admin_headers,
        json={"proof": payload["verification_value"]},
    )
    assert verified.status_code == 200, verified.text


def test_sso_rejects_common_entra_issuer_and_unverified_domains(client, admin_headers):
    hostname = f"identity-{uuid.uuid4().hex[:10]}.example"
    unverified = client.post(
        "/api/v1/orgs/current/sso-connections",
        headers=admin_headers,
        json={
            "provider": "entra",
            "issuer": "https://login.microsoftonline.com/common/v2.0",
            "client_id": "test-client",
            "client_secret_ref": "kv://test-oidc",
            "allowed_domains": [hostname],
        },
    )
    assert unverified.status_code == 409

    _verify_recipient_domain(client, admin_headers, hostname)
    common = client.post(
        "/api/v1/orgs/current/sso-connections",
        headers=admin_headers,
        json={
            "provider": "entra",
            "issuer": "https://login.microsoftonline.com/common/v2.0",
            "client_id": "test-client",
            "client_secret_ref": "kv://test-oidc",
            "allowed_domains": [hostname],
        },
    )
    assert common.status_code == 422

    tenant_id = uuid.uuid4()
    created = client.post(
        "/api/v1/orgs/current/sso-connections",
        headers=admin_headers,
        json={
            "provider": "entra",
            "issuer": f"https://login.microsoftonline.com/{tenant_id}/v2.0",
            "client_id": "test-client",
            "client_secret_ref": "kv://test-oidc",
            "allowed_domains": [hostname],
        },
    )
    assert created.status_code == 201, created.text


def test_scim_users_and_groups_are_strictly_tenant_scoped(client, admin_headers):
    first_domain = f"first-{uuid.uuid4().hex[:10]}.example"
    _verify_recipient_domain(client, admin_headers, first_domain)
    created_credential = client.post(
        "/api/v1/orgs/current/scim-credentials",
        headers=admin_headers,
        json={"description": "SCIM isolation test"},
    )
    assert created_credential.status_code == 201
    first_token = created_credential.json()["token"]
    first_headers = {"Authorization": f"Bearer {first_token}"}
    first_user = client.post(
        "/api/v1/scim/v2/Users",
        headers=first_headers,
        json={
            "externalId": f"first-{uuid.uuid4()}",
            "userName": f"analyst@{first_domain}",
            "displayName": "First Tenant Analyst",
            "emails": [{"value": f"analyst@{first_domain}", "primary": True}],
            "active": True,
        },
    )
    assert first_user.status_code == 201, first_user.text

    second_slug = f"isolation-{uuid.uuid4().hex[:12]}"
    second_domain = f"second-{uuid.uuid4().hex[:10]}.example"
    second_token = secrets.token_urlsafe(36)
    db = SessionLocal()
    try:
        second_org = Organization(name="Isolation Tenant", slug=second_slug, timezone="UTC")
        db.add(second_org)
        db.flush()
        db.add(
            OrganizationDomain(
                organization_id=second_org.id,
                hostname=second_domain,
                purpose=DomainPurpose.RECIPIENT,
                kind=DomainKind.CUSTOM,
                status=VerificationStatus.ACTIVE,
                is_primary=True,
            )
        )
        db.add(
            ScimCredential(
                organization_id=second_org.id,
                token_prefix=second_token[:12],
                token_hash=hash_token_secret(second_token),
                description="Second tenant SCIM",
            )
        )
        db.commit()
    finally:
        db.close()

    second_headers = {"Authorization": f"Bearer {second_token}"}
    second_user = client.post(
        "/api/v1/scim/v2/Users",
        headers=second_headers,
        json={
            "externalId": f"second-{uuid.uuid4()}",
            "userName": f"analyst@{second_domain}",
            "displayName": "Second Tenant Analyst",
            "emails": [{"value": f"analyst@{second_domain}", "primary": True}],
            "active": True,
        },
    )
    assert second_user.status_code == 201, second_user.text

    assert client.get(f"/api/v1/scim/v2/Users/{first_user.json()['id']}", headers=second_headers).status_code == 404
    assert client.get(f"/api/v1/scim/v2/Users/{second_user.json()['id']}", headers=first_headers).status_code == 404

    group = client.post(
        "/api/v1/scim/v2/Groups",
        headers=first_headers,
        json={
            "externalId": f"group-{uuid.uuid4()}",
            "displayName": "Security Team",
            "members": [{"value": first_user.json()["id"]}],
        },
    )
    assert group.status_code == 201, group.text
    assert client.get(f"/api/v1/scim/v2/Groups/{group.json()['id']}", headers=second_headers).status_code == 404
