from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import TrainingAssignmentStatus


class TrainingModuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    vector: str
    primary_reason_code: str
    duration_seconds: int
    guidance_points: list[str]
    body: str


class TrainingAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    campaign_id: uuid.UUID | None
    status: TrainingAssignmentStatus
    assigned_reason_codes: list[str]
    retest_scheduled_for: datetime | None
    module: TrainingModuleRead


class TrainingCompleteRequest(BaseModel):
    dwell_seconds: int = 45
