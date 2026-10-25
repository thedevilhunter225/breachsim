from __future__ import annotations

from sqlalchemy import text

from app.db.session import SessionLocal


def test_test_database_enforces_foreign_keys_like_postgresql(client):
    with SessionLocal() as db:
        assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1
