from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    CAMPAIGN_MANAGER = "campaign_manager"
    AUDITOR = "auditor"
    EMPLOYEE = "employee"


class ConsentStatus(StrEnum):
    CONSENTED = "consented"
    PENDING = "pending"
    OPTED_OUT = "opted_out"
    REDACTION_REQUESTED = "redaction_requested"


class EmployeeStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"


class Channel(StrEnum):
    EMAIL = "email"
    SMS = "sms"
    QR = "qr"
    VISHING = "vishing"


class ScenarioStatus(StrEnum):
    DRAFT = "draft"
    GENERATED = "generated"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    GENERATED = "generated"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class CampaignType(StrEnum):
    ONE_TIME = "one_time"
    RECURRING = "recurring"
    ADAPTIVE_RETEST = "adaptive_retest"


class DeliveryStatus(StrEnum):
    SANDBOXED = "sandboxed"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    FAILED = "failed"


class EventType(StrEnum):
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    OPENED_EMAIL = "opened_email"
    CLICKED_LINK = "clicked_link"
    SCANNED_QR = "scanned_qr"
    VISITED_LANDING_PAGE = "visited_landing_page"
    CLICKED_REPORT = "clicked_report"
    MARKED_SPAM = "marked_spam"
    SUBMITTED_FORM_BOOLEAN = "submitted_form_boolean"
    TRAINING_COMPLETED = "training_completed"


class DifficultyLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TrainingAssignmentStatus(StrEnum):
    ASSIGNED = "assigned"
    COMPLETED = "completed"
    RETEST_SCHEDULED = "retest_scheduled"
