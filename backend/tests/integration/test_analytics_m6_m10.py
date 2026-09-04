"""Integration tests for Step 12.6 — M-6 (R-distribution) and M-10 (Dimension Breakdown).

  GET /v1/analytics/r-distribution
  GET /v1/analytics/breakdown?dimension=<dim>

Requires the full Docker Compose stack (PostgreSQL at DATABASE_URL).

M-6 Scenarios:
  TC-RDIST-001  Six buckets: all non-zero with correct counts for a known dataset
  TC-RDIST-002  insufficient_sample=True when fewer than 5 trades have non-null r_multiple
  TC-RDIST-003  NULL r_multiple trades excluded from all buckets and total_with_r
  TC-RDIST-004  Filter by direction reduces bucket counts

M-10 Scenarios:
  TC-BREAK-001  dimension=direction: two groups (LONG/SHORT) with correct metrics
  TC-BREAK-002  dimension=setup: NULL setup_name groups as "(no setup)"
  TC-BREAK-003  dimension=instrument: groups by symbol
  TC-BREAK-004  dimension=trade_type: groups by trade_type
  TC-BREAK-005  dimension=segment: groups by exchange_segment
  TC-BREAK-006  avg_r_multiple=null for groups where all trades have NULL r_multiple
  TC-BREAK-007  filter pass-through: direction=LONG filter excludes SHORT group
  TC-BREAK-008  unknown dimension returns 422
  TC-BREAK-009  empty result when no trades match filter
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
# Seed helpers (shared with other integration tests — kept local for isolation)
# ---------------------------------------------------------------------------


async def _insert_user(session: AsyncSession) -> uuid.UUID:
    uid = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO users (id, email, password_hash, is_email_verified) "
            "VALUES (:id, :email, :ph, true)"
        ),
        {"id": str(uid), "email": f"m6m10-{uid}@example.com", "ph": "$argon2id$placeholder"},
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


async def _insert_instrument(
    session: AsyncSession,
    *,
    exchange_segment: str = "NSE_EQ",
    instrument_type: str = "EQ",
) -> tuple[uuid.UUID, str]:
    """Insert an instrument with a unique UUID-based symbol.

    Returns (instrument_id, symbol) so callers can record the actual symbol name.
    Uses UUID-derived symbols to avoid collisions with the partial unique indexes
    (uq_instruments_eq, uq_instruments_fut, uq_instruments_opt) across test runs.
    Instruments are never cleaned up (they're user-independent), so symbols must
    be globally unique per test invocation.
    """
    iid = uuid.uuid4()
    sym = f"M6{str(iid).replace('-', '')[:8].upper()}"
    await session.execute(
        text(
            "INSERT INTO instruments (id, symbol, exchange_segment, instrument_type, name) "
            "VALUES (:id, :sym, :seg, :itype, :name)"
        ),
        {
            "id": str(iid),
            "sym": sym,
            "seg": exchange_segment,
            "itype": instrument_type,
            "name": sym,
        },
    )
    return iid, sym


async def _insert_trade(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    instrument_id: uuid.UUID,
    trade_date: date,
    first_fill_at: datetime,
    direction: str = "LONG",
    trade_type: str = "MIS",
    setup_name: str | None = None,
) -> uuid.UUID:
    tid = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO trades "
            "(id, user_id, account_id, instrument_id, trade_type, direction, status, "
            " trade_date, first_fill_at, last_fill_at, "
            " total_entry_quantity, total_exit_quantity, "
            " net_position, average_entry, average_exit, setup_name) "
            "VALUES (:id, :uid, :aid, :iid, :ttype, :dir, 'CLOSED', "
            " :td, :ffa, :ffa, 100, 100, 0, 250.0000, 260.0000, :sname)"
        ),
        {
            "id": str(tid),
            "uid": str(user_id),
            "aid": str(account_id),
            "iid": str(instrument_id),
            "ttype": trade_type,
            "dir": direction,
            "td": trade_date,
            "ffa": first_fill_at,
            "sname": setup_name,
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
    r_multiple: Decimal | None,
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
# M-6 Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def user_r_distribution(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[uuid.UUID, None]:
    """8 trades with r_multiples spanning all 6 buckets + 2 NULL r_multiple trades.

    Bucket distribution:
      lt_neg2      (R < -2):      r = -3.0  × 1
      neg2_to_neg1 (-2 ≤ R < -1): r = -1.5  × 2
      neg1_to_0    (-1 ≤ R < 0):  r = -0.5  × 1
      0_to_1       (0 ≤ R < 1):   r =  0.5  × 1
      1_to_2       (1 ≤ R < 2):   r =  1.5  × 1
      gt2          (R ≥ 2):       r =  2.5  × 1
      NULL r_multiple:            2 trades excluded from all bucket counts
    """
    r_values: list[Decimal | None] = [
        Decimal("-3.0"),  # lt_neg2
        Decimal("-1.5"),  # neg2_to_neg1
        Decimal("-1.5"),  # neg2_to_neg1
        Decimal("-0.5"),  # neg1_to_0
        Decimal("0.5"),  # 0_to_1
        Decimal("1.5"),  # 1_to_2
        Decimal("2.5"),  # gt2
        None,  # excluded
        None,  # excluded
    ]
    base_ts = datetime(2025, 5, 1, 9, 30, tzinfo=UTC)

    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
            account_id = await _insert_trading_account(session, uid)
            iid, _sym = await _insert_instrument(session)

            for i, r in enumerate(r_values):
                tid = await _insert_trade(
                    session,
                    user_id=uid,
                    account_id=account_id,
                    instrument_id=iid,
                    trade_date=(base_ts + timedelta(days=i)).date(),
                    first_fill_at=base_ts + timedelta(days=i),
                )
                pnl = Decimal("200") if (r is None or r >= 0) else Decimal("-200")
                await _insert_pnl(
                    session,
                    trade_id=tid,
                    user_id=uid,
                    account_id=account_id,
                    net_pnl=pnl,
                    r_multiple=r,
                )

    yield uid
    await _cleanup(session_factory, uid)


@pytest.fixture
async def user_few_r_trades(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[uuid.UUID, None]:
    """3 trades with non-null r_multiple → insufficient_sample must be True (< 5)."""
    base_ts = datetime(2025, 6, 1, 9, 30, tzinfo=UTC)

    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
            account_id = await _insert_trading_account(session, uid)
            iid, _sym = await _insert_instrument(session)

            for i in range(3):
                tid = await _insert_trade(
                    session,
                    user_id=uid,
                    account_id=account_id,
                    instrument_id=iid,
                    trade_date=(base_ts + timedelta(days=i)).date(),
                    first_fill_at=base_ts + timedelta(days=i),
                )
                await _insert_pnl(
                    session,
                    trade_id=tid,
                    user_id=uid,
                    account_id=account_id,
                    net_pnl=Decimal("200"),
                    r_multiple=Decimal("1.0"),
                )

    yield uid
    await _cleanup(session_factory, uid)


@pytest.fixture
async def user_r_direction_filter(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[uuid.UUID, None]:
    """3 LONG trades (r=2.5) and 2 SHORT trades (r=-1.5) for filter tests."""
    base_ts = datetime(2025, 7, 1, 9, 30, tzinfo=UTC)

    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
            account_id = await _insert_trading_account(session, uid)
            iid, _sym = await _insert_instrument(session)

            directions = ["LONG", "LONG", "LONG", "SHORT", "SHORT"]
            r_values = [
                Decimal("2.5"),
                Decimal("2.5"),
                Decimal("2.5"),
                Decimal("-1.5"),
                Decimal("-1.5"),
            ]
            for i, (direction, r) in enumerate(zip(directions, r_values, strict=True)):
                tid = await _insert_trade(
                    session,
                    user_id=uid,
                    account_id=account_id,
                    instrument_id=iid,
                    trade_date=(base_ts + timedelta(days=i)).date(),
                    first_fill_at=base_ts + timedelta(days=i),
                    direction=direction,
                )
                pnl = Decimal("300") if r > 0 else Decimal("-200")
                await _insert_pnl(
                    session,
                    trade_id=tid,
                    user_id=uid,
                    account_id=account_id,
                    net_pnl=pnl,
                    r_multiple=r,
                )

    yield uid
    await _cleanup(session_factory, uid)


# ---------------------------------------------------------------------------
# TC-RDIST-001: all six buckets with correct counts
# ---------------------------------------------------------------------------


async def test_tc_rdist_001_all_buckets_correct_counts(
    user_r_distribution: uuid.UUID,
) -> None:
    """TC-RDIST-001: 7 trades with non-null R → all 6 buckets present with correct counts."""
    uid = user_r_distribution
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/r-distribution")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()

    assert "buckets" in body, "Response must contain 'buckets'"
    assert len(body["buckets"]) == 6, f"Expected 6 buckets, got {len(body['buckets'])}"

    by_label = {b["label"]: b["count"] for b in body["buckets"]}
    assert by_label["< -2R"] == 1, f"lt_neg2 bucket: expected 1, got {by_label.get('< -2R')}"
    assert by_label["-2R to -1R"] == 2, (
        f"neg2_to_neg1 bucket: expected 2, got {by_label.get('-2R to -1R')}"
    )
    assert by_label["-1R to 0R"] == 1, (
        f"neg1_to_0 bucket: expected 1, got {by_label.get('-1R to 0R')}"
    )
    assert by_label["0R to 1R"] == 1, f"0_to_1 bucket: expected 1, got {by_label.get('0R to 1R')}"
    assert by_label["1R to 2R"] == 1, f"1_to_2 bucket: expected 1, got {by_label.get('1R to 2R')}"
    assert by_label["> 2R"] == 1, f"gt2 bucket: expected 1, got {by_label.get('> 2R')}"


# ---------------------------------------------------------------------------
# TC-RDIST-002: insufficient_sample=True when < 5 trades with non-null r_multiple
# ---------------------------------------------------------------------------


async def test_tc_rdist_002_insufficient_sample_below_threshold(
    user_few_r_trades: uuid.UUID,
) -> None:
    """TC-RDIST-002: 3 non-null R trades → insufficient_sample=True (threshold=5)."""
    uid = user_few_r_trades
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/r-distribution")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["insufficient_sample"] is True, (
        f"Expected insufficient_sample=True for 3 trades (threshold=5), got {body['insufficient_sample']}"
    )
    assert body["coverage_count"] == 3, (
        f"coverage_count must be 3 (non-null R trades), got {body['coverage_count']}"
    )


# ---------------------------------------------------------------------------
# TC-RDIST-003: NULL r_multiple trades excluded from bucket counts
# ---------------------------------------------------------------------------


async def test_tc_rdist_003_null_r_excluded(user_r_distribution: uuid.UUID) -> None:
    """TC-RDIST-003: 9 total trades (7 with R, 2 NULL) → bucket totals sum to 7."""
    uid = user_r_distribution
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/r-distribution")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()

    total_in_buckets = sum(b["count"] for b in body["buckets"])
    assert total_in_buckets == 7, (
        f"NULL R trades must be excluded: expected 7 in buckets, got {total_in_buckets}"
    )
    assert body["coverage_count"] == 7, (
        f"coverage_count must be 7 (non-null R trades), got {body['coverage_count']}"
    )
    assert body["total_count"] == 9, (
        f"total_count must be 9 (all CLOSED trades), got {body['total_count']}"
    )


# ---------------------------------------------------------------------------
# TC-RDIST-004: direction filter reduces bucket counts
# ---------------------------------------------------------------------------


async def test_tc_rdist_004_direction_filter_reduces_counts(
    user_r_direction_filter: uuid.UUID,
) -> None:
    """TC-RDIST-004: filtering by LONG keeps only LONG trades in the distribution."""
    uid = user_r_direction_filter
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/v1/analytics/r-distribution", params={"directions": "LONG"}
            )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()

    # All 3 LONG trades have r=2.5 → all in gt2 bucket; SHORT trades excluded
    total_in_buckets = sum(b["count"] for b in body["buckets"])
    assert total_in_buckets == 3, (
        f"direction=LONG filter must keep only LONG trades; expected 3 total, got {total_in_buckets}"
    )
    by_label = {b["label"]: b["count"] for b in body["buckets"]}
    assert by_label.get("> 2R") == 3, (
        f"All LONG trades have r=2.5 → should be in '>2R' bucket, got {by_label}"
    )


# ---------------------------------------------------------------------------
# M-10 Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def user_breakdown_multi(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[dict, None]:
    """Seed 6 trades across multiple dimensions for M-10 breakdown tests.

    Instruments use UUID-based symbols to avoid collision with the partial unique
    indexes (uq_instruments_eq, uq_instruments_fut) across repeated test runs.
    The fixture yields the actual generated symbol names for use in test assertions.

    Trade configuration:
      t1: LONG,  MIS,      setup="momentum", sym_eq,  NSE_EQ, r=1.5,  pnl=+500
      t2: SHORT, CNC,      setup="momentum", sym_eq,  NSE_EQ, r=-1.0, pnl=-200
      t3: LONG,  MIS,      setup=NULL,       sym_fut, NSE_FO, r=2.0,  pnl=+800
      t4: SHORT, CNC,      setup=NULL,       sym_fut, NSE_FO, r=NULL, pnl=-300
      t5: LONG,  NRML_FUT, setup="trend",   sym_fut2, NSE_FO, r=0.5, pnl=+100
      t6: LONG,  NRML_FUT, setup="trend",   sym_fut2, NSE_FO, r=NULL, pnl=-50
    """
    base_ts = datetime(2025, 8, 1, 9, 30, tzinfo=UTC)

    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
            account_id = await _insert_trading_account(session, uid)

            # 3 instruments: 1 EQ on NSE_EQ, 2 FUT on NSE_FO
            iid_eq, sym_eq = await _insert_instrument(
                session, exchange_segment="NSE_EQ", instrument_type="EQ"
            )
            iid_fut, sym_fut = await _insert_instrument(
                session, exchange_segment="NSE_FO", instrument_type="FUT"
            )
            iid_fut2, sym_fut2 = await _insert_instrument(
                session, exchange_segment="NSE_FO", instrument_type="FUT"
            )

            #      dir     ttype      setup       iid       r                  pnl
            trades = [
                ("LONG", "MIS", "momentum", iid_eq, Decimal("1.5"), Decimal("500")),
                ("SHORT", "CNC", "momentum", iid_eq, Decimal("-1.0"), Decimal("-200")),
                ("LONG", "MIS", None, iid_fut, Decimal("2.0"), Decimal("800")),
                ("SHORT", "CNC", None, iid_fut, None, Decimal("-300")),
                ("LONG", "NRML_FUT", "trend", iid_fut2, Decimal("0.5"), Decimal("100")),
                ("LONG", "NRML_FUT", "trend", iid_fut2, None, Decimal("-50")),
            ]
            for i, (direction, ttype, setup, iid, r, pnl) in enumerate(trades):
                tid = await _insert_trade(
                    session,
                    user_id=uid,
                    account_id=account_id,
                    instrument_id=iid,
                    trade_date=(base_ts + timedelta(days=i)).date(),
                    first_fill_at=base_ts + timedelta(days=i),
                    direction=direction,
                    trade_type=ttype,
                    setup_name=setup,
                )
                await _insert_pnl(
                    session,
                    trade_id=tid,
                    user_id=uid,
                    account_id=account_id,
                    net_pnl=pnl,
                    r_multiple=r,
                )

    yield {
        "uid": uid,
        "account_id": account_id,
        "sym_eq": sym_eq,
        "sym_fut": sym_fut,
        "sym_fut2": sym_fut2,
    }
    await _cleanup(session_factory, uid)


# ---------------------------------------------------------------------------
# TC-BREAK-001: dimension=direction
# ---------------------------------------------------------------------------


async def test_tc_break_001_direction_breakdown(user_breakdown_multi: dict) -> None:
    """TC-BREAK-001: dimension=direction returns LONG and SHORT groups."""
    uid = user_breakdown_multi["uid"]
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/v1/analytics/breakdown", params={"dimension": "direction"}
            )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dimension"] == "direction"

    labels = {g["label"] for g in body["groups"]}
    assert "LONG" in labels and "SHORT" in labels, f"Expected LONG and SHORT, got {labels}"

    long_group = next(g for g in body["groups"] if g["label"] == "LONG")
    assert long_group["trade_count"] == 4, (
        f"Expected 4 LONG trades, got {long_group['trade_count']}"
    )
    assert long_group["win_count"] == 3, (
        f"Expected 3 LONG wins (pnl>0), got {long_group['win_count']}"
    )

    short_group = next(g for g in body["groups"] if g["label"] == "SHORT")
    assert short_group["trade_count"] == 2, (
        f"Expected 2 SHORT trades, got {short_group['trade_count']}"
    )

    # Sorted by total_net_pnl descending → LONG first (total_net_pnl = 500+800+100-50=1350)
    assert body["groups"][0]["label"] == "LONG", "LONG group must be first (higher total_net_pnl)"


# ---------------------------------------------------------------------------
# TC-BREAK-002: dimension=setup — NULL groups as "(no setup)"
# ---------------------------------------------------------------------------


async def test_tc_break_002_setup_null_groups_as_no_setup(user_breakdown_multi: dict) -> None:
    """TC-BREAK-002: NULL setup_name groups as '(no setup)' string."""
    uid = user_breakdown_multi["uid"]
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/breakdown", params={"dimension": "setup"})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dimension"] == "setup"

    labels = {g["label"] for g in body["groups"]}
    assert "(no setup)" in labels, f"NULL setup_name must appear as '(no setup)', got {labels}"
    assert "momentum" in labels
    assert "trend" in labels

    no_setup_group = next(g for g in body["groups"] if g["label"] == "(no setup)")
    assert no_setup_group["trade_count"] == 2, (
        f"Expected 2 trades in (no setup) group, got {no_setup_group['trade_count']}"
    )


# ---------------------------------------------------------------------------
# TC-BREAK-003: dimension=instrument
# ---------------------------------------------------------------------------


async def test_tc_break_003_instrument_breakdown(user_breakdown_multi: dict) -> None:
    """TC-BREAK-003: dimension=instrument groups by instrument symbol.

    Uses fixture-supplied symbol names (UUID-based) to avoid dependency on fixed names.
    """
    uid = user_breakdown_multi["uid"]
    sym_eq = user_breakdown_multi["sym_eq"]
    sym_fut = user_breakdown_multi["sym_fut"]
    sym_fut2 = user_breakdown_multi["sym_fut2"]

    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/v1/analytics/breakdown", params={"dimension": "instrument"}
            )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dimension"] == "instrument"

    labels = {g["label"] for g in body["groups"]}
    assert sym_eq in labels, f"Expected sym_eq={sym_eq!r} in groups, got {labels}"
    assert sym_fut in labels, f"Expected sym_fut={sym_fut!r} in groups, got {labels}"
    assert sym_fut2 in labels, f"Expected sym_fut2={sym_fut2!r} in groups, got {labels}"

    # sym_eq has 2 trades (t1+t2)
    eq_group = next(g for g in body["groups"] if g["label"] == sym_eq)
    assert eq_group["trade_count"] == 2, (
        f"sym_eq instrument has 2 trades, got {eq_group['trade_count']}"
    )


# ---------------------------------------------------------------------------
# TC-BREAK-004: dimension=trade_type
# ---------------------------------------------------------------------------


async def test_tc_break_004_trade_type_breakdown(user_breakdown_multi: dict) -> None:
    """TC-BREAK-004: dimension=trade_type groups by trade_type."""
    uid = user_breakdown_multi["uid"]
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/v1/analytics/breakdown", params={"dimension": "trade_type"}
            )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dimension"] == "trade_type"

    labels = {g["label"] for g in body["groups"]}
    assert "MIS" in labels, f"Expected 'MIS' trade_type group, got {labels}"
    assert "CNC" in labels, f"Expected 'CNC' trade_type group, got {labels}"
    assert "NRML_FUT" in labels, f"Expected 'NRML_FUT' trade_type group, got {labels}"


# ---------------------------------------------------------------------------
# TC-BREAK-005: dimension=segment
# ---------------------------------------------------------------------------


async def test_tc_break_005_segment_breakdown(user_breakdown_multi: dict) -> None:
    """TC-BREAK-005: dimension=segment groups by exchange_segment."""
    uid = user_breakdown_multi["uid"]
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/breakdown", params={"dimension": "segment"})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dimension"] == "segment"

    labels = {g["label"] for g in body["groups"]}
    assert "NSE_EQ" in labels, f"Expected NSE_EQ segment group, got {labels}"
    assert "NSE_FO" in labels, f"Expected NSE_FO segment group, got {labels}"

    nse_eq = next(g for g in body["groups"] if g["label"] == "NSE_EQ")
    assert nse_eq["trade_count"] == 2, f"NSE_EQ has 2 trades (t1+t2), got {nse_eq['trade_count']}"

    nse_fo = next(g for g in body["groups"] if g["label"] == "NSE_FO")
    assert nse_fo["trade_count"] == 4, (
        f"NSE_FO has 4 trades (t3+t4+t5+t6), got {nse_fo['trade_count']}"
    )


# ---------------------------------------------------------------------------
# TC-BREAK-006: avg_r_multiple=null for groups where all trades have NULL r
# ---------------------------------------------------------------------------


async def test_tc_break_006_null_r_group_returns_null_avg(user_breakdown_multi: dict) -> None:
    """TC-BREAK-006: group where all trades have NULL r_multiple returns avg_r_multiple=null.

    Strategy: filter direction=SHORT on setup dimension.
    SHORT trades: t2 (setup=momentum, r=-1.0), t4 (setup=None/no setup, r=NULL).
    The "(no setup)" group then contains ONLY t4 which has NULL r → avg must be null.
    """
    uid = user_breakdown_multi["uid"]
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/v1/analytics/breakdown",
                params={"dimension": "setup", "directions": "SHORT"},
            )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()

    no_setup_group = next((g for g in body["groups"] if g["label"] == "(no setup)"), None)
    assert no_setup_group is not None, "Expected a '(no setup)' group for SHORT trades"
    assert no_setup_group["avg_r_multiple"] is None, (
        "Group where all trades have NULL r_multiple must return avg_r_multiple=null, not 0"
    )

    momentum_group = next((g for g in body["groups"] if g["label"] == "momentum"), None)
    assert momentum_group is not None, "Expected 'momentum' group for SHORT trades"
    assert momentum_group["avg_r_multiple"] is not None, (
        "momentum SHORT group has r=-1.0 → avg_r_multiple must be non-null"
    )


# ---------------------------------------------------------------------------
# TC-BREAK-007: filter pass-through — direction filter excludes SHORT group
# ---------------------------------------------------------------------------


async def test_tc_break_007_filter_passthrough(user_breakdown_multi: dict) -> None:
    """TC-BREAK-007: directions=LONG filter excludes SHORT trades from breakdown.

    After LONG filter:
      sym_eq:   only t1 (LONG); t2 (SHORT) excluded → trade_count=1
      sym_fut:  only t3 (LONG); t4 (SHORT) excluded → trade_count=1
      sym_fut2: t5+t6 (both LONG)                   → trade_count=2
    Total: 4 LONG trades across 3 instrument groups.
    """
    uid = user_breakdown_multi["uid"]
    sym_fut = user_breakdown_multi["sym_fut"]

    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/v1/analytics/breakdown",
                params={"dimension": "instrument", "directions": "LONG"},
            )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()

    total_trades = sum(g["trade_count"] for g in body["groups"])
    assert total_trades == 4, (
        f"direction=LONG filter must keep only 4 LONG trades, got {total_trades}"
    )

    # sym_fut group (iid_fut): t3 is LONG (count=1), t4 is SHORT (excluded)
    fut_group = next((g for g in body["groups"] if g["label"] == sym_fut), None)
    assert fut_group is not None, (
        f"sym_fut instrument group missing; labels={[g['label'] for g in body['groups']]}"
    )
    assert fut_group["trade_count"] == 1, (
        f"sym_fut with LONG filter: only t3 (LONG), got {fut_group['trade_count']}"
    )


# ---------------------------------------------------------------------------
# TC-BREAK-008: unknown dimension returns 422
# ---------------------------------------------------------------------------


async def test_tc_break_008_invalid_dimension_returns_422() -> None:
    """TC-BREAK-008: unknown dimension value returns HTTP 422."""
    dummy_uid = uuid.uuid4()
    app.dependency_overrides[get_current_user_id] = lambda: dummy_uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/breakdown", params={"dimension": "foobar"})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 422, (
        f"Invalid dimension must return 422, got {response.status_code}: {response.text}"
    )


# ---------------------------------------------------------------------------
# TC-BREAK-009: empty result when no trades match filter
# ---------------------------------------------------------------------------


async def test_tc_break_009_empty_result_no_match(user_breakdown_multi: dict) -> None:
    """TC-BREAK-009: no trades match the filter → empty groups list (not a 404)."""
    uid = user_breakdown_multi["uid"]
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/v1/analytics/breakdown",
                params={"dimension": "direction", "date_from": "2099-01-01"},
            )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["groups"] == [], "No trades matching filter must return empty groups, not 404"
    assert body["dimension"] == "direction"
