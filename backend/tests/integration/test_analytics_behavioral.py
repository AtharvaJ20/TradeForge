"""Integration tests for Step 12.5 behavioral analytics endpoints.

  GET /v1/analytics/streaks       (M-12)
  GET /v1/analytics/hold-duration (M-13)
  GET /v1/analytics/by-exit-type  (M-14)

Requires the full Docker Compose stack (PostgreSQL at DATABASE_URL).

Scenarios:
  TC-BEH-001  /streaks — W W B L L pattern; breakeven resets streak (G-STREAK-01)
  TC-BEH-002  /streaks — empty user returns zero streaks
  TC-BEH-003  /hold-duration — 3 trades in 3 different buckets
  TC-BEH-004  /hold-duration — empty user returns empty buckets
  TC-BEH-005  /by-exit-type — multi-fill trade: last EXIT fill wins (G-CORR-02)
  TC-BEH-006  /by-exit-type — NULL exit_type appears in response (Untagged group)
  TC-BEH-007  /by-exit-type — empty user returns empty list
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
        {"id": str(uid), "email": f"beh-test-{uid}@example.com", "ph": "$argon2id$placeholder"},
    )
    return uid


async def _insert_trading_account(session: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
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


async def _insert_instrument(session: AsyncSession) -> uuid.UUID:
    iid = uuid.uuid4()
    sym = f"BH{str(iid).replace('-', '')[:8].upper()}"
    await session.execute(
        text(
            "INSERT INTO instruments (id, symbol, exchange_segment, instrument_type, name) "
            "VALUES (:id, :sym, 'NSE_EQ', 'EQ', :name)"
        ),
        {"id": str(iid), "sym": sym, "name": sym},
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
    last_fill_at: datetime | None = None,
) -> uuid.UUID:
    tid = uuid.uuid4()
    lfa = last_fill_at if last_fill_at is not None else first_fill_at
    await session.execute(
        text(
            "INSERT INTO trades "
            "(id, user_id, account_id, instrument_id, trade_type, direction, status, "
            " trade_date, first_fill_at, last_fill_at, "
            " total_entry_quantity, total_exit_quantity, "
            " net_position, average_entry, average_exit) "
            "VALUES (:id, :uid, :aid, :iid, 'MIS', 'LONG', 'CLOSED', "
            " :td, :ffa, :lfa, 100, 100, 0, 250.0000, 260.0000)"
        ),
        {
            "id": str(tid),
            "uid": str(user_id),
            "aid": str(account_id),
            "iid": str(instrument_id),
            "td": trade_date,
            "ffa": first_fill_at,
            "lfa": lfa,
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
            r_multiple=Decimal("1") if net_pnl > 0 else (Decimal("-1") if net_pnl < 0 else None),
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


async def _insert_exit_fill(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    instrument_id: uuid.UUID,
    trade_id: uuid.UUID,
    fill_timestamp: datetime,
    exit_type: str | None,
) -> None:
    fid = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO execution_fills "
            "(id, user_id, account_id, instrument_id, trade_id, fill_role, "
            " fill_timestamp, trade_date, session, side, quantity, price, "
            " product_type, exit_type, broker, import_source) "
            "VALUES (:id, :uid, :aid, :iid, :tid, 'EXIT', "
            " :ts, :td, 'REGULAR', 'SELL', 100.0000, 260.0000, "
            " 'MIS', :exit_type, 'ZERODHA', 'MANUAL')"
        ),
        {
            "id": str(fid),
            "uid": str(user_id),
            "aid": str(account_id),
            "iid": str(instrument_id),
            "tid": str(trade_id),
            "ts": fill_timestamp,
            "td": fill_timestamp.date(),
            "exit_type": exit_type,
        },
    )


async def _cleanup(session_factory: async_sessionmaker[AsyncSession], user_id: uuid.UUID) -> None:
    async with session_factory() as session:
        async with session.begin():
            uid = str(user_id)
            # execution_fills has an immutability trigger that blocks DELETE.
            # SET LOCAL session_replication_role = replica suppresses user-defined
            # triggers for this transaction (test engine connects as postgres superuser).
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
# TC-BEH-001: /streaks — W W B L L pattern (G-STREAK-01)
# ---------------------------------------------------------------------------


@pytest.fixture
async def user_streaks_wwbll(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[uuid.UUID, None]:
    """5 trades in date order with net_pnl pattern W W B L L.

    Expected:
      max_win_streak=2, max_loss_streak=2
      current_win_streak=0, current_loss_streak=2
    """
    base_ts = datetime(2025, 1, 1, 9, 30, tzinfo=UTC)
    net_pnls = [
        Decimal("500"),  # WIN
        Decimal("300"),  # WIN
        Decimal("0"),  # BREAKEVEN — resets win streak
        Decimal("-400"),  # LOSS
        Decimal("-200"),  # LOSS (current loss streak = 2)
    ]

    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
            account_id = await _insert_trading_account(session, uid)
            iid = await _insert_instrument(session)

            for i, pnl in enumerate(net_pnls):
                td = date(2025, 1, i + 1)
                ts = base_ts + timedelta(days=i)
                tid = await _insert_trade(
                    session,
                    user_id=uid,
                    account_id=account_id,
                    instrument_id=iid,
                    trade_date=td,
                    first_fill_at=ts,
                    last_fill_at=ts,
                )
                await _insert_pnl(
                    session,
                    trade_id=tid,
                    user_id=uid,
                    account_id=account_id,
                    net_pnl=pnl,
                )

    yield uid
    await _cleanup(session_factory, uid)


async def test_tc_beh_001_streaks_wwbll(user_streaks_wwbll: uuid.UUID) -> None:
    """TC-BEH-001: W W B L L → max_win=2, max_loss=2, current_loss=2 (G-STREAK-01)."""
    uid = user_streaks_wwbll
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/streaks")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["max_win_streak"] == 2, f"Expected max_win_streak=2, got {body['max_win_streak']}"
    assert body["max_loss_streak"] == 2, (
        f"Expected max_loss_streak=2, got {body['max_loss_streak']}"
    )
    assert body["current_win_streak"] == 0, "Breakeven must reset win streak to 0"
    assert body["current_loss_streak"] == 2, "Loss streak must be 2 after breakeven"
    # avg_win_streak: one win run of 2 → 2.0
    assert Decimal(body["avg_win_streak"]) == Decimal("2")
    # avg_loss_streak: one loss run of 2 → 2.0
    assert Decimal(body["avg_loss_streak"]) == Decimal("2")


# ---------------------------------------------------------------------------
# TC-BEH-002: /streaks — empty user
# ---------------------------------------------------------------------------


@pytest.fixture
async def user_empty(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[uuid.UUID, None]:
    """User with no trades at all."""
    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
    yield uid
    await _cleanup(session_factory, uid)


async def test_tc_beh_002_streaks_empty(user_empty: uuid.UUID) -> None:
    """TC-BEH-002: /streaks with no trades returns all zeros."""
    uid = user_empty
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/streaks")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["max_win_streak"] == 0
    assert body["max_loss_streak"] == 0
    assert body["current_win_streak"] == 0
    assert body["current_loss_streak"] == 0


# ---------------------------------------------------------------------------
# TC-BEH-003: /hold-duration — 3 trades spanning 3 different buckets
# ---------------------------------------------------------------------------


@pytest.fixture
async def user_hold_duration(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[uuid.UUID, None]:
    """3 trades with different hold durations in 3 buckets.

    Trade 1: 0 min hold → "< 15 min"
    Trade 2: 30 min hold → "15 min – 1 hr"
    Trade 3: 120 min hold → "1 – 4 hr"
    """
    base_date = date(2025, 2, 1)
    base_ts = datetime(2025, 2, 1, 9, 30, tzinfo=UTC)
    holds_minutes = [0, 30, 120]

    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
            account_id = await _insert_trading_account(session, uid)
            iid = await _insert_instrument(session)

            for i, hold_min in enumerate(holds_minutes):
                first_fill = base_ts + timedelta(days=i)
                last_fill = first_fill + timedelta(minutes=hold_min)
                tid = await _insert_trade(
                    session,
                    user_id=uid,
                    account_id=account_id,
                    instrument_id=iid,
                    trade_date=base_date + timedelta(days=i),
                    first_fill_at=first_fill,
                    last_fill_at=last_fill,
                )
                await _insert_pnl(
                    session,
                    trade_id=tid,
                    user_id=uid,
                    account_id=account_id,
                    net_pnl=Decimal("200"),
                )

    yield uid
    await _cleanup(session_factory, uid)


async def test_tc_beh_003_hold_duration_three_buckets(user_hold_duration: uuid.UUID) -> None:
    """TC-BEH-003: 3 trades land in 3 distinct duration buckets."""
    uid = user_hold_duration
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/hold-duration")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()

    buckets = body["buckets"]
    bucket_names = {b["bucket"] for b in buckets}

    assert "< 15 min" in bucket_names, f"Expected '< 15 min' bucket, got {bucket_names}"
    assert "15 min – 1 hr" in bucket_names, f"Expected '15 min – 1 hr' bucket, got {bucket_names}"
    assert "1 – 4 hr" in bucket_names, f"Expected '1 – 4 hr' bucket, got {bucket_names}"

    total_count = sum(b["count"] for b in buckets)
    assert total_count == 3, f"Expected 3 trades total across all buckets, got {total_count}"

    # avg/median duration_minutes must be present
    assert body["avg_duration_minutes"] is not None
    assert body["median_duration_minutes"] is not None

    # Buckets must be ordered by bucket_order (ascending)
    orders = [b["bucket_order"] for b in buckets]
    assert orders == sorted(orders), "Buckets must be returned in ascending bucket_order"


# ---------------------------------------------------------------------------
# TC-BEH-004: /hold-duration — empty user
# ---------------------------------------------------------------------------


async def test_tc_beh_004_hold_duration_empty(user_empty: uuid.UUID) -> None:
    """TC-BEH-004: /hold-duration with no trades returns empty buckets and null durations."""
    uid = user_empty
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/hold-duration")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["buckets"] == []
    assert body["avg_duration_minutes"] is None
    assert body["median_duration_minutes"] is None


# ---------------------------------------------------------------------------
# TC-BEH-005: /by-exit-type — G-CORR-02: last EXIT fill wins
# ---------------------------------------------------------------------------


@pytest.fixture
async def user_exit_types(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[dict, None]:
    """Seed 3 trades:

    Trade 1: 2 EXIT fills — STOP_HIT at T1, TARGET_HIT at T2 (T2 > T1)
             → G-CORR-02: assigned TARGET_HIT (last fill by timestamp)
    Trade 2: 1 EXIT fill — DISCRETIONARY
    Trade 3: 1 EXIT fill — NULL exit_type → Untagged group in response
    """
    base_ts = datetime(2025, 3, 1, 9, 30, tzinfo=UTC)

    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
            account_id = await _insert_trading_account(session, uid)
            iid = await _insert_instrument(session)

            # Trade 1: multi-fill — last fill (TARGET_HIT) must win
            tid1 = await _insert_trade(
                session,
                user_id=uid,
                account_id=account_id,
                instrument_id=iid,
                trade_date=date(2025, 3, 1),
                first_fill_at=base_ts,
                last_fill_at=base_ts + timedelta(hours=1),
            )
            await _insert_pnl(
                session, trade_id=tid1, user_id=uid, account_id=account_id, net_pnl=Decimal("500")
            )
            # Earlier EXIT fill with STOP_HIT (should be superseded)
            await _insert_exit_fill(
                session,
                user_id=uid,
                account_id=account_id,
                instrument_id=iid,
                trade_id=tid1,
                fill_timestamp=base_ts + timedelta(minutes=30),
                exit_type="STOP_HIT",
            )
            # Later EXIT fill with TARGET_HIT (must be the winning exit_type)
            await _insert_exit_fill(
                session,
                user_id=uid,
                account_id=account_id,
                instrument_id=iid,
                trade_id=tid1,
                fill_timestamp=base_ts + timedelta(hours=1),
                exit_type="TARGET_HIT",
            )

            # Trade 2: single DISCRETIONARY exit
            tid2 = await _insert_trade(
                session,
                user_id=uid,
                account_id=account_id,
                instrument_id=iid,
                trade_date=date(2025, 3, 2),
                first_fill_at=base_ts + timedelta(days=1),
                last_fill_at=base_ts + timedelta(days=1),
            )
            await _insert_pnl(
                session, trade_id=tid2, user_id=uid, account_id=account_id, net_pnl=Decimal("200")
            )
            await _insert_exit_fill(
                session,
                user_id=uid,
                account_id=account_id,
                instrument_id=iid,
                trade_id=tid2,
                fill_timestamp=base_ts + timedelta(days=1),
                exit_type="DISCRETIONARY",
            )

            # Trade 3: NULL exit_type
            tid3 = await _insert_trade(
                session,
                user_id=uid,
                account_id=account_id,
                instrument_id=iid,
                trade_date=date(2025, 3, 3),
                first_fill_at=base_ts + timedelta(days=2),
                last_fill_at=base_ts + timedelta(days=2),
            )
            await _insert_pnl(
                session,
                trade_id=tid3,
                user_id=uid,
                account_id=account_id,
                net_pnl=Decimal("-100"),
            )
            await _insert_exit_fill(
                session,
                user_id=uid,
                account_id=account_id,
                instrument_id=iid,
                trade_id=tid3,
                fill_timestamp=base_ts + timedelta(days=2),
                exit_type=None,
            )

    yield {"user_id": uid, "tid1": tid1}
    await _cleanup(session_factory, uid)


async def test_tc_beh_005_exit_type_last_fill_wins(user_exit_types: dict) -> None:
    """TC-BEH-005: G-CORR-02 — multi-fill trade is assigned the exit_type of the latest fill."""
    uid = user_exit_types["user_id"]
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/by-exit-type")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    rows = response.json()

    exit_types_in_response = {r["exit_type"] for r in rows}

    # Trade 1 must be under TARGET_HIT (not STOP_HIT)
    assert "TARGET_HIT" in exit_types_in_response, (
        f"G-CORR-02 violated: TARGET_HIT not found. Got: {exit_types_in_response}"
    )
    assert "STOP_HIT" not in exit_types_in_response, (
        "G-CORR-02 violated: STOP_HIT must not appear — earlier fill must be superseded"
    )

    target_hit_row = next(r for r in rows if r["exit_type"] == "TARGET_HIT")
    assert target_hit_row["trade_count"] == 1

    # Each of the 3 groups has 1 trade
    total_trades = sum(r["trade_count"] for r in rows)
    assert total_trades == 3, f"Expected 3 total trades across exit type groups, got {total_trades}"


async def test_tc_beh_006_null_exit_type_present(user_exit_types: dict) -> None:
    """TC-BEH-006: NULL exit_type group (Untagged) appears in the response."""
    uid = user_exit_types["user_id"]
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/by-exit-type")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    rows = response.json()

    null_rows = [r for r in rows if r["exit_type"] is None]
    assert len(null_rows) == 1, f"Expected exactly 1 NULL exit_type group, got {len(null_rows)}"
    assert null_rows[0]["trade_count"] == 1


# ---------------------------------------------------------------------------
# TC-BEH-007: /by-exit-type — empty user
# ---------------------------------------------------------------------------


async def test_tc_beh_007_exit_type_empty(user_empty: uuid.UUID) -> None:
    """TC-BEH-007: /by-exit-type with no trades returns empty list."""
    uid = user_empty
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/by-exit-type")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    assert response.json() == []


# ---------------------------------------------------------------------------
# COV-12.5-01: /hold-duration — all 6 buckets covered
# ---------------------------------------------------------------------------
# TC-BEH-003 covers buckets 1-3 (< 15 min, 15 min–1 hr, 1–4 hr).
# This fixture covers buckets 4-6 (4–24 hr, 1–7 days, > 7 days).
# "1–7 days" is the multi_day bucket (2–6 days inclusive) absent from prior tests.


@pytest.fixture
async def user_hold_duration_extended(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[uuid.UUID, None]:
    """3 trades spanning hold-duration buckets 4, 5, and 6.

    Trade 1: 720 min (12 hr)  → bucket 4  "4 – 24 hr"
    Trade 2: 2880 min (2 days) → bucket 5  "1 – 7 days"  (multi_day coverage)
    Trade 3: 15000 min (~10 d) → bucket 6  "> 7 days"
    """
    base_ts = datetime(2025, 4, 1, 9, 30, tzinfo=UTC)
    holds_minutes = [720, 2880, 15000]

    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
            account_id = await _insert_trading_account(session, uid)
            iid = await _insert_instrument(session)

            for i, hold_min in enumerate(holds_minutes):
                first_fill = base_ts + timedelta(days=i * 20)
                last_fill = first_fill + timedelta(minutes=hold_min)
                tid = await _insert_trade(
                    session,
                    user_id=uid,
                    account_id=account_id,
                    instrument_id=iid,
                    trade_date=(base_ts + timedelta(days=i * 20)).date(),
                    first_fill_at=first_fill,
                    last_fill_at=last_fill,
                )
                await _insert_pnl(
                    session,
                    trade_id=tid,
                    user_id=uid,
                    account_id=account_id,
                    net_pnl=Decimal("300"),
                )

    yield uid
    await _cleanup(session_factory, uid)


async def test_tc_beh_cov01_hold_duration_extended_buckets(
    user_hold_duration_extended: uuid.UUID,
) -> None:
    """COV-12.5-01: trades land in buckets 4 (4–24 hr), 5 (1–7 days), 6 (>7 days).

    Closes the multi_day coverage gap identified by Sahadeva in Step 12.5.
    """
    uid = user_hold_duration_extended
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/hold-duration")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()

    bucket_names = {b["bucket"] for b in body["buckets"]}
    assert "4 – 24 hr" in bucket_names, f"Bucket '4 – 24 hr' missing from {bucket_names}"
    assert "1 – 7 days" in bucket_names, f"Bucket '1 – 7 days' (multi_day) missing from {bucket_names}"
    assert "> 7 days" in bucket_names, f"Bucket '> 7 days' missing from {bucket_names}"

    total_count = sum(b["count"] for b in body["buckets"])
    assert total_count == 3, f"Expected 3 trades total across buckets, got {total_count}"

    # Verify ordering
    orders = [b["bucket_order"] for b in body["buckets"]]
    assert orders == sorted(orders), "Buckets must be in ascending bucket_order"


# ---------------------------------------------------------------------------
# COV-12.5-02: filter pass-through tests for behavioral analytics endpoints
# ---------------------------------------------------------------------------
# One test per endpoint confirming that date_from, date_to, account_ids, and
# directions filters correctly reduce the result set.


async def test_tc_beh_cov02a_streaks_filter_passthrough(
    user_streaks_wwbll: uuid.UUID,
) -> None:
    """COV-12.5-02a: /streaks — from_date after all trade dates returns zero streaks."""
    uid = user_streaks_wwbll
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # All trades are in Jan 2025; filtering from 2099-01-01 yields zero trades
            response = await client.get(
                "/v1/analytics/streaks", params={"date_from": "2099-01-01"}
            )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["max_win_streak"] == 0, "date_from filter must exclude all trades → zero streaks"
    assert body["max_loss_streak"] == 0
    assert body["current_win_streak"] == 0
    assert body["current_loss_streak"] == 0

    # Also verify direction filter: trades are LONG; SHORT filter → zero streaks
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response2 = await client.get(
                "/v1/analytics/streaks", params={"directions": "SHORT"}
            )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response2.status_code == 200, response2.text
    body2 = response2.json()
    assert body2["max_win_streak"] == 0, "direction=SHORT filter must exclude LONG trades"


async def test_tc_beh_cov02b_hold_duration_filter_passthrough(
    user_hold_duration: uuid.UUID,
) -> None:
    """COV-12.5-02b: /hold-duration — date_to before all trade dates returns empty buckets."""
    uid = user_hold_duration
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Trades are Feb 2025; filter date_to=2025-01-01 excludes all
            response = await client.get(
                "/v1/analytics/hold-duration", params={"date_to": "2025-01-01"}
            )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["buckets"] == [], "date_to filter before trade dates must yield empty buckets"
    assert body["avg_duration_minutes"] is None
    assert body["median_duration_minutes"] is None

    # Also verify account_ids filter with a random unknown account → empty
    unknown_account = uuid.uuid4()
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response2 = await client.get(
                "/v1/analytics/hold-duration",
                params={"account_ids": str(unknown_account)},
            )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response2.status_code == 200, response2.text
    body2 = response2.json()
    assert body2["buckets"] == [], "account_ids filter for unknown account must yield empty buckets"


async def test_tc_beh_cov02c_exit_type_filter_passthrough(
    user_exit_types: dict,
) -> None:
    """COV-12.5-02c: /by-exit-type — from_date after all trade dates returns empty list."""
    uid = user_exit_types["user_id"]
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Trades are March 2025; filter date_from=2099-01-01 excludes all
            response = await client.get(
                "/v1/analytics/by-exit-type", params={"date_from": "2099-01-01"}
            )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    assert response.json() == [], "date_from filter must exclude all trades → empty exit-type list"

    # Also verify directions filter
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response2 = await client.get(
                "/v1/analytics/by-exit-type", params={"directions": "SHORT"}
            )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response2.status_code == 200, response2.text
    assert response2.json() == [], "directions=SHORT filter must exclude all LONG trades"
