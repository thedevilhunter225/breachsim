"""On-disk storage and lifecycle for media assets.

Bytes are written under a per-organization directory in the media store; the database
holds the metadata and retention clock. Access to a generated clip is via a single-use,
unguessable token rather than a predictable path, and every asset carries an expiry so
cloned media does not linger past its purpose.

Nothing here talks to a provider — it is the persistence half of the media layer.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import MediaAsset
from app.models.enums import MediaAssetKind, MediaAssetStatus

EXTENSION_BY_CONTENT_TYPE = {
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/wav": ".wav",
    "audio/webm": ".webm",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


def store_root() -> Path:
    root = Path(settings.media_storage_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[2] / settings.media_storage_dir
    return root


def _asset_path(organization_id, asset_id, content_type: str) -> Path:
    extension = EXTENSION_BY_CONTENT_TYPE.get(content_type, ".bin")
    directory = store_root() / str(organization_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{asset_id}{extension}"


def _retention_expiry(persona_expires_at: datetime | None) -> datetime:
    """The sooner of the platform retention window and the persona's consent expiry."""
    default = datetime.now(timezone.utc) + timedelta(days=settings.media_retention_days)
    if persona_expires_at is None:
        return default
    consent = persona_expires_at if persona_expires_at.tzinfo else persona_expires_at.replace(tzinfo=timezone.utc)
    return min(default, consent)


def write_asset(
    db: Session,
    *,
    organization_id,
    kind: MediaAssetKind,
    content: bytes,
    content_type: str,
    persona_id=None,
    scenario_version_id=None,
    created_by_user_id=None,
    provider: str | None = None,
    provider_ref: str | None = None,
    duration_ms: int | None = None,
    persona_consent_expires_at: datetime | None = None,
    generation_detail: dict | None = None,
) -> MediaAsset:
    asset = MediaAsset(
        organization_id=organization_id,
        persona_id=persona_id,
        scenario_version_id=scenario_version_id,
        created_by_user_id=created_by_user_id,
        kind=kind,
        status=MediaAssetStatus.READY,
        provider=provider,
        provider_ref=provider_ref,
        content_type=content_type,
        byte_size=len(content),
        checksum=hashlib.sha256(content).hexdigest(),
        duration_ms=duration_ms,
        access_token=secrets.token_urlsafe(24),
        expires_at=_retention_expiry(persona_consent_expires_at),
        generation_detail=generation_detail or {},
    )
    db.add(asset)
    db.flush()

    path = _asset_path(organization_id, asset.id, content_type)
    path.write_bytes(content)
    # Store relative to the root so the DB stays portable across machines.
    asset.storage_path = str(path.relative_to(store_root()))
    db.flush()
    return asset


def create_pending_asset(
    db: Session,
    *,
    organization_id,
    kind: MediaAssetKind,
    content_type: str,
    persona_id=None,
    scenario_version_id=None,
    created_by_user_id=None,
    provider: str | None = None,
    provider_ref: str | None = None,
    persona_consent_expires_at: datetime | None = None,
) -> MediaAsset:
    """Record an asynchronous render (video) before its bytes exist."""
    asset = MediaAsset(
        organization_id=organization_id,
        persona_id=persona_id,
        scenario_version_id=scenario_version_id,
        created_by_user_id=created_by_user_id,
        kind=kind,
        status=MediaAssetStatus.PENDING,
        provider=provider,
        provider_ref=provider_ref,
        content_type=content_type,
        access_token=secrets.token_urlsafe(24),
        expires_at=_retention_expiry(persona_consent_expires_at),
    )
    db.add(asset)
    db.flush()
    return asset


def attach_bytes(db: Session, asset: MediaAsset, *, content: bytes) -> MediaAsset:
    """Fill in a previously-pending asset once its render completes."""
    path = _asset_path(asset.organization_id, asset.id, asset.content_type)
    path.write_bytes(content)
    asset.storage_path = str(path.relative_to(store_root()))
    asset.byte_size = len(content)
    asset.checksum = hashlib.sha256(content).hexdigest()
    asset.status = MediaAssetStatus.READY
    db.flush()
    return asset


def read_bytes(asset: MediaAsset) -> bytes:
    if not asset.storage_path:
        raise FileNotFoundError("Asset has no stored bytes yet.")
    path = store_root() / asset.storage_path
    return path.read_bytes()


def delete_asset_bytes(asset: MediaAsset) -> None:
    """Remove the bytes from disk (revocation, expiry). The row is kept for the audit trail."""
    if not asset.storage_path:
        return
    path = store_root() / asset.storage_path
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def get_asset_by_token(db: Session, token: str) -> MediaAsset | None:
    return db.query(MediaAsset).filter(MediaAsset.access_token == token).first()


def expire_persona_media(db: Session, persona_id) -> int:
    """Delete every stored clip for a persona (used on revocation). Returns the count."""
    assets = db.query(MediaAsset).filter(MediaAsset.persona_id == persona_id).all()
    removed = 0
    for asset in assets:
        if asset.storage_path:
            delete_asset_bytes(asset)
            removed += 1
        asset.status = MediaAssetStatus.EXPIRED
        asset.storage_path = None
    db.flush()
    return removed


def sweep_expired(db: Session, *, now: datetime | None = None) -> int:
    """Delete bytes for any asset past its retention window. Returns the count swept."""
    moment = now or datetime.now(timezone.utc)
    assets = (
        db.query(MediaAsset)
        .filter(
            MediaAsset.status == MediaAssetStatus.READY,
            MediaAsset.expires_at.isnot(None),
            MediaAsset.expires_at <= moment,
        )
        .all()
    )
    for asset in assets:
        delete_asset_bytes(asset)
        asset.status = MediaAssetStatus.EXPIRED
        asset.storage_path = None
    if assets:
        db.commit()
    return len(assets)
