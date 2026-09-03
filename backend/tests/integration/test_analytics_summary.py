"""Integration tests for GET /v1/analytics/summary → risk_adjusted serialization.

Closes QA-12.1-D1: verifies Sharpe and Sortino fields added in Step 12.1 are
correctly serialized in the HTTP response at the API boundary.

Requires the full Docker Compose stack (PostgreSQL at DATABASE_URL).

Data is committed before each test (not rolled back) so the app's own DB session
sees it. Cleanup deletes the seeded rows in FK order after each test.

Scenarios:
  TC-RA-001: 30 trades (20 wins +2R, 5 losses -1R, 5 losses -2R) →
             risk_adjusted present; sharpe_ratio and sortino_ratio non-null;
             n_per_year = 252; r_coverage_count = 30.
  TC-RA-002: 5 trades (3 wins, 2 losses) → insufficient_sample = True;
             sharpe_ratio and sortino_ratio are null; r_coverage_count = 5.
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
# Session factory — module-scoped to reuse the connection pool
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
# Seed helpers
# ---------------------------------------------------------------------------


async def _insert_user(session: AsyncSession) -> uuid.UUID:
    uid = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO users (id, email, password_hash, is_email_verified) "
            "VALUES (:id, :email, :ph, true)"
        ),
        {"id": str(uid), "email": f"ra-test-{uid}@example.com", "ph": "$argon2id$placeholder"},
    )
    return uid


async def _insert_trading_account(session: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    account_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO trading_accounts "
            "(id, user_id, broker, display_name, account_type, base_currency, status) "
            "VALUES (:id, :uid, 'ZERODHA', 'RA Test Account', 'INDIVIDUAL', 'INR', 'ACTIVE')"
        ),
        {"id": str(account_id), "uid": str(user_id)},
    )
    return account_id


async def _insert_instrument(session: AsyncSession) -> uuid.UUID:
    iid = uuid.uuid4()
    sym = f"RA{str(iid).replace('-', '')[:8].upper()}"
    await session.execute(
        text(
            "INSERT INTO instruments (id, symbol, exchange_segment, instrument_type, name) "
            "VALUES (:id, :sym, 'NSE_EQ', 'EQ', :name)"
        ),
        {"id": str(iid), "sym": sym, "name": sym},
    )
    return iid


async def _insert_closed_trade(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    instrument_id: uuid.UUID,
    trade_date: date,
) -> uuid.UUID:
    tid = uuid.uuid4()
    ts = datetime(2025, 1, 1, 9, 30, tzinfo=UTC)
    await session.execute(
        text(
            "INSERT INTO trades "
            "(id, user_id, account_id, instrument_id, trade_type, direction, status, "
            " trade_date, first_fill_at, total_entry_quantity, total_exit_quantity, "
            " net_position, average_entry, average_exit) "
            "VALUES (:id, :uid, :aid, :iid, 'MIS', 'LONG', 'CLOSED', "
            " :td, :ts, 100, 100, 0, 250.0000, 260.0000)"
        ),
        {
            "id": str(tid),
            "uid": str(user_id),
            "aid": str(account_id),
            "iid": str(instrument_id),
            "td": trade_date,
            "ts": ts,
        },
    )
    return tid


def _pnl_row(
    trade_id: uuid.UUID,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    *,
    net_pnl: Decimal,
    r_multiple: Decimal,
) -> PnlResult:
    # gross_pnl = net_pnl + total_charges (net is after charges are deducted)
    return PnlResult(
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
        total_charges=Decimal("50"),  # sum of 7 components above
        broker="ZERODHA",
        charge_schedule_version="2024-10-01",
        engine_version=PNL_ENGINE_VERSION,
    )


async def _seed(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    instrument_id: uuid.UUID,
    trades: list[tuple[Decimal, Decimal]],
) -> None:
    """Insert one closed trade + trade_pnl row per (net_pnl, r_multiple) pair."""
    repo = PnlRepository(session)
    base = date(2025, 1, 1)
    for i, (net_pnl, r_multiple) in enumerate(trades):
        trade_id = await _insert_closed_trade(
            session,
            user_id=user_id,
            account_id=account_id,
            instrument_id=instrument_id,
            trade_date=base + timedelta(days=i),
        )
        await repo.upsert(
            _pnl_row(trade_id, user_id, account_id, net_pnl=net_pnl, r_multiple=r_multiple)
        )
    await session.flush()


# ---------------------------------------------------------------------------
# Test scenarios
# ---------------------------------------------------------------------------

# TC-RA-001: 20 wins +2R, 5 losses -1R, 5 losses -2R.
# Mixed loss values → downside_dev > 0 → sortino_ratio is not None.
_TRADES_30: list[tuple[Decimal, Decimal]] = (
    [(Decimal("950"), Decimal("2"))] * 20
    + [(Decimal("-1050"), Decimal("-1"))] * 5
    + [(Decimal("-2050"), Decimal("-2"))] * 5
)

# TC-RA-002: 3 wins + 2 losses (total = 5, below _MIN_SAMPLE = 30).
_TRADES_5: list[tuple[Decimal, Decimal]] = [(Decimal("950"), Decimal("2"))] * 3 + [
    (Decimal("-1050"), Decimal("-1"))
] * 2


# ---------------------------------------------------------------------------
# Fixtures: committed data with teardown cleanup
# ---------------------------------------------------------------------------


async def _create_and_commit(
    session_factory: async_sessionmaker[AsyncSession],
    trades: list[tuple[Decimal, Decimal]],
) -> uuid.UUID:
    async with session_factory() as session:
        async with session.begin():
            user_id = await _insert_user(session)
            account_id = await _insert_trading_account(session, user_id)
            instrument_id = await _insert_instrument(session)
            await _seed(
                session,
                user_id=user_id,
                account_id=account_id,
                instrument_id=instrument_id,
                trades=trades,
            )
    return user_id


async def _cleanup(session_factory: async_sessionmaker[AsyncSession], user_id: uuid.UUID) -> None:
    async with session_factory() as session:
        async with session.begin():
            uid = str(user_id)
            # Delete in FK dependency order: trade_pnl → trades → trading_accounts → users
            await session.execute(text("DELETE FROM trade_pnl WHERE user_id = :uid"), {"uid": uid})
            await session.execute(text("DELETE FROM trades WHERE user_id = :uid"), {"uid": uid})
            await session.execute(
                text("DELETE FROM trading_accounts WHERE user_id = :uid"), {"uid": uid}
            )
            await session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": uid})


@pytest.fixture
async def user_30_trades(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[uuid.UUID, None]:
    user_id = await _create_and_commit(session_factory, _TRADES_30)
    yield user_id
    await _cleanup(session_factory, user_id)


@pytest.fixture
async def user_5_trades(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[uuid.UUID, None]:
    user_id = await _create_and_commit(session_factory, _TRADES_5)
    yield user_id
    await _cleanup(session_factory, user_id)


# ---------------------------------------------------------------------------
# TC-RA-001: happy path — 30 trades with r_multiples
# ---------------------------------------------------------------------------


async def test_tc_ra_001_risk_adjusted_present_with_sufficient_sample(
    user_30_trades: uuid.UUID,
) -> None:
    """TC-RA-001: 30 trades → risk_adjusted serialized; ratios non-null; n_per_year=252."""
    app.dependency_overrides[get_current_user_id] = lambda: user_30_trades
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/summary")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()

    assert "risk_adjusted" in body
    ra = body["risk_adjusted"]
    sharpe = ra["sharpe"]
    sortino = ra["sortino"]

    # --- Shape: all fields present ---
    for key in (
        "sharpe_ratio",
        "mean_r",
        "std_r",
        "n_per_year",
        "r_coverage_count",
        "insufficient_sample",
    ):
        assert key in sharpe, f"sharpe missing field: {key}"
    for key in (
        "sortino_ratio",
        "mean_r",
        "downside_dev",
        "n_per_year",
        "r_coverage_count",
        "insufficient_sample",
        "no_downside_trades",
    ):
        assert key in sortino, f"sortino missing field: {key}"

    # --- Sharpe: sufficient sample, non-null ratio ---
    assert sharpe["insufficient_sample"] is False
    assert sharpe["sharpe_ratio"] is not None
    assert sharpe["n_per_year"] == 252
    assert sharpe["r_coverage_count"] == 30
    # Decimal serializes as a string in JSON
    assert isinstance(sharpe["sharpe_ratio"], str)
    assert isinstance(sharpe["n_per_year"], int)
    assert isinstance(sharpe["r_coverage_count"], int)

    # --- Sortino: sufficient sample, non-null ratio ---
    assert sortino["insufficient_sample"] is False
    assert sortino["no_downside_trades"] is False
    assert sortino["sortino_ratio"] is not None
    assert sortino["n_per_year"] == 252
    assert sortino["r_coverage_count"] == 30
    assert isinstance(sortino["sortino_ratio"], str)
    assert isinstance(sortino["n_per_year"], int)
    assert isinstance(sortino["r_coverage_count"], int)


# ---------------------------------------------------------------------------
# TC-RA-002: insufficient sample — fewer than 30 trades
# ---------------------------------------------------------------------------


async def test_tc_ra_002_risk_adjusted_null_ratios_below_threshold(
    user_5_trades: uuid.UUID,
) -> None:
    """TC-RA-002: 5 trades → insufficient_sample=True; ratios are null."""
    app.dependency_overrides[get_current_user_id] = lambda: user_5_trades
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/summary")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()

    ra = body["risk_adjusted"]
    sharpe = ra["sharpe"]
    sortino = ra["sortino"]

    assert sharpe["insufficient_sample"] is True
    assert sharpe["sharpe_ratio"] is None
    assert sharpe["mean_r"] is None
    assert sharpe["r_coverage_count"] == 5

    assert sortino["insufficient_sample"] is True
    assert sortino["sortino_ratio"] is None
    assert sortino["mean_r"] is None
    assert sortino["r_coverage_count"] == 5
