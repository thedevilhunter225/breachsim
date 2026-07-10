from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import Employee, Scenario, ScenarioVersion
from app.models.enums import ScenarioStatus
from app.schemas.scenarios import ScenarioEditRequest, ScenarioGenerateRequest
from app.services.audit import audit_log
from app.services.llm import LLMProvider, LLMProviderError, ScenarioPrompt, get_default_llm_provider
from app.services.policy_engine import get_or_create_policy, validate_generated_content, validate_generation_request
from app.services.profiling import ensure_context_profile


def generate_scenario(db: Session, *, request: ScenarioGenerateRequest, actor, llm_provider: LLMProvider | None = None) -> Scenario:
    employee = db.query(Employee).filter(Employee.id == request.employee_id, Employee.organization_id == actor.organization_id).first()
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    policy = get_or_create_policy(db, actor.organization_id)
    validation = validate_generation_request(policy, channel=request.channel, theme=request.theme, difficulty_level=request.difficulty_level)
    if not validation.passed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"errors": validation.errors})

    profile = ensure_context_profile(db, employee)
    provider = llm_provider or get_default_llm_provider()
    try:
        result = provider.generate(
            ScenarioPrompt(
                employee_name=employee.full_name,
                role_title=employee.role_title,
                department_name=employee.department.name if employee.department else "General",
                channel=request.channel,
                theme=request.theme,
                difficulty_level=request.difficulty_level,
                context_profile=profile.employee_context_profile,
                prompt_instructions=request.prompt_instructions,
                previous_failure_reasons=request.previous_failure_reasons,
                prior_training_history=request.prior_training_history,
            )
        )
    except LLMProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

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
    )
    db.add(version)
    db.flush()
    scenario.current_version_id = version.id

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
            "model": result["rationale_metadata"].get("model", settings.gemini_model if settings.gemini_api_key else "fallback"),
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
