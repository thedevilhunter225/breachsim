"""Structured content builders for the interactive simulation channels.

Email, SMS and QR simulations are a single message with a single decision: click or
report. Voice (vishing) and synthetic-media (deepfake) simulations are *conversations* —
the target is pushed through escalating pressure and can bail out, comply, or verify at
each turn. This module turns a scenario prompt into that branching script.

Design note
-----------
The language model is only ever asked for the *narrative* fields (the pretext, the
opening line, the transcript). The branching structure, the safe options, the scoring
weights and the red-flag debrief are assembled deterministically here. That keeps the
simulation safe and consistent regardless of which provider is configured — including
when no provider is configured at all — while still letting the LLM supply realism.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.enums import Channel, DifficultyLevel, EventType, MediaModality

#: Modules the frontend simulators switch on.
VOICE_MODULE = "voice_simulation"
SYNTHETIC_MEDIA_MODULE = "synthetic_media_simulation"


@dataclass
class PersonaContext:
    """The consented identity a voice or deepfake simulation is allowed to imitate."""

    display_name: str = "Internal Operations Lead"
    role_title: str = "Operations Lead"
    relationship_to_targets: str = "internal colleague"
    modality: MediaModality = MediaModality.VOICE_NOTE
    voice_profile: dict[str, Any] = field(default_factory=dict)
    detection_tells: list[str] = field(default_factory=list)
    reference_code: str | None = None
    synthetic_disclosure_text: str = (
        "Simulated synthetic media. No real recording of this person was used."
    )

    def public_dict(self) -> dict[str, Any]:
        return {
            "display_name": self.display_name,
            "role_title": self.role_title,
            "relationship_to_targets": self.relationship_to_targets,
            "modality": self.modality.value,
            "reference_code": self.reference_code,
        }


DEFAULT_VOICE_PROFILE = {"lang": "en-US", "rate": 1.02, "pitch": 0.95, "volume": 1.0}


# --------------------------------------------------------------------------------------
# Option vocabulary
# --------------------------------------------------------------------------------------
# Each option carries the event it emits and the weight it contributes to the employee's
# risk score. Unsafe options are positive weight, protective options are negative.

def _comply(key: str, label: str, followup: str, *, weight: int, event: EventType) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "outcome": "unsafe",
        "safe": False,
        "risk_weight": weight,
        "event_type": event.value,
        "followup_line": followup,
        "coaching": None,
    }


def _protect(
    key: str,
    label: str,
    followup: str,
    *,
    weight: int,
    event: EventType,
    coaching: str,
    terminal: bool = False,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "outcome": "safe",
        "safe": True,
        "risk_weight": weight,
        "event_type": event.value,
        "followup_line": followup,
        "coaching": coaching,
        "terminal": terminal,
    }


def _hesitate(key: str, label: str, followup: str) -> dict[str, Any]:
    """Neutral stalling: not a failure, but not verification either."""
    return {
        "key": key,
        "label": label,
        "outcome": "neutral",
        "safe": False,
        "risk_weight": 2,
        "event_type": None,
        "followup_line": followup,
        "coaching": None,
    }


# --------------------------------------------------------------------------------------
# Voice / vishing
# --------------------------------------------------------------------------------------

_PRESSURE_BY_DIFFICULTY = {
    DifficultyLevel.LOW: ("a routine check", "polite", 1),
    DifficultyLevel.MEDIUM: ("a time-boxed request", "brisk", 2),
    DifficultyLevel.HIGH: ("an escalated approval", "insistent", 3),
}


def build_voice_script(
    *,
    employee_name: str,
    role_title: str,
    department_name: str,
    theme: str,
    difficulty_level: DifficultyLevel,
    persona: PersonaContext,
    opening_line: str | None = None,
    pretext: str | None = None,
    reference_code: str = "OPS-REQ-00",
) -> dict[str, Any]:
    """Assemble a three-turn vishing call with escalating pressure at each turn."""

    tone_label, tone, escalation_steps = _PRESSURE_BY_DIFFICULTY[difficulty_level]
    first_name = employee_name.split()[0] if employee_name.strip() else "there"

    greeting = opening_line or (
        f"Hi {first_name}, this is {persona.display_name} from {department_name} operations. "
        f"I'm calling about {tone_label} on the {theme} queue — reference {reference_code}."
    )
    context_line = pretext or (
        f"We've got a {theme} item sitting against your {role_title} queue and the batch "
        f"closes shortly. I just need you to confirm it from your side so it clears."
    )

    script: list[dict[str, Any]] = [
        {
            "key": "opening",
            "index": 0,
            "speaker_line": greeting,
            "pressure_tactic": "authority",
            "hint": "The caller has supplied a name and a reference number, but nothing you can check.",
            "options": [
                _comply(
                    "engage",
                    "Confirm who you are and ask what they need",
                    "Great, thanks. I'll just need you to confirm a couple of details on the record.",
                    weight=6,
                    event=EventType.ANSWERED_CALL,
                ),
                _hesitate(
                    "stall",
                    "Say you're busy and ask them to be quick",
                    "No problem, this will take thirty seconds — I just need the confirmation.",
                ),
                _protect(
                    "verify_identity",
                    "Ask for their extension and say you'll call back through the directory",
                    "I'm not at my desk right now, and this really needs to clear today.",
                    weight=-8,
                    event=EventType.VERIFIED_CALLER,
                    coaching="Correct. A caller who resists an internal call-back is the single strongest vishing signal.",
                ),
            ],
        },
        {
            "key": "pretext",
            "index": 1,
            "speaker_line": context_line,
            "pressure_tactic": "role-relevance",
            "hint": "The request is shaped to fit work you genuinely do, which is what makes it land.",
            "options": [
                _comply(
                    "share_context",
                    "Describe the workflow item and its current status",
                    "Perfect — that matches what I have. One more thing and we're done.",
                    weight=10,
                    event=EventType.DISCLOSED_ON_CALL,
                ),
                _hesitate(
                    "ask_email",
                    "Ask them to send it by email instead",
                    "I would, but the mail relay is backed up — that's actually why I'm calling.",
                ),
                _protect(
                    "refuse_details",
                    "Decline to discuss workflow details on an unverified call",
                    "I understand, but this is going to miss the cut-off.",
                    weight=-10,
                    event=EventType.VERIFIED_CALLER,
                    coaching="Correct. Internal process details are useful to an attacker even when no password is shared.",
                ),
            ],
        },
        {
            "key": "ask",
            "index": 2,
            "speaker_line": (
                f"Last thing — I need you to approve the {theme} item on your side so it clears "
                "the batch. Can you action it while we're on the line?"
            ),
            "pressure_tactic": "urgency",
            "hint": "The final ask always arrives when the target already feels invested in helping.",
            "options": [
                _comply(
                    "take_action",
                    "Action the request while they wait",
                    "Brilliant, that's cleared. Appreciate the help.",
                    weight=16,
                    event=EventType.DISCLOSED_ON_CALL,
                ),
                _protect(
                    "hang_up",
                    "End the call and verify through the internal directory",
                    "The call ends.",
                    weight=-12,
                    event=EventType.ENDED_CALL_SAFELY,
                    coaching="Correct. Ending an unverified call costs you two minutes; complying can cost the organization far more.",
                    terminal=True,
                ),
                _protect(
                    "report_call",
                    "End the call and report it to the security team",
                    "The call ends.",
                    weight=-16,
                    event=EventType.CLICKED_REPORT,
                    coaching="Best possible outcome — reporting turns your single call into organization-wide warning.",
                    terminal=True,
                ),
            ],
        },
    ]

    return {
        "module": VOICE_MODULE,
        "channel": Channel.VISHING.value,
        "header": {
            "caller_id_display": _caller_id_for(department_name),
            "caller_id_label": f"{department_name} Service Desk",
            "spoofed_display_name": persona.display_name,
            "call_reason": f"{theme} — {reference_code}",
            "tone": tone,
            "escalation_steps": escalation_steps,
        },
        "persona": persona.public_dict(),
        "voice_profile": {**DEFAULT_VOICE_PROFILE, **(persona.voice_profile or {})},
        "script": script,
        "red_flags": [
            "Inbound call asking you to action something immediately.",
            "Caller supplies a reference number you cannot independently look up.",
            "Pressure framed around a deadline or batch cut-off.",
            "Resistance when you offer to call back through the internal directory.",
            "A plausible reason why the normal channel (email, ticket) is unavailable.",
        ],
        "verification_procedure": (
            "Hang up. Look the caller up in the internal directory yourself and dial that number. "
            "Never use a number, extension or link supplied by the caller."
        ),
        "debrief": (
            "Voice requests bypass every email control your organization has. The only reliable "
            "defence is an out-of-band call-back you initiate."
        ),
        "safety_notice": (
            "BreachSim does not place real phone calls. This call is rendered in your browser and "
            "no audio leaves your device."
        ),
    }


def _caller_id_for(department_name: str) -> str:
    """Stable, plausible-looking internal caller ID derived from the department name."""
    extension = sum(ord(character) for character in department_name) % 9000 + 1000
    return f"+92 51 111 {extension}"


# --------------------------------------------------------------------------------------
# Synthetic media / deepfake
# --------------------------------------------------------------------------------------

_MODALITY_COPY = {
    MediaModality.VOICE_NOTE: (
        "voice note",
        "A voice note arrives in your team chat.",
        "audio",
    ),
    MediaModality.VOICEMAIL: (
        "voicemail",
        "A voicemail lands in your inbox as an audio attachment.",
        "audio",
    ),
    MediaModality.VIDEO_MESSAGE: (
        "video message",
        "A short video message is shared with you directly.",
        "video",
    ),
    MediaModality.LIVE_VIDEO_CALL: (
        "live video call",
        "An unscheduled video call starts from a familiar name.",
        "video",
    ),
}

_AUDIO_ARTIFACTS = [
    {
        "key": "cadence",
        "label": "Flat prosody",
        "detail": "Sentence rhythm stays even where a real speaker would rise, pause or trail off.",
        "timestamp_hint": "0:03",
    },
    {
        "key": "breath",
        "label": "No breath sounds",
        "detail": "Long phrases run without the inhale a person needs between clauses.",
        "timestamp_hint": "0:09",
    },
    {
        "key": "room_tone",
        "label": "Missing room tone",
        "detail": "Background noise cuts to digital silence between words instead of staying constant.",
        "timestamp_hint": "0:12",
    },
    {
        "key": "name_seam",
        "label": "Seam on personalisation",
        "detail": "Your name and the amount sit at a slightly different volume from the rest.",
        "timestamp_hint": "0:16",
    },
]

_VIDEO_ARTIFACTS = [
    {
        "key": "blink",
        "label": "Irregular blink rate",
        "detail": "Blinks arrive in bursts, then stop for an unnaturally long stretch.",
        "timestamp_hint": "0:05",
    },
    {
        "key": "edge_warp",
        "label": "Warping at the jawline",
        "detail": "The face edge shimmers against the background when the head turns.",
        "timestamp_hint": "0:08",
    },
    {
        "key": "lip_sync",
        "label": "Lip-sync drift",
        "detail": "Mouth shapes lag the audio by a frame or two on plosive sounds.",
        "timestamp_hint": "0:11",
    },
    {
        "key": "lighting",
        "label": "Lighting mismatch",
        "detail": "Light on the face does not match the light on the shoulders and room behind.",
        "timestamp_hint": "0:14",
    },
]

_CONTEXT_ARTIFACTS = [
    {
        "key": "channel_switch",
        "label": "Wrong channel for the ask",
        "detail": "A request of this size would normally arrive through the approvals system, not a message.",
        "timestamp_hint": None,
    },
    {
        "key": "no_reply",
        "label": "One-way conversation",
        "detail": "The sender pushes a recording but avoids a live back-and-forth where they'd have to react.",
        "timestamp_hint": None,
    },
    {
        "key": "secrecy",
        "label": "Discretion requested",
        "detail": "You are asked to keep it between you — which removes the colleague who would catch it.",
        "timestamp_hint": None,
    },
]


def build_synthetic_media_brief(
    *,
    employee_name: str,
    role_title: str,
    department_name: str,
    theme: str,
    difficulty_level: DifficultyLevel,
    persona: PersonaContext,
    transcript: str | None = None,
    requested_action: str | None = None,
    reference_code: str = "OPS-REQ-00",
    disclosure_text: str | None = None,
) -> dict[str, Any]:
    """Assemble a synthetic-media impersonation simulation with its detection tells."""

    modality = persona.modality
    modality_noun, arrival_line, media_kind = _MODALITY_COPY.get(
        modality, _MODALITY_COPY[MediaModality.VOICE_NOTE]
    )
    first_name = employee_name.split()[0] if employee_name.strip() else "there"

    action = requested_action or (
        f"Approve the pending {theme} item ({reference_code}) before the cut-off."
    )
    spoken = transcript or (
        f"{first_name}, it's {persona.display_name}. I'm between meetings so I'm sending this "
        f"instead of calling. The {theme} item under {reference_code} is still sitting unapproved "
        f"and it needs to clear today. Can you push it through from your side? "
        "Keep it between us for now — I don't want it escalated before it's resolved."
    )

    artifacts = (_AUDIO_ARTIFACTS if media_kind == "audio" else _VIDEO_ARTIFACTS).copy()
    artifacts += _CONTEXT_ARTIFACTS
    # Harder simulations expose fewer tells up front — the employee has to work for it.
    visible_count = {DifficultyLevel.LOW: len(artifacts), DifficultyLevel.MEDIUM: 5, DifficultyLevel.HIGH: 3}[
        difficulty_level
    ]
    for index, artifact in enumerate(artifacts):
        artifact["revealed_upfront"] = index < max(0, visible_count - len(_CONTEXT_ARTIFACTS))

    # A persona whose display name already states the role should not read
    # "It is from Group Finance Director, Group Finance Director."
    sender_line = persona.display_name
    if persona.role_title and persona.role_title.strip().lower() != persona.display_name.strip().lower():
        sender_line = f"{persona.display_name}, {persona.role_title}"

    script: list[dict[str, Any]] = [
        {
            "key": "receipt",
            "index": 0,
            "speaker_line": f"{arrival_line} It is from {sender_line}.",
            "pressure_tactic": "familiarity",
            "hint": "Recognising a voice or face is not authentication. It is only recognition.",
            "options": [
                _comply(
                    "play_media",
                    f"Play the {modality_noun}",
                    "The recording plays.",
                    weight=2,
                    event=EventType.PLAYED_SYNTHETIC_MEDIA,
                ),
                _protect(
                    "verify_before_play",
                    "Message them on a known channel before engaging",
                    "You send a separate message to the number in the internal directory.",
                    weight=-6,
                    event=EventType.VERIFIED_OUT_OF_BAND,
                    coaching="Strong instinct — verifying before you engage denies the attacker the pressure they need.",
                ),
            ],
        },
        {
            "key": "request",
            "index": 1,
            "speaker_line": spoken,
            "pressure_tactic": "authority",
            "hint": "The ask pairs seniority with secrecy — the combination that removes your safety net.",
            "options": [
                _comply(
                    "comply_now",
                    "Action the request as asked",
                    "You approve the item.",
                    weight=18,
                    event=EventType.TRUSTED_SYNTHETIC_MEDIA,
                ),
                _hesitate(
                    "reply_media",
                    f"Reply to the same {modality_noun} asking for confirmation",
                    "A second recording arrives repeating the request more urgently.",
                ),
                _protect(
                    "call_back",
                    "Call them on the number in the internal directory",
                    "You reach them directly. They know nothing about the request.",
                    weight=-12,
                    event=EventType.VERIFIED_OUT_OF_BAND,
                    coaching="Correct. Out-of-band verification is the only control that survives a convincing fake.",
                ),
                _protect(
                    "flag_media",
                    "Flag it to security as possible synthetic media",
                    "You report it before taking any action.",
                    weight=-16,
                    event=EventType.FLAGGED_SYNTHETIC_MEDIA,
                    coaching="Best possible outcome — early reporting lets the security team warn everyone else targeted.",
                    terminal=True,
                ),
            ],
        },
    ]

    return {
        "module": SYNTHETIC_MEDIA_MODULE,
        "channel": Channel.DEEPFAKE.value,
        "header": {
            "modality": modality.value,
            "modality_noun": modality_noun,
            "media_kind": media_kind,
            "arrival_context": arrival_line,
            "sender_display_name": persona.display_name,
            "sender_role_title": persona.role_title,
            "requested_action": action,
            "reference": reference_code,
        },
        "persona": persona.public_dict(),
        "voice_profile": {**DEFAULT_VOICE_PROFILE, **(persona.voice_profile or {})},
        "transcript": spoken,
        "script": script,
        "synthetic_artifacts": artifacts,
        "detection_tells": persona.detection_tells or [
            "Verify any high-value request through a channel you chose, not the one it arrived on.",
            "Treat a request for secrecy as a red flag, not a reason to act quietly.",
            "Seniority in a recording is a claim, not proof.",
        ],
        "red_flags": [
            f"A {modality_noun} used for an approval that normally goes through a system.",
            "Urgency tied to a deadline you cannot independently confirm.",
            "An explicit request to keep it between the two of you.",
            "The sender avoids any live, interactive conversation.",
        ],
        "verification_procedure": (
            "Contact the person through a channel you already trust — the internal directory number "
            "or a face-to-face check. Do not reply on the channel the media arrived on."
        ),
        "debrief": (
            "Synthetic voice and video are now cheap enough to target ordinary approval workflows, "
            "not just executives. Recognition is not verification."
        ),
        "safety_notice": disclosure_text or persona.synthetic_disclosure_text,
    }


# --------------------------------------------------------------------------------------
# Lookup helpers used by delivery, scoring and the public simulator API
# --------------------------------------------------------------------------------------

def find_step(channel_payload: dict[str, Any], step_key: str) -> dict[str, Any] | None:
    for step in channel_payload.get("script") or []:
        if step.get("key") == step_key:
            return step
    return None


def find_option(step: dict[str, Any], response_key: str) -> dict[str, Any] | None:
    for option in step.get("options") or []:
        if option.get("key") == response_key:
            return option
    return None


def script_step_count(channel_payload: dict[str, Any]) -> int:
    return len(channel_payload.get("script") or [])
