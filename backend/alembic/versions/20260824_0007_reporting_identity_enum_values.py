"""normalize persisted reporting identity enum values

Revision ID: 20260824_0007
Revises: 20260824_0006
Create Date: 2026-08-24 01:38:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260824_0007"
down_revision = "20260824_0006"
branch_labels = None
depends_on = None


def _normalize_values(bind: sa.engine.Connection, table_name: str) -> None:
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if "reporting_identity_mode" not in columns:
        return
    bind.execute(
        sa.text(
            f"UPDATE {table_name} "
            "SET reporting_identity_mode = CASE LOWER(reporting_identity_mode) "
            "WHEN 'pseudonymous' THEN 'PSEUDONYMOUS' "
            "WHEN 'named' THEN 'NAMED' "
            "ELSE reporting_identity_mode END"
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    _normalize_values(bind, "organizations")
    _normalize_values(bind, "campaign_runs")

    inspector = sa.inspect(bind)
    if "organizations" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("organizations")}
    if "reporting_identity_mode" not in columns:
        return

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("organizations", recreate="always") as batch_op:
            batch_op.alter_column(
                "reporting_identity_mode",
                existing_type=sa.String(32),
                existing_nullable=False,
                server_default="PSEUDONYMOUS",
            )
    else:
        op.alter_column("organizations", "reporting_identity_mode", server_default="PSEUDONYMOUS")


def downgrade() -> None:
    # Normalized enum values are valid for the preceding application version and
    # intentionally remain uppercase; restoring invalid lowercase values would
    # make ORM reads fail again.
    pass
