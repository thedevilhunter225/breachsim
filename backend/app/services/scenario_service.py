from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.entities import Employee, Organization, Scenario, ScenarioVersion
from app.models.enums import ScenarioStatus
from app.schemas.scenarios import ScenarioEditRequest, ScenarioGenerateRequest
from app.services.audit import audit_log
from app.services.llm import (
    LLMProvider,
    LLMProviderError,
    RuleBasedLLMProvider,
    ScenarioPrompt,
    get_default_llm_provider,
)
from app.services.media_generation import generate_media_for_version
from app.services.personas import resolve_persona_for_scenario, to_context
from app.services.policy_engine import get_or_create_policy, validate_generated_content, validate_generation_request
from app.services.profiling import ensure_context_profile


def generate_scenario(db: Session, *, request: ScenarioGenerateRequest, actor, llm_provider: LLMProvider | None = None) -> Scenario:
    employee = db.query(Employee).filter(Employee.id == request.employee_id, Employee.organization_id == actor.organization_id).first()
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    organization = db.query(Organization).filter(Organization.id == actor.organization_id).first()
    policy = get_or_create_policy(db, actor.organization_id)
    validation = validate_generation_request(policy, channel=request.channel, theme=request.theme, difficulty_level=request.difficulty_level)
    if not validation.passed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"errors": validation.errors})

    # Voice and synthetic-media scenarios cannot be generated without an approved,
    # in-consent persona. This raises before any content is produced.
    persona = resolve_persona_for_scenario(
        db,
        organization=organization,
        channel=request.channel,
        persona_id=request.persona_id,
    )

    profile = ensure_context_profile(db, employee)
    prompt = ScenarioPrompt(
        employee_name=employee.full_name,
        role_title=employee.role_title,
        department_name=employee.department.name if employee.department else "General",
        company_name=organization.name if organization else "Organization",
        channel=request.channel,
        theme=request.theme,
        difficulty_level=request.difficulty_level,
        context_profile=profile.employee_context_profile,
        prompt_instructions=request.prompt_instructions,
        previous_failure_reasons=request.previous_failure_reasons,
        prior_training_history=request.prior_training_history,
        persona=to_context(persona, disclosure_text=organization.impersonation_disclosure_text if organization else None),
        disclosure_text=organization.impersonation_disclosure_text if organization else None,
    )
    provider = llm_provider or get_default_llm_provider()
    try:
        result = provider.generate(prompt)
    except LLMProviderError as exc:
        result = RuleBasedLLMProvider().generate(prompt)
        result["rationale_metadata"].update(
            {
                "provider_status": "fallback",
                "fallback_from": type(provider).__name__,
                "fallback_reason": str(exc),
            }
        )

    post_validation = validate_generated_content(
        policy,
        subject=result["subject"],
        body_copy=result["body_copy"],
        cta_text=result["cta_text"],
        landing_page_copy=result["landing_page_copy"],
    )
    if not post_validation.passed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"errors": post_validation.errors})

    scenario = Scenario(
        organization_id=actor.organization_id,
        created_by_user_id=actor.id,
        profile_id=profile.id,
        persona_id=persona.id if persona else None,
        title=result["title"],
        channel=request.channel,
        theme=request.theme,
        difficulty_level=request.difficulty_level,
        status=ScenarioStatus.GENERATED,
        detected_persuasion_triggers=result["detected_persuasion_triggers"],
        policy_validation={"errors": post_validation.errors, "warnings": post_validation.warnings, "passed": True},
    )
    db.add(scenario)
    db.flush()

    version = ScenarioVersion(
        scenario_id=scenario.id,
        version_number=1,
        created_by_user_id=actor.id,
        subject=result["subject"],
        body_copy=result["body_copy"],
        cta_text=result["cta_text"],
        landing_page_copy=result["landing_page_copy"],
        rationale_metadata=result["rationale_metadata"],
        detected_persuasion_triggers=result["detected_persuasion_triggers"],
        difficulty_score=result["difficulty_score"],
        validation_result={"errors": post_validation.errors, "warnings": post_validation.warnings, "passed": True},
        channel_payload=result.get("channel_payload") or {},
    )
    db.add(version)
    db.flush()
    scenario.current_version_id = version.id

    if persona:
        persona.usage_count = (persona.usage_count or 0) + 1

    # Render real cloned voice/video for the interactive channels. Best-effort: a missing
    # or failing provider leaves the scenario fully usable on the browser-TTS fallback.
    media_summary = generate_media_for_version(
        db, version=version, persona=persona, channel=request.channel, actor=actor
    )
    if media_summary.get("voice") != "skipped":
        rationale = dict(version.rationale_metadata or {})
        rationale["media_generation"] = media_summary
        version.rationale_metadata = rationale
        db.flush()

    audit_log(
        db,
        organization_id=actor.organization_id,
        user_id=actor.id,
        action="scenario.generate",
        resource_type="scenario",
        resource_id=str(scenario.id),
        details={
            "theme": request.theme,
            "channel": request.channel.value,
            "prompt_instructions": request.prompt_instructions,
            "provider": result["rationale_metadata"].get("provider", "rule-based"),
            "model": result["rationale_metadata"].get("model", "fallback"),
            "persona_id": str(persona.id) if persona else None,
            "persona_reference": persona.reference_code if persona else None,
        },
    )
    db.commit()
    db.refresh(scenario)
    return scenario


def create_scenario_version(db: Session, *, scenario: Scenario, edit: ScenarioEditRequest, actor) -> Scenario:
    policy = get_or_create_policy(db, actor.organization_id)
    post_validation = validate_generated_content(
        policy,
        subject=edit.subject,
        body_copy=edit.body_copy,
        cta_text=edit.cta_text,
        landing_page_copy=edit.landing_page_copy,
    )
    if not post_validation.passed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"errors": post_validation.errors})

    latest = max(scenario.versions, key=lambda version: version.version_number)
    next_number = latest.version_number + 1
    version = ScenarioVersion(
        scenario_id=scenario.id,
        version_number=next_number,
        created_by_user_id=actor.id,
        subject=edit.subject,
        body_copy=edit.body_copy,
        cta_text=edit.cta_text,
        landing_page_copy=edit.landing_page_copy,
        rationale_metadata=latest.rationale_metadata,
        detected_persuasion_triggers=latest.detected_persuasion_triggers,
        difficulty_score=latest.difficulty_score,
        validation_result={"errors": post_validation.errors, "warnings": post_validation.warnings, "passed": True},
        notes=edit.notes,
        # Manual copy edits never rewrite the branching script; the structure stays governed.
        channel_payload=latest.channel_payload or {},
    )
    db.add(version)
    db.flush()
    scenario.title = edit.subject
    scenario.current_version_id = version.id
    scenario.status = ScenarioStatus.PENDING_APPROVAL
    audit_log(
        db,
        organization_id=actor.organization_id,
        user_id=actor.id,
        action="scenario.edit",
        resource_type="scenario",
        resource_id=str(scenario.id),
        details={"version": next_number},
    )
    db.commit()
    db.refresh(scenario)
    return scenario


def approve_scenario(db: Session, *, scenario: Scenario, actor) -> Scenario:
    scenario.status = ScenarioStatus.APPROVED
    scenario.approved_by_user_id = actor.id
    scenario.approved_at = datetime.now(timezone.utc)
    audit_log(
        db,
        organization_id=actor.organization_id,
        user_id=actor.id,
        action="scenario.approve",
        resource_type="scenario",
        resource_id=str(scenario.id),
    )
    db.commit()
    db.refresh(scenario)
    return scenario


def reject_scenario(db: Session, *, scenario: Scenario, actor, reason: str | None = None) -> Scenario:
    scenario.status = ScenarioStatus.REJECTED
    audit_log(
        db,
        organization_id=actor.organization_id,
        user_id=actor.id,
        action="scenario.reject",
        resource_type="scenario",
        resource_id=str(scenario.id),
        details={"reason": reason or "No reason provided"},
    )
    db.commit()
    db.refresh(scenario)
    return scenario
