from __future__ import annotations


def test_risk_intelligence_returns_department_reports(client, admin_headers):
    response = client.get("/api/v1/analytics/risk-intelligence", headers=admin_headers)
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["overview"]["monitored_employees"] >= 1
    assert payload["department_reports"]
    assert "department" in payload["department_reports"][0]
    assert "behavior_trend" in payload["department_reports"][0]


def test_adaptive_recommendations_only_use_permitted_themes(client, admin_headers):
    policy = client.get("/api/v1/policies/current", headers=admin_headers).json()
    policy.pop("id", None)
    policy.pop("organization_id", None)
    original_themes = list(policy["allowed_themes"])
    policy["allowed_themes"] = ["document review"]
    assert client.put("/api/v1/policies/current", json=policy, headers=admin_headers).status_code == 200
    try:
        payload = client.get("/api/v1/analytics/risk-intelligence", headers=admin_headers).json()
        assert payload["adaptive_recommendations"]
        assert {row["recommended_theme"] for row in payload["adaptive_recommendations"]} == {"document review"}
    finally:
        # The test database is shared across modules; restore the themes other tests use.
        policy["allowed_themes"] = original_themes
        client.put("/api/v1/policies/current", json=policy, headers=admin_headers)
