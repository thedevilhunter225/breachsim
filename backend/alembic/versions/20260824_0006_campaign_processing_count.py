"""separate queued and processing campaign-run counts

Revision ID: 20260824_0006
Revises: 20260823_0005
Create Date: 2026-08-24 00:15:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260824_0006"
down_revision = "20260823_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "campaign_runs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("campaign_runs")}
    if "processing_count" not in columns:
        op.add_column(
            "campaign_runs",
            sa.Column("processing_count", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "campaign_runs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("campaign_runs")}
    if "processing_count" in columns:
        op.drop_column("campaign_runs", "processing_count")
