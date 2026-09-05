"""Durable storage for generated audit evidence.

Local development keeps exports on disk. Production writes once to the private,
immutable Azure Blob container using the Container Apps managed identity.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import is_production_environment, settings


def _blob_name(*, organization_id: object, report_type: str, extension: str) -> str:
    now = datetime.now(timezone.utc)
    return (
        f"organizations/{organization_id}/{now:%Y/%m/%d}/"
        f"{report_type}-{now:%H%M%S}-{uuid.uuid4().hex}.{extension}"
    )


def persist_evidence(
    content: bytes,
    *,
    organization_id: object,
    report_type: str,
    extension: str,
    content_type: str,
) -> str:
    """Persist an evidence export and return an opaque storage reference."""

    blob_name = _blob_name(
        organization_id=organization_id,
        report_type=report_type,
        extension=extension,
    )
    if not is_production_environment(settings.environment):
        path = Path(__file__).resolve().parents[3] / settings.report_export_dir / blob_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)

    if not settings.evidence_storage_account_url:
        raise RuntimeError("EVIDENCE_STORAGE_ACCOUNT_URL is required in production")

    # Imports remain lazy so local/test installs do not try Azure authentication.
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient, ContentSettings

    service = BlobServiceClient(
        account_url=settings.evidence_storage_account_url,
        credential=DefaultAzureCredential(),
    )
    blob = service.get_blob_client(
        container=settings.evidence_storage_container,
        blob=blob_name,
    )
    blob.upload_blob(
        content,
        overwrite=False,
        content_settings=ContentSettings(content_type=content_type),
    )
    return f"azblob://{settings.evidence_storage_container}/{blob_name}"
