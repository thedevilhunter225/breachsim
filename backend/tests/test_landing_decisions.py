from __future__ import annotations

from app.db.session import SessionLocal
from app.models.entities import EventLog, LandingToken


def _sandbox_landing_token(client, admin_headers, manager_headers, name: str) -> str:
    employee = client.get("/api/v1/employees", headers=manager_headers).json()[0]
    scenario = client.post(
        "/api/v1/scenarios/generate",
        json={"employee_id": employee["id"], "channel": "email", "theme": "document review", "difficulty_level": "low"},
        headers=manager_headers,
    ).json()
    client.post(f"/api/v1/scenarios/{scenario['id']}/approve", headers=admin_headers)
    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "name": name,
            "channel": "email",
            "target_employee_ids": [employee["id"]],
            "scenario_ids": [scenario["id"]],
            "requires_second_approval": False,
        },
        headers=manager_headers,
    ).json()
    client.post(f"/api/v1/campaigns/{campaign['id']}/request-approval", headers=manager_headers)
    client.post(f"/api/v1/campaigns/{campaign['id']}/approve", headers=admin_headers)
    attempts = client.post(f"/api/v1/campaigns/{campaign['id']}/launch-sandbox", headers=admin_headers).json()
    return attempts[0]["preview_payload"]["preview_url"].rstrip("/").split("/")[-1]


def _events_for(token: str) -> list[EventLog]:
    session = SessionLocal()
    try:
        landing = session.query(LandingToken).filter(LandingToken.token == token).one()
        return session.query(EventLog).filter(EventLog.landing_token_id == landing.id).all()
    finally:
        session.close()


def test_first_landing_answer_wins_and_is_returned_on_reload(client, admin_headers, manager_headers):
    token = _sandbox_landing_token(client, admin_headers, manager_headers, "Landing first answer")
    assert client.get(f"/api/v1/public/training/{token}").json()["recorded_decision"] is None

    first = client.post(
        f"/api/v1/public/training/{token}/events",
        json={"event_type": "submitted_form_boolean", "metadata": {"simulation_choice": "would_provide_details"}},
    )
    assert first.status_code == 200, first.text

    replay = client.post(f"/api/v1/public/training/{token}/events", json={"event_type": "clicked_report"})
    assert replay.status_code == 409
    assert replay.json()["detail"]["recorded_decision"]["event_type"] == "submitted_form_boolean"

    reloaded = client.get(f"/api/v1/public/training/{token}").json()
    assert reloaded["recorded_decision"]["event_type"] == "submitted_form_boolean"
    assert reloaded["recorded_decision"]["occurred_at"].endswith("+00:00"), "times carry their UTC offset"
    decisions = [event for event in _events_for(token) if event.event_type.value in {"submitted_form_boolean", "clicked_report"}]
    assert len(decisions) == 1


def test_page_reloads_do_not_inflate_visit_counts(client, admin_headers, manager_headers):
    token = _sandbox_landing_token(client, admin_headers, manager_headers, "Landing reload")
    for _ in range(3):
        response = client.post(f"/api/v1/public/training/{token}/events", json={"event_type": "visited_landing_page"})
        assert response.status_code == 200, response.text
    visits = [event for event in _events_for(token) if event.event_type.value == "visited_landing_page"]
    assert len(visits) == 1


def test_public_pages_cannot_report_server_side_events(client, admin_headers, manager_headers):
    token = _sandbox_landing_token(client, admin_headers, manager_headers, "Landing server events")
    for event_type in ["training_completed", "delivered", "opened_email", "answered_call"]:
        response = client.post(f"/api/v1/public/training/{token}/events", json={"event_type": event_type})
        assert response.status_code == 422, (event_type, response.text)
