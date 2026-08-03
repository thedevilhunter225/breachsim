"""Synthetic media generation providers.

Mirrors the pluggable LLM layer: a protocol plus concrete adapters, selected by
configuration, with graceful degradation when nothing is configured.

Two capabilities are modelled separately because most deployments mix them:

``voice``
    Clone a consented person's voice from a short reference sample and synthesize
    arbitrary speech in it. Used by the vishing and deepfake channels.

``video``
    Render a talking-head video from a consented still image plus generated audio.
    Used by the deepfake channel when the persona modality is video.

Adapters
--------
``ElevenLabsVoiceProvider``   hosted voice cloning + TTS (paid API key)
``LocalCommandVoiceProvider`` self-hosted CLI, e.g. Coqui XTTS-v2 (free, local GPU)
``DIDVideoProvider``          hosted talking-head video (paid API key)
``LocalCommandVideoProvider`` self-hosted CLI, e.g. SadTalker / Wav2Lip
``NullProvider``              no generation; the simulator falls back to browser speech

Every generation call is expected to be made *after* the persona consent gate in
``app.services.personas`` has already passed. These adapters do not re-check consent —
they are the mechanism, not the policy.
"""

from __future__ import annotations

import base64
import shlex
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from app.core.config import settings


class MediaProviderError(RuntimeError):
    """Raised when generation fails. Callers degrade to browser speech synthesis."""


@dataclass
class VoiceRequest:
    text: str
    voice_ref: str | None
    #: Speaking-rate / stability hints, provider-interpreted.
    profile: dict


@dataclass
class VideoRequest:
    audio_bytes: bytes
    image_bytes: bytes
    image_mime: str


class VoiceProvider(Protocol):
    name: str

    def clone_voice(self, *, display_name: str, sample_bytes: bytes, sample_filename: str) -> str:
        """Register a reference sample and return a provider-side voice identifier."""

    def synthesize(self, request: VoiceRequest) -> tuple[bytes, str]:
        """Return (audio_bytes, mime_type)."""

    def delete_voice(self, voice_ref: str) -> None:
        """Remove the cloned voice from the provider when consent is revoked."""


class VideoProvider(Protocol):
    name: str

    def generate(self, request: VideoRequest) -> tuple[bytes, str]:
        """Return (video_bytes, mime_type)."""


# --------------------------------------------------------------------------------------
# ElevenLabs — hosted voice cloning
# --------------------------------------------------------------------------------------

class ElevenLabsVoiceProvider:
    """Instant Voice Cloning + text-to-speech.

    Requires a paid plan for voice cloning. ElevenLabs requires the account holder to
    confirm they have the speaker's permission; BreachSim's persona consent record is
    the organization-side counterpart to that attestation.
    """

    name = "elevenlabs"
    base_url = "https://api.elevenlabs.io/v1"

    def __init__(self, api_key: str, model: str = "eleven_multilingual_v2") -> None:
        self.api_key = api_key
        self.model = model

    def _headers(self) -> dict[str, str]:
        return {"xi-api-key": self.api_key}

    def clone_voice(self, *, display_name: str, sample_bytes: bytes, sample_filename: str) -> str:
        try:
            response = httpx.post(
                f"{self.base_url}/voices/add",
                headers=self._headers(),
                data={
                    "name": display_name[:64],
                    "description": "BreachSim authorized security awareness persona.",
                },
                files={"files": (sample_filename, sample_bytes, "audio/mpeg")},
                timeout=180.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise MediaProviderError(
                f"ElevenLabs rejected the voice sample: {exc.response.text[:300]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise MediaProviderError(f"ElevenLabs request failed: {exc}") from exc

        voice_id = response.json().get("voice_id")
        if not voice_id:
            raise MediaProviderError("ElevenLabs did not return a voice_id")
        return str(voice_id)

    def synthesize(self, request: VoiceRequest) -> tuple[bytes, str]:
        if not request.voice_ref:
            raise MediaProviderError("No cloned voice registered for this persona")

        profile = request.profile or {}
        try:
            response = httpx.post(
                f"{self.base_url}/text-to-speech/{request.voice_ref}",
                headers={**self._headers(), "Content-Type": "application/json"},
                json={
                    "text": request.text,
                    "model_id": self.model,
                    "voice_settings": {
                        "stability": float(profile.get("stability", 0.5)),
