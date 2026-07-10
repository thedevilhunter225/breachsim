from __future__ import annotations


def test_risk_intelligence_returns_department_reports(client, admin_headers):
    response = client.get("/api/v1/analytics/risk-intelligence", headers=admin_headers)
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["overview"]["monitored_employees"] >= 1
    assert payload["department_reports"]
    assert "department" in payload["department_reports"][0]
    assert "behavior_trend" in payload["department_reports"][0]
