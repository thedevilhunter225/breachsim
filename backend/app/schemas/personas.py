from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MediaModality, PersonaStatus


class PersonaCreate(BaseModel):
    display_name: str = Field(min_length=2, max_length=255)
    role_title: str = Field(min_length=2, max_length=255)
    relationship_to_targets: str = "internal colleague"
    modality: MediaModality = MediaModality.VOICE_NOTE
    reference_code: str | None = None

    #: When true the persona represents an identifiable individual, which makes
    #: consent_reference and consent_expires_at mandatory.
    is_real_person: bool = False
    linked_employee_id: uuid.UUID | None = None
    consent_reference: str | None = None
    consent_evidence_note: str | None = None
    consent_granted_at: datetime | None = None
    consent_expires_at: datetime | None = None

    voice_profile: dict[str, Any] = Field(default_factory=dict)
    detection_tells: list[str] = Field(default_factory=list)


class PersonaRevokeRequest(BaseModel):
    reason: str | None = None


class PersonaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference_code: str
    display_name: str
    role_title: str
    relationship_to_targets: str
    modality: MediaModality
    status: PersonaStatus
    is_real_person: bool
    linked_employee_id: uuid.UUID | None
    consent_reference: str | None
    consent_granted_at: datetime | None
    consent_expires_at: datetime | None
    revoked_at: datetime | None
    revocation_reason: str | None
    voice_profile: dict[str, Any]
    detection_tells: list[str]
    synthetic_disclosure_text: str
    usage_count: int
    created_at: datetime
    approved_by_user_id: uuid.UUID | None
    voice_clone_provider: str | None = None
    voice_clone_ref: str | None = None
    has_face_image: bool = False
    #: Derived convenience flag so the console can grey out unusable personas.
    usable: bool = False
