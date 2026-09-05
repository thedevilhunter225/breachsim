"""enterprise tenant, email, campaign-run and QR foundations

Revision ID: 20260823_0005
Revises: 20260819_0004
Create Date: 2026-08-23 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.core.crypto import blind_index, encrypt_text
from app.db.base import Base
from app.models import entities  # noqa: F401

revision = "20260823_0005"
down_revision = "20260819_0004"
branch_labels = None
depends_on = None

NEW_TABLES = (
    "organization_domains",
    "organization_branding",
    "email_connections",
    "sso_connections",
    "scim_credentials",
    "oidc_transactions",
    "organization_invitations",
    "campaign_runs",
    "qr_asset_tokens",
    "outbox_events",
    "delivery_suppressions",
    "provider_event_receipts",
)


def _columns() -> dict[str, list[sa.Column]]:
    return {
        "organizations": [
            # SQLAlchemy's Enum persists member names (PSEUDONYMOUS/NAMED), not
            # the lowercase StrEnum values returned by the API.
            sa.Column("reporting_identity_mode", sa.String(32), nullable=False, server_default="PSEUDONYMOUS"),
            sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        ],
        "users": [
            sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("mfa_secret", sa.String(1024), nullable=True),
            sa.Column("mfa_recovery_hashes", sa.JSON(), nullable=True),
            sa.Column("external_subject", sa.String(255), nullable=True),
        ],
        "auth_sessions": [
            sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("csrf_token_hash", sa.String(64), nullable=True),
            sa.Column("auth_method", sa.String(32), nullable=False, server_default="password"),
        ],
        "employees": [
            sa.Column("email_blind_index", sa.String(64), nullable=True),
            sa.Column("directory_source", sa.String(32), nullable=False, server_default="manual"),
            sa.Column("external_id", sa.String(255), nullable=True),
        ],
        "departments": [
            sa.Column("directory_source", sa.String(32), nullable=False, server_default="manual"),
            sa.Column("external_id", sa.String(255), nullable=True),
        ],
        "email_connections": [
            sa.Column("reconciliation_secret_ref", sa.String(1024), nullable=True),
        ],
        "campaigns": [
            sa.Column("landing_domain_id", sa.Uuid(), sa.ForeignKey("organization_domains.id"), nullable=True),
            sa.Column("email_connection_id", sa.Uuid(), sa.ForeignKey("email_connections.id"), nullable=True),
        ],
        "delivery_attempts": [
            sa.Column("campaign_run_id", sa.Uuid(), sa.ForeignKey("campaign_runs.id"), nullable=True),
            sa.Column("recipient_ciphertext", sa.String(1024), nullable=True),
            sa.Column("idempotency_key", sa.String(128), nullable=True),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error_code", sa.String(128), nullable=True),
            sa.Column("last_error_detail", sa.Text(), nullable=True),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("bounced_at", sa.DateTime(timezone=True), nullable=True),
        ],
        "landing_tokens": [
            sa.Column("token_public_id", sa.String(32), nullable=True),
            sa.Column("token_secret_hash", sa.String(64), nullable=True),
            sa.Column("token_secret_ciphertext", sa.String(1024), nullable=True),
            sa.Column("landing_hostname", sa.String(253), nullable=True),
            sa.Column("first_scanned_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        ],
        "audit_logs": [
            sa.Column("previous_hash", sa.String(64), nullable=True),
            sa.Column("entry_hash", sa.String(64), nullable=True),
        ],
    }


def _extend_pg_enum(bind: sa.engine.Connection, enum_name: str, values: tuple[str, ...]) -> None:
    if bind.dialect.name != "postgresql":
        return
    for value in values:
        bind.execute(sa.text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'"))


def _present_columns(inspector: sa.Inspector, table_name: str) -> set[str]:
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    with op.get_context().autocommit_block():
        _extend_pg_enum(bind, "userrole", ("platform_operator", "risk_identity_viewer"))
        _extend_pg_enum(bind, "campaignstatus", ("cancelled",))
        _extend_pg_enum(bind, "eventtype", ("provider_accepted",))
        _extend_pg_enum(
            bind,
            "deliverystatus",
            ("queued", "processing", "accepted", "suppressed", "cancelled", "unknown"),
        )

    # Creating the new tables first allows the campaign/delivery foreign-key columns
    # below to reference them on existing installations. Fresh installs may already
    # contain these tables because the historical initial migration uses create_all.
    Base.metadata.create_all(bind=bind, tables=[Base.metadata.tables[name] for name in NEW_TABLES])

    inspector = sa.inspect(bind)
    for table_name, columns in _columns().items():
        if table_name not in inspector.get_table_names():
            continue
        present = _present_columns(inspector, table_name)
        missing = [column for column in columns if column.name not in present]
        if not missing:
            continue

        # SQLite cannot ALTER an existing table to add a foreign-key constraint.
        # Alembic batch mode recreates the table, copies its data, and installs the
        # new columns and constraints as part of the replacement CREATE TABLE.
        # Keep the direct ALTER path for PostgreSQL so production migrations remain
        # fast even on large campaign and delivery tables.
        requires_sqlite_recreate = bind.dialect.name == "sqlite" and any(
            column.foreign_keys for column in missing
        )
        if requires_sqlite_recreate:
            with op.batch_alter_table(table_name, recreate="always") as batch_op:
                for column in missing:
                    batch_op.add_column(column)
        else:
            for column in missing:
                op.add_column(table_name, column)

    # Existing employee identifiers are encrypted in place and receive a keyed blind
    # index. New writes are encrypted automatically by the SQLAlchemy type.
    if "employees" in inspector.get_table_names():
        rows = bind.execute(sa.text("SELECT id, email, full_name FROM employees")).mappings()
        for row in rows:
            email = row["email"] or ""
            full_name = row["full_name"] or ""
            encrypted_email = email if str(email).startswith("gAAAA") else encrypt_text(str(email))
            encrypted_name = full_name if str(full_name).startswith("gAAAA") else encrypt_text(str(full_name))
            bind.execute(
                sa.text(
                    "UPDATE employees SET email=:email, full_name=:full_name, email_blind_index=:email_hash "
                    "WHERE id=:employee_id"
                ),
                {
                    "email": encrypted_email,
                    "full_name": encrypted_name,
                    "email_hash": blind_index(str(email), namespace="employee-email"),
                    "employee_id": row["id"],
                },
            )

    if "context_profiles" in inspector.get_table_names():
        rows = bind.execute(sa.text("SELECT id, employee_context_profile FROM context_profiles")).mappings()
        for row in rows:
            profile = row["employee_context_profile"] or ""
            encrypted_profile = profile if str(profile).startswith("gAAAA") else encrypt_text(str(profile))
            bind.execute(
                sa.text(
                    "UPDATE context_profiles SET employee_context_profile=:profile WHERE id=:profile_id"
                ),
                {"profile": encrypted_profile, "profile_id": row["id"]},
            )

    if bind.dialect.name == "postgresql":
        op.alter_column("landing_tokens", "token", existing_type=sa.String(255), nullable=True)
        op.alter_column("employees", "email", existing_type=sa.String(255), type_=sa.String(1024))
        op.alter_column("employees", "full_name", existing_type=sa.String(255), type_=sa.String(1024))

    inspector = sa.inspect(bind)
    if "employees" in inspector.get_table_names():
        existing = {index["name"] for index in inspector.get_indexes("employees")}
        if "uq_org_employee_external" not in existing:
            op.create_index(
                "uq_org_employee_external",
                "employees",
                ["organization_id", "directory_source", "external_id"],
                unique=True,
            )
    if "departments" in inspector.get_table_names():
        existing = {index["name"] for index in inspector.get_indexes("departments")}
        if "uq_org_department_external" not in existing:
            op.create_index(
                "uq_org_department_external",
                "departments",
                ["organization_id", "directory_source", "external_id"],
                unique=True,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name, index_name in (
        ("employees", "uq_org_employee_external"),
        ("departments", "uq_org_department_external"),
    ):
        if table_name in inspector.get_table_names() and index_name in {
            index["name"] for index in inspector.get_indexes(table_name)
        }:
            op.drop_index(index_name, table_name=table_name)

    for table_name, columns in reversed(tuple(_columns().items())):
        if table_name not in inspector.get_table_names():
            continue
        present = _present_columns(inspector, table_name)
        removable = [column for column in reversed(columns) if column.name in present]
        if not removable:
            continue
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(table_name, recreate="always") as batch_op:
                for column in removable:
                    batch_op.drop_column(column.name)
        else:
            for column in removable:
                op.drop_column(table_name, column.name)

    for table_name in reversed(NEW_TABLES):
        if table_name in sa.inspect(bind).get_table_names():
            op.drop_table(table_name)

    # Values added to native Postgres enums are intentionally retained. Removing a
    # single value requires rebuilding every dependent column and is unsafe in rollback.
