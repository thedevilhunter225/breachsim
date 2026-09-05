from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import UserRole


class UserAccountRead(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    roles: list[str]
    is_active: bool
    created_at: datetime


class UserAccountCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=14, max_length=1024)
    roles: list[UserRole] = Field(min_length=1)

    @field_validator("roles")
    @classmethod
    def roles_must_be_unique(cls, value: list[UserRole]) -> list[UserRole]:
        if len(set(value)) != len(value):
            raise ValueError("roles must be unique")
        return value


class UserAccountUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    roles: list[UserRole] | None = Field(default=None, min_length=1)
    is_active: bool | None = None


class UserPasswordReset(BaseModel):
    new_password: str = Field(min_length=14, max_length=1024)
