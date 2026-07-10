from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.entities import Scenario
from app.models.enums import UserRole
from app.schemas.scenarios import ScenarioEditRequest, ScenarioGenerateRequest, ScenarioRead, ScenarioVersionRead
from app.services.scenario_service import approve_scenario, create_scenario_version, generate_scenario, reject_scenario

router = APIRouter()


def serialize_scenario(scenario: Scenario) -> ScenarioRead:
    latest = next((version for version in scenario.versions if version.id == scenario.current_version_id), None)
    if latest is None and scenario.versions:
        latest = max(scenario.versions, key=lambda version: version.version_number)
    return ScenarioRead(
        id=str(scenario.id),
        title=scenario.title,
        channel=scenario.channel,
        theme=scenario.theme,
        difficulty_level=scenario.difficulty_level,
        status=scenario.status,
        detected_persuasion_triggers=scenario.detected_persuasion_triggers,
        policy_validation=scenario.policy_validation,
        approved_at=scenario.approved_at,
        latest_version=ScenarioVersionRead.model_validate(latest) if latest else None,
    )


@router.get("/scenarios", response_model=list[ScenarioRead])
def list_scenarios(db: Annotated[Session, Depends(get_db)], user=Depends(get_current_user)):
    scenarios = (
        db.query(Scenario)
        .options(joinedload(Scenario.versions))
        .filter(Scenario.organization_id == user.organization_id)
        .order_by(Scenario.created_at.desc())
        .all()
    )
    return [serialize_scenario(scenario) for scenario in scenarios]


@router.post("/scenarios/generate", response_model=ScenarioRead, status_code=status.HTTP_201_CREATED)
def generate(payload: ScenarioGenerateRequest, db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER))):
    scenario = generate_scenario(db, request=payload, actor=user)
    scenario = db.query(Scenario).options(joinedload(Scenario.versions)).filter(Scenario.id == scenario.id).first()
    return serialize_scenario(scenario)


@router.get("/scenarios/{scenario_id}", response_model=ScenarioRead)
def get_scenario(scenario_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], user=Depends(get_current_user)):
    scenario = (
        db.query(Scenario)
        .options(joinedload(Scenario.versions))
        .filter(Scenario.id == scenario_id, Scenario.organization_id == user.organization_id)
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    return serialize_scenario(scenario)


@router.patch("/scenarios/{scenario_id}", response_model=ScenarioRead)
def edit_scenario(
    scenario_id: uuid.UUID,
    payload: ScenarioEditRequest,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER)),
):
    scenario = (
        db.query(Scenario)
        .options(joinedload(Scenario.versions))
        .filter(Scenario.id == scenario_id, Scenario.organization_id == user.organization_id)
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    scenario = create_scenario_version(db, scenario=scenario, edit=payload, actor=user)
    scenario = db.query(Scenario).options(joinedload(Scenario.versions)).filter(Scenario.id == scenario.id).first()
    return serialize_scenario(scenario)


@router.post("/scenarios/{scenario_id}/approve", response_model=ScenarioRead)
def approve(scenario_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(UserRole.ADMIN))):
    scenario = db.query(Scenario).options(joinedload(Scenario.versions)).filter(Scenario.id == scenario_id, Scenario.organization_id == user.organization_id).first()
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    return serialize_scenario(approve_scenario(db, scenario=scenario, actor=user))


@router.post("/scenarios/{scenario_id}/reject", response_model=ScenarioRead)
def reject(
    scenario_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    reason: str | None = Query(default=None),
    user=Depends(require_roles(UserRole.ADMIN)),
):
    scenario = db.query(Scenario).options(joinedload(Scenario.versions)).filter(Scenario.id == scenario_id, Scenario.organization_id == user.organization_id).first()
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    return serialize_scenario(reject_scenario(db, scenario=scenario, actor=user, reason=reason))
