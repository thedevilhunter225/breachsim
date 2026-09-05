from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=64)


class MfaEnrollRequest(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


class MfaEnrollResponse(BaseModel):
    secret: str
    provisioning_uri: str
    recovery_codes: list[str]


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    roles: list[str]
    organization_id: uuid.UUID


class TokenResponse(BaseModel):
    # Browser sessions receive the token only as a Secure, HttpOnly cookie. An
    # explicit non-browser API client may opt in to a bearer response.
    access_token: str | None = None
    token_type: str = "bearer"
    user: UserSummary
