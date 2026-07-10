from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Channel, DifficultyLevel, ScenarioStatus


class ScenarioGenerateRequest(BaseModel):
    employee_id: uuid.UUID
    channel: Channel
    theme: str
    difficulty_level: DifficultyLevel
    prompt_instructions: str | None = None
    previous_failure_reasons: list[str] = Field(default_factory=list)
    prior_training_history: list[str] = Field(default_factory=list)


class ScenarioEditRequest(BaseModel):
    subject: str
    body_copy: str
    cta_text: str
    landing_page_copy: str
    notes: str | None = None


class ScenarioVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_number: int
    subject: str
    body_copy: str
    cta_text: str
    landing_page_copy: str
    rationale_metadata: dict[str, Any]
    detected_persuasion_triggers: list[str]
    difficulty_score: int
    validation_result: dict[str, Any]
    notes: str | None
    created_at: datetime


class ScenarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    channel: Channel
    theme: str
    difficulty_level: DifficultyLevel
    status: ScenarioStatus
    detected_persuasion_triggers: list[str]
    policy_validation: dict[str, Any]
    approved_at: datetime | None
    latest_version: ScenarioVersionRead | None = None
