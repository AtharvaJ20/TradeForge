"""Integration tests for GET /v1/analytics/filters/* endpoints (Step 12.4, B-1/B-2/B-3).

Verifies the three filter-dimension endpoints return correct shapes and values
against a real PostgreSQL database seeded with known data.

Requires the full Docker Compose stack (PostgreSQL at DATABASE_URL).

Scenarios:
  TC-FD-001: user with 2 accounts, 3 setup names (one NULL), 2 brokers
             → accounts/setups/brokers all populated correctly.
  TC-FD-002: user with no CLOSED trades → all three endpoints return [].
  TC-FD-003: account record deleted (FK absent) → account still appears with UUID label fallback.
"""

from __future__ import annotations

import os
import re
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
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
        {"id": str(uid), "email": f"fd-test-{uid}@example.com", "ph": "$argon2id$placeholder"},
    )
    return uid


async def _insert_trading_account(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    broker: str = "ZERODHA",
    display_name: str = "Test Account",
) -> uuid.UUID:
    account_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO trading_accounts "
            "(id, user_id, broker, display_name, account_type, base_currency, status) "
            "VALUES (:id, :uid, :broker, :name, 'INDIVIDUAL', 'INR', 'ACTIVE')"
        ),
        {"id": str(account_id), "uid": str(user_id), "broker": broker, "name": display_name},
    )
    return account_id


async def _insert_instrument(session: AsyncSession) -> uuid.UUID:
    iid = uuid.uuid4()
    sym = f"FD{str(iid).replace('-', '')[:8].upper()}"
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
    setup_name: str | None = None,
    trade_date: date | None = None,
) -> uuid.UUID:
    tid = uuid.uuid4()
    ts = datetime(2025, 6, 1, 9, 30, tzinfo=UTC)
    td = trade_date or date(2025, 6, 1)
    await session.execute(
        text(
            "INSERT INTO trades "
            "(id, user_id, account_id, instrument_id, trade_type, direction, status, "
            " trade_date, first_fill_at, total_entry_quantity, total_exit_quantity, "
            " net_position, average_entry, average_exit, setup_name) "
            "VALUES (:id, :uid, :aid, :iid, 'MIS', 'LONG', 'CLOSED', "
            " :td, :ts, 100, 100, 0, 250.0000, 260.0000, :sn)"
        ),
        {
            "id": str(tid),
            "uid": str(user_id),
            "aid": str(account_id),
            "iid": str(instrument_id),
            "td": td,
            "ts": ts,
            "sn": setup_name,
        },
    )
    return tid


async def _insert_pnl(
    session: AsyncSession,
    *,
    trade_id: uuid.UUID,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    broker: str = "ZERODHA",
) -> None:
    repo = PnlRepository(session)
    await repo.upsert(
        PnlResult(
            trade_id=trade_id,
            user_id=user_id,
            account_id=account_id,
            gross_pnl=Decimal("1050"),
            net_pnl=Decimal("1000"),
            r_multiple=Decimal("2"),
            brokerage=Decimal("20"),
            stt=Decimal("10"),
            exchange_charges=Decimal("8"),
            sebi_charges=Decimal("2"),
            stamp_duty=Decimal("5"),
            gst=Decimal("4"),
            ipft=Decimal("1"),
            total_charges=Decimal("50"),
            broker=broker,
            charge_schedule_version="2024-10-01",
            engine_version=PNL_ENGINE_VERSION,
        )
    )


async def _cleanup(session_factory: async_sessionmaker[AsyncSession], user_id: uuid.UUID) -> None:
    async with session_factory() as session:
        async with session.begin():
            uid = str(user_id)
            await session.execute(text("DELETE FROM trade_pnl WHERE user_id = :uid"), {"uid": uid})
            await session.execute(text("DELETE FROM trades WHERE user_id = :uid"), {"uid": uid})
            await session.execute(
                text("DELETE FROM trading_accounts WHERE user_id = :uid"), {"uid": uid}
            )
            await session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": uid})


# ---------------------------------------------------------------------------
# TC-FD-001: populated dimensions
# ---------------------------------------------------------------------------


@pytest.fixture
async def user_fd_001(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[dict, None]:
    """Seed: 2 accounts (Zerodha + Upstox), 3 setups (Breakout, VWAP, NULL), 2 brokers."""
    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
            acc_z = await _insert_trading_account(
                session, uid, broker="ZERODHA", display_name="Zerodha Main"
            )
            acc_u = await _insert_trading_account(
                session, uid, broker="UPSTOX", display_name="Upstox Secondary"
            )
            iid = await _insert_instrument(session)

            for setup, account, broker in [
                ("Breakout", acc_z, "ZERODHA"),
                ("VWAP Reversion", acc_z, "ZERODHA"),
                (None, acc_u, "UPSTOX"),
            ]:
                tid = await _insert_closed_trade(
                    session,
                    user_id=uid,
                    account_id=account,
                    instrument_id=iid,
                    setup_name=setup,
                )
                await _insert_pnl(
                    session, trade_id=tid, user_id=uid, account_id=account, broker=broker
                )

    yield {"user_id": uid, "acc_z": acc_z, "acc_u": acc_u}
    await _cleanup(session_factory, uid)


async def test_tc_fd_001_accounts_returns_both_with_labels(user_fd_001: dict) -> None:
    """TC-FD-001: accounts endpoint returns both accounts with display_name labels."""
    uid = user_fd_001["user_id"]
    acc_z = user_fd_001["acc_z"]
    acc_u = user_fd_001["acc_u"]

    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/filters/accounts")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()

    assert isinstance(body, list)
    assert len(body) == 2
    ids_in_response = {item["id"] for item in body}
    assert str(acc_z) in ids_in_response
    assert str(acc_u) in ids_in_response
    labels = {item["label"] for item in body}
    assert "Zerodha Main" in labels
    assert "Upstox Secondary" in labels


async def test_tc_fd_001_setups_returns_all_including_no_setup(user_fd_001: dict) -> None:
    """TC-FD-001: setups endpoint returns 3 entries including '(no setup)' for NULL."""
    uid = user_fd_001["user_id"]

    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/filters/setups")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()

    assert isinstance(body, list)
    assert set(body) == {"Breakout", "VWAP Reversion", "(no setup)"}


async def test_tc_fd_001_brokers_returns_sorted(user_fd_001: dict) -> None:
    """TC-FD-001: brokers endpoint returns both brokers alphabetically sorted."""
    uid = user_fd_001["user_id"]

    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/filters/brokers")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()

    assert isinstance(body, list)
    assert body == sorted(body)
    assert set(body) == {"UPSTOX", "ZERODHA"}


# ---------------------------------------------------------------------------
# TC-FD-002: no CLOSED trades → all endpoints return []
# ---------------------------------------------------------------------------


@pytest.fixture
async def user_fd_002(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[uuid.UUID, None]:
    """Seed: user with no trades at all."""
    async with session_factory() as session:
        async with session.begin():
            uid = await _insert_user(session)
    yield uid
    await _cleanup(session_factory, uid)


async def test_tc_fd_002_accounts_empty(user_fd_002: uuid.UUID) -> None:
    """TC-FD-002: accounts returns [] when user has no CLOSED trades."""
    app.dependency_overrides[get_current_user_id] = lambda: user_fd_002
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/filters/accounts")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    assert response.json() == []


async def test_tc_fd_002_setups_empty(user_fd_002: uuid.UUID) -> None:
    """TC-FD-002: setups returns [] when user has no CLOSED trades."""
    app.dependency_overrides[get_current_user_id] = lambda: user_fd_002
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/filters/setups")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    assert response.json() == []


async def test_tc_fd_002_brokers_empty(user_fd_002: uuid.UUID) -> None:
    """TC-FD-002: brokers returns [] when user has no CLOSED trades."""
    app.dependency_overrides[get_current_user_id] = lambda: user_fd_002
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/filters/brokers")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    assert response.json() == []


# ---------------------------------------------------------------------------
# TC-FD-003: account record deleted — UUID label fallback
# ---------------------------------------------------------------------------


@pytest.fixture
async def user_fd_003(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[dict, None]:
    """Seed: one trade with an account_id that has no corresponding trading_accounts row.

    The FK on trades.account_id uses NO ACTION (RESTRICT) — hard-deleting a
    referenced trading_accounts row is blocked. We simulate the orphaned state by
    inserting the trade with a UUID that was never in trading_accounts, bypassing
    FK enforcement via session_replication_role = replica (superuser-only; the
    fixture engine connects as postgres).
    """
    orphaned_account_id = uuid.uuid4()

    async with session_factory() as session:
        async with session.begin():
            # SET LOCAL is transaction-scoped: FK trigger bypass reverts automatically
            # on commit, so subsequent sessions see normal constraint enforcement.
            await session.execute(text("SET LOCAL session_replication_role = replica"))
            uid = await _insert_user(session)
            iid = await _insert_instrument(session)
            await _insert_closed_trade(
                session, user_id=uid, account_id=orphaned_account_id, instrument_id=iid
            )

    yield {"user_id": uid, "orphaned_account_id": orphaned_account_id}
    await _cleanup(session_factory, uid)


async def test_tc_fd_003_orphaned_account_uses_uuid_label(user_fd_003: dict) -> None:
    """TC-FD-003: account with no trading_accounts row falls back to UUID string as label."""
    uid = user_fd_003["user_id"]
    orphaned_id = user_fd_003["orphaned_account_id"]

    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/analytics/filters/accounts")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200, response.text
    body = response.json()

    assert len(body) == 1
    assert body[0]["id"] == str(orphaned_id)
    assert body[0]["label"] == str(orphaned_id)
