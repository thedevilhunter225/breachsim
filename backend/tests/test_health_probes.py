from __future__ import annotations


def test_health_probes_answer_any_host_but_api_routes_do_not(client):
    # Container platforms probe with the pod IP as Host.
    for path in ["/health", "/health/live", "/health/ready"]:
        response = client.get(path, headers={"Host": "10.0.0.17:8000"})
        assert response.status_code in {200, 503}, (path, response.status_code)

    rejected = client.get("/api/v1/auth/me", headers={"Host": "10.0.0.17:8000"})
    assert rejected.status_code == 400
