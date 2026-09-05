"""revocable authentication sessions

Revision ID: 20260819_0004
Revises: 20260727_0003
Create Date: 2026-08-19 01:00:00
"""

from __future__ import annotations

from alembic import op

from app.db.base import Base
from app.models import entities  # noqa: F401

revision = "20260819_0004"
down_revision = "20260727_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.tables["auth_sessions"].create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    Base.metadata.tables["auth_sessions"].drop(bind=op.get_bind(), checkfirst=True)
