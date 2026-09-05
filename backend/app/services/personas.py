"""Consent governance for the voice and synthetic-media impersonation channels.

A deepfake simulation imitates somebody. That is the feature, and it is also the risk.
This service is the single gate every impersonation scenario must pass: a scenario can
only be generated against a persona that is registered, approved by an admin who is not
the persona's creator, and inside a live consent window.

Two persona kinds are supported:

``is_real_person = False``
    A synthetic composite role ("Finance Director"). No individual is imitated, so only
    admin approval is required.

``is_real_person = True``
    A named employee who has authorized use of their likeness. A consent reference and an
    expiry are mandatory, and the linked employee may revoke at any time.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.entities import Employee, ImpersonationPersona, Organization
from app.models.enums import Channel, MediaModality, PersonaStatus
from app.services.audit import audit_log
from app.services.channel_content import PersonaContext


class PersonaGuardrailError(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def slugify_reference(display_name: str, role_title: str) -> str:
    words = re.findall(r"[A-Za-z]+", f"{role_title} {display_name}")
    stub = "-".join(word.upper()[:4] for word in words[:2]) or "PERSONA"
    return f"PSN-{stub}"


def list_personas(db: Session, organization_id) -> list[ImpersonationPersona]:
    personas = (
        db.query(ImpersonationPersona)
        .filter(ImpersonationPersona.organization_id == organization_id)
        .order_by(ImpersonationPersona.created_at.desc())
        .all()
    )
    # Lazily flip expired consent so the console and the guardrail agree.
    changed = False
    for persona in personas:
        expires_at = _aware(persona.consent_expires_at)
        if persona.status == PersonaStatus.APPROVED and expires_at and expires_at <= _now():
            persona.status = PersonaStatus.EXPIRED
            changed = True
    if changed:
        db.commit()
    return personas


def get_persona(db: Session, organization_id, persona_id) -> ImpersonationPersona:
    persona = (
        db.query(ImpersonationPersona)
        .filter(
            ImpersonationPersona.id == persona_id,
            ImpersonationPersona.organization_id == organization_id,
        )
        .first()
    )
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")
    return persona


def create_persona(db: Session, *, actor, payload) -> ImpersonationPersona:
    if payload.is_real_person:
        if not payload.consent_reference:
            raise PersonaGuardrailError(
                "A persona representing a real person requires a signed consent reference."
            )
        if not payload.consent_expires_at:
            raise PersonaGuardrailError(
                "A persona representing a real person requires a consent expiry date."
            )
        if payload.linked_employee_id:
            employee = (
                db.query(Employee)
                .filter(
                    Employee.id == payload.linked_employee_id,
                    Employee.organization_id == actor.organization_id,
                )
                .first()
            )
            if not employee:
                raise PersonaGuardrailError("Linked employee not found in this organization.")

    reference_code = payload.reference_code or slugify_reference(payload.display_name, payload.role_title)
    if (
        db.query(ImpersonationPersona)
        .filter(
            ImpersonationPersona.organization_id == actor.organization_id,
            ImpersonationPersona.reference_code == reference_code,
        )
        .first()
    ):
        reference_code = f"{reference_code}-{uuid.uuid4().hex[:4].upper()}"

    persona = ImpersonationPersona(
        organization_id=actor.organization_id,
        created_by_user_id=actor.id,
        reference_code=reference_code,
        display_name=payload.display_name,
        role_title=payload.role_title,
        relationship_to_targets=payload.relationship_to_targets,
        modality=payload.modality,
        status=PersonaStatus.PENDING_CONSENT if payload.is_real_person else PersonaStatus.DRAFT,
        is_real_person=payload.is_real_person,
        linked_employee_id=payload.linked_employee_id,
        consent_reference=payload.consent_reference,
        consent_evidence_note=payload.consent_evidence_note,
        consent_granted_at=payload.consent_granted_at,
        consent_expires_at=payload.consent_expires_at,
        voice_profile=payload.voice_profile or {},
        detection_tells=payload.detection_tells or [],
    )
    db.add(persona)
    db.flush()
    audit_log(
        db,
        organization_id=actor.organization_id,
        user_id=actor.id,
        action="persona.create",
        resource_type="impersonation_persona",
        resource_id=str(persona.id),
        details={
            "display_name": persona.display_name,
            "is_real_person": persona.is_real_person,
            "modality": persona.modality.value,
            "consent_reference": persona.consent_reference,
        },
    )
    db.commit()
    db.refresh(persona)
    return persona


def approve_persona(db: Session, *, persona: ImpersonationPersona, actor) -> ImpersonationPersona:
    if persona.status == PersonaStatus.REVOKED:
        raise PersonaGuardrailError("A revoked persona cannot be re-approved. Register a new one.")
    if persona.created_by_user_id == actor.id:
        raise PersonaGuardrailError(
            "Impersonation personas require review by a second admin. "
            "The admin who registered a persona cannot approve it."
        )
    if persona.is_real_person:
        expires_at = _aware(persona.consent_expires_at)
        if not persona.consent_reference:
            raise PersonaGuardrailError("Cannot approve: no consent reference on file.")
        if not expires_at or expires_at <= _now():
            raise PersonaGuardrailError("Cannot approve: the consent window has already expired.")

    persona.status = PersonaStatus.APPROVED
    persona.approved_by_user_id = actor.id
    if not persona.consent_granted_at:
        persona.consent_granted_at = _now()
    audit_log(
        db,
        organization_id=actor.organization_id,
        user_id=actor.id,
        action="persona.approve",
        resource_type="impersonation_persona",
        resource_id=str(persona.id),
        details={"consent_expires_at": persona.consent_expires_at.isoformat() if persona.consent_expires_at else None},
    )
    db.commit()
    db.refresh(persona)
    return persona


def revoke_persona(db: Session, *, persona: ImpersonationPersona, actor, reason: str | None) -> ImpersonationPersona:
    persona.status = PersonaStatus.REVOKED
    persona.revoked_at = _now()
    persona.revocation_reason = reason or "Revoked by administrator"

    # Revocation must be meaningful: delete every cloned clip and retire the enrolled
    # voice at the provider so the likeness can no longer be synthesized anywhere.
    from app.services.media_enrollment import purge_persona_media

    removed = purge_persona_media(db, persona)

    audit_log(
        db,
        organization_id=actor.organization_id,
        user_id=actor.id,
        action="persona.revoke",
        resource_type="impersonation_persona",
        resource_id=str(persona.id),
        details={"reason": persona.revocation_reason, "media_assets_purged": removed},
    )
    db.commit()
    db.refresh(persona)
    return persona


def resolve_persona_for_scenario(
    db: Session,
    *,
    organization: Organization,
    channel: Channel,
    persona_id,
) -> ImpersonationPersona | None:
    """Enforce every impersonation guardrail before a scenario may be generated."""

    if channel not in {Channel.VISHING, Channel.DEEPFAKE}:
        return None

    if channel == Channel.DEEPFAKE and not organization.impersonation_enabled:
        raise PersonaGuardrailError(
            "Synthetic media impersonation is disabled for this organization. "
            "An administrator must enable it in Workspace Settings before deepfake scenarios can be generated."
        )

    if not persona_id:
        raise PersonaGuardrailError(
            f"The {channel.value} channel requires an approved impersonation persona. "
            "Register one in Governance -> Personas first."
        )

    persona = get_persona(db, organization.id, persona_id)

    if persona.status == PersonaStatus.REVOKED:
        raise PersonaGuardrailError(
            f"Persona '{persona.display_name}' was revoked and can no longer be used."
        )
    expires_at = _aware(persona.consent_expires_at)
    if expires_at and expires_at <= _now():
        if persona.status != PersonaStatus.EXPIRED:
            persona.status = PersonaStatus.EXPIRED
            db.commit()
        raise PersonaGuardrailError(
            f"Consent for persona '{persona.display_name}' expired on {expires_at.date().isoformat()}. "
            "Renew the authorization before running further simulations."
        )
    if persona.status != PersonaStatus.APPROVED:
        raise PersonaGuardrailError(
            f"Persona '{persona.display_name}' is '{persona.status.value}' and has not been approved by a second admin."
        )
    if persona.is_real_person and not persona.consent_reference:
        raise PersonaGuardrailError(
            f"Persona '{persona.display_name}' represents a real person but has no consent reference on file."
        )
    if channel == Channel.VISHING and persona.modality in {
        MediaModality.VIDEO_MESSAGE,
        MediaModality.LIVE_VIDEO_CALL,
    }:
        raise PersonaGuardrailError(
            f"Persona '{persona.display_name}' is registered for video, which cannot be used on a voice call."
        )

    return persona


def to_context(persona: ImpersonationPersona | None, *, disclosure_text: str | None = None) -> PersonaContext:
    """Adapt a stored persona into the content builder's value object."""
    if persona is None:
        return PersonaContext()
    return PersonaContext(
        display_name=persona.display_name,
        role_title=persona.role_title,
        relationship_to_targets=persona.relationship_to_targets,
        modality=persona.modality,
        voice_profile=persona.voice_profile or {},
        detection_tells=persona.detection_tells or [],
        reference_code=persona.reference_code,
        synthetic_disclosure_text=disclosure_text or persona.synthetic_disclosure_text,
    )
