from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import ContextProfile, Employee
from app.models.enums import Channel

DEPARTMENT_THEME_MAP = {
    "finance": ["invoice/payment approval", "document review"],
    "hr": ["policy update", "leave request"],
    "it": ["password reset", "mfa notice"],
    "sales": ["client contract", "quote request"],
    "operations": ["document review", "qr verification"],
}


def derive_theme_candidates(department_name: str, role_title: str) -> list[str]:
    key = department_name.lower()
    themes = DEPARTMENT_THEME_MAP.get(key, ["document review", "policy update"])
    role_lower = role_title.lower()
    if "manager" in role_lower and "document review" not in themes:
        themes.append("document review")
    if "finance" in role_lower and "invoice/payment approval" not in themes:
        themes.append("invoice/payment approval")
    return themes


def build_context_profile(db: Session, employee: Employee) -> ContextProfile:
    department_name = employee.department.name if employee.department else "General"
    themes = derive_theme_candidates(department_name, employee.role_title)
    allowed_channels = [Channel.EMAIL.value, Channel.QR.value]
    if employee.phone:
        allowed_channels.append(Channel.SMS.value)
    if employee.consent_status.value == "consented":
        allowed_channels.append(Channel.VISHING.value)

    sensitivity_tags: list[str] = []
    role_lower = employee.role_title.lower()
    if "finance" in role_lower or department_name.lower() == "finance":
        sensitivity_tags.append("payment-flows")
    if "hr" in role_lower or department_name.lower() == "hr":
        sensitivity_tags.append("personnel-policy")
    if "it" in role_lower or "security" in role_lower:
        sensitivity_tags.append("access-management")

    summary_parts = [
        f"{employee.full_name} works in {department_name} as {employee.role_title}.",
        f"Approved context: {employee.approved_context_summary or 'No additional approved notes.'}",
    ]
    if employee.approved_public_profile_summary:
        summary_parts.append(f"Provided public profile summary: {employee.approved_public_profile_summary}")

    profile = ContextProfile(
        employee_id=employee.id,
        employee_context_profile=" ".join(summary_parts),
        likely_scenario_themes=themes,
        allowed_channels=allowed_channels,
        sensitivity_tags=sensitivity_tags or ["general-awareness"],
    )
    db.add(profile)
    db.flush()
    return profile


def ensure_context_profile(db: Session, employee: Employee) -> ContextProfile:
    profile = (
        db.query(ContextProfile)
        .filter(ContextProfile.employee_id == employee.id)
        .order_by(ContextProfile.created_at.desc())
        .first()
    )
    if profile:
        return profile
    return build_context_profile(db, employee)
