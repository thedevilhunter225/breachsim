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
