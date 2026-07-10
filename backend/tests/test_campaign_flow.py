from __future__ import annotations


def test_launch_sandbox_and_track_event_updates_risk(client, admin_headers):
    campaigns = client.get("/api/v1/campaigns", headers=admin_headers).json()
    campaign_id = campaigns[0]["id"]

    launch_response = client.post(f"/api/v1/campaigns/{campaign_id}/launch-sandbox", headers=admin_headers)
    assert launch_response.status_code == 200, launch_response.text
    attempts = launch_response.json()
    assert attempts

    preview_url = attempts[0]["preview_payload"]["preview_url"]
    token = preview_url.rsplit("/", 1)[-1]
    event_response = client.post(
        f"/api/v1/public/training/{token}/events",
        json={"event_type": "clicked_link", "metadata": {"source": "test"}},
    )
    assert event_response.status_code == 200, event_response.text
    payload = event_response.json()
    assert payload["assignment_id"] is not None
    assert payload["risk_score"] >= 0

    assignments = client.get("/api/v1/training/assignments", headers=admin_headers).json()
    assert assignments
