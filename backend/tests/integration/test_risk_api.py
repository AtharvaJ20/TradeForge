"""Integration tests for Step 13 — Basic Risk Metrics.

  GET /v1/risk/daily-summary
  GET /v1/risk/summary

Requires the full Docker Compose stack (PostgreSQL at DATABASE_URL).

Test IDs (from STEP-13-EXECUTION-PLAN.md):
  I-13-01  daily-summary 200 with 1 open trade — correct totals
  I-13-02  daily-summary total_at_risk_inr=null when no planned_risk_amount
  I-13-02b daily-summary includes open trades from prior trade_dates (Dhanvantari guard)
  I-13-03  summary 200 with all fields present including current_loss_streak
  I-13-04  summary 401 for unauthenticated request
  I-13-05  daily-summary scopes to account — other account's trade excluded
  I-13-06  PARTIAL trade included at full planned_risk_amount, not pro-rated (G-RISK-01-A/B)
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
# Seed helpers
# ---------------------------------------------------------------------------


async def _insert_user(session: AsyncSession) -> uuid.UUID:
    uid = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO users (id, email, password_hash, is_email_verified) "
            "VALUES (:id, :email, :ph, true)"
        ),
        {"id": str(uid), "email": f"risk13-{uid}@example.com", "ph": "$argon2id$placeholder"},
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
    sym = f"R13{str(iid).replace('-', '')[:8].upper()}"
    await session.execute(
        text(
            "INSERT INTO instruments (id, symbol, exchange_segment, instrument_type, name) "
            "VALUES (:id, :sym, 'NSE_EQ', 'EQ', :sym)"
        ),
        {"id": str(iid), "sym": sym},
    )
    return iid


async def _insert_open_trade(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    instrument_id: uuid.UUID,
    trade_date: date,
    status: str = "OPEN",
    planned_risk_amount: Decimal | None = None,
    total_exit_quantity: int = 0,
) -> uuid.UUID:
    tid = uuid.uuid4()
    net_position = 100 - total_exit_quantity
    await session.execute(
        text(
            "INSERT INTO trades "
            "(id, user_id, account_id, instrument_id, trade_type, direction, status, "
            " trade_date, first_fill_at, last_fill_at, "
            " total_entry_quantity, total_exit_quantity, net_position, "
            " average_entry, planned_risk_amount) "
            "VALUES (:id, :uid, :aid, :iid, 'MIS', 'LONG', :status, "
            " :td, :ffa, :ffa, 100, :teq, :np, 250.0000, :pra)"
        ),
        {
            "id": str(tid),
            "uid": str(user_id),
            "aid": str(account_id),
            "iid": str(instrument_id),
            "status": status,
            "td": trade_date,
            "ffa": datetime.now(UTC),
            "teq": total_exit_quantity,
            "np": net_position,
            "pra": str(planned_risk_amount) if planned_risk_amount is not None else None,
        },
    )
    return tid


async def _insert_closed_trade(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    instrument_id: uuid.UUID,
    trade_date: date,
    net_pnl: Decimal,
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
            " :td, :ffa, :ffa, 100, 100, 0, 250.0000, :exit)"
        ),
        {
            "id": str(tid),
            "uid": str(user_id),
            "aid": str(account_id),
            "iid": str(instrument_id),
            "td": trade_date,
            "ffa": datetime.now(UTC),
            "exit": str(250 + net_pnl / 100),
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
) -> None:
    repo = PnlRepository(session)
    await repo.upsert(
        PnlResult(
            trade_id=trade_id,
            user_id=user_id,
            account_id=account_id,
            gross_pnl=net_pnl + Decimal("50"),
            net_pnl=net_pnl,
            r_multiple=None,
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


_TODAY = date.today()
_YESTERDAY = _TODAY - timedelta(days=1)


# ---------------------------------------------------------------------------
# I-13-01: daily-summary 200 with 1 open trade — correct totals
# ---------------------------------------------------------------------------


@pytest.fixture
async def user_one_open_trade(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[tuple[uuid.UUID, uuid.UUID], None]:
    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
            aid = await _insert_trading_account(session, uid)
            iid = await _insert_instrument(session)
            await _insert_open_trade(
                session,
                user_id=uid,
                account_id=aid,
                instrument_id=iid,
                trade_date=_TODAY,
                planned_risk_amount=Decimal("3000"),
            )
    yield uid, aid
    await _cleanup(session_factory, uid)


@pytest.mark.asyncio
async def test_daily_summary_with_one_open_trade(
    user_one_open_trade: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """I-13-01: 1 open trade with planned_risk_amount → correct counts and total."""
    uid, aid = user_one_open_trade
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/v1/risk/daily-summary?account_id={aid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["open_trade_count"] == 1
        assert Decimal(data["total_at_risk_inr"]) == Decimal("3000")
        assert "as_of_date" in data
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)


# ---------------------------------------------------------------------------
# I-13-02: total_at_risk_inr=null when open trade has no planned_risk_amount
# ---------------------------------------------------------------------------


@pytest.fixture
async def user_open_trade_no_planned_risk(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[tuple[uuid.UUID, uuid.UUID], None]:
    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
            aid = await _insert_trading_account(session, uid)
            iid = await _insert_instrument(session)
            await _insert_open_trade(
                session,
                user_id=uid,
                account_id=aid,
                instrument_id=iid,
                trade_date=_TODAY,
                planned_risk_amount=None,
            )
    yield uid, aid
    await _cleanup(session_factory, uid)


@pytest.mark.asyncio
async def test_daily_summary_null_at_risk_when_no_planned_risk(
    user_open_trade_no_planned_risk: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """I-13-02: SUM(planned_risk_amount) is NULL → total_at_risk_inr=null in response."""
    uid, aid = user_open_trade_no_planned_risk
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/v1/risk/daily-summary?account_id={aid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_at_risk_inr"] is None
        assert data["open_trade_count"] == 1
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)


# ---------------------------------------------------------------------------
# I-13-02b: open trades from prior trade_dates included (Dhanvantari guard)
# ---------------------------------------------------------------------------


@pytest.fixture
async def user_open_trade_prior_date(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[tuple[uuid.UUID, uuid.UUID], None]:
    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
            aid = await _insert_trading_account(session, uid)
            iid = await _insert_instrument(session)
            # Trade opened yesterday — still OPEN today, still at risk
            await _insert_open_trade(
                session,
                user_id=uid,
                account_id=aid,
                instrument_id=iid,
                trade_date=_YESTERDAY,
                planned_risk_amount=Decimal("2000"),
            )
    yield uid, aid
    await _cleanup(session_factory, uid)


@pytest.mark.asyncio
async def test_daily_summary_includes_open_trade_from_prior_date(
    user_open_trade_prior_date: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """I-13-02b: Open trade from yesterday is included — no trade_date filter on at-risk query."""
    uid, aid = user_open_trade_prior_date
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/v1/risk/daily-summary?account_id={aid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["open_trade_count"] == 1
        assert Decimal(data["total_at_risk_inr"]) == Decimal("2000")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)


# ---------------------------------------------------------------------------
# I-13-03: summary 200 with all fields including current_loss_streak
# ---------------------------------------------------------------------------


@pytest.fixture
async def user_with_closed_trades(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[tuple[uuid.UUID, uuid.UUID], None]:
    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
            aid = await _insert_trading_account(session, uid)
            iid = await _insert_instrument(session)
            # 2 closed losing trades today (for daily_loss_inr) + 1 open trade
            for _i in range(2):
                tid = await _insert_closed_trade(
                    session,
                    user_id=uid,
                    account_id=aid,
                    instrument_id=iid,
                    trade_date=_TODAY,
                    net_pnl=Decimal("-500"),
                )
                await _insert_pnl(
                    session,
                    trade_id=tid,
                    user_id=uid,
                    account_id=aid,
                    net_pnl=Decimal("-500"),
                )
            await _insert_open_trade(
                session,
                user_id=uid,
                account_id=aid,
                instrument_id=iid,
                trade_date=_TODAY,
                planned_risk_amount=Decimal("4000"),
            )
    yield uid, aid
    await _cleanup(session_factory, uid)


@pytest.mark.asyncio
async def test_summary_returns_200_with_all_fields(
    user_with_closed_trades: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """I-13-03: GET /v1/risk/summary returns 200 with all required fields present."""
    uid, aid = user_with_closed_trades
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/v1/risk/summary?account_ids={aid}")
        assert resp.status_code == 200
        data = resp.json()
        # All fields must be present
        for field in (
            "max_drawdown_inr",
            "max_drawdown_pct",
            "current_drawdown_inr",
            "current_drawdown_pct",
            "max_loss_streak",
            "current_loss_streak",
            "daily_loss_inr",
            "daily_loss_trade_count",
            "total_at_risk_inr",
            "open_trade_count",
            "as_of_date",
        ):
            assert field in data, f"Missing field: {field}"
        assert data["current_loss_streak"] is not None
        assert data["open_trade_count"] == 1
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)


# ---------------------------------------------------------------------------
# I-13-04: summary 401 for unauthenticated request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summary_returns_401_for_unauthenticated() -> None:
    """I-13-04: No auth session → 401."""
    app.dependency_overrides.pop(get_current_user_id, None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/risk/summary")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# I-13-05: daily-summary scopes to account — other account excluded
# ---------------------------------------------------------------------------


@pytest.fixture
async def two_accounts_setup(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[tuple[uuid.UUID, uuid.UUID, uuid.UUID], None]:
    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
            aid1 = await _insert_trading_account(session, uid)
            aid2 = await _insert_trading_account(session, uid)
            iid = await _insert_instrument(session)
            # Only account 2 has an open trade
            await _insert_open_trade(
                session,
                user_id=uid,
                account_id=aid2,
                instrument_id=iid,
                trade_date=_TODAY,
                planned_risk_amount=Decimal("5000"),
            )
    yield uid, aid1, aid2
    await _cleanup(session_factory, uid)


@pytest.mark.asyncio
async def test_daily_summary_excludes_other_account_trade(
    two_accounts_setup: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
) -> None:
    """I-13-05: Query for account 1 excludes the open trade on account 2."""
    uid, aid1, aid2 = two_accounts_setup
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/v1/risk/daily-summary?account_id={aid1}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["open_trade_count"] == 0
        assert data["total_at_risk_inr"] is None
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)


# ---------------------------------------------------------------------------
# I-13-06: PARTIAL trade included at full planned_risk_amount (G-RISK-01-A/B)
# ---------------------------------------------------------------------------


@pytest.fixture
async def user_partial_trade(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[tuple[uuid.UUID, uuid.UUID], None]:
    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
            aid = await _insert_trading_account(session, uid)
            iid = await _insert_instrument(session)
            # 50 of 100 shares exited → status PARTIAL, net_position=50
            await _insert_open_trade(
                session,
                user_id=uid,
                account_id=aid,
                instrument_id=iid,
                trade_date=_TODAY,
                status="PARTIAL",
                total_exit_quantity=50,
                planned_risk_amount=Decimal("6000"),
            )
    yield uid, aid
    await _cleanup(session_factory, uid)


@pytest.mark.asyncio
async def test_daily_summary_partial_trade_included_at_full_planned_risk(
    user_partial_trade: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """I-13-06: PARTIAL trade (50 of 100 shares remain) included at full planned_risk_amount.

    G-RISK-01-A: PARTIAL is in the status IN ('OPEN', 'PARTIAL') filter.
    G-RISK-01-B: No pro-ration — full planned_risk_amount used (overstates, safe direction).
    """
    uid, aid = user_partial_trade
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/v1/risk/daily-summary?account_id={aid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["open_trade_count"] == 1
        assert Decimal(data["total_at_risk_inr"]) == Decimal("6000")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
