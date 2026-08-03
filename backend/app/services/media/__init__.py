"""Media provider selection.

Chooses a voice/video provider from configuration, or returns ``None`` when none is
configured — in which case callers fall back to the in-browser speech engine, so the
platform stays fully functional with no paid media service.
"""

from __future__ import annotations

from app.core.config import settings
from app.services.media.base import (
    GeneratedMedia,
    MediaKind,
    ProviderError,
    VideoProvider,
    VoiceEnrollment,
    VoiceProvider,
)
from app.services.media.did_video import DIDVideoProvider
from app.services.media.elevenlabs import ElevenLabsVoiceProvider

__all__ = [
    "GeneratedMedia",
    "MediaKind",
    "ProviderError",
    "VideoProvider",
    "VoiceEnrollment",
    "VoiceProvider",
    "get_voice_provider",
    "get_video_provider",
    "voice_provider_status",
    "video_provider_status",
]


def get_voice_provider() -> VoiceProvider | None:
    provider = (settings.voice_clone_provider or "none").lower().strip()
    if provider == "elevenlabs" and settings.elevenlabs_api_key:
        return ElevenLabsVoiceProvider(
            api_key=settings.elevenlabs_api_key,
            base_url=settings.elevenlabs_base_url,
            model_id=settings.elevenlabs_model_id,
            allow_cloning=settings.elevenlabs_allow_voice_cloning,
        )
    return None


def get_video_provider() -> VideoProvider | None:
    provider = (settings.video_clone_provider or "none").lower().strip()
    if provider == "did" and settings.did_api_key:
        return DIDVideoProvider(api_key=settings.did_api_key, base_url=settings.did_base_url)
    return None


def voice_provider_status() -> dict:
    provider = get_voice_provider()
    return {
        "configured": provider is not None,
        "provider": provider.name if provider else (settings.voice_clone_provider or "none"),
        "supports_cloning": bool(provider and provider.supports_cloning()),
    }


def video_provider_status() -> dict:
    provider = get_video_provider()
    return {
        "configured": provider is not None,
        "provider": provider.name if provider else (settings.video_clone_provider or "none"),
        "supports_talking_head": bool(provider and provider.supports_talking_head()),
    }
