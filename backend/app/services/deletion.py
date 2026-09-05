"""Guarded deletion.

Deleting things in a security-awareness platform is not a plain cascade. A scenario that
has been used in a campaign is part of that campaign's evidence chain; a campaign that has
recorded events is the proof an exercise took place. So each entity has explicit rules, and
anything that would destroy evidence requires the caller to say so deliberately.

Every deletion is written to the append-only audit log with counts of what was removed —
never the personal data itself.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.entities import (
    Campaign,
    CampaignScenario,
    CampaignTarget,
    ConsentRecord,
    ContextProfile,
    DeliveryAttempt,
    Department,
    Employee,
    EventLog,
    ImpersonationPersona,
    LandingToken,
    MediaAsset,
    RiskScore,
    Scenario,
    ScenarioVersion,
    SimulationResponse,
    TrainingAssignment,
    TrainingCompletion,
)
from app.models.enums import CampaignStatus, PersonaStatus
from app.services import media_store
from app.services.audit import audit_log


class DeletionBlocked(HTTPException):
    """A referential or evidence guardrail refused the deletion."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


@dataclass
class DeletionResult:
    resource: str
    resource_id: str
    label: str
    removed: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "resource_id": self.resource_id,
            "label": self.label,
            "removed": {key: value for key, value in self.removed.items() if value},
        }


def _count(db: Session, model, *criteria) -> int:
    return db.query(model).filter(*criteria).count()


# --------------------------------------------------------------------------------------
# Scenario
# --------------------------------------------------------------------------------------

def delete_scenario(db: Session, *, organization_id, scenario_id, actor) -> DeletionResult:
    """Remove a scenario and its versions.

    Refused while the scenario is attached to any campaign: the campaign's report cites it,
    so the campaign must be dealt with first. This keeps the evidence chain intact rather
    than leaving reports pointing at nothing.
    """
    scenario = (
        db.query(Scenario)
        .filter(Scenario.id == scenario_id, Scenario.organization_id == organization_id)
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")

    links = (
        db.query(CampaignScenario, Campaign)
        .join(Campaign, Campaign.id == CampaignScenario.campaign_id)
        .filter(CampaignScenario.scenario_id == scenario.id)
        .all()
    )
    if links:
        names = ", ".join(sorted({campaign.name for _, campaign in links}))
        raise DeletionBlocked(
            f"This scenario is used by {len(links)} campaign(s): {names}. "
            "Delete or detach those campaigns first — their reports reference this content."
        )

    version_ids = [version.id for version in scenario.versions]
    removed: dict[str, int] = {}

    if version_ids:
        assets = db.query(MediaAsset).filter(MediaAsset.scenario_version_id.in_(version_ids)).all()
        for asset in assets:
            media_store.delete_asset_bytes(asset)
        if assets:
            db.query(MediaAsset).filter(MediaAsset.scenario_version_id.in_(version_ids)).delete(
                synchronize_session=False
            )
            removed["media_assets"] = len(assets)

    # Any delivery attempt referencing this scenario would be orphaned; a scenario with no
    # campaign should not have any, but clear the pointer defensively.
    orphan_attempts = db.query(DeliveryAttempt).filter(DeliveryAttempt.scenario_id == scenario.id).count()
    if orphan_attempts:
        db.query(DeliveryAttempt).filter(DeliveryAttempt.scenario_id == scenario.id).update(
            {DeliveryAttempt.scenario_id: None}, synchronize_session=False
        )
        removed["detached_delivery_attempts"] = orphan_attempts

    label = scenario.title
    removed["scenario_versions"] = len(version_ids)
    # Break the self-reference first: current_version_id points into scenario_versions,
    # which would otherwise be a dangling FK mid-delete. The versions themselves are
    # removed by the relationship's delete-orphan cascade — deleting them manually here
    # too would make the ORM try to delete already-gone rows.
    scenario.current_version_id = None
    db.flush()
    db.delete(scenario)

    result = DeletionResult(resource="scenario", resource_id=str(scenario_id), label=label, removed=removed)
    audit_log(
        db,
        organization_id=organization_id,
        user_id=actor.id,
        action="scenario.delete",
        resource_type="scenario",
        resource_id=str(scenario_id),
        details=result.as_dict(),
    )
    db.commit()
    return result


# --------------------------------------------------------------------------------------
# Campaign
# --------------------------------------------------------------------------------------

def delete_campaign(db: Session, *, organization_id, campaign_id, actor, purge_evidence: bool = False) -> DeletionResult:
    """Remove a campaign.

    An active campaign must be paused first. A campaign that has recorded interaction
    evidence is refused unless ``purge_evidence`` is set, so nobody quietly erases the
    record of an exercise that already ran.
    """
    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.organization_id == organization_id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    if campaign.status == CampaignStatus.ACTIVE:
        raise DeletionBlocked(
            "This campaign is active. Pause it before deleting, so no simulation is cut off mid-flight."
        )

    event_count = _count(db, EventLog, EventLog.campaign_id == campaign.id)
    response_count = _count(db, SimulationResponse, SimulationResponse.campaign_id == campaign.id)
    if (event_count or response_count) and not purge_evidence:
        raise DeletionBlocked(
            f"This campaign holds {event_count} recorded event(s) and {response_count} interaction "
            "response(s) — that is the evidence the exercise happened. Re-send with "
            "purge_evidence=true to delete it anyway; the purge itself is audited."
        )

    removed: dict[str, int] = {}
    attempt_ids = [
        row.id for row in db.query(DeliveryAttempt).filter(DeliveryAttempt.campaign_id == campaign.id).all()
    ]

    assignment_ids = [
        row.id for row in db.query(TrainingAssignment).filter(TrainingAssignment.campaign_id == campaign.id).all()
    ]
    if assignment_ids:
        removed["training_completions"] = (
            db.query(TrainingCompletion)
            .filter(TrainingCompletion.assignment_id.in_(assignment_ids))
            .delete(synchronize_session=False)
        )
        removed["training_assignments"] = (
            db.query(TrainingAssignment)
            .filter(TrainingAssignment.id.in_(assignment_ids))
            .delete(synchronize_session=False)
        )

    removed["simulation_responses"] = (
        db.query(SimulationResponse)
        .filter(SimulationResponse.campaign_id == campaign.id)
        .delete(synchronize_session=False)
    )
    removed["events"] = (
        db.query(EventLog).filter(EventLog.campaign_id == campaign.id).delete(synchronize_session=False)
    )
    removed["landing_tokens"] = (
        db.query(LandingToken).filter(LandingToken.campaign_id == campaign.id).delete(synchronize_session=False)
    )
    if attempt_ids:
        removed["delivery_attempts"] = (
            db.query(DeliveryAttempt)
            .filter(DeliveryAttempt.id.in_(attempt_ids))
            .delete(synchronize_session=False)
        )
    removed["targets"] = (
        db.query(CampaignTarget).filter(CampaignTarget.campaign_id == campaign.id).delete(synchronize_session=False)
    )
    removed["scenario_links"] = (
        db.query(CampaignScenario)
        .filter(CampaignScenario.campaign_id == campaign.id)
        .delete(synchronize_session=False)
    )

    label = campaign.name
    db.delete(campaign)

    result = DeletionResult(resource="campaign", resource_id=str(campaign_id), label=label, removed=removed)
    audit_log(
        db,
        organization_id=organization_id,
        user_id=actor.id,
        action="campaign.delete",
        resource_type="campaign",
        resource_id=str(campaign_id),
        details={**result.as_dict(), "purged_evidence": bool(purge_evidence)},
    )
    db.commit()
    return result


# --------------------------------------------------------------------------------------
# Employee
# --------------------------------------------------------------------------------------

REDACTED = "[redacted]"


def _redact_employee_from_content(db: Session, *, employee, scenario_ids: list) -> int:
    """Strip an erased employee's name out of already-generated scenario copy.

    The generator personalises content with the target's real name, so simply deleting
    the employee row would leave their name readable in `scenario_versions.body_copy` —
    including via the unauthenticated training landing page. Erasure has to reach it.
    """
    if not scenario_ids:
        return 0

    names = [part for part in [employee.full_name, *(employee.full_name or "").split()] if len(part) > 2]
    # Longest first, so "Ada Lovelace" is replaced before the bare "Ada".
    names = sorted(set(names), key=len, reverse=True)

    redacted = 0
    versions = db.query(ScenarioVersion).filter(ScenarioVersion.scenario_id.in_(scenario_ids)).all()
    for version in versions:
        changed = False
        for field_name in ("subject", "body_copy", "landing_page_copy", "cta_text"):
            value = getattr(version, field_name, None)
            if not value:
                continue
            scrubbed = value
            for name in names:
                scrubbed = scrubbed.replace(name, REDACTED)
            if scrubbed != value:
                setattr(version, field_name, scrubbed)
                changed = True

        payload = version.channel_payload or {}
        if payload:
            serialized = json.dumps(payload)
            scrubbed_payload = serialized
            for name in names:
                scrubbed_payload = scrubbed_payload.replace(name, REDACTED)
            if scrubbed_payload != serialized:
                version.channel_payload = json.loads(scrubbed_payload)
                changed = True

        if changed:
            redacted += 1
    db.flush()
    return redacted


def delete_employee(db: Session, *, organization_id, employee_id, actor) -> DeletionResult:
    """Erase an employee and everything personally attributable to them.

    This is the right-to-erasure path: consent records, context profiles, risk history,
    training, interaction responses and events all go. The audit entry records counts only,
    never the person's data, so the deletion is provable without re-storing what was erased.
    """
    employee = (
        db.query(Employee)
        .filter(Employee.id == employee_id, Employee.organization_id == organization_id)
        .first()
    )
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    linked_persona = (
        db.query(ImpersonationPersona)
        .filter(
            ImpersonationPersona.linked_employee_id == employee.id,
            ImpersonationPersona.status != PersonaStatus.REVOKED,
        )
        .first()
    )
    if linked_persona:
        raise DeletionBlocked(
            f"This employee backs the active impersonation persona '{linked_persona.display_name}'. "
            "Revoke that persona first — revoking also destroys any cloned media of them."
        )

    removed: dict[str, int] = {}
    assignment_ids = [
        row.id for row in db.query(TrainingAssignment).filter(TrainingAssignment.employee_id == employee.id).all()
    ]
    if assignment_ids:
        removed["training_completions"] = (
            db.query(TrainingCompletion)
            .filter(TrainingCompletion.assignment_id.in_(assignment_ids))
            .delete(synchronize_session=False)
        )
        removed["training_assignments"] = (
            db.query(TrainingAssignment)
            .filter(TrainingAssignment.id.in_(assignment_ids))
            .delete(synchronize_session=False)
        )

    removed["simulation_responses"] = (
        db.query(SimulationResponse)
        .filter(SimulationResponse.employee_id == employee.id)
        .delete(synchronize_session=False)
    )
    removed["events"] = (
        db.query(EventLog).filter(EventLog.employee_id == employee.id).delete(synchronize_session=False)
    )
    removed["landing_tokens"] = (
        db.query(LandingToken).filter(LandingToken.employee_id == employee.id).delete(synchronize_session=False)
    )
    removed["delivery_attempts"] = (
        db.query(DeliveryAttempt)
        .filter(DeliveryAttempt.employee_id == employee.id)
        .delete(synchronize_session=False)
    )
    removed["campaign_targets"] = (
        db.query(CampaignTarget)
        .filter(CampaignTarget.employee_id == employee.id)
        .delete(synchronize_session=False)
    )
    removed["risk_scores"] = (
        db.query(RiskScore).filter(RiskScore.employee_id == employee.id).delete(synchronize_session=False)
    )

    # Scenarios point at this employee's context profile and any revoked persona points at
    # the employee row itself. Both must be released before the parents go, or Postgres —
    # which, unlike our local SQLite, enforces foreign keys — raises IntegrityError and the
    # whole erasure fails.
    profile_ids = [
        row.id for row in db.query(ContextProfile).filter(ContextProfile.employee_id == employee.id).all()
    ]
    # Capture the affected scenarios *before* detaching them — once profile_id is nulled
    # there is no way back to find which content mentioned this person.
    scenario_ids = (
        [row.id for row in db.query(Scenario).filter(Scenario.profile_id.in_(profile_ids)).all()]
        if profile_ids
        else []
    )

    # Generated copy embeds the person's name, so erasure is incomplete until it is scrubbed.
    if scenario_ids:
        removed["scenario_versions_redacted"] = _redact_employee_from_content(
            db, employee=employee, scenario_ids=scenario_ids
        )
        removed["scenarios_detached"] = (
            db.query(Scenario)
            .filter(Scenario.id.in_(scenario_ids))
            .update({Scenario.profile_id: None}, synchronize_session=False)
        )

    removed["personas_unlinked"] = (
        db.query(ImpersonationPersona)
        .filter(ImpersonationPersona.linked_employee_id == employee.id)
        .update({ImpersonationPersona.linked_employee_id: None}, synchronize_session=False)
    )

    removed["context_profiles"] = (
        db.query(ContextProfile)
        .filter(ContextProfile.employee_id == employee.id)
        .delete(synchronize_session=False)
    )
    removed["consent_records"] = (
        db.query(ConsentRecord)
        .filter(ConsentRecord.employee_id == employee.id)
        .delete(synchronize_session=False)
    )

    label = employee.employee_id  # internal code, not the person's name
    db.delete(employee)

    result = DeletionResult(resource="employee", resource_id=str(employee_id), label=label, removed=removed)
    audit_log(
        db,
        organization_id=organization_id,
        user_id=actor.id,
        action="employee.delete",
        resource_type="employee",
        resource_id=str(employee_id),
        details=result.as_dict(),
    )
    db.commit()
    return result


# --------------------------------------------------------------------------------------
# Department
# --------------------------------------------------------------------------------------

def delete_department(db: Session, *, organization_id, department_id, actor) -> DeletionResult:
    department = (
        db.query(Department)
        .filter(Department.id == department_id, Department.organization_id == organization_id)
        .first()
    )
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    headcount = _count(db, Employee, Employee.department_id == department.id)
    if headcount:
        raise DeletionBlocked(
            f"{headcount} employee(s) are still assigned to '{department.name}'. "
            "Reassign or remove them first."
        )

    removed = {
        "risk_scores": db.query(RiskScore)
        .filter(RiskScore.department_id == department.id)
        .delete(synchronize_session=False)
    }
    label = department.name
    db.delete(department)

    result = DeletionResult(resource="department", resource_id=str(department_id), label=label, removed=removed)
    audit_log(
        db,
        organization_id=organization_id,
        user_id=actor.id,
        action="department.delete",
        resource_type="department",
        resource_id=str(department_id),
        details=result.as_dict(),
    )
    db.commit()
    return result


# --------------------------------------------------------------------------------------
# Persona
# --------------------------------------------------------------------------------------

def delete_persona(db: Session, *, organization_id, persona_id, actor) -> DeletionResult:
    """Remove a persona that was never used.

    A persona with scenario history is refused — revocation is the correct action there,
    since it destroys the cloned media while preserving the consent record that proves the
    impersonation was authorized at the time.
    """
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

    used_by = _count(db, Scenario, Scenario.persona_id == persona.id)
    if used_by:
        raise DeletionBlocked(
            f"'{persona.display_name}' has been used in {used_by} scenario(s). Revoke it instead — "
            "revocation destroys the cloned media while keeping the consent record that proves "
            "the impersonation was authorized."
        )

    assets = db.query(MediaAsset).filter(MediaAsset.persona_id == persona.id).all()
    for asset in assets:
        media_store.delete_asset_bytes(asset)
    removed = {
        "media_assets": db.query(MediaAsset)
        .filter(MediaAsset.persona_id == persona.id)
        .delete(synchronize_session=False)
    }

    # Retire any enrolled voice at the provider before dropping the row.
    if persona.voice_clone_ref:
        from app.services.media import get_voice_provider

        provider = get_voice_provider()
        if provider:
            provider.delete_voice(persona.voice_clone_ref)
        removed["provider_voice_retired"] = 1

    label = persona.display_name
    db.delete(persona)

    result = DeletionResult(resource="persona", resource_id=str(persona_id), label=label, removed=removed)
    audit_log(
        db,
        organization_id=organization_id,
        user_id=actor.id,
        action="persona.delete",
        resource_type="impersonation_persona",
        resource_id=str(persona_id),
        details=result.as_dict(),
    )
    db.commit()
    return result
