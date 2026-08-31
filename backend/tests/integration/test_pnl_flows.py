"""Integration tests for PnlRepository and ChargeScheduleRepository.

Requires the full Docker Compose stack (PostgreSQL at DATABASE_URL).
Each test runs in its own rolled-back transaction so the DB stays clean.

Run with:
    cd backend
    pytest tests/integration/test_pnl_flows.py -v

Scenarios covered — PnlRepository:
  - get_trade_snapshot returns None for unknown trade
  - get_trade_snapshot returns None for OPEN trade (only CLOSED is eligible)
  - get_trade_snapshot assembles TradeSnapshot from trade + instrument + fills
  - get_trade_snapshot includes planned_risk_amount from journal_entries when present
  - get_trade_snapshot returns planned_risk_amount=None when no journal entry
  - upsert creates a new trade_pnl row
  - upsert called twice updates in place (idempotent ON CONFLICT)
  - get_for_trade returns the upserted row; None when not found
  - update_r_multiple overwrites the field; passing None clears it

Scenarios covered — ChargeScheduleRepository:
  - get_for_date returns None for unknown (broker, trade_type, exchange_segment)
  - get_for_date returns the seeded Zerodha MIS NSE_EQ schedule
  - get_for_date selects the effective row closest to (but not after) trade_date
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tradeforge.domain.pnl.types import PNL_ENGINE_VERSION, PnlResult
from tradeforge.infrastructure.repositories.charge_schedule_repo import ChargeScheduleRepository
from tradeforge.infrastructure.repositories.pnl_repo import PnlRepository

# ---------------------------------------------------------------------------
# Session factory — module-scoped to reuse the connection pool
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set — Docker Compose stack required")
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


async def _insert_user(session: AsyncSession) -> uuid.UUID:
    uid = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO users (id, email, password_hash, is_email_verified) "
            "VALUES (:id, :email, :ph, true)"
        ),
        {"id": str(uid), "email": f"pnl-test-{uid}@example.com", "ph": "$argon2id$placeholder"},
    )
    return uid


async def _insert_instrument(session: AsyncSession, *, instrument_type: str = "EQ") -> uuid.UUID:
    iid = uuid.uuid4()
    sym = f"SYM_{str(iid).replace('-', '')[:8]}"
    await session.execute(
        text(
            "INSERT INTO instruments (id, symbol, exchange_segment, instrument_type, name) "
            "VALUES (:id, :sym, 'NSE_EQ', :itype, :name)"
        ),
        {"id": str(iid), "sym": sym, "itype": instrument_type, "name": sym},
    )
    return iid


async def _insert_closed_trade(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    instrument_id: uuid.UUID,
    trade_type: str = "MIS",
    direction: str = "LONG",
    average_entry: str = "250.0000",
    average_exit: str = "260.0000",
    total_entry_quantity: str = "100.0000",
    trade_date: date | None = None,
) -> uuid.UUID:
    tid = uuid.uuid4()
    td = trade_date or date(2026, 1, 15)
    now = datetime(2026, 1, 15, 9, 31, tzinfo=timezone.utc)
    await session.execute(
        text(
            "INSERT INTO trades "
            "(id, user_id, instrument_id, trade_type, direction, status, "
            " trade_date, first_fill_at, total_entry_quantity, total_exit_quantity, "
            " net_position, average_entry, average_exit) "
            "VALUES (:id, :uid, :iid, :tt, :dir, 'CLOSED', "
            " :td, :ts, :teq, :teq, 0, :avg_e, :avg_x)"
        ),
        {
            "id": str(tid),
            "uid": str(user_id),
            "iid": str(instrument_id),
            "tt": trade_type,
            "dir": direction,
            "td": td,
            "ts": now,
            "teq": total_entry_quantity,
            "avg_e": average_entry,
            "avg_x": average_exit,
        },
    )
    return tid


async def _insert_open_trade(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    instrument_id: uuid.UUID,
) -> uuid.UUID:
    tid = uuid.uuid4()
    now = datetime(2026, 1, 15, 9, 31, tzinfo=timezone.utc)
    await session.execute(
        text(
            "INSERT INTO trades "
            "(id, user_id, instrument_id, trade_type, direction, status, "
            " trade_date, first_fill_at, total_entry_quantity, total_exit_quantity, "
            " net_position, average_entry) "
            "VALUES (:id, :uid, :iid, 'MIS', 'LONG', 'OPEN', "
            " :td, :ts, 100, 0, 100, 250.0000)"
        ),
        {"id": str(tid), "uid": str(user_id), "iid": str(instrument_id),
         "td": date(2026, 1, 15), "ts": now},
    )
    return tid


async def _insert_entry_fill(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    instrument_id: uuid.UUID,
    trade_id: uuid.UUID,
    broker: str = "ZERODHA",
) -> None:
    now = datetime(2026, 1, 15, 9, 31, tzinfo=timezone.utc)
    await session.execute(
        text(
            "INSERT INTO execution_fills "
            "(id, user_id, instrument_id, trade_id, fill_timestamp, trade_date, session, "
            " side, quantity, price, product_type, broker, import_source, fill_role) "
            "VALUES (:id, :uid, :iid, :tid, :ts, :td, 'REGULAR', "
            " 'BUY', 100, 250.00, 'MIS', :broker, 'BROKER', 'ENTRY')"
        ),
        {
            "id": str(uuid.uuid4()),
            "uid": str(user_id),
            "iid": str(instrument_id),
            "tid": str(trade_id),
            "ts": now,
            "td": date(2026, 1, 15),
            "broker": broker,
        },
    )


async def _insert_journal_entry(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    trade_id: uuid.UUID,
    planned_risk_amount: str = "1000.0000",
) -> None:
    eid = uuid.uuid4()
    now = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    await session.execute(
        text(
            "INSERT INTO journal_entries "
            "(id, trade_id, user_id, planned_risk_amount, created_at, updated_at) "
            "VALUES (:id, :tid, :uid, :pra, :now, :now)"
        ),
        {
            "id": str(eid),
            "tid": str(trade_id),
            "uid": str(user_id),
            "pra": planned_risk_amount,
            "now": now,
        },
    )


def _build_pnl_result(
    trade_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    gross_pnl: str = "1000.0000",
    net_pnl: str = "950.0000",
    r_multiple: str | None = "2.500000",
) -> PnlResult:
    charge = Decimal("50.0000")
    charge_component = Decimal("7.1429")  # roughly charge / 7
    # Ensure total_charges identity: brokerage + stt + exchange + sebi + stamp + gst + ipft
    # Use round numbers that sum exactly to 50
    return PnlResult(
        trade_id=trade_id,
        user_id=user_id,
        gross_pnl=Decimal(gross_pnl),
        net_pnl=Decimal(net_pnl),
        r_multiple=Decimal(r_multiple) if r_multiple is not None else None,
        brokerage=Decimal("20.0000"),
        stt=Decimal("10.0000"),
        exchange_charges=Decimal("8.0000"),
        sebi_charges=Decimal("2.0000"),
        stamp_duty=Decimal("5.0000"),
        gst=Decimal("4.0000"),
        ipft=Decimal("1.0000"),
        total_charges=Decimal("50.0000"),
        broker="ZERODHA",
        charge_schedule_version="2024-10-01",
        engine_version=PNL_ENGINE_VERSION,
    )


# ---------------------------------------------------------------------------
# PnlRepository — get_trade_snapshot
# ---------------------------------------------------------------------------


async def test_get_trade_snapshot_returns_none_for_unknown_trade(session: AsyncSession) -> None:
    repo = PnlRepository(session)
    result = await repo.get_trade_snapshot(uuid.uuid4())
    assert result is None


async def test_get_trade_snapshot_returns_none_for_open_trade(session: AsyncSession) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)
    trade_id = await _insert_open_trade(session, user_id=user_id, instrument_id=instrument_id)
    await _insert_entry_fill(session, user_id=user_id, instrument_id=instrument_id, trade_id=trade_id)

    repo = PnlRepository(session)
    result = await repo.get_trade_snapshot(trade_id)
    assert result is None


async def test_get_trade_snapshot_assembles_correct_fields(session: AsyncSession) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)
    trade_id = await _insert_closed_trade(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        average_entry="250.0000",
        average_exit="260.0000",
        total_entry_quantity="100.0000",
    )
    await _insert_entry_fill(
        session, user_id=user_id, instrument_id=instrument_id, trade_id=trade_id, broker="ZERODHA"
    )

    repo = PnlRepository(session)
    snapshot = await repo.get_trade_snapshot(trade_id)

    assert snapshot is not None
    assert snapshot.trade_id == trade_id
    assert snapshot.user_id == user_id
    assert snapshot.trade_type == "MIS"
    assert snapshot.direction == "LONG"
    assert snapshot.exchange_segment == "NSE_EQ"
    assert snapshot.broker == "ZERODHA"
    assert snapshot.average_entry == Decimal("250.0000")
    assert snapshot.average_exit == Decimal("260.0000")
    assert snapshot.total_entry_quantity == Decimal("100.0000")
    assert snapshot.planned_risk_amount is None  # no journal entry


async def test_get_trade_snapshot_includes_planned_risk_from_journal(
    session: AsyncSession,
) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)
    trade_id = await _insert_closed_trade(
        session, user_id=user_id, instrument_id=instrument_id
    )
    await _insert_entry_fill(
        session, user_id=user_id, instrument_id=instrument_id, trade_id=trade_id
    )
    await _insert_journal_entry(
        session, user_id=user_id, trade_id=trade_id, planned_risk_amount="500.0000"
    )

    repo = PnlRepository(session)
    snapshot = await repo.get_trade_snapshot(trade_id)

    assert snapshot is not None
    assert snapshot.planned_risk_amount == Decimal("500.0000")


async def test_get_trade_snapshot_returns_none_when_no_entry_fill(
    session: AsyncSession,
) -> None:
    """get_trade_snapshot requires at least one ENTRY fill to determine broker."""
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)
    trade_id = await _insert_closed_trade(
        session, user_id=user_id, instrument_id=instrument_id
    )
    # No fills inserted — _get_broker_for_trade returns None

    repo = PnlRepository(session)
    result = await repo.get_trade_snapshot(trade_id)
    assert result is None


# ---------------------------------------------------------------------------
# PnlRepository — upsert / get_for_trade / update_r_multiple
# ---------------------------------------------------------------------------


async def test_upsert_creates_trade_pnl_row(session: AsyncSession) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)
    trade_id = await _insert_closed_trade(
        session, user_id=user_id, instrument_id=instrument_id
    )

    repo = PnlRepository(session)
    pnl = _build_pnl_result(trade_id, user_id)
    await repo.upsert(pnl)
    await session.flush()

    row = await repo.get_for_trade(trade_id)
    assert row is not None
    assert row.trade_id == trade_id
    assert row.user_id == user_id
    assert row.gross_pnl == Decimal("1000.0000")
    assert row.net_pnl == Decimal("950.0000")
    assert row.total_charges == Decimal("50.0000")
    assert row.broker == "ZERODHA"
    assert row.engine_version == PNL_ENGINE_VERSION


async def test_upsert_is_idempotent(session: AsyncSession) -> None:
    """Calling upsert twice must update in place — no duplicate rows."""
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)
    trade_id = await _insert_closed_trade(
        session, user_id=user_id, instrument_id=instrument_id
    )

    repo = PnlRepository(session)
    await repo.upsert(_build_pnl_result(trade_id, user_id, gross_pnl="1000.0000", net_pnl="950.0000"))
    await session.flush()

    # Second upsert with different values
    await repo.upsert(_build_pnl_result(trade_id, user_id, gross_pnl="1200.0000", net_pnl="1150.0000"))
    await session.flush()

    row_count = await session.execute(
        text("SELECT COUNT(*) FROM trade_pnl WHERE trade_id = :tid"), {"tid": str(trade_id)}
    )
    assert row_count.scalar_one() == 1

    # Values are updated to the second upsert
    row = await repo.get_for_trade(trade_id)
    assert row is not None
    assert row.gross_pnl == Decimal("1200.0000")


async def test_get_for_trade_returns_none_when_not_found(session: AsyncSession) -> None:
    repo = PnlRepository(session)
    result = await repo.get_for_trade(uuid.uuid4())
    assert result is None


async def test_update_r_multiple(session: AsyncSession) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)
    trade_id = await _insert_closed_trade(
        session, user_id=user_id, instrument_id=instrument_id
    )

    repo = PnlRepository(session)
    await repo.upsert(_build_pnl_result(trade_id, user_id, r_multiple=None))
    await session.flush()

    await repo.update_r_multiple(trade_id, Decimal("3.500000"))
    await session.flush()

    row = await repo.get_for_trade(trade_id)
    assert row is not None
    assert row.r_multiple == Decimal("3.500000")


async def test_update_r_multiple_to_none_clears_it(session: AsyncSession) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)
    trade_id = await _insert_closed_trade(
        session, user_id=user_id, instrument_id=instrument_id
    )

    repo = PnlRepository(session)
    await repo.upsert(_build_pnl_result(trade_id, user_id, r_multiple="2.000000"))
    await session.flush()

    await repo.update_r_multiple(trade_id, None)
    await session.flush()

    row = await repo.get_for_trade(trade_id)
    assert row is not None
    assert row.r_multiple is None


# ---------------------------------------------------------------------------
# ChargeScheduleRepository
# ---------------------------------------------------------------------------


async def test_charge_schedule_returns_none_for_unknown_combination(
    session: AsyncSession,
) -> None:
    repo = ChargeScheduleRepository(session)
    result = await repo.get_for_date(
        broker="UNKNOWN_BROKER",
        trade_type="MIS",
        exchange_segment="NSE_EQ",
        trade_date=date(2026, 1, 15),
    )
    assert result is None


async def test_charge_schedule_returns_seeded_zerodha_mis_row(session: AsyncSession) -> None:
    repo = ChargeScheduleRepository(session)
    row = await repo.get_for_date(
        broker="ZERODHA",
        trade_type="MIS",
        exchange_segment="NSE_EQ",
        trade_date=date(2026, 1, 15),
    )

    assert row is not None
    assert row.broker == "ZERODHA"
    assert row.trade_type == "MIS"
    assert row.exchange_segment == "NSE_EQ"
    assert row.gst_rate == Decimal("0.18")
    assert row.stt_buy_rate >= Decimal("0")
    assert row.stt_sell_rate >= Decimal("0")


async def test_charge_schedule_effective_date_selects_latest_before_trade_date(
    session: AsyncSession,
) -> None:
    """Two seeded rows exist for Zerodha NSE_EQ: 2023-01-01 and 2024-10-01.

    A trade on 2024-09-30 must get the 2023-01-01 row (the newest one still ≤ trade_date).
    A trade on 2024-10-01 must get the 2024-10-01 row.
    """
    repo = ChargeScheduleRepository(session)

    before = await repo.get_for_date(
        broker="ZERODHA",
        trade_type="MIS",
        exchange_segment="NSE_EQ",
        trade_date=date(2024, 9, 30),
    )
    after = await repo.get_for_date(
        broker="ZERODHA",
        trade_type="MIS",
        exchange_segment="NSE_EQ",
        trade_date=date(2024, 10, 1),
    )

    assert before is not None
    assert after is not None
    # The 2024-10-01 row is the post-Budget row; effective dates must differ
    assert before.effective_from < after.effective_from
    assert after.effective_from == date(2024, 10, 1)
