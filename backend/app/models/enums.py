from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    PLATFORM_OPERATOR = "platform_operator"
    ADMIN = "admin"
    CAMPAIGN_MANAGER = "campaign_manager"
    AUDITOR = "auditor"
    RISK_IDENTITY_VIEWER = "risk_identity_viewer"
    EMPLOYEE = "employee"


class ReportingIdentityMode(StrEnum):
    PSEUDONYMOUS = "pseudonymous"
    NAMED = "named"


class DomainPurpose(StrEnum):
    LANDING = "landing"
    RECIPIENT = "recipient"
    SENDER = "sender"


class DomainKind(StrEnum):
    PLATFORM = "platform"
    CUSTOM = "custom"


class VerificationStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    ACTIVE = "active"
    FAILED = "failed"
    DEACTIVATED = "deactivated"


class EmailProviderKind(StrEnum):
    MICROSOFT_GRAPH = "microsoft_graph"
    GOOGLE_WORKSPACE = "google_workspace"
    SMTP_LAB = "smtp_lab"


class ConnectionStatus(StrEnum):
    PENDING = "pending"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    REVOKED = "revoked"


class CampaignRunStatus(StrEnum):
    SCHEDULED = "scheduled"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class OutboxStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"


class SuppressionReason(StrEnum):
    HARD_BOUNCE = "hard_bounce"
    OPT_OUT = "opt_out"
    INACTIVE = "inactive"
    INVALID_DOMAIN = "invalid_domain"
    ADMINISTRATIVE = "administrative"


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
    DEEPFAKE = "deepfake"


#: Channels whose simulation is an interactive, in-platform experience rather than
#: an outbound message. These never place a real call or publish synthetic media.
INTERACTIVE_CHANNELS = frozenset({Channel.VISHING, Channel.DEEPFAKE})


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
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class CampaignType(StrEnum):
    ONE_TIME = "one_time"
    RECURRING = "recurring"
    ADAPTIVE_RETEST = "adaptive_retest"


class DeliveryStatus(StrEnum):
    SANDBOXED = "sandboxed"
    QUEUED = "queued"
    PROCESSING = "processing"
    ACCEPTED = "accepted"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    SUPPRESSED = "suppressed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class EventType(StrEnum):
    PROVIDER_ACCEPTED = "provider_accepted"
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
    # SMS / smishing
    REPLIED_SMS = "replied_sms"
    # Vishing / voice
    ANSWERED_CALL = "answered_call"
    DISCLOSED_ON_CALL = "disclosed_on_call"
    VERIFIED_CALLER = "verified_caller"
    ENDED_CALL_SAFELY = "ended_call_safely"
    # Deepfake / synthetic media impersonation
    PLAYED_SYNTHETIC_MEDIA = "played_synthetic_media"
    TRUSTED_SYNTHETIC_MEDIA = "trusted_synthetic_media"
    FLAGGED_SYNTHETIC_MEDIA = "flagged_synthetic_media"
    VERIFIED_OUT_OF_BAND = "verified_out_of_band"


#: Events that indicate the employee took the unsafe path in a simulation.
RISKY_EVENT_TYPES = frozenset(
    {
        EventType.CLICKED_LINK,
        EventType.SCANNED_QR,
        EventType.SUBMITTED_FORM_BOOLEAN,
        EventType.REPLIED_SMS,
        EventType.DISCLOSED_ON_CALL,
        EventType.TRUSTED_SYNTHETIC_MEDIA,
    }
)

#: Events that indicate correct, resilient security behaviour.
PROTECTIVE_EVENT_TYPES = frozenset(
    {
        EventType.CLICKED_REPORT,
        EventType.MARKED_SPAM,
        EventType.VERIFIED_CALLER,
        EventType.ENDED_CALL_SAFELY,
        EventType.FLAGGED_SYNTHETIC_MEDIA,
        EventType.VERIFIED_OUT_OF_BAND,
        EventType.TRAINING_COMPLETED,
    }
)


class PersonaStatus(StrEnum):
    """Lifecycle of a registered impersonation persona."""

    DRAFT = "draft"
    PENDING_CONSENT = "pending_consent"
    APPROVED = "approved"
    REVOKED = "revoked"
    EXPIRED = "expired"


class MediaModality(StrEnum):
    """How a synthetic-media impersonation is presented to the target."""

    VOICE_NOTE = "voice_note"
    VOICEMAIL = "voicemail"
    VIDEO_MESSAGE = "video_message"
    LIVE_VIDEO_CALL = "live_video_call"


class MediaAssetKind(StrEnum):
    """What a stored media artefact is."""

    VOICE_SAMPLE = "voice_sample"      # consented enrolment sample for a real person
    FACE_IMAGE = "face_image"          # consented still for talking-head video
    GENERATED_AUDIO = "generated_audio"  # cloned speech rendered for a scenario
    GENERATED_VIDEO = "generated_video"  # talking-head clip rendered for a scenario


class MediaAssetStatus(StrEnum):
    PENDING = "pending"    # async render in flight (video)
    READY = "ready"
    FAILED = "failed"
    EXPIRED = "expired"    # retention window passed; bytes removed


class DifficultyLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TrainingAssignmentStatus(StrEnum):
    ASSIGNED = "assigned"
    COMPLETED = "completed"
    RETEST_SCHEDULED = "retest_scheduled"
