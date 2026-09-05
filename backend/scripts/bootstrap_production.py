"""Create the first production organization and two administrators idempotently.

Run after ``alembic upgrade head``. Once two administrators exist, the command exits
without reading or changing bootstrap passwords, so those secrets can be removed.
"""

from __future__ import annotations

import sys

import pyotp

from app.core.config import is_production_environment, settings
from app.core.security import hash_password, password_is_strong
from app.db.session import SessionLocal
from app.models.entities import Organization, OrganizationBranding, User, UserRoleLink
from app.models.enums import UserRole
from app.services.domains import ensure_platform_landing_domain
from app.services.policy_engine import get_or_create_policy
from app.services.seed import ensure_failure_reasons, ensure_roles, ensure_training_modules


def main() -> int:
    if not is_production_environment(settings.environment):
        print("Refusing production bootstrap unless ENVIRONMENT=production.", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        existing_admins = (
            db.query(User)
            .join(UserRoleLink, UserRoleLink.user_id == User.id)
            .filter(UserRoleLink.role.has(name=UserRole.ADMIN))
            .all()
        )
        if len(existing_admins) >= 2:
            platform_operators = (
                db.query(User)
                .join(UserRoleLink, UserRoleLink.user_id == User.id)
                .filter(UserRoleLink.role.has(name=UserRole.PLATFORM_OPERATOR), User.mfa_enabled.is_(True))
                .count()
            )
            if platform_operators:
                print("Production administrators and an MFA-protected platform operator already exist.")
                return 0

        accounts = [
            (
                settings.bootstrap_admin_email,
                settings.bootstrap_admin_name,
                settings.bootstrap_admin_password,
                settings.bootstrap_admin_mfa_secret,
                "BOOTSTRAP_ADMIN",
                (UserRole.ADMIN, UserRole.PLATFORM_OPERATOR),
            ),
            (
                settings.bootstrap_reviewer_email,
                settings.bootstrap_reviewer_name,
                settings.bootstrap_reviewer_password,
                settings.bootstrap_reviewer_mfa_secret,
                "BOOTSTRAP_REVIEWER",
                (UserRole.ADMIN,),
            ),
        ]
        if any(not email or not password or not mfa for email, _name, password, mfa, _label, _roles in accounts):
            print(
                "Both bootstrap administrator and reviewer email/password/MFA-secret sets are required "
                "until two administrators exist.",
                file=sys.stderr,
            )
            return 2
        normalized_emails = [str(email).lower() for email, _name, _password, _mfa, _label, _roles in accounts]
        if len(set(normalized_emails)) != 2:
            print("Bootstrap administrator and reviewer emails must be different.", file=sys.stderr)
            return 2
        passwords = [str(password) for _email, _name, password, _mfa, _label, _roles in accounts]
        if passwords[0] == passwords[1]:
            print("Bootstrap administrator passwords must be different.", file=sys.stderr)
            return 2
        for _email, _name, password, mfa_secret, label, _roles in accounts:
            if not password_is_strong(str(password)):
                print(
                    f"{label}_PASSWORD must be at least 14 characters and contain upper, lower, digit, and symbol.",
                    file=sys.stderr,
                )
                return 2
            try:
                pyotp.TOTP(str(mfa_secret)).now()
            except Exception:
                print(f"{label}_MFA_SECRET must be a valid base32 TOTP secret.", file=sys.stderr)
                return 2

        roles = ensure_roles(db)
        organization = db.query(Organization).filter(Organization.slug == settings.bootstrap_org_slug).first()
        if not organization:
            organization = Organization(
                name=settings.bootstrap_org_name,
                slug=settings.bootstrap_org_slug,
                timezone=settings.bootstrap_org_timezone,
            )
            db.add(organization)
            db.flush()
        ensure_platform_landing_domain(db, organization)
        if not db.query(OrganizationBranding).filter(OrganizationBranding.organization_id == organization.id).first():
            db.add(OrganizationBranding(organization_id=organization.id, sender_name=organization.name))

        ensure_failure_reasons(db)
        ensure_training_modules(db, organization)
        get_or_create_policy(db, organization.id)
        existing_admin_emails = {user.email.lower() for user in existing_admins}
        for email, full_name, password, mfa_secret, _label, account_roles in accounts:
            normalized_email = str(email).lower()
            user = db.query(User).filter(User.email == normalized_email).first()
            if user and user.organization_id != organization.id:
                print(f"Cannot bootstrap {normalized_email}: email belongs to another organization.", file=sys.stderr)
                db.rollback()
                return 2
            if not user:
                user = User(
                    organization_id=organization.id,
                    email=normalized_email,
                    full_name=full_name,
                    password_hash=hash_password(str(password)),
                    mfa_enabled=True,
                    mfa_secret=str(mfa_secret),
                    mfa_recovery_hashes=[],
                )
                db.add(user)
                db.flush()
            user.mfa_enabled = True
            user.mfa_secret = str(mfa_secret)
            for role_name in account_roles:
                if not db.query(UserRoleLink).filter(
                    UserRoleLink.user_id == user.id,
                    UserRoleLink.role_id == roles[role_name].id,
                ).first():
                    db.add(UserRoleLink(user_id=user.id, role_id=roles[role_name].id))
            existing_admin_emails.add(normalized_email)
        db.commit()
        print("Production administrator bootstrap complete: " + ", ".join(sorted(existing_admin_emails)))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
