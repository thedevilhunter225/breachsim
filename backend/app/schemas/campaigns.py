from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CampaignStatus, CampaignType, Channel, DeliveryStatus


class CampaignCreate(BaseModel):
    name: str
    description: str | None = None
    channel: Channel
    campaign_type: CampaignType = CampaignType.ONE_TIME
    schedule_at: datetime | None = None
    throttling_per_hour: int = 25
    target_employee_ids: list[uuid.UUID] = Field(default_factory=list)
    scenario_ids: list[uuid.UUID] = Field(default_factory=list)
    requires_second_approval: bool = True
    sandbox_mode: bool = True
    learning_objective: str = "Recognize social engineering patterns."
    target_filters: dict[str, Any] = Field(default_factory=dict)
    landing_domain_id: uuid.UUID | None = None
    email_connection_id: uuid.UUID | None = None


class CampaignUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    schedule_at: datetime | None = None
    throttling_per_hour: int | None = None
    requires_second_approval: bool | None = None
    sandbox_mode: bool | None = None
    learning_objective: str | None = None
    target_filters: dict[str, Any] | None = None
    landing_domain_id: uuid.UUID | None = None
    email_connection_id: uuid.UUID | None = None


class CampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    channel: Channel
    campaign_type: CampaignType
    status: CampaignStatus
    schedule_at: datetime | None
    throttling_per_hour: int
    requires_second_approval: bool
    sandbox_mode: bool
    learning_objective: str
    target_filters: dict[str, Any]
    target_count: int = 0
    scenario_count: int = 0
    landing_domain_id: uuid.UUID | None = None
    email_connection_id: uuid.UUID | None = None


class DeliveryAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    campaign_id: uuid.UUID
    employee_id: uuid.UUID
    channel: Channel
    status: DeliveryStatus
    sandbox_mode: bool
    preview_payload: dict[str, Any]
    delivered_at: datetime | None
    campaign_run_id: uuid.UUID | None = None
    provider_message_id: str | None = None
    retry_count: int = 0
    next_attempt_at: datetime | None = None
    last_error_code: str | None = None
