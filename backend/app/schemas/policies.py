from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class PolicyUpdate(BaseModel):
    name: str = "Default policy"
    allowed_themes: list[str] = Field(default_factory=list)
    prohibited_words: list[str] = Field(default_factory=list)
    allowed_sender_names: list[str] = Field(default_factory=list)
    approved_training_domains: list[str] = Field(default_factory=list)
    allowed_delivery_channels: list[str] = Field(default_factory=list)
    difficulty_levels: list[str] = Field(default_factory=list)
    maximum_frequency_per_employee: int = 2
    working_hours_start: int = 9
    working_hours_end: int = 18
    second_approval_required: bool = True
    opt_out_respected: bool = True
    prohibited_topics: list[str] = Field(default_factory=list)


class PolicyRead(PolicyUpdate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
