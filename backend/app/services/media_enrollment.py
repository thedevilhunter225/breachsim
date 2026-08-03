"""Consent-gated enrolment of a persona's real voice and face.

This is the bridge between the consent registry and the cloning providers. A voice
sample or face image can only be attached to a persona that represents a real person and
carries a consent reference — the same gate that governs whether the persona can be used
at all. Enrolling a voice pushes the sample to the provider (e.g. ElevenLabs) and stores
the returned reference on the persona so later scenarios can synthesize in that voice.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import ImpersonationPersona, MediaAsset
from app.models.enums import MediaAssetKind
from app.services import media_store
from app.services.audit import audit_log
from app.services.media import ProviderError, get_video_provider, get_voice_provider

MAX_UPLOAD_BYTES = settings.media_max_upload_mb * 1024 * 1024
ALLOWED_AUDIO = {"audio/mpeg", "audio/mp4", "audio/wav", "audio/x-wav", "audio/webm", "audio/ogg"}
ALLOWED_IMAGE = {"image/jpeg", "image/png"}


def _require_real_person(persona: ImpersonationPersona) -> None:
    if not persona.is_real_person:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This persona is a synthetic composite role, not a real person. Cloning a real "
                "voice or face is only permitted for a persona registered as a real individual "
                "with a signed consent reference on file."
            ),
        )
    if not persona.consent_reference:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot enrol media: this persona has no signed consent reference on file.",
        )


def _validate_upload(content: bytes, content_type: str, allowed: set[str], label: str) -> None:
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Empty {label} upload.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"{label} exceeds the {settings.media_max_upload_mb} MB limit.",
        )
    if content_type not in allowed:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported {label} type '{content_type}'. Allowed: {', '.join(sorted(allowed))}.",
        )


def enroll_voice_sample(
    db: Session,
    *,
    persona: ImpersonationPersona,
    actor,
    content: bytes,
    content_type: str,
) -> MediaAsset:
    """Store a consented voice sample and register it with the cloning provider."""
    _require_real_person(persona)
    _validate_upload(content, content_type, ALLOWED_AUDIO, "voice sample")

    provider = get_voice_provider()
    voice_ref = None
    provider_name = None
    if provider and provider.supports_cloning():
        try:
            enrollment = provider.enroll_voice(
                display_name=persona.display_name, sample=content, content_type=content_type
            )
        except ProviderError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        voice_ref = enrollment.voice_ref
        provider_name = enrollment.provider
        # Replacing an existing clone: retire the old provider-side voice.
        if persona.voice_clone_ref and persona.voice_clone_ref != voice_ref:
            _safe_delete_voice(persona)
        persona.voice_clone_provider = provider_name
        persona.voice_clone_ref = voice_ref

    asset = media_store.write_asset(
        db,
        organization_id=persona.organization_id,
        kind=MediaAssetKind.VOICE_SAMPLE,
        content=content,
        content_type=content_type,
        persona_id=persona.id,
        created_by_user_id=actor.id,
        provider=provider_name,
        provider_ref=voice_ref,
        persona_consent_expires_at=persona.consent_expires_at,
        generation_detail={"enrolled": bool(voice_ref)},
    )
    audit_log(
        db,
        organization_id=persona.organization_id,
        user_id=actor.id,
        action="persona.voice_enrolled",
        resource_type="impersonation_persona",
        resource_id=str(persona.id),
        details={
            "provider": provider_name or "stored-only",
            "voice_ref": voice_ref,
            "consent_reference": persona.consent_reference,
            "byte_size": len(content),
        },
    )
    db.commit()
    db.refresh(asset)
    return asset


def enroll_face_image(
    db: Session,
    *,
    persona: ImpersonationPersona,
    actor,
    content: bytes,
    content_type: str,
) -> MediaAsset:
    """Store a consented face image for talking-head video generation."""
    _require_real_person(persona)
    _validate_upload(content, content_type, ALLOWED_IMAGE, "face image")

    asset = media_store.write_asset(
        db,
        organization_id=persona.organization_id,
        kind=MediaAssetKind.FACE_IMAGE,
        content=content,
        content_type=content_type,
        persona_id=persona.id,
        created_by_user_id=actor.id,
        persona_consent_expires_at=persona.consent_expires_at,
    )
    persona.has_face_image = True
    audit_log(
        db,
        organization_id=persona.organization_id,
        user_id=actor.id,
        action="persona.face_enrolled",
        resource_type="impersonation_persona",
        resource_id=str(persona.id),
        details={"consent_reference": persona.consent_reference, "byte_size": len(content)},
    )
    db.commit()
    db.refresh(asset)
    return asset


def latest_face_asset(db: Session, persona: ImpersonationPersona) -> MediaAsset | None:
    return (
        db.query(MediaAsset)
        .filter(MediaAsset.persona_id == persona.id, MediaAsset.kind == MediaAssetKind.FACE_IMAGE)
        .order_by(MediaAsset.created_at.desc())
        .first()
    )


def _safe_delete_voice(persona: ImpersonationPersona) -> None:
    provider = get_voice_provider()
    if provider and persona.voice_clone_ref:
        provider.delete_voice(persona.voice_clone_ref)


def purge_persona_media(db: Session, persona: ImpersonationPersona) -> int:
    """Remove all cloned media for a persona and retire its provider-side voice.

    Called on revocation. Deleting the enrolled voice at the provider is what makes
    revocation meaningful: the clone can no longer be synthesized anywhere.
    """
    _safe_delete_voice(persona)
    persona.voice_clone_provider = None
    persona.voice_clone_ref = None
    persona.has_face_image = False
    removed = media_store.expire_persona_media(db, persona.id)
    return removed
