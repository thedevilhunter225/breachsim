from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import Policy, PolicyVersion
from app.models.enums import Channel, DifficultyLevel

DEFAULT_POLICY = {
    "name": "Default BreachSim Guardrails",
    "allowed_themes": [
        "invoice/payment approval",
        "policy update",
        "leave request",
        "password reset",
        "mfa notice",
        "client contract",
        "quote request",
        "document review",
        "qr verification",
        "vendor payment release",
        "executive approval request",
    ],
    "prohibited_words": ["wire transfer", "arrest", "police", "hospital", "lawsuit", "terror", "emergency"],
    "allowed_sender_names": ["BreachSim Training", "Security Awareness Team", "Northwind IT", "HR Operations"],
    "approved_training_domains": ["training.breachsim.local", "awareness.breachsim.local"],
    "allowed_delivery_channels": ["email", "sms", "qr", "vishing", "deepfake"],
    "difficulty_levels": ["low", "medium", "high"],
    "maximum_frequency_per_employee": 2,
    "working_hours_start": 9,
    "working_hours_end": 18,
    "second_approval_required": True,
    "opt_out_respected": True,
    "prohibited_topics": [
        "health emergency deception",
        "law enforcement impersonation",
        "real credential capture",
        "harassment",
        "threats",
        "illegal impersonation",
        "real external brand abuse",
        "impersonation without registered consent",
        "synthetic media of a public figure",
        "cloning a voice or likeness from scraped media",
        "distributing generated media outside the platform",
    ],
}


@dataclass
class PolicyValidationResult:
    passed: bool
    errors: list[str]
    warnings: list[str]


def get_or_create_policy(db: Session, organization_id: Any) -> Policy:
    policy = db.query(Policy).filter(Policy.organization_id == organization_id).first()
    if policy:
        return policy
    policy = Policy(organization_id=organization_id, **DEFAULT_POLICY)
    db.add(policy)
    db.flush()
    db.add(PolicyVersion(policy_id=policy.id, snapshot=DEFAULT_POLICY))
    db.commit()
    db.refresh(policy)
    return policy


def snapshot_policy(policy: Policy) -> dict:
    return {
        "name": policy.name,
        "allowed_themes": policy.allowed_themes,
        "prohibited_words": policy.prohibited_words,
        "allowed_sender_names": policy.allowed_sender_names,
        "approved_training_domains": policy.approved_training_domains,
        "allowed_delivery_channels": policy.allowed_delivery_channels,
        "difficulty_levels": policy.difficulty_levels,
        "maximum_frequency_per_employee": policy.maximum_frequency_per_employee,
        "working_hours_start": policy.working_hours_start,
        "working_hours_end": policy.working_hours_end,
        "second_approval_required": policy.second_approval_required,
        "opt_out_respected": policy.opt_out_respected,
        "prohibited_topics": policy.prohibited_topics,
    }


def validate_generation_request(policy: Policy, *, channel: Channel, theme: str, difficulty_level: DifficultyLevel) -> PolicyValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    if channel.value not in policy.allowed_delivery_channels:
        errors.append(
            f"The {channel.value} channel is switched off in this organization's controls. "
            "An administrator can enable it under Governance -> Controls."
        )
    if theme not in policy.allowed_themes:
        errors.append(
            f"Theme '{theme}' is not on the permitted list. "
            "Add it under Governance -> Controls before generating this scenario."
        )
    if difficulty_level.value not in policy.difficulty_levels:
        errors.append(f"Difficulty '{difficulty_level.value}' is not allowed by policy.")
    return PolicyValidationResult(passed=not errors, errors=errors, warnings=warnings)


def validate_generated_content(policy: Policy, *, subject: str, body_copy: str, cta_text: str, landing_page_copy: str) -> PolicyValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    joined = " ".join([subject, body_copy, cta_text, landing_page_copy]).lower()

    for word in policy.prohibited_words:
        if word.lower() in joined:
            errors.append(f"Prohibited word detected: {word}")

    hard_blocks = [
        "enter your real password",
        "submit your real password",
        "send your bank details",
        "police investigation",
        "medical emergency",
        "law enforcement notice",
    ]
    for phrase in hard_blocks:
        if phrase in joined:
            errors.append(f"Hard-block phrase detected: {phrase}")

    if "training simulation" not in joined and "security awareness" not in joined:
        warnings.append("Content should clearly include an internal training label.")

    approved_domains = tuple(policy.approved_training_domains)
    if "http" in landing_page_copy and approved_domains and not any(domain in landing_page_copy for domain in approved_domains):
        errors.append("Landing page references a domain outside the approved training domains.")

    return PolicyValidationResult(passed=not errors, errors=errors, warnings=warnings)
