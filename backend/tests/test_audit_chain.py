"""The hash-chained audit log must verify even when the clock does not move between entries.

On Windows with Python 3.12 the wall clock advances only every 15.6 ms, so two entries
written in one request can carry the same timestamp. Verification walks the chain in
timestamp order, so a tie must never leave the order ambiguous.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.db.session import SessionLocal
from app.models.entities import AuditLog, Organization
from app.services import audit as audit_module
from app.services.audit import GENESIS_HASH, audit_log, verify_audit_chain

FROZEN = datetime(2026, 11, 17, 12, 0, 0, 123456, tzinfo=timezone.utc)


class FrozenClock(datetime):
    """Every call returns the same instant, as a coarse clock does within one tick."""

    @classmethod
    def now(cls, tz=None):
        return FROZEN if tz is not None else FROZEN.replace(tzinfo=None)


@pytest.fixture()
def organization_id(client):
    """A tenant of its own, so the chain under test holds only this test's entries.

    Depends on ``client`` because starting the app is what creates the test schema.
    """
    db = SessionLocal()
    try:
        organization = Organization(name="Audit Chain Org", slug=f"audit-chain-{uuid.uuid4().hex[:8]}", timezone="UTC")
        db.add(organization)
        db.commit()
        return organization.id
    finally:
        db.close()


def _write(db, organization_id, action: str) -> None:
    audit_log(db, organization_id=organization_id, user_id=None, action=action, resource_type="test", resource_id=action)


def _chain(db, organization_id) -> list[AuditLog]:
    return (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == organization_id)
        .order_by(AuditLog.occurred_at.asc(), AuditLog.id.asc())
        .all()
    )


def test_chain_stays_valid_when_entries_share_a_clock_tick(monkeypatch, organization_id):
    monkeypatch.setattr(audit_module, "datetime", FrozenClock)

    db = SessionLocal()
    try:
        # Several entries in one transaction with no flush in between: sessions do not
        # autoflush, so each new entry must still link to the one added just before it.
        for action in ("first", "second", "third"):
            _write(db, organization_id, action)
        db.commit()
        # More entries in later transactions, still within the same clock tick.
        for action in ("fourth", "fifth"):
            _write(db, organization_id, action)
            db.commit()

        rows = _chain(db, organization_id)
        assert [row.action for row in rows] == ["first", "second", "third", "fourth", "fifth"]
        assert rows[0].previous_hash == GENESIS_HASH
        for before, after in zip(rows, rows[1:]):
            assert after.previous_hash == before.entry_hash, f"{after.action} must link to {before.action}"
            assert after.occurred_at > before.occurred_at, "timestamps strictly increase, so the order is unambiguous"
        assert verify_audit_chain(db, organization_id) == {
            "valid": True,
            "entries": 5,
            "invalid_index": None,
            "invalid_entry_id": None,
        }
    finally:
        db.close()


def test_tampering_is_still_detected_after_a_tie(monkeypatch, organization_id):
    monkeypatch.setattr(audit_module, "datetime", FrozenClock)

    db = SessionLocal()
    try:
        for action in ("approve", "launch", "export"):
            _write(db, organization_id, action)
        db.commit()

        launch = next(row for row in _chain(db, organization_id) if row.action == "launch")
        launch.details = {"note": "rewritten after the fact"}
        db.commit()

        result = verify_audit_chain(db, organization_id)
        assert result["valid"] is False
        assert result["invalid_index"] == 1
        assert result["invalid_entry_id"] == str(launch.id)
    finally:
        db.close()
