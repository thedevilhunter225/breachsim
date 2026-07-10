from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class EmailIntegrationRead(BaseModel):
    email_provider_enabled: bool
    email_provider_mode: str
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_from_email: EmailStr | None
    smtp_sender_name: str | None
    smtp_recipient_allowlist: list[EmailStr]
    has_password: bool


class EmailIntegrationUpdate(BaseModel):
    email_provider_enabled: bool = False
    email_provider_mode: str = "sandbox"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: EmailStr | None = None
    smtp_sender_name: str | None = None
    smtp_recipient_allowlist: list[EmailStr] = Field(default_factory=list)
