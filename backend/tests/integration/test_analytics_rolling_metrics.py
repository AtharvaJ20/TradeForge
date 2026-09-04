"""Integration tests for Step 12.7 — N-4 (Kelly), N-2 (Time-of-Day), N-1 (Rolling Expectancy).

  GET /v1/analytics/kelly
  GET /v1/analytics/time-of-day
  GET /v1/analytics/rolling-expectancy

Requires the full Docker Compose stack (PostgreSQL at DATABASE_URL).

N-4 Scenarios:
  TC-KELLY-001  30+ trades with r_multiple → kelly_pct and half_kelly_pct non-null
  TC-KELLY-002  fewer than 30 trades → insufficient_sample=True, null fractions

N-2 Scenarios:
  TC-TOD-001    6 trades seeded across 5 different bands — correct bucket counts
  TC-TOD-002    Always returns all 6 canonical buckets (missing bands get zeros)

N-1 Scenarios:
  TC-RE-001     20+ trades → rolling_expectancy data non-empty
  TC-RE-002     fewer than 20 trades → insufficient_sample=True
"""

from __future__ import annotations

import os
import re
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from tradeforge.api.v1.deps import get_current_user_id
from tradeforge.domain.pnl.types import PNL_ENGINE_VERSION, PnlResult
from tradeforge.infrastructure.repositories.pnl_repo import PnlRepository
from tradeforge.main import app

# ---------------------------------------------------------------------------
# Module-scoped DB engine
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set — Docker Compose stack required")
    return re.sub(r"//[^@]+@", "//postgres:postgres@", url)


@pytest.fixture(scope="module")
async def engine(db_url: str) -> AsyncGenerator[AsyncEngine, None]:
    eng = create_async_engine(db_url, echo=False)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="module")
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Seed helpers (replicating the pattern from test_analytics_m6_m10.py)
# ---------------------------------------------------------------------------


async def _insert_user(session: AsyncSession) -> uuid.UUID:
    uid = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO users (id, email, password_hash, is_email_verified) "
            "VALUES (:id, :email, :ph, true)"
        ),
        {"id": str(uid), "email": f"n12-{uid}@example.com", "ph": "$argon2id$placeholder"},
    )
    return uid


async def _insert_trading_account(session: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    aid = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO trading_accounts "
            "(id, user_id, broker, display_name, account_type, base_currency, status) "
            "VALUES (:id, :uid, 'ZERODHA', 'Test', 'INDIVIDUAL', 'INR', 'ACTIVE')"
        ),
        {"id": str(aid), "uid": str(user_id)},
    )
    return aid


async def _insert_instrument(session: AsyncSession) -> uuid.UUID:
    iid = uuid.uuid4()
    sym = f"N7{str(iid).replace('-', '')[:8].upper()}"
    await session.execute(
        text(
            "INSERT INTO instruments (id, symbol, exchange_segment, instrument_type, name) "
            "VALUES (:id, :sym, 'NSE_EQ', 'EQ', :sym)"
        ),
        {"id": str(iid), "sym": sym},
    )
    return iid


async def _insert_trade(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    instrument_id: uuid.UUID,
    trade_date: date,
    first_fill_at: datetime,
) -> uuid.UUID:
    tid = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO trades "
            "(id, user_id, account_id, instrument_id, trade_type, direction, status, "
            " trade_date, first_fill_at, last_fill_at, "
            " total_entry_quantity, total_exit_quantity, net_position, "
            " average_entry, average_exit) "
            "VALUES (:id, :uid, :aid, :iid, 'MIS', 'LONG', 'CLOSED', "
            " :td, :ffa, :ffa, 100, 100, 0, 250.0000, 260.0000)"
        ),
        {
            "id": str(tid),
            "uid": str(user_id),
            "aid": str(account_id),
            "iid": str(instrument_id),
            "td": trade_date,
            "ffa": first_fill_at,
        },
    )
    return tid


async def _insert_pnl(
    session: AsyncSession,
    *,
    trade_id: uuid.UUID,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    net_pnl: Decimal,
    r_multiple: Decimal | None = None,
) -> None:
    repo = PnlRepository(session)
    await repo.upsert(
        PnlResult(
            trade_id=trade_id,
            user_id=user_id,
            account_id=account_id,
            gross_pnl=net_pnl + Decimal("50"),
            net_pnl=net_pnl,
            r_multiple=r_multiple,
            brokerage=Decimal("20"),
            stt=Decimal("10"),
            exchange_charges=Decimal("8"),
            sebi_charges=Decimal("2"),
            stamp_duty=Decimal("5"),
            gst=Decimal("4"),
            ipft=Decimal("1"),
            total_charges=Decimal("50"),
            broker="ZERODHA",
            charge_schedule_version="2024-10-01",
            engine_version=PNL_ENGINE_VERSION,
        )
    )


async def _cleanup(session_factory: async_sessionmaker[AsyncSession], user_id: uuid.UUID) -> None:
    async with session_factory() as session:
        async with session.begin():
            uid = str(user_id)
            await session.execute(text("SET LOCAL session_replication_role = replica"))
            await session.execute(
                text("DELETE FROM execution_fills WHERE user_id = :uid"), {"uid": uid}
            )
            await session.execute(text("DELETE FROM trade_pnl WHERE user_id = :uid"), {"uid": uid})
            await session.execute(text("DELETE FROM trades WHERE user_id = :uid"), {"uid": uid})
            await session.execute(
                text("DELETE FROM trading_accounts WHERE user_id = :uid"), {"uid": uid}
            )
            await session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": uid})


# ---------------------------------------------------------------------------
# IST-to-UTC helper (IST = UTC+5:30)
# ---------------------------------------------------------------------------

_IST_OFFSET = 5 * 3600 + 30 * 60  # seconds


def _ist_to_utc(d: date, h: int, m: int, s: int = 0) -> datetime:
    """Create a UTC datetime from IST time-of-day and a local date."""
    naive_ist = datetime(d.year, d.month, d.day, h, m, s)
    return (naive_ist - timedelta(seconds=_IST_OFFSET)).replace(tzinfo=UTC)


# ---------------------------------------------------------------------------
# N-4: Kelly Fraction — TC-KELLY-001 / TC-KELLY-002
# ---------------------------------------------------------------------------

_TD = date(2024, 6, 1)
_FFA = datetime(2024, 6, 1, 4, 0, 0, tzinfo=UTC)  # 09:30 IST


@pytest.fixture
async def user_kelly_sufficient(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[uuid.UUID, None]:
    """30 trades: 20 wins at r=+2.0, 10 losses at r=-1.0.

    Expected Kelly:
      expectancy_r = 0.667 × 2.0 - 0.333 × 1.0 = 1.333 - 0.333 = 1.0
      avg_positive_r = 2.0
      kelly_pct = 1.0 / 2.0 = 0.5
    """
    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
            aid = await _insert_trading_account(session, uid)
            iid = await _insert_instrument(session)
            for i in range(20):
                tid = await _insert_trade(
                    session,
                    user_id=uid,
                    account_id=aid,
                    instrument_id=iid,
                    trade_date=date(2024, 6, i + 1),
                    first_fill_at=_FFA,
                )
                await _insert_pnl(
                    session,
                    trade_id=tid,
                    user_id=uid,
                    account_id=aid,
                    net_pnl=Decimal("200"),
                    r_multiple=Decimal("2.0"),
                )
            for i in range(10):
                tid = await _insert_trade(
                    session,
                    user_id=uid,
                    account_id=aid,
                    instrument_id=iid,
                    trade_date=date(2024, 7, i + 1),
                    first_fill_at=_FFA,
                )
                await _insert_pnl(
                    session,
                    trade_id=tid,
                    user_id=uid,
                    account_id=aid,
                    net_pnl=Decimal("-100"),
                    r_multiple=Decimal("-1.0"),
                )

    yield uid
    await _cleanup(session_factory, uid)


@pytest.fixture
async def user_kelly_insufficient(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[uuid.UUID, None]:
    """15 trades — below the 30-trade minimum for Kelly."""
    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
            aid = await _insert_trading_account(session, uid)
            iid = await _insert_instrument(session)
            for i in range(15):
                tid = await _insert_trade(
                    session,
                    user_id=uid,
                    account_id=aid,
                    instrument_id=iid,
                    trade_date=date(2024, 6, i + 1),
                    first_fill_at=_FFA,
                )
                await _insert_pnl(
                    session,
                    trade_id=tid,
                    user_id=uid,
                    account_id=aid,
                    net_pnl=Decimal("100"),
                    r_multiple=Decimal("1.0"),
                )

    yield uid
    await _cleanup(session_factory, uid)


@pytest.mark.asyncio
async def test_kelly_sufficient_sample(
    user_kelly_sufficient: uuid.UUID,
) -> None:
    """TC-KELLY-001: 30 trades → non-null kelly_pct and half_kelly_pct."""
    uid = user_kelly_sufficient
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/v1/analytics/kelly")
        assert resp.status_code == 200
        data = resp.json()
        assert data["insufficient_sample"] is False
        assert data["trades_with_r"] == 30
        assert data["kelly_pct"] is not None
        assert data["half_kelly_pct"] is not None
        # kelly_pct should be approximately 0.5 (expectancy_r=1.0, avg_positive_r=2.0)
        kelly = Decimal(str(data["kelly_pct"]))
        assert abs(kelly - Decimal("0.5")) < Decimal("0.01")
        # half_kelly = kelly / 2
        half = Decimal(str(data["half_kelly_pct"]))
        assert abs(half - kelly / Decimal("2")) < Decimal("0.001")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)


@pytest.mark.asyncio
async def test_kelly_insufficient_sample(
    user_kelly_insufficient: uuid.UUID,
) -> None:
    """TC-KELLY-002: 15 trades → insufficient_sample=True, null fractions."""
    uid = user_kelly_insufficient
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/v1/analytics/kelly")
        assert resp.status_code == 200
        data = resp.json()
        assert data["insufficient_sample"] is True
        assert data["kelly_pct"] is None
        assert data["half_kelly_pct"] is None
        assert data["trades_with_r"] == 15
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)


# ---------------------------------------------------------------------------
# N-2: Time-of-Day — TC-TOD-001 / TC-TOD-002
# ---------------------------------------------------------------------------


@pytest.fixture
async def user_time_of_day(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[uuid.UUID, None]:
    """5 trades seeded at distinct IST session times, 1 trade with NULL first_fill_at fallback.

    Seed times (IST):
      09:22 → pre_open
      09:45 → open_volatility
      10:30 → mid_morning
      12:00 → lunch
      15:30 → close  (>= 15:00)
    The trade at 09:22 IST is a win (net_pnl > 0); rest are losses.
    """
    d = date(2024, 6, 10)
    seed_times_ist = [
        (9, 22),  # pre_open
        (9, 45),  # open_volatility
        (10, 30),  # mid_morning
        (12, 0),  # lunch
        (15, 30),  # close
    ]
    pnls = [
        Decimal("500"),  # win — pre_open
        Decimal("-100"),  # loss — open_volatility
        Decimal("-200"),  # loss — mid_morning
        Decimal("-150"),  # loss — lunch
        Decimal("-300"),  # loss — close
    ]

    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
            aid = await _insert_trading_account(session, uid)
            iid = await _insert_instrument(session)
            for (h, m), pnl in zip(seed_times_ist, pnls, strict=True):
                ffa = _ist_to_utc(d, h, m)
                tid = await _insert_trade(
                    session,
                    user_id=uid,
                    account_id=aid,
                    instrument_id=iid,
                    trade_date=d,
                    first_fill_at=ffa,
                )
                await _insert_pnl(
                    session,
                    trade_id=tid,
                    user_id=uid,
                    account_id=aid,
                    net_pnl=pnl,
                )

    yield uid
    await _cleanup(session_factory, uid)


@pytest.mark.asyncio
async def test_time_of_day_bucket_counts(
    user_time_of_day: uuid.UUID,
) -> None:
    """TC-TOD-001: 5 trades land in distinct bands with correct trade counts."""
    uid = user_time_of_day
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/v1/analytics/time-of-day")
        assert resp.status_code == 200
        data = resp.json()
        buckets = {b["bucket"]: b for b in data["buckets"]}

        assert buckets["pre_open"]["trade_count"] == 1
        assert buckets["pre_open"]["win_count"] == 1

        assert buckets["open_volatility"]["trade_count"] == 1
        assert buckets["open_volatility"]["win_count"] == 0

        assert buckets["mid_morning"]["trade_count"] == 1
        assert buckets["lunch"]["trade_count"] == 1
        assert buckets["close"]["trade_count"] == 1
        # afternoon gets zero (no trades seeded there)
        assert buckets["afternoon"]["trade_count"] == 0
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)


@pytest.mark.asyncio
async def test_time_of_day_always_six_buckets(
    user_time_of_day: uuid.UUID,
) -> None:
    """TC-TOD-002: response always has exactly 6 buckets in canonical session order."""
    uid = user_time_of_day
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/v1/analytics/time-of-day")
        data = resp.json()
        buckets = data["buckets"]
        assert len(buckets) == 6
        expected_order = [
            "pre_open",
            "open_volatility",
            "mid_morning",
            "lunch",
            "afternoon",
            "close",
        ]
        assert [b["bucket"] for b in buckets] == expected_order
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)


# ---------------------------------------------------------------------------
# N-1: Rolling Expectancy — TC-RE-001 / TC-RE-002
# ---------------------------------------------------------------------------


@pytest.fixture
async def user_rolling_sufficient(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[uuid.UUID, None]:
    """25 trades: 15 wins at +100, 10 losses at -50, each with r_multiple."""
    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
            aid = await _insert_trading_account(session, uid)
            iid = await _insert_instrument(session)
            for i in range(25):
                d = date(2024, 5, i + 1)
                ffa = datetime(2024, 5, i + 1, 4, 0, 0, tzinfo=UTC)
                is_win = i < 15
                tid = await _insert_trade(
                    session,
                    user_id=uid,
                    account_id=aid,
                    instrument_id=iid,
                    trade_date=d,
                    first_fill_at=ffa,
                )
                await _insert_pnl(
                    session,
                    trade_id=tid,
                    user_id=uid,
                    account_id=aid,
                    net_pnl=Decimal("100") if is_win else Decimal("-50"),
                    r_multiple=Decimal("2.0") if is_win else Decimal("-1.0"),
                )

    yield uid
    await _cleanup(session_factory, uid)


@pytest.fixture
async def user_rolling_insufficient(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[uuid.UUID, None]:
    """10 trades — below the 20-trade rolling expectancy window."""
    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
            aid = await _insert_trading_account(session, uid)
            iid = await _insert_instrument(session)
            for i in range(10):
                d = date(2024, 5, i + 1)
                ffa = datetime(2024, 5, i + 1, 4, 0, 0, tzinfo=UTC)
                tid = await _insert_trade(
                    session,
                    user_id=uid,
                    account_id=aid,
                    instrument_id=iid,
                    trade_date=d,
                    first_fill_at=ffa,
                )
                await _insert_pnl(
                    session,
                    trade_id=tid,
                    user_id=uid,
                    account_id=aid,
                    net_pnl=Decimal("100"),
                    r_multiple=Decimal("1.0"),
                )

    yield uid
    await _cleanup(session_factory, uid)


@pytest.mark.asyncio
async def test_rolling_expectancy_sufficient_sample(
    user_rolling_sufficient: uuid.UUID,
) -> None:
    """TC-RE-001: 25 trades → 6 rolling data points (25 - 20 + 1), non-empty data."""
    uid = user_rolling_sufficient
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/v1/analytics/rolling-expectancy")
        assert resp.status_code == 200
        data = resp.json()
        assert data["insufficient_sample"] is False
        assert data["window"] == 20
        assert len(data["data"]) == 6  # 25 - 20 + 1
        # Indices should be sequential starting at 20
        indices = [pt["trade_index"] for pt in data["data"]]
        assert indices == list(range(20, 26))
        # rolling_exp_inr should be a number (not null)
        for pt in data["data"]:
            assert pt["rolling_exp_inr"] is not None
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)


@pytest.mark.asyncio
async def test_rolling_expectancy_insufficient_sample(
    user_rolling_insufficient: uuid.UUID,
) -> None:
    """TC-RE-002: 10 trades → insufficient_sample=True, empty data array."""
    uid = user_rolling_insufficient
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/v1/analytics/rolling-expectancy")
        assert resp.status_code == 200
        data = resp.json()
        assert data["insufficient_sample"] is True
        assert data["data"] == []
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
