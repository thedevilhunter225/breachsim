from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    CampaignStatus,
    CampaignType,
    Channel,
    ConsentStatus,
    DeliveryStatus,
    DifficultyLevel,
    EmployeeStatus,
    EventType,
    ScenarioStatus,
    TrainingAssignmentStatus,
    UserRole,
)
from app.models.types import EncryptedString


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    retention_days: Mapped[int] = mapped_column(Integer, default=365)
    privacy_notice: Mapped[str] = mapped_column(Text, default="Training and security awareness platform.")
    email_provider_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    email_provider_mode: Mapped[str] = mapped_column(String(32), default="sandbox")
    smtp_host: Mapped[str | None] = mapped_column(String(255))
    smtp_port: Mapped[int] = mapped_column(Integer, default=587)
    smtp_username: Mapped[str | None] = mapped_column(String(255))
    smtp_password: Mapped[str | None] = mapped_column(EncryptedString(1024))
    smtp_from_email: Mapped[str | None] = mapped_column(String(255))
    smtp_sender_name: Mapped[str | None] = mapped_column(String(255))
    smtp_recipient_allowlist: Mapped[list[str]] = mapped_column(JSON, default=list)

    users: Mapped[list["User"]] = relationship(back_populates="organization")
    departments: Mapped[list["Department"]] = relationship(back_populates="organization")
    employees: Mapped[list["Employee"]] = relationship(back_populates="organization")


class Role(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "roles"

    name: Mapped[UserRole] = mapped_column(Enum(UserRole), unique=True, nullable=False)

    users: Mapped[list["UserRoleLink"]] = relationship(back_populates="role")


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    organization: Mapped["Organization"] = relationship(back_populates="users")
    roles: Mapped[list["UserRoleLink"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    employee_links: Mapped[list["Employee"]] = relationship(back_populates="portal_user")


class UserRoleLink(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"), nullable=False)

    user: Mapped["User"] = relationship(back_populates="roles")
    role: Mapped["Role"] = relationship(back_populates="users")


class Department(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "departments"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)

    organization: Mapped["Organization"] = relationship(back_populates="departments")
    employees: Mapped[list["Employee"]] = relationship(back_populates="department")


class Employee(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("organization_id", "employee_id", name="uq_org_employee_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id"), index=True)
    portal_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    employee_id: Mapped[str] = mapped_column(String(64), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(EncryptedString(1024))
    role_title: Mapped[str] = mapped_column(String(255), nullable=False)
    approved_context_summary: Mapped[str | None] = mapped_column(EncryptedString(4096))
    approved_public_profile_summary: Mapped[str | None] = mapped_column(EncryptedString(4096))
    training_preferences: Mapped[list[str]] = mapped_column(JSON, default=list)
    consent_status: Mapped[ConsentStatus] = mapped_column(Enum(ConsentStatus), default=ConsentStatus.PENDING, index=True)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[EmployeeStatus] = mapped_column(Enum(EmployeeStatus), default=EmployeeStatus.ACTIVE, index=True)

    organization: Mapped["Organization"] = relationship(back_populates="employees")
    department: Mapped["Department"] = relationship(back_populates="employees")
    portal_user: Mapped["User | None"] = relationship(back_populates="employee_links")
    consent_records: Mapped[list["ConsentRecord"]] = relationship(back_populates="employee", cascade="all, delete-orphan")
    context_profiles: Mapped[list["ContextProfile"]] = relationship(back_populates="employee", cascade="all, delete-orphan")
    campaign_targets: Mapped[list["CampaignTarget"]] = relationship(back_populates="employee")
    training_assignments: Mapped[list["TrainingAssignment"]] = relationship(back_populates="employee")
    risk_scores: Mapped[list["RiskScore"]] = relationship(back_populates="employee")


class ConsentRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "consent_records"

    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    status: Mapped[ConsentStatus] = mapped_column(Enum(ConsentStatus), nullable=False)
    source: Mapped[str] = mapped_column(String(255), default="manual")
    note: Mapped[str | None] = mapped_column(Text)
    opt_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    redaction_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    employee: Mapped["Employee"] = relationship(back_populates="consent_records")


class ContextProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "context_profiles"

    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    employee_context_profile: Mapped[str] = mapped_column(Text, nullable=False)
    likely_scenario_themes: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_channels: Mapped[list[str]] = mapped_column(JSON, default=list)
    sensitivity_tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    employee: Mapped["Employee"] = relationship(back_populates="context_profiles")


class Policy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "policies"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), default="Default policy")
    allowed_themes: Mapped[list[str]] = mapped_column(JSON, default=list)
    prohibited_words: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_sender_names: Mapped[list[str]] = mapped_column(JSON, default=list)
    approved_training_domains: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_delivery_channels: Mapped[list[str]] = mapped_column(JSON, default=list)
    difficulty_levels: Mapped[list[str]] = mapped_column(JSON, default=list)
    maximum_frequency_per_employee: Mapped[int] = mapped_column(Integer, default=2)
    working_hours_start: Mapped[int] = mapped_column(Integer, default=9)
    working_hours_end: Mapped[int] = mapped_column(Integer, default=18)
    second_approval_required: Mapped[bool] = mapped_column(Boolean, default=True)
    opt_out_respected: Mapped[bool] = mapped_column(Boolean, default=True)
    prohibited_topics: Mapped[list[str]] = mapped_column(JSON, default=list)

    versions: Mapped[list["PolicyVersion"]] = relationship(back_populates="policy", cascade="all, delete-orphan")


class PolicyVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "policy_versions"

    policy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("policies.id"), nullable=False, index=True)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)

    policy: Mapped["Policy"] = relationship(back_populates="versions")


class FailureReason(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "failure_reasons"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class Scenario(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scenarios"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("context_profiles.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[Channel] = mapped_column(Enum(Channel), nullable=False)
    theme: Mapped[str] = mapped_column(String(255), nullable=False)
    difficulty_level: Mapped[DifficultyLevel] = mapped_column(Enum(DifficultyLevel), nullable=False)
    status: Mapped[ScenarioStatus] = mapped_column(Enum(ScenarioStatus), default=ScenarioStatus.DRAFT, index=True)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scenario_versions.id"))
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detected_persuasion_triggers: Mapped[list[str]] = mapped_column(JSON, default=list)
    policy_validation: Mapped[dict] = mapped_column(JSON, default=dict)

    versions: Mapped[list["ScenarioVersion"]] = relationship(
        back_populates="scenario",
        cascade="all, delete-orphan",
        foreign_keys="ScenarioVersion.scenario_id",
    )


class ScenarioVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scenario_versions"

    scenario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scenarios.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body_copy: Mapped[str] = mapped_column(Text, nullable=False)
    cta_text: Mapped[str] = mapped_column(String(255), nullable=False)
    landing_page_copy: Mapped[str] = mapped_column(Text, nullable=False)
    rationale_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    detected_persuasion_triggers: Mapped[list[str]] = mapped_column(JSON, default=list)
    difficulty_score: Mapped[int] = mapped_column(Integer, default=30)
    validation_result: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)

    scenario: Mapped["Scenario"] = relationship(back_populates="versions", foreign_keys=[scenario_id])


class Campaign(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "campaigns"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    second_approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    channel: Mapped[Channel] = mapped_column(Enum(Channel), nullable=False)
    campaign_type: Mapped[CampaignType] = mapped_column(Enum(CampaignType), default=CampaignType.ONE_TIME)
    status: Mapped[CampaignStatus] = mapped_column(Enum(CampaignStatus), default=CampaignStatus.DRAFT, index=True)
    schedule_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    throttling_per_hour: Mapped[int] = mapped_column(Integer, default=25)
    requires_second_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    target_filters: Mapped[dict] = mapped_column(JSON, default=dict)
    sandbox_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    learning_objective: Mapped[str] = mapped_column(String(255), default="Recognize social engineering patterns.")

    targets: Mapped[list["CampaignTarget"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")
    scenario_links: Mapped[list["CampaignScenario"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")
    delivery_attempts: Mapped[list["DeliveryAttempt"]] = relationship(back_populates="campaign")
    events: Mapped[list["EventLog"]] = relationship(back_populates="campaign")


class CampaignTarget(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "campaign_targets"

    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    target_group_label: Mapped[str | None] = mapped_column(String(255))

    campaign: Mapped["Campaign"] = relationship(back_populates="targets")
    employee: Mapped["Employee"] = relationship(back_populates="campaign_targets")


class CampaignScenario(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "campaign_scenarios"

    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    scenario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scenarios.id"), nullable=False, index=True)

    campaign: Mapped["Campaign"] = relationship(back_populates="scenario_links")
    scenario: Mapped["Scenario"] = relationship()


class DeliveryAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "delivery_attempts"

    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    scenario_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scenarios.id"))
    channel: Mapped[Channel] = mapped_column(Enum(Channel), nullable=False, index=True)
    status: Mapped[DeliveryStatus] = mapped_column(Enum(DeliveryStatus), default=DeliveryStatus.SANDBOXED)
    sandbox_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    preview_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    campaign: Mapped["Campaign"] = relationship(back_populates="delivery_attempts")


class LandingToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "landing_tokens"

    delivery_attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("delivery_attempts.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    landing_type: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EventLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "event_logs"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("employees.id"), index=True)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("campaigns.id"), index=True)
    delivery_attempt_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("delivery_attempts.id"), index=True)
    landing_token_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("landing_tokens.id"))
    event_type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False, index=True)
    channel: Mapped[Channel | None] = mapped_column(Enum(Channel))
    event_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    pseudo_event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    campaign: Mapped["Campaign | None"] = relationship(back_populates="events")


class TrainingModule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "training_modules"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    vector: Mapped[str] = mapped_column(String(64), nullable=False)
    primary_reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=45)
    guidance_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    assignments: Mapped[list["TrainingAssignment"]] = relationship(back_populates="module")


class TrainingAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "training_assignments"

    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("training_modules.id"), nullable=False)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("campaigns.id"))
    source_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("event_logs.id"))
    status: Mapped[TrainingAssignmentStatus] = mapped_column(
        Enum(TrainingAssignmentStatus),
        default=TrainingAssignmentStatus.ASSIGNED,
    )
    assigned_reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    retest_scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    employee: Mapped["Employee"] = relationship(back_populates="training_assignments")
    module: Mapped["TrainingModule"] = relationship(back_populates="assignments")
    completions: Mapped[list["TrainingCompletion"]] = relationship(back_populates="assignment", cascade="all, delete-orphan")


class TrainingCompletion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "training_completions"

    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("training_assignments.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    dwell_seconds: Mapped[int] = mapped_column(Integer, default=30)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    assignment: Mapped["TrainingAssignment"] = relationship(back_populates="completions")


class RiskScore(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "risk_scores"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("employees.id"), index=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id"), index=True)
    channel: Mapped[Channel | None] = mapped_column(Enum(Channel))
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    employee: Mapped["Employee | None"] = relationship(back_populates="risk_scores")


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(255))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AccessLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "access_logs"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    resource_type: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(64), default="read")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ReportExport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "report_exports"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    generated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    report_type: Mapped[str] = mapped_column(String(128), nullable=False)
    format: Mapped[str] = mapped_column(String(32), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
