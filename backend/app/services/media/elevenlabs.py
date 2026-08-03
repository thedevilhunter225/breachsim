"""ElevenLabs voice provider — real voice cloning and speech synthesis.

Uses two endpoints:

- ``POST /v1/voices/add``            enrol a consented sample, returns a ``voice_id``
- ``POST /v1/text-to-speech/{id}``  render text in that cloned (or a stock) voice

Cloning an identifiable person requires a paid ElevenLabs plan *and* is gated on this
platform by per-persona consent plus the organization impersonation switch. The API key
is read from configuration and never leaves the backend.
"""

from __future__ import annotations

import httpx

from app.services.media.base import (
    GeneratedMedia,
    MediaKind,
    ProviderError,
    VoiceEnrollment,
)

#: A stable ElevenLabs stock voice, used when a persona has no cloned voice enrolled
#: (synthetic composite roles that were never given a real sample).
DEFAULT_STOCK_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # "Rachel", a public preset


class ElevenLabsVoiceProvider:
    name = "elevenlabs"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.elevenlabs.io",
        model_id: str = "eleven_multilingual_v2",
        allow_cloning: bool = True,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id
        self.allow_cloning = allow_cloning

    def _headers(self, extra: dict | None = None) -> dict:
        return {"xi-api-key": self.api_key, **(extra or {})}

    def supports_cloning(self) -> bool:
        return self.allow_cloning

    def enroll_voice(self, *, display_name: str, sample: bytes, content_type: str) -> VoiceEnrollment:
        if not self.allow_cloning:
            raise ProviderError("Voice cloning is disabled for this ElevenLabs configuration.")
        try:
            response = httpx.post(
                f"{self.base_url}/v1/voices/add",
                headers=self._headers(),
                data={
                    "name": f"BreachSim · {display_name}"[:128],
                    "description": "Consented persona voice for authorized security awareness simulation.",
                },
                files={"files": (f"{display_name}.mp3", sample, content_type or "audio/mpeg")},
                timeout=120.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderError(f"ElevenLabs voice enrolment failed: {exc.response.text[:300]}") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"ElevenLabs voice enrolment request failed: {exc}") from exc

        voice_id = str(response.json().get("voice_id") or "").strip()
        if not voice_id:
            raise ProviderError("ElevenLabs did not return a voice_id.")
        return VoiceEnrollment(provider=self.name, voice_ref=voice_id, detail={"display_name": display_name})

    def delete_voice(self, voice_ref: str) -> None:
        try:
            httpx.delete(
                f"{self.base_url}/v1/voices/{voice_ref}",
                headers=self._headers(),
                timeout=30.0,
            )
        except httpx.HTTPError:
            # Deletion is best-effort cleanup; a failure here must not block revocation.
            pass

    def synthesize(self, *, text: str, voice_ref: str | None, options: dict | None = None) -> GeneratedMedia:
        options = options or {}
        voice_id = voice_ref or DEFAULT_STOCK_VOICE_ID
        payload = {
            "text": text,
            "model_id": options.get("model_id", self.model_id),
            "voice_settings": {
                "stability": options.get("stability", 0.5),
                "similarity_boost": options.get("similarity_boost", 0.85),
                "style": options.get("style", 0.3),
                "use_speaker_boost": True,
            },
        }
        try:
            response = httpx.post(
                f"{self.base_url}/v1/text-to-speech/{voice_id}",
                headers=self._headers({"Accept": "audio/mpeg", "Content-Type": "application/json"}),
                json=payload,
                timeout=120.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300] if exc.response is not None else str(exc)
            raise ProviderError(f"ElevenLabs synthesis failed: {detail}") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"ElevenLabs synthesis request failed: {exc}") from exc

        audio = response.content
        if not audio:
            raise ProviderError("ElevenLabs returned empty audio.")
        return GeneratedMedia(
            kind=MediaKind.VOICE,
            provider=self.name,
            content_type="audio/mpeg",
            content=audio,
            status="ready",
            detail={"voice_id": voice_id, "cloned": bool(voice_ref)},
        )
