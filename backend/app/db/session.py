from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def ensure_schema_compatibility() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    required_columns = {
        "organizations": {
            "email_provider_enabled": "INTEGER NOT NULL DEFAULT 0",
            "email_provider_mode": "VARCHAR(32) NOT NULL DEFAULT 'sandbox'",
            "smtp_host": "VARCHAR(255)",
            "smtp_port": "INTEGER NOT NULL DEFAULT 587",
            "smtp_username": "VARCHAR(255)",
            "smtp_password": "TEXT",
            "smtp_from_email": "VARCHAR(255)",
            "smtp_sender_name": "VARCHAR(255)",
            "smtp_recipient_allowlist": "JSON",
        }
    }

    with engine.begin() as connection:
        tables = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).all()
        }
        for table_name, columns in required_columns.items():
            if table_name not in tables:
                continue
            existing_columns = {
                row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table_name})").all()
            }
            for column_name, definition in columns.items():
                if column_name in existing_columns:
                    continue
                connection.exec_driver_sql(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
                )
            if table_name == "organizations" and "smtp_recipient_allowlist" in columns:
                connection.exec_driver_sql(
                    "UPDATE organizations SET smtp_recipient_allowlist = '[]' WHERE smtp_recipient_allowlist IS NULL"
                )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import entities  # noqa: F401
    from app.services.seed import seed_database

    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility()
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
