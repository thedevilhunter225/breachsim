"""Coverage for the real synthetic-media layer: enrolment guardrails, generation,
token-gated serving, and consent-revocation cleanup.

A stub provider stands in for ElevenLabs/D-ID so the wiring is exercised without any
paid API key or network call.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import app.services.media_enrollment as media_enrollment
import app.services.media_generation as media_generation
from app.services.media.base import GeneratedMedia, MediaKind, VoiceEnrollment
from tests.conftest import login


class StubVoiceProvider:
    name = "stub-voice"

    def supports_cloning(self) -> bool:
        return True

    def enroll_voice(self, *, display_name, sample, content_type):
        return VoiceEnrollment(provider=self.name, voice_ref=f"voice-{display_name[:6]}", detail={})

    def delete_voice(self, voice_ref):
        StubVoiceProvider.deleted.append(voice_ref)

    def synthesize(self, *, text, voice_ref, options=None):
        return GeneratedMedia(
            kind=MediaKind.VOICE,
            provider=self.name,
            content_type="audio/mpeg",
            content=b"ID3" + text.encode("utf-8")[:64],
            status="ready",
            detail={"cloned": bool(voice_ref)},
        )


StubVoiceProvider.deleted = []


@pytest.fixture()
def stub_voice(monkeypatch):
    provider = StubVoiceProvider()
    StubVoiceProvider.deleted = []
    monkeypatch.setattr(media_enrollment, "get_voice_provider", lambda: provider)
    monkeypatch.setattr(media_generation, "get_voice_provider", lambda: provider)
    monkeypatch.setattr(media_generation, "get_video_provider", lambda: None)
    return provider


def _enable(client, admin):
    client.put(
        "/api/v1/integrations/impersonation",
        json={"impersonation_enabled": True, "voice_provider_enabled": True, "voice_provider_mode": "simulator"},
        headers=admin,
    )


def _register_real_persona(client, admin, **overrides):
    payload = {
        "display_name": "Exec Voice Clone",
        "role_title": "Chief Executive",
        "modality": "voice_note",
        "is_real_person": True,
        "consent_reference": "HR-AUTH-CLONE-01",
        "consent_expires_at": (datetime.now(timezone.utc) + timedelta(days=60)).isoformat(),
    }
    payload.update(overrides)
    r = client.post("/api/v1/personas", json=payload, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()


def _approve(client, persona_id):
    reviewer = login(client, "reviewer@breachsim-lab.com", "Reviewer123!")
    r = client.post(f"/api/v1/personas/{persona_id}/approve", headers=reviewer)
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------------------------------------------------------------------
# Enrolment guardrails
# --------------------------------------------------------------------------------------

def test_synthetic_role_cannot_enrol_a_real_voice(client: TestClient, admin_headers, stub_voice):
    _enable(client, admin_headers)
    persona = client.post(
        "/api/v1/personas",
        json={"display_name": "Composite Role", "role_title": "Finance Lead", "is_real_person": False},
        headers=admin_headers,
    ).json()

    response = client.post(
        f"/api/v1/personas/{persona['id']}/voice-sample",
        files={"file": ("sample.mp3", b"fake-audio-bytes", "audio/mpeg")},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "real" in response.text.lower()


def test_voice_enrolment_clones_and_sets_reference(client: TestClient, admin_headers, stub_voice):
    _enable(client, admin_headers)
    persona = _register_real_persona(client, admin_headers)

    response = client.post(
        f"/api/v1/personas/{persona['id']}/voice-sample",
        files={"file": ("ceo.mp3", b"a-consented-voice-sample", "audio/mpeg")},
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["cloned"] is True
    assert body["voice_ref"].startswith("voice-")

    # The persona now reports an enrolled clone.
    refreshed = client.get(f"/api/v1/personas/{persona['id']}", headers=admin_headers).json()
    assert refreshed["voice_clone_ref"] == body["voice_ref"]


def test_oversized_upload_is_rejected(client: TestClient, admin_headers, stub_voice):
    _enable(client, admin_headers)
    persona = _register_real_persona(client, admin_headers, display_name="Big Upload Persona")
    huge = b"0" * (26 * 1024 * 1024)  # 26 MB, over the 25 MB cap
    response = client.post(
        f"/api/v1/personas/{persona['id']}/voice-sample",
        files={"file": ("big.mp3", huge, "audio/mpeg")},
        headers=admin_headers,
    )
    assert response.status_code == 413


# --------------------------------------------------------------------------------------
# Generation + serving + revocation
# --------------------------------------------------------------------------------------

def _generate_deepfake_scenario(client, admin, manager, persona_id):
    employee = client.get("/api/v1/employees", headers=manager).json()[0]
    # Ensure the theme is permitted.
    policy = client.get("/api/v1/policies/current", headers=admin).json()
    if "executive approval request" not in policy["allowed_themes"]:
        policy["allowed_themes"].append("executive approval request")
        policy.pop("id", None)
        policy.pop("organization_id", None)
        client.put("/api/v1/policies/current", json=policy, headers=admin)

    return client.post(
        "/api/v1/scenarios/generate",
        json={
            "employee_id": employee["id"],
            "channel": "deepfake",
            "theme": "executive approval request",
            "difficulty_level": "high",
            "persona_id": persona_id,
        },
        headers=manager,
    )


def test_generated_media_is_served_by_token(client: TestClient, admin_headers, manager_headers, stub_voice):
    _enable(client, admin_headers)
    persona = _register_real_persona(client, admin_headers, display_name="Serve Test CEO")
    client.post(
        f"/api/v1/personas/{persona['id']}/voice-sample",
        files={"file": ("ceo.mp3", b"consented-sample", "audio/mpeg")},
        headers=admin_headers,
    )
    _approve(client, persona["id"])

    scenario = _generate_deepfake_scenario(client, admin_headers, manager_headers, persona["id"])
    assert scenario.status_code == 201, scenario.text

    # Approve + deliver so a landing token exists, then load the public simulation.
    client.post(f"/api/v1/scenarios/{scenario.json()['id']}/approve", headers=admin_headers)
    employee = client.get("/api/v1/employees", headers=manager_headers).json()[0]
    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "name": "Cloned media serve test",
            "channel": "deepfake",
            "target_employee_ids": [employee["id"]],
            "scenario_ids": [scenario.json()["id"]],
            "requires_second_approval": False,
        },
        headers=manager_headers,
    ).json()
    client.post(f"/api/v1/campaigns/{campaign['id']}/request-approval", headers=manager_headers)
    client.post(f"/api/v1/campaigns/{campaign['id']}/approve", headers=admin_headers)
    attempt = client.post(f"/api/v1/campaigns/{campaign['id']}/deliver", headers=manager_headers).json()[0]
    token = attempt["preview_payload"]["media_url"].rstrip("/").split("/")[-1]

    state = client.get(f"/api/v1/public/simulation/{token}").json()
    assert state["media"]["audio_token"], "cloned audio should be exposed to the simulator"

    audio = client.get(f"/api/v1/public/media/{state['media']['audio_token']}")
    assert audio.status_code == 200
    assert audio.headers["content-type"] == "audio/mpeg"
    assert audio.content.startswith(b"ID3")
    assert client.get(f"/api/v1/public/media/{state['media']['audio_token']}").status_code == 404


def test_revocation_deletes_cloned_media_and_retires_voice(
    client: TestClient, admin_headers, stub_voice
):
    _enable(client, admin_headers)
    persona = _register_real_persona(client, admin_headers, display_name="Revoke Clone CEO")
    client.post(
        f"/api/v1/personas/{persona['id']}/voice-sample",
        files={"file": ("ceo.mp3", b"consented-sample", "audio/mpeg")},
        headers=admin_headers,
    )
    voice_ref = client.get(f"/api/v1/personas/{persona['id']}", headers=admin_headers).json()["voice_clone_ref"]
    assert voice_ref

    revoke = client.post(
        f"/api/v1/personas/{persona['id']}/revoke",
        json={"reason": "Consent withdrawn"},
        headers=admin_headers,
    )
    assert revoke.status_code == 200
    body = revoke.json()
    assert body["status"] == "revoked"
    assert body["voice_clone_ref"] in (None, "")
    # The provider-side voice was retired, which is what makes revocation meaningful.
    assert voice_ref in StubVoiceProvider.deleted


def test_media_provider_status_endpoint(client: TestClient, admin_headers):
    response = client.get("/api/v1/media/providers", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert "voice" in body and "video" in body
    assert "max_upload_mb" in body


def test_expired_media_token_returns_404(client: TestClient):
    response = client.get(f"/api/v1/public/media/{uuid.uuid4().hex}")
    assert response.status_code == 404
