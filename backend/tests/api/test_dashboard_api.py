"""API-layer tests for Step 18 — Dashboard, Trade List, and Recent Journal endpoints.

Tests use the FastAPI dependency_overrides pattern to mock out the DB session
and auth dependency, avoiding any real DB connections.

Test IDs:
  B-18-01 through B-18-11   — GET /v1/dashboard/summary (dashboard stats)
  B-18-12, B-18-12b         — GET /v1/trades (status filter)
  B-18-13, B-18-13b         — GET /v1/trades (status=invalid → 422; lowercase → 422)
  B-18-14, B-18-15, ...     — GET /v1/trades (sort, pagination)
  B-18-15b                  — sort_dir invalid value → 200 with desc order
  B-18-15c                  — sort_by unknown value → 200 with last_fill_at default
  B-18-16 through B-18-21   — GET /v1/trades (additional filters)
  B-18-22 through B-18-26   — GET /v1/journal/recent
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_USER_ID = uuid.uuid4()
_ACCOUNT_ID = uuid.uuid4()
_TRADE_ID = uuid.uuid4()
_JOURNAL_ID = uuid.uuid4()
_INSTR_ID = uuid.uuid4()


# ---------------------------------------------------------------------------
# Mock row factories
# ---------------------------------------------------------------------------


def _dashboard_row(
    all_time_net_pnl: Any = Decimal("12345.67"),
    mtd_net_pnl: Any = Decimal("1000.00"),
    wtd_net_pnl: Any = Decimal("500.00"),
    total_closed_trades: int = 42,
    open_trade_count: int = 3,
    starting_capital: Any = Decimal("500000.00"),
) -> MagicMock:
    row = MagicMock()
    row.all_time_net_pnl = all_time_net_pnl
    row.mtd_net_pnl = mtd_net_pnl
    row.wtd_net_pnl = wtd_net_pnl
    row.total_closed_trades = total_closed_trades
    row.open_trade_count = open_trade_count
    row.starting_capital = starting_capital
    return row


def _trade_list_row(
    *,
    id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
    symbol: str = "RELIANCE",
    instrument_type: str = "EQ",
    direction: str = "LONG",
    status: str = "CLOSED",
    trade_date: date | None = None,
    last_fill_at: datetime | None = None,
    net_pnl: Decimal | None = Decimal("500.00"),
    r_multiple: Decimal | None = Decimal("2.0"),
) -> MagicMock:
    row = MagicMock()
    row.id = id or _TRADE_ID
    row.account_id = account_id or _ACCOUNT_ID
    row.symbol = symbol
    row.instrument_type = instrument_type
    row.direction = direction
    row.status = status
    row.trade_date = trade_date or date(2026, 9, 1)
    row.last_fill_at = last_fill_at or datetime(2026, 9, 1, 10, 30, tzinfo=UTC)
    row.net_pnl = net_pnl
    row.r_multiple = r_multiple
    return row


def _journal_row(
    *,
    id: uuid.UUID | None = None,
    trade_id: uuid.UUID | None = None,
    symbol: str = "INFY",
    instrument_type: str = "EQ",
    direction: str = "LONG",
    trade_date: date | None = None,
    discipline_score: int | None = 8,
    emotion_before: str | None = "CALM",
    emotion_during: str | None = "CONFIDENT",
    emotion_after: str | None = "NEUTRAL",
    created_at: datetime | None = None,
) -> MagicMock:
    row = MagicMock()
    row.id = id or _JOURNAL_ID
    row.trade_id = trade_id or _TRADE_ID
    row.symbol = symbol
    row.instrument_type = instrument_type
    row.direction = direction
    row.trade_date = trade_date or date(2026, 9, 1)
    row.discipline_score = discipline_score
    row.emotion_before = emotion_before
    row.emotion_during = emotion_during
    row.emotion_after = emotion_after
    row.created_at = created_at or datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    return row


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_db(rows: list[Any]) -> AsyncMock:
    """Return a mock AsyncSession whose execute() returns rows."""
    mock_db = AsyncMock()
    result = MagicMock()
    result.one.return_value = rows[0] if rows else MagicMock()
    result.all.return_value = rows
    mock_db.execute.return_value = result
    return mock_db


@pytest.fixture(autouse=True)
def override_user_id() -> None:
    from tradeforge.api.v1.deps import get_current_user_id
    from tradeforge.main import app

    app.dependency_overrides[get_current_user_id] = lambda: _USER_ID
    yield
    app.dependency_overrides.pop(get_current_user_id, None)


# ---------------------------------------------------------------------------
# Dashboard summary tests: B-18-01 through B-18-11
# ---------------------------------------------------------------------------


async def test_dashboard_summary_returns_200(http_client: AsyncClient) -> None:
    """B-18-01: GET /v1/dashboard/summary returns 200 with correct shape."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_dashboard_row()])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/dashboard/summary?account_id={_ACCOUNT_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert "account_id" in body
    assert "as_of_date" in body
    assert "all_time_net_pnl" in body
    assert "mtd_net_pnl" in body
    assert "wtd_net_pnl" in body
    assert "starting_capital" in body
    assert "realized_equity" in body
    assert "total_closed_trades" in body
    assert "open_trade_count" in body


async def test_dashboard_summary_all_time_pnl(http_client: AsyncClient) -> None:
    """B-18-02: all_time_net_pnl matches aggregate row value."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_dashboard_row(all_time_net_pnl=Decimal("99999.99"))])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/dashboard/summary?account_id={_ACCOUNT_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert Decimal(response.json()["all_time_net_pnl"]) == Decimal("99999.99")


async def test_dashboard_summary_mtd_pnl(http_client: AsyncClient) -> None:
    """B-18-03: mtd_net_pnl matches the month-to-date slice."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_dashboard_row(mtd_net_pnl=Decimal("1500.00"))])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/dashboard/summary?account_id={_ACCOUNT_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert Decimal(response.json()["mtd_net_pnl"]) == Decimal("1500.00")


async def test_dashboard_summary_wtd_pnl(http_client: AsyncClient) -> None:
    """B-18-04: wtd_net_pnl matches the week-to-date slice."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_dashboard_row(wtd_net_pnl=Decimal("300.00"))])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/dashboard/summary?account_id={_ACCOUNT_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert Decimal(response.json()["wtd_net_pnl"]) == Decimal("300.00")


async def test_dashboard_summary_total_closed(http_client: AsyncClient) -> None:
    """B-18-05: total_closed_trades is the count of CLOSED trades."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_dashboard_row(total_closed_trades=17)])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/dashboard/summary?account_id={_ACCOUNT_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.json()["total_closed_trades"] == 17


async def test_dashboard_summary_open_count(http_client: AsyncClient) -> None:
    """B-18-06: open_trade_count is the count of OPEN + PARTIAL trades."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_dashboard_row(open_trade_count=5)])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/dashboard/summary?account_id={_ACCOUNT_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.json()["open_trade_count"] == 5


async def test_dashboard_summary_zero_pnl_on_no_trades(http_client: AsyncClient) -> None:
    """B-18-07: COALESCE means zero P&L (not null) when user has no trades."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_dashboard_row(all_time_net_pnl=0, mtd_net_pnl=0, wtd_net_pnl=0)])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/dashboard/summary?account_id={_ACCOUNT_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    body = response.json()
    assert body["all_time_net_pnl"] is not None
    assert body["mtd_net_pnl"] is not None
    assert body["wtd_net_pnl"] is not None


async def test_dashboard_summary_negative_pnl(http_client: AsyncClient) -> None:
    """B-18-08: Negative P&L values serialize correctly."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_dashboard_row(all_time_net_pnl=Decimal("-5000.00"))])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/dashboard/summary?account_id={_ACCOUNT_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert Decimal(response.json()["all_time_net_pnl"]) == Decimal("-5000.00")


async def test_dashboard_summary_requires_auth(http_client: AsyncClient) -> None:
    """B-18-09: Unauthenticated request → 401 (user_id dep removed)."""
    from tradeforge.api.v1.deps import get_current_user_id
    from tradeforge.main import app

    app.dependency_overrides.pop(get_current_user_id, None)
    try:
        response = await http_client.get(f"/v1/dashboard/summary?account_id={_ACCOUNT_ID}")
    finally:
        app.dependency_overrides[get_current_user_id] = lambda: _USER_ID

    assert response.status_code == 401


async def test_dashboard_summary_counts_are_int(http_client: AsyncClient) -> None:
    """B-18-10: total_closed_trades and open_trade_count are integers, not floats."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_dashboard_row(total_closed_trades=10, open_trade_count=2)])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/dashboard/summary?account_id={_ACCOUNT_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    body = response.json()
    assert isinstance(body["total_closed_trades"], int)
    assert isinstance(body["open_trade_count"], int)


async def test_dashboard_summary_large_pnl(http_client: AsyncClient) -> None:
    """B-18-11: Large P&L value (Numeric 14,2 boundary) serializes without overflow."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_dashboard_row(all_time_net_pnl=Decimal("99999999999999.99"))])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/dashboard/summary?account_id={_ACCOUNT_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200


async def test_dashboard_summary_missing_account_id_returns_422(
    http_client: AsyncClient,
) -> None:
    """B-18-11b: Missing required account_id query param → 422."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_dashboard_row()])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get("/v1/dashboard/summary")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 422


async def test_dashboard_summary_null_starting_capital(http_client: AsyncClient) -> None:
    """B-18-11c: starting_capital=None → realized_equity is also None."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_dashboard_row(starting_capital=None)])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/dashboard/summary?account_id={_ACCOUNT_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    body = response.json()
    assert body["starting_capital"] is None
    assert body["realized_equity"] is None


async def test_dashboard_summary_realized_equity_calculation(http_client: AsyncClient) -> None:
    """B-18-11d: realized_equity = starting_capital + all_time_net_pnl."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db(
        [_dashboard_row(starting_capital=Decimal("500000.00"), all_time_net_pnl=Decimal("27500.00"))]
    )
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/dashboard/summary?account_id={_ACCOUNT_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    body = response.json()
    assert Decimal(body["realized_equity"]) == Decimal("527500.00")


async def test_dashboard_summary_account_id_echoed_in_response(http_client: AsyncClient) -> None:
    """B-18-11e: account_id in the response matches the query param supplied."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_dashboard_row()])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/dashboard/summary?account_id={_ACCOUNT_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.json()["account_id"] == str(_ACCOUNT_ID)


# ---------------------------------------------------------------------------
# Trade list tests: B-18-12, B-18-12b, B-18-13, B-18-13b, B-18-14–21
# ---------------------------------------------------------------------------


async def test_list_trades_returns_200(http_client: AsyncClient) -> None:
    """B-18-12: GET /v1/trades returns 200 with list of trades."""
    from tradeforge.api.v1.trades import get_account_service
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_trade_list_row()])
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_account_service] = lambda: MagicMock()
    try:
        response = await http_client.get("/v1/trades")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_account_service, None)

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["symbol"] == "RELIANCE"


async def test_list_trades_status_partial_filter(http_client: AsyncClient) -> None:
    """B-18-12b: status=PARTIAL filter is accepted and returns 200."""
    from tradeforge.api.v1.trades import get_account_service
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_trade_list_row(status="PARTIAL")])
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_account_service] = lambda: MagicMock()
    try:
        response = await http_client.get("/v1/trades?status=PARTIAL")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_account_service, None)

    assert response.status_code == 200


async def test_list_trades_invalid_status_returns_422(http_client: AsyncClient) -> None:
    """B-18-13: status=INVALID → 422 INVALID_STATUS."""
    from tradeforge.api.v1.trades import get_account_service
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([])
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_account_service] = lambda: MagicMock()
    try:
        response = await http_client.get("/v1/trades?status=INVALID")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_account_service, None)

    assert response.status_code == 422
    assert response.json()["detail"] == "INVALID_STATUS"


async def test_list_trades_lowercase_status_returns_422(http_client: AsyncClient) -> None:
    """B-18-13b: status=closed (lowercase) → 422 INVALID_STATUS (case-sensitive validation)."""
    from tradeforge.api.v1.trades import get_account_service
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([])
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_account_service] = lambda: MagicMock()
    try:
        response = await http_client.get("/v1/trades?status=closed")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_account_service, None)

    assert response.status_code == 422
    assert response.json()["detail"] == "INVALID_STATUS"


async def test_list_trades_sort_by_net_pnl(http_client: AsyncClient) -> None:
    """B-18-14: sort_by=net_pnl is whitelisted and returns 200."""
    from tradeforge.api.v1.trades import get_account_service
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_trade_list_row()])
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_account_service] = lambda: MagicMock()
    try:
        response = await http_client.get("/v1/trades?sort_by=net_pnl")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_account_service, None)

    assert response.status_code == 200


async def test_list_trades_sort_dir_asc(http_client: AsyncClient) -> None:
    """B-18-15: sort_dir=asc is accepted and returns 200."""
    from tradeforge.api.v1.trades import get_account_service
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_trade_list_row()])
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_account_service] = lambda: MagicMock()
    try:
        response = await http_client.get("/v1/trades?sort_dir=asc")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_account_service, None)

    assert response.status_code == 200


async def test_list_trades_invalid_sort_dir_returns_desc(http_client: AsyncClient) -> None:
    """B-18-15b: sort_dir=invalid silently defaults to desc — returns 200."""
    from tradeforge.api.v1.trades import get_account_service
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_trade_list_row()])
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_account_service] = lambda: MagicMock()
    try:
        response = await http_client.get("/v1/trades?sort_dir=RANDOM")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_account_service, None)

    assert response.status_code == 200


async def test_list_trades_unknown_sort_by_defaults_to_last_fill_at(
    http_client: AsyncClient,
) -> None:
    """B-18-15c: sort_by=unknown silently defaults to last_fill_at — returns 200."""
    from tradeforge.api.v1.trades import get_account_service
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_trade_list_row()])
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_account_service] = lambda: MagicMock()
    try:
        response = await http_client.get("/v1/trades?sort_by=nonexistent_column")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_account_service, None)

    assert response.status_code == 200


async def test_list_trades_status_open_filter(http_client: AsyncClient) -> None:
    """B-18-16: status=OPEN filter is accepted and returns 200."""
    from tradeforge.api.v1.trades import get_account_service
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_trade_list_row(status="OPEN")])
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_account_service] = lambda: MagicMock()
    try:
        response = await http_client.get("/v1/trades?status=OPEN")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_account_service, None)

    assert response.status_code == 200


async def test_list_trades_status_closed_filter(http_client: AsyncClient) -> None:
    """B-18-17: status=CLOSED filter is accepted and returns 200."""
    from tradeforge.api.v1.trades import get_account_service
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_trade_list_row(status="CLOSED")])
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_account_service] = lambda: MagicMock()
    try:
        response = await http_client.get("/v1/trades?status=CLOSED")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_account_service, None)

    assert response.status_code == 200


async def test_list_trades_account_id_filter(http_client: AsyncClient) -> None:
    """B-18-18: account_id filter is accepted and returns 200."""
    from tradeforge.api.v1.trades import get_account_service
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_trade_list_row()])
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_account_service] = lambda: MagicMock()
    try:
        response = await http_client.get(f"/v1/trades?account_id={_ACCOUNT_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_account_service, None)

    assert response.status_code == 200


async def test_list_trades_empty_result(http_client: AsyncClient) -> None:
    """B-18-19: Returns empty list when no matching trades exist."""
    from tradeforge.api.v1.trades import get_account_service
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([])
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_account_service] = lambda: MagicMock()
    try:
        response = await http_client.get("/v1/trades")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_account_service, None)

    assert response.status_code == 200
    assert response.json() == []


async def test_list_trades_pagination_limit(http_client: AsyncClient) -> None:
    """B-18-20: limit and offset query params are accepted."""
    from tradeforge.api.v1.trades import get_account_service
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_trade_list_row()])
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_account_service] = lambda: MagicMock()
    try:
        response = await http_client.get("/v1/trades?limit=10&offset=5")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_account_service, None)

    assert response.status_code == 200


async def test_list_trades_null_pnl_for_open_trade(http_client: AsyncClient) -> None:
    """B-18-21: net_pnl and r_multiple are null for OPEN trades (no trade_pnl row)."""
    from tradeforge.api.v1.trades import get_account_service
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_trade_list_row(status="OPEN", net_pnl=None, r_multiple=None)])
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_account_service] = lambda: MagicMock()
    try:
        response = await http_client.get("/v1/trades")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_account_service, None)

    body = response.json()
    assert body[0]["net_pnl"] is None
    assert body[0]["r_multiple"] is None


# ---------------------------------------------------------------------------
# Recent journal tests: B-18-22 through B-18-26
# ---------------------------------------------------------------------------


async def test_recent_journal_returns_200(http_client: AsyncClient) -> None:
    """B-18-22: GET /v1/journal/recent returns 200 with list."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_journal_row()])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get("/v1/journal/recent")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1


async def test_recent_journal_fields(http_client: AsyncClient) -> None:
    """B-18-23: Response includes expected fields for each entry."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_journal_row(symbol="INFY", direction="LONG", discipline_score=9)])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get("/v1/journal/recent")
    finally:
        app.dependency_overrides.pop(get_db, None)

    entry = response.json()[0]
    assert entry["symbol"] == "INFY"
    assert entry["direction"] == "LONG"
    assert entry["discipline_score"] == 9
    assert "emotion_before" in entry
    assert "created_at" in entry


async def test_recent_journal_empty(http_client: AsyncClient) -> None:
    """B-18-24: Returns empty list when no journal entries exist."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get("/v1/journal/recent")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json() == []


async def test_recent_journal_limit_param(http_client: AsyncClient) -> None:
    """B-18-25: limit query param is accepted (default 10)."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_journal_row()])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get("/v1/journal/recent?limit=5")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200


async def test_recent_journal_null_discipline_score(http_client: AsyncClient) -> None:
    """B-18-26: discipline_score may be null for entries with no score set."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db([_journal_row(discipline_score=None)])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get("/v1/journal/recent")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.json()[0]["discipline_score"] is None
