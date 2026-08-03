"""real synthetic media: voice/video cloning assets

Adds the media asset registry and the persona voice-clone reference columns that back
real ElevenLabs voice cloning and D-ID talking-head video.

Revision ID: 20260727_0003
Revises: 20260727_0002
Create Date: 2026-07-27 14:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.db.base import Base
from app.models import entities  # noqa: F401

revision = "20260727_0003"
down_revision = "20260727_0002"
branch_labels = None
depends_on = None

NEW_TABLES = ("media_assets",)


def persona_columns() -> list[sa.Column]:
    return [
        sa.Column("voice_clone_provider", sa.String(64), nullable=True),
        sa.Column("voice_clone_ref", sa.String(255), nullable=True),
        sa.Column("has_face_image", sa.Boolean(), nullable=False, server_default=sa.false()),
    ]


def _existing(inspector: sa.Inspector, table: str) -> set[str]:
    if table not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    present = _existing(inspector, "impersonation_personas")
    for column in persona_columns():
        if column.name not in present:
            op.add_column("impersonation_personas", column)

    Base.metadata.create_all(bind=bind, tables=[Base.metadata.tables[name] for name in NEW_TABLES])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name in NEW_TABLES:
        if table_name in inspector.get_table_names():
            op.drop_table(table_name)

    present = _existing(inspector, "impersonation_personas")
    for column in persona_columns():
        if column.name in present:
            op.drop_column("impersonation_personas", column.name)

    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS mediaassetkind")
        op.execute("DROP TYPE IF EXISTS mediaassetstatus")
