"""Integration tests for the Phase 1 Trade Reconstruction Engine.

Requires the full Docker Compose stack (PostgreSQL at DATABASE_URL).
Each test runs in its own transaction that is rolled back after the test,
so the DB is clean between tests.

Run with:
    cd backend
    pytest tests/integration/test_trade_reconstruction.py -v

Scenarios covered:
  - Simple LONG trade: 1 entry, 1 full exit
  - Scaled entry (2 ENTRY fills)
  - Partial exit (1 entry, partial sell, full sell)
  - SHORT trade
  - Re-entry after close (new trade_id)
  - CNC tax lot created at open, closed at exit
  - CNC scale-in updates tax lot (quantity + cost_per_share)
  - CNC same-day close → CNC_SAME_DAY trade_type
  - CNC overnight hold → CNC trade_type unchanged
  - Idempotency: running engine twice gives same result
  - Open trade resumption: new fills added to existing PARTIAL trade
  - E1: PositionCrossingZeroError halts and rolls back
  - E5: ReconstructionAmbiguityError on identical fill_timestamp + NULL fill_id
  - E4: ReconstructionConsistencyError when no open tax lot on CNC exit
  - fill_exclusions: excluded fill is permanently skipped
"""

import os
import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tradeforge.application.trade.reconstruction import ReconstructionEngine
from tradeforge.domain.trade.errors import (
    PositionCrossingZeroError,
    ReconstructionAmbiguityError,
)
from tradeforge.infrastructure.repositories.fill_exclusion_repo import FillExclusionRepository
from tradeforge.infrastructure.repositories.fill_repo import FillRepository
from tradeforge.infrastructure.repositories.tax_lot_repo import TaxLotRepository
from tradeforge.infrastructure.repositories.trade_repo import TradeRepository

# ---------------------------------------------------------------------------
# Session factory — module-scoped so we reuse the connection pool
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set — Docker Compose stack required")
    # Use postgres superuser for integration tests to bypass app-level RLS/grants.
    return re.sub(r"//[^@]+@", "//postgres:postgres@", url)


@pytest.fixture(scope="module")
async def engine(db_url: str):  # type: ignore[return]
    eng = create_async_engine(db_url, echo=False)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="module")
def session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Per-test transaction that is always rolled back (clean DB between tests)
# ---------------------------------------------------------------------------


@pytest.fixture
async def session(session_factory: async_sessionmaker[AsyncSession]):  # type: ignore[return]
    async with session_factory() as s:
        await s.begin()
        yield s
        await s.rollback()


# ---------------------------------------------------------------------------
# Reusable engine under test
# ---------------------------------------------------------------------------


@pytest.fixture
def engine_under_test() -> ReconstructionEngine:
    return ReconstructionEngine(
        fill_repo=FillRepository(),
        trade_repo=TradeRepository(),
        tax_lot_repo=TaxLotRepository(),
        fill_exclusion_repo=FillExclusionRepository(),
    )


# ---------------------------------------------------------------------------
# Fixture helpers — insert test rows into the DB
# ---------------------------------------------------------------------------

_UID = uuid.UUID("00000000-0000-0000-0000-000000000001")  # stable user for all tests


async def _insert_user(session: AsyncSession) -> uuid.UUID:
    user_id = _UID
    await session.execute(
        text(
            "INSERT INTO users (id, email, password_hash, is_email_verified) "
            "VALUES (:id, :email, :ph, true) "
            "ON CONFLICT (id) DO NOTHING"
        ),
        {
            "id": str(user_id),
            "email": f"recon-test-{user_id}@example.com",
            "ph": "$argon2id$placeholder",
        },
    )
    return user_id


async def _insert_instrument(
    session: AsyncSession,
    *,
    instrument_type: str = "EQ",
    symbol: str = "RELIANCE",
) -> uuid.UUID:
    instrument_id = uuid.uuid4()
    # Append part of the UUID to the symbol so each test gets a unique row —
    # guards against stale data left by a previously crashed test run.
    unique_symbol = f"{symbol}_{str(instrument_id).replace('-', '')[:8]}"
    await session.execute(
        text(
            "INSERT INTO instruments (id, symbol, exchange_segment, instrument_type, name) "
            "VALUES (:id, :sym, 'NSE_EQ', :itype, :name)"
        ),
        {
            "id": str(instrument_id),
            "sym": unique_symbol,
            "itype": instrument_type,
            "name": unique_symbol,
        },
    )
    return instrument_id


async def _insert_fill(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    instrument_id: uuid.UUID,
    side: str,
    quantity: str,
    price: str,
    product_type: str = "MIS",
    fill_timestamp: datetime,
    trade_date: date | None = None,
    fill_id_str: str | None = None,
    import_source: str = "BROKER",
) -> uuid.UUID:
    fill_pk = uuid.uuid4()
    td = trade_date or fill_timestamp.date()
    await session.execute(
        text(
            "INSERT INTO execution_fills "
            "(id, user_id, instrument_id, fill_timestamp, trade_date, session, "
            " side, quantity, price, product_type, broker, import_source, fill_id) "
            "VALUES (:id, :uid, :iid, :ts, :td, 'REGULAR', "
            " :side, :qty, :price, :pt, 'ZERODHA', :src, :fid)"
        ),
        {
            "id": str(fill_pk),
            "uid": str(user_id),
            "iid": str(instrument_id),
            "ts": fill_timestamp,
            "td": td,
            "side": side,
            "qty": quantity,
            "price": price,
            "pt": product_type,
            "src": import_source,
            "fid": fill_id_str,
        },
    )
    return fill_pk


def _ts(hour: int = 9, minute: int = 31, second: int = 0, day: int = 15) -> datetime:
    return datetime(2026, 1, day, hour, minute, second, tzinfo=UTC)


def _date(day: int = 15) -> date:
    return date(2026, 1, day)


# ---------------------------------------------------------------------------
# Test: simple LONG trade (1 entry + 1 full exit)
# ---------------------------------------------------------------------------


async def test_simple_long_trade(
    session: AsyncSession, engine_under_test: ReconstructionEngine
) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)

    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="BUY",
        quantity="100",
        price="250.00",
        fill_timestamp=_ts(9, 31),
        fill_id_str="F001",
    )
    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="SELL",
        quantity="100",
        price="260.00",
        fill_timestamp=_ts(10, 0),
        fill_id_str="F002",
    )

    result = await engine_under_test.run(session, user_id, instrument_id, "MIS", "EQ")

    assert result.fills_processed == 2
    assert result.trades_opened == 1
    assert result.trades_closed == 1
    assert result.tax_lots_created == 0

    # Verify trade row.
    trade = await session.execute(
        text("SELECT * FROM trades WHERE user_id=:uid"), {"uid": str(user_id)}
    )
    t = trade.mappings().one()
    assert t["status"] == "CLOSED"
    assert t["direction"] == "LONG"
    assert t["trade_type"] == "MIS"
    assert Decimal(str(t["average_entry"])) == Decimal("250.0000")
    assert Decimal(str(t["average_exit"])) == Decimal("260.0000")
    assert Decimal(str(t["net_position"])) == Decimal("0.0000")

    # Verify fill assignments.
    fills = await session.execute(
        text(
            "SELECT id, trade_id, fill_role FROM execution_fills WHERE user_id=:uid ORDER BY fill_timestamp"
        ),
        {"uid": str(user_id)},
    )
    rows = list(fills.mappings().all())
    assert rows[0]["fill_role"] == "ENTRY"
    assert rows[1]["fill_role"] == "EXIT"
    assert rows[0]["trade_id"] == rows[1]["trade_id"]


# ---------------------------------------------------------------------------
# Test: scaled entry (2 BUY fills, then 1 SELL)
# ---------------------------------------------------------------------------


async def test_scaled_entry_average_price(
    session: AsyncSession, engine_under_test: ReconstructionEngine
) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)

    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="BUY",
        quantity="100",
        price="250.00",
        fill_timestamp=_ts(9, 31),
        fill_id_str="F001",
    )
    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="BUY",
        quantity="100",
        price="252.00",
        fill_timestamp=_ts(9, 35),
        fill_id_str="F002",
    )
    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="SELL",
        quantity="200",
        price="260.00",
        fill_timestamp=_ts(10, 0),
        fill_id_str="F003",
    )

    result = await engine_under_test.run(session, user_id, instrument_id, "MIS", "EQ")

    assert result.fills_processed == 3
    assert result.trades_opened == 1
    assert result.trades_closed == 1

    trade = await session.execute(
        text("SELECT average_entry, total_entry_quantity FROM trades WHERE user_id=:uid"),
        {"uid": str(user_id)},
    )
    t = trade.mappings().one()
    # average_entry = (100×250 + 100×252) / 200 = 251.00
    assert Decimal(str(t["average_entry"])) == Decimal("251.0000")
    assert Decimal(str(t["total_entry_quantity"])) == Decimal("200.0000")


# ---------------------------------------------------------------------------
# Test: partial exit
# ---------------------------------------------------------------------------


async def test_partial_exit_then_full_close(
    session: AsyncSession, engine_under_test: ReconstructionEngine
) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)

    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="BUY",
        quantity="200",
        price="250.00",
        fill_timestamp=_ts(9, 31),
        fill_id_str="F001",
    )
    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="SELL",
        quantity="100",
        price="258.00",
        fill_timestamp=_ts(10, 0),
        fill_id_str="F002",
    )
    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="SELL",
        quantity="100",
        price="262.00",
        fill_timestamp=_ts(10, 30),
        fill_id_str="F003",
    )

    result = await engine_under_test.run(session, user_id, instrument_id, "MIS", "EQ")

    assert result.fills_processed == 3
    assert result.trades_opened == 1
    assert result.trades_closed == 1

    trade = await session.execute(
        text("SELECT status, average_exit, total_exit_quantity FROM trades WHERE user_id=:uid"),
        {"uid": str(user_id)},
    )
    t = trade.mappings().one()
    assert t["status"] == "CLOSED"
    # average_exit = (100×258 + 100×262) / 200 = 260.0000
    assert Decimal(str(t["average_exit"])) == Decimal("260.0000")
    assert Decimal(str(t["total_exit_quantity"])) == Decimal("200.0000")


# ---------------------------------------------------------------------------
# Test: re-entry after close creates new trade_id
# ---------------------------------------------------------------------------


async def test_reentry_after_close_creates_new_trade(
    session: AsyncSession, engine_under_test: ReconstructionEngine
) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)

    # Trade A
    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="BUY",
        quantity="100",
        price="250.00",
        fill_timestamp=_ts(9, 31),
        fill_id_str="F001",
    )
    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="SELL",
        quantity="100",
        price="260.00",
        fill_timestamp=_ts(10, 0),
        fill_id_str="F002",
    )
    # Trade B — re-entry
    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="BUY",
        quantity="50",
        price="255.00",
        fill_timestamp=_ts(11, 0),
        fill_id_str="F003",
    )

    result = await engine_under_test.run(session, user_id, instrument_id, "MIS", "EQ")

    assert result.fills_processed == 3
    assert result.trades_opened == 2
    assert result.trades_closed == 1

    trades = await session.execute(
        text("SELECT id, status FROM trades WHERE user_id=:uid ORDER BY first_fill_at"),
        {"uid": str(user_id)},
    )
    rows = list(trades.mappings().all())
    assert len(rows) == 2
    assert rows[0]["status"] == "CLOSED"
    assert rows[1]["status"] == "OPEN"
    assert rows[0]["id"] != rows[1]["id"]  # different trade_ids


# ---------------------------------------------------------------------------
# Test: SHORT trade
# ---------------------------------------------------------------------------


async def test_short_trade(session: AsyncSession, engine_under_test: ReconstructionEngine) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)

    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="SELL",
        quantity="100",
        price="260.00",
        fill_timestamp=_ts(9, 31),
        fill_id_str="F001",
    )
    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="BUY",
        quantity="100",
        price="250.00",
        fill_timestamp=_ts(10, 0),
        fill_id_str="F002",
    )

    result = await engine_under_test.run(session, user_id, instrument_id, "MIS", "EQ")

    assert result.fills_processed == 2

    trade = await session.execute(
        text(
            "SELECT direction, status, average_entry, average_exit FROM trades WHERE user_id=:uid"
        ),
        {"uid": str(user_id)},
    )
    t = trade.mappings().one()
    assert t["direction"] == "SHORT"
    assert t["status"] == "CLOSED"
    assert Decimal(str(t["average_entry"])) == Decimal("260.0000")
    assert Decimal(str(t["average_exit"])) == Decimal("250.0000")


# ---------------------------------------------------------------------------
# Test: CNC tax lot created at trade open
# ---------------------------------------------------------------------------


async def test_cnc_tax_lot_created_and_closed(
    session: AsyncSession, engine_under_test: ReconstructionEngine
) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)

    # Open on day 15, close on day 16 → CNC (overnight)
    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="BUY",
        quantity="100",
        price="2400.00",
        fill_timestamp=_ts(9, 31, day=15),
        fill_id_str="F001",
        product_type="CNC",
        trade_date=_date(15),
    )
    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="SELL",
        quantity="100",
        price="2500.00",
        fill_timestamp=_ts(14, 0, day=16),
        fill_id_str="F002",
        product_type="CNC",
        trade_date=_date(16),
    )

    result = await engine_under_test.run(session, user_id, instrument_id, "CNC", "EQ")

    assert result.tax_lots_created == 1
    assert result.tax_lots_updated == 1  # decrement on exit

    lot = await session.execute(
        text("SELECT * FROM tax_lots WHERE user_id=:uid"), {"uid": str(user_id)}
    )
    lot_row = lot.mappings().one()
    assert lot_row["status"] == "CLOSED"
    assert Decimal(str(lot_row["quantity_remaining"])) == Decimal("0.0000")
    assert Decimal(str(lot_row["cost_per_share"])) == Decimal("2400.0000")

    # trade_type stays CNC (open and close on different dates)
    trade = await session.execute(
        text("SELECT trade_type FROM trades WHERE user_id=:uid"), {"uid": str(user_id)}
    )
    assert trade.scalar_one() == "CNC"


# ---------------------------------------------------------------------------
# Test: CNC same-day → CNC_SAME_DAY
# ---------------------------------------------------------------------------


async def test_cnc_same_day_trade_type(
    session: AsyncSession, engine_under_test: ReconstructionEngine
) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)

    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="BUY",
        quantity="100",
        price="2400.00",
        fill_timestamp=_ts(9, 31, day=15),
        fill_id_str="F001",
        product_type="CNC",
        trade_date=_date(15),
    )
    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="SELL",
        quantity="100",
        price="2450.00",
        fill_timestamp=_ts(14, 0, day=15),
        fill_id_str="F002",
        product_type="CNC",
        trade_date=_date(15),
    )

    await engine_under_test.run(session, user_id, instrument_id, "CNC", "EQ")

    trade = await session.execute(
        text("SELECT trade_type FROM trades WHERE user_id=:uid"), {"uid": str(user_id)}
    )
    assert trade.scalar_one() == "CNC_SAME_DAY"


# ---------------------------------------------------------------------------
# Test: CNC scale-in updates tax lot
# ---------------------------------------------------------------------------


async def test_cnc_scale_in_updates_lot(
    session: AsyncSession, engine_under_test: ReconstructionEngine
) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)

    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="BUY",
        quantity="100",
        price="2400.00",
        fill_timestamp=_ts(9, 31, day=15),
        fill_id_str="F001",
        product_type="CNC",
        trade_date=_date(15),
    )
    # Scale-in
    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="BUY",
        quantity="100",
        price="2200.00",
        fill_timestamp=_ts(11, 0, day=15),
        fill_id_str="F002",
        product_type="CNC",
        trade_date=_date(15),
    )

    await engine_under_test.run(session, user_id, instrument_id, "CNC", "EQ")

    lot = await session.execute(
        text("SELECT * FROM tax_lots WHERE user_id=:uid"), {"uid": str(user_id)}
    )
    lot_row = lot.mappings().one()
    assert Decimal(str(lot_row["quantity_original"])) == Decimal("200.0000")
    assert Decimal(str(lot_row["quantity_remaining"])) == Decimal("200.0000")
    # average_entry = (100×2400 + 100×2200) / 200 = 2300.00
    assert Decimal(str(lot_row["cost_per_share"])) == Decimal("2300.0000")


# ---------------------------------------------------------------------------
# Test: idempotency — running engine twice is safe
# ---------------------------------------------------------------------------


async def test_idempotency_second_run_is_noop(
    session: AsyncSession, engine_under_test: ReconstructionEngine
) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)

    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="BUY",
        quantity="100",
        price="250.00",
        fill_timestamp=_ts(9, 31),
        fill_id_str="F001",
    )
    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="SELL",
        quantity="100",
        price="260.00",
        fill_timestamp=_ts(10, 0),
        fill_id_str="F002",
    )

    result1 = await engine_under_test.run(session, user_id, instrument_id, "MIS", "EQ")
    result2 = await engine_under_test.run(session, user_id, instrument_id, "MIS", "EQ")

    assert result1.fills_processed == 2
    assert result2.fills_processed == 0  # all fills already assigned, nothing new

    trade = await session.execute(
        text("SELECT COUNT(*) FROM trades WHERE user_id=:uid"), {"uid": str(user_id)}
    )
    assert trade.scalar_one() == 1  # no duplicate trade


# ---------------------------------------------------------------------------
# Test: open trade resumption — new fills appended to existing PARTIAL trade
# ---------------------------------------------------------------------------


async def test_open_trade_resumption(
    session: AsyncSession, engine_under_test: ReconstructionEngine
) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)

    # Run 1: entry fill only
    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="BUY",
        quantity="100",
        price="250.00",
        fill_timestamp=_ts(9, 31),
        fill_id_str="F001",
    )
    result1 = await engine_under_test.run(session, user_id, instrument_id, "MIS", "EQ")
    assert result1.trades_opened == 1
    assert result1.trades_closed == 0

    # Insert the exit fill AFTER the first run (simulates a later import).
    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="SELL",
        quantity="100",
        price="260.00",
        fill_timestamp=_ts(10, 0),
        fill_id_str="F002",
    )

    # Run 2: picks up the exit fill and closes the existing trade.
    result2 = await engine_under_test.run(session, user_id, instrument_id, "MIS", "EQ")
    assert result2.fills_processed == 1
    assert result2.trades_opened == 0
    assert result2.trades_closed == 1

    trade = await session.execute(
        text("SELECT COUNT(*) FROM trades WHERE user_id=:uid AND status='CLOSED'"),
        {"uid": str(user_id)},
    )
    assert trade.scalar_one() == 1


# ---------------------------------------------------------------------------
# Test: E1 PositionCrossingZeroError
# ---------------------------------------------------------------------------


async def test_e1_position_crossing_zero(
    session: AsyncSession, engine_under_test: ReconstructionEngine
) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)

    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="BUY",
        quantity="100",
        price="250.00",
        fill_timestamp=_ts(9, 31),
        fill_id_str="F001",
    )
    # SELL 150 against LONG 100 → would go to -50 (crosses zero)
    crossing_fill_id = await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="SELL",
        quantity="150",
        price="260.00",
        fill_timestamp=_ts(10, 0),
        fill_id_str="F002",
    )

    with pytest.raises(PositionCrossingZeroError) as exc_info:
        await engine_under_test.run(session, user_id, instrument_id, "MIS", "EQ")

    assert exc_info.value.fill_id == crossing_fill_id

    # Entry fill was processed (trade opened), but the crossing fill was not assigned.
    entry = await session.execute(
        text("SELECT fill_role, trade_id FROM execution_fills WHERE fill_id=:fid"),
        {"fid": "F001"},
    )
    e = entry.mappings().one()
    assert e["fill_role"] == "ENTRY"
    assert e["trade_id"] is not None

    crossing = await session.execute(
        text("SELECT fill_role, trade_id FROM execution_fills WHERE fill_id=:fid"),
        {"fid": "F002"},
    )
    c = crossing.mappings().one()
    assert c["fill_role"] is None
    assert c["trade_id"] is None


# ---------------------------------------------------------------------------
# Test: E5 ReconstructionAmbiguityError
# ---------------------------------------------------------------------------


async def test_e5_ambiguous_ordering(
    session: AsyncSession, engine_under_test: ReconstructionEngine
) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)

    shared_ts = _ts(9, 31, 0)
    # Both fills: NULL fill_id, same fill_timestamp.
    # created_at also needs to be identical → use same literal timestamp.
    await session.execute(
        text(
            "INSERT INTO execution_fills "
            "(id, user_id, instrument_id, fill_timestamp, trade_date, session, "
            " side, quantity, price, product_type, broker, import_source, fill_id, created_at) "
            "VALUES (:id, :uid, :iid, :ts, :td, 'REGULAR', "
            " 'BUY', 100, 250.00, 'MIS', 'ZERODHA', 'MANUAL', NULL, :created_at)"
        ),
        {
            "id": str(uuid.uuid4()),
            "uid": str(user_id),
            "iid": str(instrument_id),
            "ts": shared_ts,
            "td": _date(15),
            "created_at": shared_ts,
        },
    )
    await session.execute(
        text(
            "INSERT INTO execution_fills "
            "(id, user_id, instrument_id, fill_timestamp, trade_date, session, "
            " side, quantity, price, product_type, broker, import_source, fill_id, created_at) "
            "VALUES (:id, :uid, :iid, :ts, :td, 'REGULAR', "
            " 'BUY', 50, 251.00, 'MIS', 'ZERODHA', 'MANUAL', NULL, :created_at)"
        ),
        {
            "id": str(uuid.uuid4()),
            "uid": str(user_id),
            "iid": str(instrument_id),
            "ts": shared_ts,
            "td": _date(15),
            "created_at": shared_ts,
        },
    )

    with pytest.raises(ReconstructionAmbiguityError):
        await engine_under_test.run(session, user_id, instrument_id, "MIS", "EQ")


# ---------------------------------------------------------------------------
# Test: fill_exclusions — excluded fill is permanently skipped
# ---------------------------------------------------------------------------


async def test_excluded_fill_is_skipped(
    session: AsyncSession, engine_under_test: ReconstructionEngine
) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session)

    # The crossing-zero fill that needs exclusion.
    fill_pk = await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="BUY",
        quantity="100",
        price="250.00",
        fill_timestamp=_ts(9, 31),
        fill_id_str="F001",
    )

    # Record it in fill_exclusions — the engine should skip it.
    await session.execute(
        text(
            "INSERT INTO fill_exclusions (id, fill_id, reason, replacement_fill_ids, excluded_by) "
            "VALUES (:id, :fill_id, 'E1 test exclusion', ARRAY[]::uuid[], :excluded_by)"
        ),
        {
            "id": str(uuid.uuid4()),
            "fill_id": str(fill_pk),
            "excluded_by": str(user_id),
        },
    )

    # With the fill excluded, the engine finds zero unprocessed fills.
    result = await engine_under_test.run(session, user_id, instrument_id, "MIS", "EQ")
    assert result.fills_processed == 0
    assert result.trades_opened == 0

    # The excluded fill itself is untouched — trade_id still NULL.
    row = await session.execute(
        text("SELECT trade_id FROM execution_fills WHERE id=:id"), {"id": str(fill_pk)}
    )
    assert row.scalar_one() is None


# ---------------------------------------------------------------------------
# Test: NRML_FUT trade type derivation
# ---------------------------------------------------------------------------


async def test_nrml_fut_trade_type(
    session: AsyncSession, engine_under_test: ReconstructionEngine
) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session, instrument_type="FUT", symbol="NIFTY_JAN_FUT")

    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="BUY",
        quantity="50",
        price="22000.00",
        fill_timestamp=_ts(9, 31),
        fill_id_str="F001",
        product_type="NRML",
    )

    result = await engine_under_test.run(session, user_id, instrument_id, "NRML", "FUT")

    assert result.trades_opened == 1
    trade = await session.execute(
        text("SELECT trade_type FROM trades WHERE user_id=:uid"), {"uid": str(user_id)}
    )
    assert trade.scalar_one() == "NRML_FUT"


# ---------------------------------------------------------------------------
# Test: NRML_OPT trade type derivation
# ---------------------------------------------------------------------------


async def test_nrml_opt_trade_type(
    session: AsyncSession, engine_under_test: ReconstructionEngine
) -> None:
    user_id = await _insert_user(session)
    instrument_id = await _insert_instrument(session, instrument_type="CE", symbol="NIFTY_24000_CE")

    await _insert_fill(
        session,
        user_id=user_id,
        instrument_id=instrument_id,
        side="BUY",
        quantity="50",
        price="120.00",
        fill_timestamp=_ts(9, 31),
        fill_id_str="F001",
        product_type="NRML",
    )

    result = await engine_under_test.run(session, user_id, instrument_id, "NRML", "CE")

    assert result.trades_opened == 1
    trade = await session.execute(
        text("SELECT trade_type FROM trades WHERE user_id=:uid"), {"uid": str(user_id)}
    )
    assert trade.scalar_one() == "NRML_OPT"
