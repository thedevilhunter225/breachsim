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


class SmsIntegrationRead(BaseModel):
    sms_provider_enabled: bool
    sms_provider_mode: str
    sms_api_base_url: str | None
    sms_account_sid: str | None
    sms_from_number: str | None
    sms_recipient_allowlist: list[str]
    has_auth_token: bool


class SmsIntegrationUpdate(BaseModel):
    sms_provider_enabled: bool = False
    sms_provider_mode: str = "sandbox"
    sms_api_base_url: str | None = None
    sms_account_sid: str | None = None
    sms_auth_token: str | None = None
    sms_from_number: str | None = None
    sms_recipient_allowlist: list[str] = Field(default_factory=list)


class ImpersonationSettingsRead(BaseModel):
    impersonation_enabled: bool
    impersonation_disclosure_text: str
    approved_persona_count: int
    voice_provider_enabled: bool
    voice_provider_mode: str
    #: Real cloning provider status, so the settings screen can guide setup.
    voice_clone_provider: str = "none"
    voice_clone_configured: bool = False
    video_clone_provider: str = "none"
    video_clone_configured: bool = False


class ImpersonationSettingsUpdate(BaseModel):
    impersonation_enabled: bool = False
    impersonation_disclosure_text: str | None = None
    voice_provider_enabled: bool = False
    voice_provider_mode: str = "simulator"
