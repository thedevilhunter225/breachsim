"""Render real cloned media for an interactive scenario version.

When a vishing or deepfake scenario is generated, this turns the branching script's
spoken lines into actual audio in the persona's cloned voice, and — for a video persona
with a consented face image — a talking-head clip. Results are stored as ``MediaAsset``
rows bound to the scenario version, so re-approving a scenario reuses the media instead
of regenerating (and re-billing) it.

Every step is best-effort: if no provider is configured, or a provider errors, the
scenario is still fully usable and the simulator falls back to the browser speech engine.
Realism degrades; the exercise does not break.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import ImpersonationPersona, MediaAsset, ScenarioVersion
from app.models.enums import Channel, MediaAssetKind, MediaAssetStatus, MediaModality
from app.services import media_store
from app.services.audit import audit_log
from app.services.media import ProviderError, get_video_provider, get_voice_provider
from app.services.media_enrollment import latest_face_asset

VIDEO_MODALITIES = {MediaModality.VIDEO_MESSAGE, MediaModality.LIVE_VIDEO_CALL}


def _spoken_text(version: ScenarioVersion) -> str:
    """The line the persona actually says — the deepfake transcript or the call opener."""
    payload = version.channel_payload or {}
    transcript = (payload.get("transcript") or "").strip()
    if transcript:
        return transcript
    script = payload.get("script") or []
    if script:
        opener = (script[0].get("speaker_line") or "").strip()
        if opener:
            return opener
    return (version.body_copy or "").strip()


def generate_media_for_version(
    db: Session,
    *,
    version: ScenarioVersion,
    persona: ImpersonationPersona | None,
    channel: Channel,
    actor,
) -> dict:
    """Synthesize cloned voice (and video where possible) for one scenario version.

    Returns a summary dict recorded on the scenario so the studio can show what was made.
    """
    summary: dict = {"voice": "skipped", "video": "skipped"}
    if persona is None or channel not in {Channel.VISHING, Channel.DEEPFAKE}:
        return summary

    text = _spoken_text(version)
    if not text:
        return summary

    voice_provider = get_voice_provider()
    voice_asset: MediaAsset | None = None

    if voice_provider is None:
        summary["voice"] = "fallback_browser_tts"
    else:
        try:
            rendered = voice_provider.synthesize(
                text=text,
                voice_ref=persona.voice_clone_ref,  # None -> stock voice for synthetic roles
                options={},
            )
            voice_asset = media_store.write_asset(
                db,
                organization_id=persona.organization_id,
                kind=MediaAssetKind.GENERATED_AUDIO,
                content=rendered.content or b"",
                content_type=rendered.content_type,
                persona_id=persona.id,
                scenario_version_id=version.id,
                created_by_user_id=actor.id,
                provider=rendered.provider,
                provider_ref=persona.voice_clone_ref,
                duration_ms=rendered.duration_ms,
                persona_consent_expires_at=persona.consent_expires_at,
                generation_detail={"cloned": bool(persona.voice_clone_ref), **rendered.detail},
            )
            summary["voice"] = "cloned" if persona.voice_clone_ref else "stock_voice"
        except ProviderError as exc:
            summary["voice"] = "fallback_browser_tts"
            summary["voice_error"] = str(exc)

    # Talking-head video: only for a video-modality persona with a consented face image,
    # and only if a video provider is configured. Prefer the cloned audio we just made.
    if channel == Channel.DEEPFAKE and persona.modality in VIDEO_MODALITIES and persona.has_face_image:
        video_provider = get_video_provider()
        face = latest_face_asset(db, persona)
        if video_provider is not None and face is not None:
            try:
                face_bytes = media_store.read_bytes(face)
                audio_bytes = media_store.read_bytes(voice_asset) if voice_asset else None
                result = video_provider.generate_talking_head(
                    face_image=face_bytes,
                    face_content_type=face.content_type,
                    audio=audio_bytes,
                    audio_content_type=voice_asset.content_type if voice_asset else None,
                    text=None if audio_bytes else text,
                    options={},
                )
                if result.status == "ready" and result.content:
                    media_store.write_asset(
                        db,
                        organization_id=persona.organization_id,
                        kind=MediaAssetKind.GENERATED_VIDEO,
                        content=result.content,
                        content_type=result.content_type,
                        persona_id=persona.id,
                        scenario_version_id=version.id,
                        created_by_user_id=actor.id,
                        provider=result.provider,
                        persona_consent_expires_at=persona.consent_expires_at,
                        generation_detail=result.detail,
                    )
                    summary["video"] = "cloned"
                else:
                    # Async render: record a pending asset to be finished by the poller.
                    media_store.create_pending_asset(
                        db,
                        organization_id=persona.organization_id,
                        kind=MediaAssetKind.GENERATED_VIDEO,
                        content_type=result.content_type,
                        persona_id=persona.id,
                        scenario_version_id=version.id,
                        created_by_user_id=actor.id,
                        provider=result.provider,
                        provider_ref=result.remote_ref,
                        persona_consent_expires_at=persona.consent_expires_at,
                    )
                    summary["video"] = "pending"
            except ProviderError as exc:
                summary["video"] = "fallback_avatar"
                summary["video_error"] = str(exc)
        else:
            summary["video"] = "fallback_avatar"

    audit_log(
        db,
        organization_id=persona.organization_id,
        user_id=actor.id,
        action="media.generate",
        resource_type="scenario_version",
        resource_id=str(version.id),
        details={"persona_id": str(persona.id), **summary},
    )
    db.flush()
    return summary


def finalize_pending_video(db: Session, asset: MediaAsset) -> MediaAsset:
    """Poll a provider for an async video render and attach the bytes when ready."""
    if asset.status != MediaAssetStatus.PENDING or not asset.provider_ref:
        return asset
    provider = get_video_provider()
    if provider is None:
        return asset
    try:
        result = provider.poll(asset.provider_ref)
    except ProviderError:
        return asset
    if result.status == "ready" and result.content:
        media_store.attach_bytes(db, asset, content=result.content)
        db.commit()
    elif result.status == "failed":
        asset.status = MediaAssetStatus.FAILED
        db.commit()
    return asset


def media_for_version(db: Session, version_id) -> dict:
    """The ready audio/video access tokens for a scenario version, for the simulator."""
    assets = (
        db.query(MediaAsset)
        .filter(
            MediaAsset.scenario_version_id == version_id,
            MediaAsset.kind.in_([MediaAssetKind.GENERATED_AUDIO, MediaAssetKind.GENERATED_VIDEO]),
        )
        .order_by(MediaAsset.created_at.desc())
        .all()
    )
    audio = next((a for a in assets if a.kind == MediaAssetKind.GENERATED_AUDIO and a.is_available()), None)
    video = next((a for a in assets if a.kind == MediaAssetKind.GENERATED_VIDEO and a.is_available()), None)
    pending_video = any(
        a.kind == MediaAssetKind.GENERATED_VIDEO and a.status == MediaAssetStatus.PENDING for a in assets
    )
    return {
        "audio_token": audio.access_token if audio else None,
        "video_token": video.access_token if video else None,
        "video_pending": pending_video and video is None,
    }
