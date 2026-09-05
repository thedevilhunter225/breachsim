from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator, model_validator

from app.models.enums import (
    CampaignRunStatus,
    ConnectionStatus,
    DomainKind,
    DomainPurpose,
    EmailProviderKind,
    ReportingIdentityMode,
    SuppressionReason,
    UserRole,
    VerificationStatus,
)


class OrganizationDomainCreate(BaseModel):
    hostname: str = Field(min_length=3, max_length=253)
    purpose: DomainPurpose


class OrganizationDomainRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    hostname: str
    purpose: DomainPurpose
    kind: DomainKind
    status: VerificationStatus
    dns_instructions: dict
    validation_error: str | None
    is_primary: bool
    verified_at: datetime | None
    deactivated_at: datetime | None
    verification_value: str | None = None


class DomainVerificationRequest(BaseModel):
    # Accepted only outside production for deterministic local/integration testing.
    proof: str | None = Field(default=None, max_length=512)


class OrganizationBrandingUpdate(BaseModel):
    logo_url: HttpUrl | None = None
    primary_color: str = "#173B73"
    accent_color: str = "#175CD3"
    sender_name: str = Field(default="Security Awareness", min_length=2, max_length=255)
    legal_footer: str = Field(default="Authorized security-awareness simulation.", min_length=3, max_length=2000)
    approved_template_ids: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("primary_color", "accent_color")
    @classmethod
    def validate_hex_color(cls, value: str) -> str:
        if len(value) != 7 or not value.startswith("#"):
            raise ValueError("must be a six-digit hexadecimal color")
        int(value[1:], 16)
        return value.upper()


class OrganizationBrandingRead(OrganizationBrandingUpdate):
    id: uuid.UUID
    organization_id: uuid.UUID


class EmailConnectionCreate(BaseModel):
    provider: EmailProviderKind
    display_name: str = Field(min_length=2, max_length=255)
    sender_email: EmailStr
    sender_name: str = Field(min_length=2, max_length=255)
    customer_tenant_id: str | None = Field(default=None, max_length=255)
    delegated_subject: EmailStr | None = None
    rate_limit_per_minute: int = Field(default=120, ge=1, le=2000)


class EmailConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: EmailProviderKind
    display_name: str
    customer_tenant_id: str | None
    sender_email: EmailStr
    sender_name: str
    delegated_subject: EmailStr | None
    reconciliation_secret_ref: str | None
    scopes: list[str]
    status: ConnectionStatus
    rate_limit_per_minute: int
    last_health_check_at: datetime | None
    last_error: str | None
    authorized_at: datetime | None
    revoked_at: datetime | None


class ProviderReconciliationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=4, max_length=255)
    attempt_id: uuid.UUID | None = None
    provider_message_id: str | None = Field(default=None, max_length=255)
    status: str = Field(pattern=r"^(accepted|bounced|unknown|failed)$")
    reason_code: str | None = Field(default=None, max_length=128)
    hard_bounce: bool = False

    @model_validator(mode="after")
    def require_attempt_or_provider_id(self):
        if self.provider_message_id is None and self.attempt_id is None:
            raise ValueError("attempt_id or provider_message_id is required")
        return self


class OAuthStartResponse(BaseModel):
    connection: EmailConnectionRead
    authorization_url: str


class EmailConnectionTestRead(BaseModel):
    connection: EmailConnectionRead
    provider_authorized: bool
    sender_domain_verified: bool
    spf_present: bool
    dmarc_present: bool
    dkim_present: bool
    test_message_status: str | None = None


class GoogleDomainWideDelegationRead(BaseModel):
    connection_id: uuid.UUID
    admin_console_url: str
    oauth_client_id: str
    oauth_scope: str
    delegated_subject: EmailStr


class DeliverySuppressionCreate(BaseModel):
    email: EmailStr
    reason: SuppressionReason = SuppressionReason.ADMINISTRATIVE
    note: str | None = Field(default=None, max_length=500)


class DeliverySuppressionRead(BaseModel):
    id: uuid.UUID
    reference: str
    reason: SuppressionReason
    provider: EmailProviderKind | None
    active: bool
    created_at: datetime
    updated_at: datetime


class CampaignRunCreate(BaseModel):
    scheduled_for: datetime | None = None


class CampaignRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    campaign_id: uuid.UUID
    status: CampaignRunStatus
    scheduled_for: datetime | None
    target_count: int
    queued_count: int
    processing_count: int
    accepted_count: int
    bounced_count: int
    suppressed_count: int
    failed_count: int
    unknown_count: int
    reporting_identity_mode: ReportingIdentityMode
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class PlatformOrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    admin_email: EmailStr
    admin_name: str = Field(min_length=2, max_length=255)


class PlatformOrganizationRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    timezone: str
    reporting_identity_mode: ReportingIdentityMode
    suspended_at: datetime | None
    platform_url: str
    onboarding: dict[str, bool]
    invite_token: str | None = None
    invite_url: str | None = None
    invite_expires_at: datetime | None = None


class InvitationAccept(BaseModel):
    token: str = Field(min_length=20, max_length=255)
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=14, max_length=1024)


class ScimCredentialCreate(BaseModel):
    description: str = Field(default="SCIM provisioning token", min_length=2, max_length=255)


class ScimCredentialRead(BaseModel):
    id: uuid.UUID
    token_prefix: str
    description: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    token: str | None = None


class SsoConnectionCreate(BaseModel):
    provider: str = Field(pattern=r"^(entra|google)$")
    issuer: HttpUrl
    client_id: str = Field(min_length=3, max_length=255)
    client_secret_ref: str = Field(min_length=6, max_length=1024, pattern=r"^(kv|env)://")
    allowed_domains: list[str] = Field(default_factory=list, max_length=50)
    group_role_mappings: dict[str, UserRole] = Field(default_factory=dict)
