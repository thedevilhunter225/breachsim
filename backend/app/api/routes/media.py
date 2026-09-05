from __future__ import annotations

import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.config import settings
from app.db.session import get_db
from app.models.enums import MediaAssetStatus, UserRole
from app.services import media_store
from app.services.media import video_provider_status, voice_provider_status
from app.services.media_enrollment import MAX_UPLOAD_BYTES, enroll_face_image, enroll_voice_sample
from app.services.media_generation import finalize_pending_video
from app.services.personas import get_persona

router = APIRouter()


async def _read_bounded_upload(file: UploadFile) -> bytes:
    try:
        return await file.read(MAX_UPLOAD_BYTES + 1)
    finally:
        await file.close()


@router.get("/media/providers")
def media_providers(
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER)),
):
    """What real cloning is available, so the console can guide setup."""
    return {
        "voice": voice_provider_status(),
        "video": video_provider_status(),
        "max_upload_mb": settings.media_max_upload_mb,
        "retention_days": settings.media_retention_days,
    }


@router.post("/personas/{persona_id}/voice-sample", status_code=status.HTTP_201_CREATED)
async def upload_voice_sample(
    persona_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
    user=Depends(require_roles(UserRole.ADMIN)),
):
    persona = get_persona(db, user.organization_id, persona_id)
    content = await _read_bounded_upload(file)
    asset = enroll_voice_sample(
        db,
        persona=persona,
        actor=user,
        content=content,
        content_type=file.content_type or "audio/mpeg",
    )
    return {
        "asset_id": str(asset.id),
        "provider": asset.provider,
        "cloned": bool(persona.voice_clone_ref),
        "voice_ref": persona.voice_clone_ref,
    }


@router.post("/personas/{persona_id}/face-image", status_code=status.HTTP_201_CREATED)
async def upload_face_image(
    persona_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
    user=Depends(require_roles(UserRole.ADMIN)),
):
    persona = get_persona(db, user.organization_id, persona_id)
    content = await _read_bounded_upload(file)
    asset = enroll_face_image(
        db,
        persona=persona,
        actor=user,
        content=content,
        content_type=file.content_type or "image/jpeg",
    )
    return {"asset_id": str(asset.id), "has_face_image": persona.has_face_image}


@router.get("/public/media/{token}")
def serve_media(token: str, db: Annotated[Session, Depends(get_db)]):
    """Stream a generated clip to the simulator via its single-use access token.

    Unauthenticated by design — the unguessable token *is* the credential, exactly as the
    simulated message would be in the real world. A pending video render is polled here so
    the simulator can fetch it the moment it is ready.
    """
    asset = media_store.get_asset_by_token(db, token)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

    if asset.status == MediaAssetStatus.PENDING:
        asset = finalize_pending_video(db, asset)

    if not asset.is_available():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This media is not available (still rendering, expired, or removed).",
        )

    try:
        content = media_store.read_bytes(asset)
    except (FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media bytes are unavailable") from exc

    # Rotate after a successful read so a leaked media URL cannot be replayed. The
    # simulation endpoint can issue the current token again to an authorized participant.
    asset.access_token = secrets.token_urlsafe(24)
    db.commit()

    return Response(
        content=content,
        media_type=asset.content_type,
        headers={
            "Cache-Control": "private, max-age=0, no-store",
            "Content-Disposition": "inline",
        },
    )
