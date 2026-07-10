from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import ConsentStatus, EmployeeStatus


class DepartmentCreate(BaseModel):
    name: str
    code: str


class DepartmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str


class EmployeeBase(BaseModel):
    employee_id: str
    full_name: str
    email: EmailStr
    phone: str | None = None
    department_id: uuid.UUID | None = None
    role_title: str
    approved_context_summary: str | None = None
    approved_public_profile_summary: str | None = None
    training_preferences: list[str] = Field(default_factory=list)
    consent_status: ConsentStatus = ConsentStatus.PENDING
    status: EmployeeStatus = EmployeeStatus.ACTIVE


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    department_id: uuid.UUID | None = None
    role_title: str | None = None
    approved_context_summary: str | None = None
    approved_public_profile_summary: str | None = None
    training_preferences: list[str] | None = None
    consent_status: ConsentStatus | None = None
    status: EmployeeStatus | None = None


class ConsentUpdate(BaseModel):
    status: ConsentStatus
    note: str | None = None
    source: str = "manual"


class ContextProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_context_profile: str
    likely_scenario_themes: list[str]
    allowed_channels: list[str]
    sensitivity_tags: list[str]
    created_at: datetime


class EmployeeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: str
    full_name: str
    email: EmailStr
    phone: str | None
    role_title: str
    approved_context_summary: str | None
    approved_public_profile_summary: str | None
    training_preferences: list[str]
    consent_status: ConsentStatus
    risk_score: int
    status: EmployeeStatus
    department_id: uuid.UUID | None
    department_name: str | None = None
    latest_context_profile: ContextProfileRead | None = None


class EmployeeImportRecord(BaseModel):
    employee_id: str
    full_name: str
    email: EmailStr
    phone: str | None = None
    department: str
    role_title: str
    approved_context_summary: str | None = None
    consent_status: ConsentStatus = ConsentStatus.PENDING


class EmployeeImportPayload(BaseModel):
    rows: list[EmployeeImportRecord]


class EmployeeImportResult(BaseModel):
    created: int
    updated: int
    errors: list[dict[str, Any]]
