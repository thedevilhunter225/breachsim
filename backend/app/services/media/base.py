"""Provider-agnostic contracts for real synthetic-media generation.

The media layer mirrors the LLM layer: a small protocol that concrete providers
(ElevenLabs for voice, D-ID for talking-head video, or a local worker) implement,
plus a factory that selects one from configuration. Every provider is optional —
with none configured the simulators fall back to the browser speech engine, so the
platform still runs end to end with no paid service.

Realism is the whole point of an enterprise deepfake drill: a cloned executive voice
saying the exact pretext is what makes the exercise land. The safety boundary is not
"don't make it realistic" — it is "only ever clone a registered, consented persona,
keep the artefact access-controlled, and delete it on a retention clock."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class MediaKind(StrEnum):
    VOICE = "voice"
    VIDEO = "video"


class ProviderError(RuntimeError):
    """Raised when a media provider cannot complete a request.

    Callers treat this as recoverable and fall back to the browser speech engine, so a
    provider outage degrades realism but never breaks a simulation.
    """


@dataclass
class VoiceEnrollment:
    """The result of registering a persona's voice sample with a cloning provider."""

    provider: str
    voice_ref: str  # provider-side voice/actor id
    detail: dict = field(default_factory=dict)


@dataclass
class GeneratedMedia:
    """A rendered clip. ``content`` is the raw bytes; ``status`` may be 'pending' for
    providers whose render is asynchronous (video), in which case ``remote_ref`` is the
    id to poll."""

    kind: MediaKind
    provider: str
    content_type: str
    content: bytes | None = None
    remote_ref: str | None = None
    status: str = "ready"  # ready | pending | failed
    duration_ms: int | None = None
    detail: dict = field(default_factory=dict)


class VoiceProvider(Protocol):
    name: str

    def supports_cloning(self) -> bool:
        """True when this provider can enrol a real person's voice from a sample."""
        ...

    def enroll_voice(self, *, display_name: str, sample: bytes, content_type: str) -> VoiceEnrollment:
        """Register a consented voice sample and return a reusable voice reference."""
        ...

    def delete_voice(self, voice_ref: str) -> None:
        """Remove an enrolled voice from the provider (used on revocation/expiry)."""
        ...

    def synthesize(self, *, text: str, voice_ref: str | None, options: dict | None = None) -> GeneratedMedia:
        """Render speech. With ``voice_ref`` it clones that voice; without, a stock voice."""
        ...


class VideoProvider(Protocol):
    name: str

    def supports_talking_head(self) -> bool:
        ...

    def generate_talking_head(
        self,
        *,
        face_image: bytes,
        face_content_type: str,
        audio: bytes | None,
        audio_content_type: str | None,
        text: str | None,
        options: dict | None = None,
    ) -> GeneratedMedia:
        """Animate a consented still image to speak the audio (or text)."""
        ...

    def poll(self, remote_ref: str) -> GeneratedMedia:
        """Check an asynchronous render and return the finished clip when ready."""
        ...
