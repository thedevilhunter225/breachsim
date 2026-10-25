from __future__ import annotations

import uuid

from tests.test_enterprise_identity import _verify_recipient_domain


def _scim(client, admin_headers) -> tuple[dict[str, str], str]:
    domain = f"scim-{uuid.uuid4().hex[:10]}.example"
    _verify_recipient_domain(client, admin_headers, domain)
    credential = client.post(
        "/api/v1/orgs/current/scim-credentials",
        headers=admin_headers,
        json={"description": "SCIM lifecycle test"},
    )
    assert credential.status_code == 201, credential.text
    return {"Authorization": f"Bearer {credential.json()['token']}"}, domain


def _user(client, headers, domain: str, local: str, **extra) -> dict:
    response = client.post(
        "/api/v1/scim/v2/Users",
        headers=headers,
        json={
            "externalId": f"{local}-{uuid.uuid4()}",
            "userName": f"{local}@{domain}",
            "displayName": local.title(),
            "emails": [{"value": f"{local}@{domain}", "primary": True}],
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_scim_requires_a_valid_bearer_token(client):
    assert client.get("/api/v1/scim/v2/Users").status_code == 401
    assert client.get("/api/v1/scim/v2/Users", headers={"Authorization": "Bearer not-a-real-token"}).status_code == 401


def test_scim_user_lifecycle_from_joiner_to_leaver(client, admin_headers):
    headers, domain = _scim(client, admin_headers)
    user = _user(client, headers, domain, "joiner", title="Analyst")
    assert user["active"] is True

    duplicate = client.post(
        "/api/v1/scim/v2/Users",
        headers=headers,
        json={"userName": f"joiner@{domain}", "emails": [{"value": f"joiner@{domain}", "primary": True}]},
    )
    assert duplicate.status_code == 409
    outside = client.post(
        "/api/v1/scim/v2/Users",
        headers=headers,
        json={"emails": [{"value": "someone@unverified.example", "primary": True}]},
    )
    assert outside.status_code == 409
    assert client.post("/api/v1/scim/v2/Users", headers=headers, json={"emails": []}).status_code == 400

    listed = client.get("/api/v1/scim/v2/Users", headers=headers, params={"filter": f'userName eq "joiner@{domain}"'})
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()["Resources"]] == [user["id"]]
    assert client.get(f"/api/v1/scim/v2/Users/{user['id']}", headers=headers).json()["userName"] == f"joiner@{domain}"

    replaced = client.put(
        f"/api/v1/scim/v2/Users/{user['id']}",
        headers=headers,
        json={
            "displayName": "Joiner Renamed",
            "title": "Senior Analyst",
            "emails": [{"value": f"joiner.renamed@{domain}", "primary": True}],
            "active": True,
        },
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["displayName"] == "Joiner Renamed"

    other = _user(client, headers, domain, "colleague")
    taken = client.patch(
        f"/api/v1/scim/v2/Users/{other['id']}",
        headers=headers,
        json={"Operations": [{"op": "replace", "path": "userName", "value": f"joiner.renamed@{domain}"}]},
    )
    assert taken.status_code == 409, "two employees must not share an email"

    patched = client.patch(
        f"/api/v1/scim/v2/Users/{user['id']}",
        headers=headers,
        json={
            "Operations": [
                {"op": "replace", "path": "title", "value": "Lead Analyst"},
                {"op": "replace", "path": "displayName", "value": "Joiner Lead"},
                {"op": "replace", "value": {"title": "Principal Analyst"}},
                {"op": "replace", "path": "active", "value": False},
            ]
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["active"] is False
    assert patched.json()["title"] == "Principal Analyst"

    unsupported_op = client.patch(
        f"/api/v1/scim/v2/Users/{user['id']}", headers=headers, json={"Operations": [{"op": "move", "path": "title"}]}
    )
    assert unsupported_op.status_code == 400
    unsupported_path = client.patch(
        f"/api/v1/scim/v2/Users/{user['id']}",
        headers=headers,
        json={"Operations": [{"op": "replace", "path": "nickName", "value": "x"}]},
    )
    assert unsupported_path.status_code == 400

    assert client.delete(f"/api/v1/scim/v2/Users/{other['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/scim/v2/Users/{other['id']}", headers=headers).json()["active"] is False
    assert client.get(f"/api/v1/scim/v2/Users/{uuid.uuid4()}", headers=headers).status_code == 404


def test_scim_group_membership_maps_to_departments(client, admin_headers):
    headers, domain = _scim(client, admin_headers)
    first = _user(client, headers, domain, "first")
    second = _user(client, headers, domain, "second")

    assert client.post("/api/v1/scim/v2/Groups", headers=headers, json={"displayName": " "}).status_code == 400
    bad_member = client.post(
        "/api/v1/scim/v2/Groups", headers=headers, json={"displayName": "Bad", "members": [{"value": "nope"}]}
    )
    assert bad_member.status_code == 400

    group = client.post(
        "/api/v1/scim/v2/Groups",
        headers=headers,
        json={"displayName": "Treasury", "members": [{"value": first["id"]}]},
    ).json()
    assert group["meta"]["memberCount"] == 1
    assert any(row["id"] == group["id"] for row in client.get("/api/v1/scim/v2/Groups", headers=headers).json()["Resources"])

    added = client.patch(
        f"/api/v1/scim/v2/Groups/{group['id']}",
        headers=headers,
        json={
            "Operations": [
                {"op": "add", "path": "members", "value": [{"value": second["id"]}]},
                {"op": "replace", "path": "displayName", "value": "Treasury Ops"},
            ]
        },
    )
    assert added.status_code == 200, added.text
    assert added.json()["displayName"] == "Treasury Ops"
    assert added.json()["meta"]["memberCount"] == 2

    removed = client.patch(
        f"/api/v1/scim/v2/Groups/{group['id']}",
        headers=headers,
        json={"Operations": [{"op": "remove", "path": f'members[value eq "{first["id"]}"]'}]},
    )
    assert removed.json()["meta"]["memberCount"] == 1

    replaced = client.put(
        f"/api/v1/scim/v2/Groups/{group['id']}",
        headers=headers,
        json={"displayName": "Treasury", "members": [{"value": first["id"]}, {"value": second["id"]}]},
    )
    assert replaced.json()["meta"]["memberCount"] == 2
    assert client.get(f"/api/v1/scim/v2/Groups/{group['id']}", headers=headers).json()["meta"]["memberCount"] == 2

    unsupported = client.patch(
        f"/api/v1/scim/v2/Groups/{group['id']}",
        headers=headers,
        json={"Operations": [{"op": "replace", "path": "owner", "value": "x"}]},
    )
    assert unsupported.status_code == 400

    assert client.delete(f"/api/v1/scim/v2/Groups/{group['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/scim/v2/Groups/{group['id']}", headers=headers).status_code == 404
    assert client.put(f"/api/v1/scim/v2/Groups/{group['id']}", headers=headers, json={}).status_code == 404
