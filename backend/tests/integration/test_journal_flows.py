"""Integration tests for Step 9 Journal annotation layer.

Requires the full Docker Compose stack (PostgreSQL at DATABASE_URL).
Each test runs in its own rolled-back transaction so the DB stays clean.

Run with:
    cd backend
    pytest tests/integration/test_journal_flows.py -v

Scenarios covered:
  - Create and read journal entry via repository
  - Upsert twice: second write produces audit log for changed fields only
  - Unchanged fields do not produce audit log rows
  - Cross-user IDOR prevention: user A cannot retrieve user B's entry
  - Attachment lifecycle: create PENDING → confirm → soft-delete
  - Attachment ownership: user B cannot confirm user A's attachment
  - Attachment SVG content type is rejected at service layer (422)
  - planned_risk_amount computed from average_entry × quantity
  - journal_audit_log immutability: UPDATE raises a DB exception
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tradeforge.application.journal.service import JournalService
from tradeforge.application.journal.storage import StubStorage
from tradeforge.domain.journal.errors import (
    AttachmentContentTypeNotAllowedError,
    AttachmentNotFoundError,
    JournalEntryNotFoundError,
    TradeNotFoundError,
)
from tradeforge.domain.journal.types import JournalEntryWrite
from tradeforge.infrastructure.repositories.auth_repo import AuditLogRepository
from tradeforge.infrastructure.repositories.journal_repo import JournalRepository

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set — Docker Compose stack required")
    # Integration tests use the postgres superuser to bypass app-level grants.
    return re.sub(r"//[^@]+@", "//postgres:postgres@", url)


@pytest.fixture(scope="module")
async def engine(db_url: str):  # type: ignore[return]
    eng = create_async_engine(db_url, echo=False)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="module")
def session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def session(session_factory: async_sessionmaker[AsyncSession]):  # type: ignore[return]
    async with session_factory() as s:
        await s.begin()
        yield s
        await s.rollback()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _insert_user(session: AsyncSession, suffix: str = "") -> uuid.UUID:
    uid = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO users (id, email, password_hash, is_email_verified) "
            "VALUES (:id, :email, :ph, true)"
        ),
        {
            "id": str(uid),
            "email": f"journal-test-{suffix or uid}@example.com",
            "ph": "$argon2id$placeholder",
        },
    )
    return uid


async def _insert_instrument(session: AsyncSession) -> uuid.UUID:
    iid = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO instruments (id, symbol, exchange_segment, instrument_type, name) "
            "VALUES (:id, :sym, 'NSE_EQ', 'EQ', :name)"
        ),
        {
            "id": str(iid),
            "sym": f"TESTSTOCK_{str(iid).replace('-', '')[:8]}",
            "name": "Test Stock",
        },
    )
    return iid


async def _insert_trading_account(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> uuid.UUID:
    account_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO trading_accounts "
            "(id, user_id, broker, display_name, account_type, base_currency, status) "
            "VALUES (:id, :uid, 'ZERODHA', 'Test Account', 'INDIVIDUAL', 'INR', 'ACTIVE')"
        ),
        {"id": str(account_id), "uid": str(user_id)},
    )
    return account_id


async def _insert_trade(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    instrument_id: uuid.UUID,
    average_entry: str = "500.0000",
    total_entry_quantity: str = "100.0000",
) -> uuid.UUID:
    tid = uuid.uuid4()
    now = datetime.now(UTC)
    await session.execute(
        text(
            "INSERT INTO trades "
            "(id, user_id, account_id, instrument_id, trade_type, direction, status, "
            " trade_date, first_fill_at, total_entry_quantity, total_exit_quantity, "
            " net_position, average_entry) "
            "VALUES (:id, :uid, :aid, :iid, 'MIS', 'LONG', 'OPEN', "
            " :td, :ts, :teq, 0, :teq, :avg)"
        ),
        {
            "id": str(tid),
            "uid": str(user_id),
            "aid": str(account_id),
            "iid": str(instrument_id),
            "td": now.date(),
            "ts": now,
            "teq": total_entry_quantity,
            "avg": average_entry,
        },
    )
    return tid


def _svc(session: AsyncSession) -> JournalService:
    return JournalService(
        journal_repo=JournalRepository(session),
        audit_repo=AuditLogRepository(session),
        storage=StubStorage(),
    )


# ---------------------------------------------------------------------------
# Test: create and read journal entry
# ---------------------------------------------------------------------------


async def test_create_and_read_journal_entry(session: AsyncSession) -> None:
    user_id = await _insert_user(session)
    account_id = await _insert_trading_account(session, user_id)
    instrument_id = await _insert_instrument(session)
    trade_id = await _insert_trade(
        session, user_id=user_id, account_id=account_id, instrument_id=instrument_id
    )

    svc = _svc(session)
    data = JournalEntryWrite(
        setup_name="Bull flag",
        notes="Strong volume on breakout.",
        discipline_score=8,
        planned_stop=Decimal("490"),
        planned_target=Decimal("520"),
    )
    view = await svc.upsert_entry(user_id, trade_id, data)

    assert view.trade_id == trade_id
    assert view.setup_name == "Bull flag"
    assert view.notes == "Strong volume on breakout."
    assert view.discipline_score == 8
    assert view.planned_stop == Decimal("490")
    assert view.planned_target == Decimal("520")
    # planned_risk_amount = abs(500 - 490) × 100 = 1000
    assert view.planned_risk_amount == Decimal("1000.0000")
    assert view.attachments == []

    # Read it back
    read_back = await svc.get_entry(user_id, trade_id)
    assert read_back.id == view.id
    assert read_back.setup_name == "Bull flag"


async def test_upsert_creates_entry_when_none_exists(session: AsyncSession) -> None:
    user_id = await _insert_user(session)
    account_id = await _insert_trading_account(session, user_id)
    instrument_id = await _insert_instrument(session)
    trade_id = await _insert_trade(
        session, user_id=user_id, account_id=account_id, instrument_id=instrument_id
    )

    svc = _svc(session)
    with pytest.raises(JournalEntryNotFoundError):
        await svc.get_entry(user_id, trade_id)

    await svc.upsert_entry(user_id, trade_id, JournalEntryWrite())

    view = await svc.get_entry(user_id, trade_id)
    assert view.trade_id == trade_id


# ---------------------------------------------------------------------------
# Test: audit log only captures changed fields
# ---------------------------------------------------------------------------


async def test_upsert_twice_writes_audit_log_for_changed_fields_only(
    session: AsyncSession,
) -> None:
    user_id = await _insert_user(session)
    account_id = await _insert_trading_account(session, user_id)
    instrument_id = await _insert_instrument(session)
    trade_id = await _insert_trade(
        session, user_id=user_id, account_id=account_id, instrument_id=instrument_id
    )
    svc = _svc(session)

    # First write: no existing entry — no audit log yet
    await svc.upsert_entry(
        user_id,
        trade_id,
        JournalEntryWrite(setup_name="Flag", notes="Initial note"),
    )
    # Directly check audit count after first write
    result = await session.execute(
        text(
            "SELECT COUNT(*) FROM journal_audit_log jal "
            "JOIN journal_entries je ON jal.journal_entry_id = je.id "
            "WHERE je.trade_id = :tid"
        ),
        {"tid": str(trade_id)},
    )
    assert result.scalar() == 0, "First upsert (create) should write no audit log"

    # Second write: change setup_name, keep notes the same
    await svc.upsert_entry(
        user_id,
        trade_id,
        JournalEntryWrite(
            setup_name="Breakout", notes="Initial note", change_reason="Corrected setup"
        ),
    )

    result = await session.execute(
        text(
            "SELECT field_name, change_reason FROM journal_audit_log jal "
            "JOIN journal_entries je ON jal.journal_entry_id = je.id "
            "WHERE je.trade_id = :tid"
        ),
        {"tid": str(trade_id)},
    )
    rows = result.fetchall()
    field_names = {r[0] for r in rows}
    # Only setup_name changed — notes was unchanged
    assert "setup_name" in field_names, "setup_name change should produce an audit row"
    assert "notes" not in field_names, "unchanged notes should not produce an audit row"
    assert all(r[1] == "Corrected setup" for r in rows)


async def test_audit_history_returned_by_service(session: AsyncSession) -> None:
    user_id = await _insert_user(session)
    account_id = await _insert_trading_account(session, user_id)
    instrument_id = await _insert_instrument(session)
    trade_id = await _insert_trade(
        session, user_id=user_id, account_id=account_id, instrument_id=instrument_id
    )
    svc = _svc(session)

    await svc.upsert_entry(user_id, trade_id, JournalEntryWrite(discipline_score=7))
    await svc.upsert_entry(
        user_id, trade_id, JournalEntryWrite(discipline_score=9, change_reason="Self-reflection")
    )

    entries = await svc.get_audit_history(user_id, trade_id)
    assert len(entries) == 1
    assert entries[0].field_name == "discipline_score"
    assert entries[0].previous_value == "7"
    assert entries[0].new_value == "9"
    assert entries[0].change_reason == "Self-reflection"


# ---------------------------------------------------------------------------
# Test: cross-user IDOR prevention
# ---------------------------------------------------------------------------


async def test_cross_user_idor_get_entry(session: AsyncSession) -> None:
    """User B must not retrieve user A's journal entry."""
    user_a = await _insert_user(session, "a")
    user_b = await _insert_user(session, "b")
    account_id_a = await _insert_trading_account(session, user_a)
    instrument_id = await _insert_instrument(session)
    trade_id = await _insert_trade(
        session, user_id=user_a, account_id=account_id_a, instrument_id=instrument_id
    )
    svc = _svc(session)

    # User A creates entry
    await svc.upsert_entry(user_a, trade_id, JournalEntryWrite(notes="User A's private note"))

    # User B attempts to GET using the same trade_id
    with pytest.raises(JournalEntryNotFoundError):
        await svc.get_entry(user_b, trade_id)


async def test_cross_user_idor_upsert(session: AsyncSession) -> None:
    """User B must not upsert against user A's trade (trade not found for user B)."""
    user_a = await _insert_user(session, "ua")
    user_b = await _insert_user(session, "ub")
    account_id_a = await _insert_trading_account(session, user_a)
    instrument_id = await _insert_instrument(session)
    # trade belongs to user A
    trade_id = await _insert_trade(
        session, user_id=user_a, account_id=account_id_a, instrument_id=instrument_id
    )
    svc = _svc(session)

    with pytest.raises(TradeNotFoundError):
        await svc.upsert_entry(user_b, trade_id, JournalEntryWrite(notes="Hack attempt"))


# ---------------------------------------------------------------------------
# Test: attachment lifecycle
# ---------------------------------------------------------------------------


async def test_attachment_presign_confirm_delete_lifecycle(session: AsyncSession) -> None:
    user_id = await _insert_user(session)
    account_id = await _insert_trading_account(session, user_id)
    instrument_id = await _insert_instrument(session)
    trade_id = await _insert_trade(
        session, user_id=user_id, account_id=account_id, instrument_id=instrument_id
    )
    svc = _svc(session)

    # Need an existing journal entry for attachment flow
    await svc.upsert_entry(user_id, trade_id, JournalEntryWrite())

    # Step 1: presign
    presign = await svc.presign_attachment(
        user_id=user_id,
        trade_id=trade_id,
        filename="chart.png",
        content_type="image/png",
        byte_size=4096,
        capture_moment="AT_ENTRY",
        caption="Entry chart",
    )
    att_id = presign.attachment_id
    assert presign.upload_url.startswith("https://stub-s3.local")
    assert presign.expires_in_seconds == 900

    # Verify PENDING row in DB
    row = await session.execute(
        text("SELECT status FROM journal_attachments WHERE id = :id"),
        {"id": str(att_id)},
    )
    assert row.scalar() == "PENDING"

    # Step 2: confirm
    view = await svc.confirm_attachment(user_id=user_id, attachment_id=att_id)
    assert view.status == "CONFIRMED"
    assert view.download_url is not None

    # Entry GET now includes the attachment
    entry_view = await svc.get_entry(user_id, trade_id)
    assert len(entry_view.attachments) == 1
    assert entry_view.attachments[0].id == att_id

    # Step 3: delete
    await svc.delete_attachment(user_id=user_id, attachment_id=att_id)

    # Entry GET no longer includes the attachment
    entry_view2 = await svc.get_entry(user_id, trade_id)
    assert len(entry_view2.attachments) == 0

    # Underlying row is soft-deleted, not gone
    row2 = await session.execute(
        text("SELECT deleted_at FROM journal_attachments WHERE id = :id"),
        {"id": str(att_id)},
    )
    assert row2.scalar() is not None, "Attachment should be soft-deleted, not hard-deleted"


async def test_attachment_cross_user_confirm_rejected(session: AsyncSession) -> None:
    """User B must not confirm user A's pending attachment (returns 404)."""
    user_a = await _insert_user(session, "atta")
    user_b = await _insert_user(session, "attb")
    account_id_a = await _insert_trading_account(session, user_a)
    instrument_id = await _insert_instrument(session)
    trade_id = await _insert_trade(
        session, user_id=user_a, account_id=account_id_a, instrument_id=instrument_id
    )
    svc = _svc(session)

    await svc.upsert_entry(user_a, trade_id, JournalEntryWrite())
    presign = await svc.presign_attachment(
        user_id=user_a,
        trade_id=trade_id,
        filename="entry.jpeg",
        content_type="image/jpeg",
        byte_size=2048,
        capture_moment="AT_ENTRY",
        caption=None,
    )

    # User B tries to confirm user A's attachment
    with pytest.raises(AttachmentNotFoundError):
        await svc.confirm_attachment(user_id=user_b, attachment_id=presign.attachment_id)


async def test_attachment_svg_rejected_by_service(session: AsyncSession) -> None:
    """SVG is explicitly excluded (XSS vector) — must raise AttachmentContentTypeNotAllowedError."""
    user_id = await _insert_user(session)
    account_id = await _insert_trading_account(session, user_id)
    instrument_id = await _insert_instrument(session)
    trade_id = await _insert_trade(
        session, user_id=user_id, account_id=account_id, instrument_id=instrument_id
    )
    svc = _svc(session)

    await svc.upsert_entry(user_id, trade_id, JournalEntryWrite())

    with pytest.raises(AttachmentContentTypeNotAllowedError):
        await svc.presign_attachment(
            user_id=user_id,
            trade_id=trade_id,
            filename="chart.svg",
            content_type="image/svg+xml",
            byte_size=512,
            capture_moment="AT_ENTRY",
            caption=None,
        )


# ---------------------------------------------------------------------------
# Test: planned_risk_amount
# ---------------------------------------------------------------------------


async def test_planned_risk_amount_computation(session: AsyncSession) -> None:
    """abs(avg_entry − planned_stop) × total_entry_qty = abs(500 − 490) × 100 = 1000"""
    user_id = await _insert_user(session)
    account_id = await _insert_trading_account(session, user_id)
    instrument_id = await _insert_instrument(session)
    trade_id = await _insert_trade(
        session,
        user_id=user_id,
        account_id=account_id,
        instrument_id=instrument_id,
        average_entry="500.0000",
        total_entry_quantity="100.0000",
    )
    svc = _svc(session)

    view = await svc.upsert_entry(user_id, trade_id, JournalEntryWrite(planned_stop=Decimal("490")))

    assert view.planned_risk_amount == Decimal("1000.0000")


async def test_planned_risk_amount_cleared_when_stop_removed(session: AsyncSession) -> None:
    user_id = await _insert_user(session)
    account_id = await _insert_trading_account(session, user_id)
    instrument_id = await _insert_instrument(session)
    trade_id = await _insert_trade(
        session, user_id=user_id, account_id=account_id, instrument_id=instrument_id
    )
    svc = _svc(session)

    # Set stop
    await svc.upsert_entry(user_id, trade_id, JournalEntryWrite(planned_stop=Decimal("490")))

    # Remove stop explicitly (None)
    view = await svc.upsert_entry(user_id, trade_id, JournalEntryWrite(planned_stop=None))

    assert view.planned_risk_amount is None


# ---------------------------------------------------------------------------
# Test: audit log immutability (DB-level trigger)
# ---------------------------------------------------------------------------


async def test_audit_log_immutable_trigger(session: AsyncSession) -> None:
    """The trg_audit_log_immutable trigger must raise if we attempt an UPDATE."""
    user_id = await _insert_user(session)
    account_id = await _insert_trading_account(session, user_id)
    instrument_id = await _insert_instrument(session)
    trade_id = await _insert_trade(
        session, user_id=user_id, account_id=account_id, instrument_id=instrument_id
    )
    svc = _svc(session)

    # Write two upserts to produce an audit row
    await svc.upsert_entry(user_id, trade_id, JournalEntryWrite(notes="first"))
    await svc.upsert_entry(user_id, trade_id, JournalEntryWrite(notes="second"))

    # Try to UPDATE the audit log row — should raise
    import sqlalchemy.exc

    with pytest.raises(sqlalchemy.exc.DBAPIError):
        await session.execute(
            text(
                "UPDATE journal_audit_log SET new_value = 'tampered' "
                "WHERE journal_entry_id IN ("
                "  SELECT id FROM journal_entries WHERE trade_id = :tid"
                ")"
            ),
            {"tid": str(trade_id)},
        )
