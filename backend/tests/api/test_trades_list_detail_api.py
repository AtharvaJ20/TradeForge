"""API-layer tests for Step 19 — Trade List (B-19-A) and Trade Detail (B-19-B).

Uses the FastAPI dependency_overrides pattern to mock the DB session and auth
dependency — no real DB connections.

Test IDs:
  B-19-01 through B-19-12   — GET /v1/trades (new filters + envelope shape)
  B-19-13 through B-19-23   — GET /v1/trades/{trade_id} (trade detail)
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
_INSTR_ID = uuid.uuid4()
_FILL_ID = uuid.uuid4()

_FIRST_FILL_AT = datetime(2026, 9, 1, 9, 15, tzinfo=UTC)
_LAST_FILL_AT = datetime(2026, 9, 1, 11, 45, tzinfo=UTC)
_UNSET = object()  # sentinel to distinguish "not passed" from explicit None


# ---------------------------------------------------------------------------
# Row factories
# ---------------------------------------------------------------------------


def _trade_list_row(
    *,
    row_id: uuid.UUID | None = None,
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
    row.id = row_id or _TRADE_ID
    row.account_id = account_id or _ACCOUNT_ID
    row.symbol = symbol
    row.instrument_type = instrument_type
    row.direction = direction
    row.status = status
    row.trade_date = trade_date or date(2026, 9, 1)
    row.last_fill_at = last_fill_at or _LAST_FILL_AT
    row.net_pnl = net_pnl
    row.r_multiple = r_multiple
    return row


def _trade_detail_row(
    *,
    row_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
    symbol: str = "RELIANCE",
    instrument_name: str = "Reliance Industries Ltd",
    exchange_segment: str = "NSE_EQ",
    instrument_type: str = "EQ",
    expiry_date: date | None = None,
    strike_price: Decimal | None = None,
    direction: str = "LONG",
    trade_type: str = "CNC",
    status: str = "CLOSED",
    trade_date: date | None = None,
    first_fill_at: datetime | None = None,
    last_fill_at: object = _UNSET,  # use _UNSET to distinguish from explicit None
    total_entry_quantity: Decimal = Decimal("100"),
    total_exit_quantity: Decimal = Decimal("100"),
    average_entry: Decimal | None = Decimal("2500.00"),
    average_exit: Decimal | None = Decimal("2600.00"),
    planned_stop: Decimal | None = Decimal("2450.00"),
    planned_target: Decimal | None = Decimal("2650.00"),
    planned_risk_amount: Decimal | None = Decimal("5000.00"),
    setup_name: str | None = "Bull flag",
) -> MagicMock:
    row = MagicMock()
    row.id = row_id or _TRADE_ID
    row.account_id = account_id or _ACCOUNT_ID
    row.symbol = symbol
    row.instrument_name = instrument_name
    row.exchange_segment = exchange_segment
    row.instrument_type = instrument_type
    row.expiry_date = expiry_date
    row.strike_price = strike_price
    row.direction = direction
    row.trade_type = trade_type
    row.status = status
    row.trade_date = trade_date or date(2026, 9, 1)
    row.first_fill_at = first_fill_at or _FIRST_FILL_AT
    row.last_fill_at = _LAST_FILL_AT if last_fill_at is _UNSET else last_fill_at
    row.total_entry_quantity = total_entry_quantity
    row.total_exit_quantity = total_exit_quantity
    row.average_entry = average_entry
    row.average_exit = average_exit
    row.planned_stop = planned_stop
    row.planned_target = planned_target
    row.planned_risk_amount = planned_risk_amount
    row.setup_name = setup_name
    return row


def _fill_row(
    *,
    row_id: uuid.UUID | None = None,
    side: str = "BUY",
    quantity: Decimal = Decimal("100"),
    price: Decimal = Decimal("2500.00"),
    fill_role: str | None = "ENTRY",
    fill_timestamp: datetime | None = None,
    import_source: str = "MANUAL",
    broker: str = "ZERODHA",
) -> MagicMock:
    row = MagicMock()
    row.id = row_id or _FILL_ID
    row.side = side
    row.quantity = quantity
    row.price = price
    row.fill_role = fill_role
    row.fill_timestamp = fill_timestamp or _FIRST_FILL_AT
    row.import_source = import_source
    row.broker = broker
    return row


def _pnl_row(
    *,
    gross_pnl: Decimal = Decimal("10000.00"),
    net_pnl: Decimal = Decimal("9500.00"),
    total_charges: Decimal = Decimal("500.00"),
    brokerage: Decimal = Decimal("40.00"),
    stt: Decimal = Decimal("100.00"),
    exchange_charges: Decimal = Decimal("25.00"),
    sebi_charges: Decimal = Decimal("5.00"),
    stamp_duty: Decimal = Decimal("15.00"),
    gst: Decimal = Decimal("10.00"),
    ipft: Decimal = Decimal("5.00"),
    r_multiple: Decimal | None = Decimal("2.0"),
) -> MagicMock:
    row = MagicMock()
    row.gross_pnl = gross_pnl
    row.net_pnl = net_pnl
    row.total_charges = total_charges
    row.brokerage = brokerage
    row.stt = stt
    row.exchange_charges = exchange_charges
    row.sebi_charges = sebi_charges
    row.stamp_duty = stamp_duty
    row.gst = gst
    row.ipft = ipft
    row.r_multiple = r_multiple
    return row


# ---------------------------------------------------------------------------
# Mock DB helpers
# ---------------------------------------------------------------------------


def _make_mock_db_list(rows: list[Any], total: int | None = None) -> AsyncMock:
    """Two execute() calls: COUNT scalar, then .all() for data rows."""
    mock_db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = total if total is not None else len(rows)
    data_result = MagicMock()
    data_result.all.return_value = rows
    mock_db.execute.side_effect = [count_result, data_result]
    return mock_db


def _make_mock_db_detail(
    trade_row: MagicMock | None,
    fill_rows: list[MagicMock],
    pnl_row: MagicMock | None,
) -> AsyncMock:
    """Three execute() calls: trade one_or_none, fills all, pnl scalar_one_or_none."""
    mock_db = AsyncMock()

    trade_result = MagicMock()
    trade_result.one_or_none.return_value = trade_row

    fills_result = MagicMock()
    fills_result.all.return_value = fill_rows

    pnl_result = MagicMock()
    pnl_result.scalar_one_or_none.return_value = pnl_row

    mock_db.execute.side_effect = [trade_result, fills_result, pnl_result]
    return mock_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def override_user_id() -> None:
    from tradeforge.api.v1.deps import get_current_user_id
    from tradeforge.main import app

    app.dependency_overrides[get_current_user_id] = lambda: _USER_ID
    yield
    app.dependency_overrides.pop(get_current_user_id, None)


# ---------------------------------------------------------------------------
# B-19-A: list_trades new filters
# ---------------------------------------------------------------------------


async def test_list_trades_direction_long(http_client: AsyncClient) -> None:
    """B-19-01: direction=LONG is accepted and returns 200."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_list([_trade_list_row(direction="LONG")])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get("/v1/trades?direction=LONG")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200


async def test_list_trades_direction_short(http_client: AsyncClient) -> None:
    """B-19-02: direction=SHORT is accepted and returns 200."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_list([_trade_list_row(direction="SHORT")])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get("/v1/trades?direction=SHORT")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200


async def test_list_trades_invalid_direction_returns_422(http_client: AsyncClient) -> None:
    """B-19-03: direction=INVALID → 422 INVALID_DIRECTION."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_list([])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get("/v1/trades?direction=INVALID")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 422
    assert response.json()["detail"] == "INVALID_DIRECTION"


async def test_list_trades_trade_type_mis(http_client: AsyncClient) -> None:
    """B-19-04: trade_type=MIS is accepted and returns 200."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_list([_trade_list_row()])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get("/v1/trades?trade_type=MIS")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200


async def test_list_trades_trade_type_nrml_opt(http_client: AsyncClient) -> None:
    """B-19-05: trade_type=NRML_OPT is accepted and returns 200."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_list([_trade_list_row()])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get("/v1/trades?trade_type=NRML_OPT")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200


async def test_list_trades_invalid_trade_type_returns_422(http_client: AsyncClient) -> None:
    """B-19-05b: trade_type=NRML (old value, not in whitelist) → 422 INVALID_TRADE_TYPE."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_list([])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get("/v1/trades?trade_type=NRML")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 422
    assert response.json()["detail"] == "INVALID_TRADE_TYPE"


async def test_list_trades_from_date_filter(http_client: AsyncClient) -> None:
    """B-19-06: from_date filter is accepted and returns 200."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_list([_trade_list_row()])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get("/v1/trades?from_date=2026-09-01")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200


async def test_list_trades_to_date_filter(http_client: AsyncClient) -> None:
    """B-19-07: to_date filter is accepted and returns 200."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_list([_trade_list_row()])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get("/v1/trades?to_date=2026-09-30")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200


async def test_list_trades_invalid_date_range_returns_422(http_client: AsyncClient) -> None:
    """B-19-08: from_date > to_date → 422 INVALID_DATE_RANGE."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_list([])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get("/v1/trades?from_date=2026-09-30&to_date=2026-09-01")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 422
    assert response.json()["detail"] == "INVALID_DATE_RANGE"


async def test_list_trades_instrument_prefix_filter(http_client: AsyncClient) -> None:
    """B-19-09: instrument prefix filter is accepted and returns 200."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_list([_trade_list_row(symbol="RELIANCE")])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get("/v1/trades?instrument=REL")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200


async def test_list_trades_limit_cap_101_returns_422(http_client: AsyncClient) -> None:
    """B-19-10: limit=101 exceeds new cap of 100 → 422 from FastAPI param validation."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_list([])
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get("/v1/trades?limit=101")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 422


async def test_list_trades_envelope_fields(http_client: AsyncClient) -> None:
    """B-19-11: Response envelope has items, total, limit, offset fields."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_list([_trade_list_row()], total=42)
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get("/v1/trades?limit=10&offset=5")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "total" in body
    assert "limit" in body
    assert "offset" in body
    assert body["limit"] == 10
    assert body["offset"] == 5


async def test_list_trades_total_reflects_count_not_items(http_client: AsyncClient) -> None:
    """B-19-12: total comes from COUNT query, not len(items) (supports pagination)."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_list([_trade_list_row()], total=99)
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get("/v1/trades?limit=1&offset=0")
    finally:
        app.dependency_overrides.pop(get_db, None)

    body = response.json()
    assert body["total"] == 99
    assert len(body["items"]) == 1


# ---------------------------------------------------------------------------
# B-19-B: get_trade_detail
# ---------------------------------------------------------------------------


async def test_get_trade_detail_returns_200(http_client: AsyncClient) -> None:
    """B-19-13: GET /v1/trades/{trade_id} returns 200 with TradeDetailOut shape."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_detail(
        trade_row=_trade_detail_row(),
        fill_rows=[_fill_row()],
        pnl_row=_pnl_row(),
    )
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/trades/{_TRADE_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(_TRADE_ID)
    assert "symbol" in body
    assert "instrument_name" in body
    assert "fills" in body
    assert "pnl" in body


async def test_get_trade_detail_not_found_returns_404(http_client: AsyncClient) -> None:
    """B-19-14: Non-existent trade_id → 404 TRADE_NOT_FOUND."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_detail(trade_row=None, fill_rows=[], pnl_row=None)
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/trades/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404
    assert response.json()["detail"] == "TRADE_NOT_FOUND"


async def test_get_trade_detail_wrong_owner_returns_404(http_client: AsyncClient) -> None:
    """B-19-14b: Trade owned by a different user → 404, not 403 (ownership via WHERE clause)."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    # The WHERE clause includes user_id, so a different user's trade returns no row.
    mock_db = _make_mock_db_detail(trade_row=None, fill_rows=[], pnl_row=None)
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/trades/{_TRADE_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404
    assert response.json()["detail"] == "TRADE_NOT_FOUND"


async def test_get_trade_detail_fills_populated(http_client: AsyncClient) -> None:
    """B-19-15: fills list is populated with fill data."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    fill = _fill_row(side="BUY", quantity=Decimal("100"), price=Decimal("2500.00"))
    mock_db = _make_mock_db_detail(
        trade_row=_trade_detail_row(),
        fill_rows=[fill],
        pnl_row=_pnl_row(),
    )
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/trades/{_TRADE_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    body = response.json()
    assert len(body["fills"]) == 1
    f = body["fills"][0]
    assert f["side"] == "BUY"
    assert Decimal(f["quantity"]) == Decimal("100")
    assert Decimal(f["price"]) == Decimal("2500.00")
    assert "fill_timestamp" in f
    assert "import_source" in f
    assert "broker" in f


async def test_get_trade_detail_pnl_populated(http_client: AsyncClient) -> None:
    """B-19-16: pnl block is populated when TradePnl row exists."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_detail(
        trade_row=_trade_detail_row(status="CLOSED"),
        fill_rows=[_fill_row()],
        pnl_row=_pnl_row(net_pnl=Decimal("9500.00"), gross_pnl=Decimal("10000.00")),
    )
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/trades/{_TRADE_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    body = response.json()
    assert body["pnl"] is not None
    assert Decimal(body["pnl"]["net_pnl"]) == Decimal("9500.00")
    assert Decimal(body["pnl"]["gross_pnl"]) == Decimal("10000.00")


async def test_get_trade_detail_pnl_null_for_open_trade(http_client: AsyncClient) -> None:
    """B-19-17: pnl is null when no TradePnl row (OPEN trade)."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_detail(
        trade_row=_trade_detail_row(status="OPEN", last_fill_at=None),
        fill_rows=[_fill_row()],
        pnl_row=None,
    )
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/trades/{_TRADE_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.json()["pnl"] is None


async def test_get_trade_detail_hold_duration_seconds(http_client: AsyncClient) -> None:
    """B-19-18: hold_duration_seconds = int((last_fill_at - first_fill_at).total_seconds())."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    first = datetime(2026, 9, 1, 9, 0, 0, tzinfo=UTC)
    last = datetime(2026, 9, 1, 11, 30, 0, tzinfo=UTC)
    expected_seconds = int((last - first).total_seconds())  # 9000

    mock_db = _make_mock_db_detail(
        trade_row=_trade_detail_row(first_fill_at=first, last_fill_at=last),
        fill_rows=[_fill_row()],
        pnl_row=_pnl_row(),
    )
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/trades/{_TRADE_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.json()["hold_duration_seconds"] == expected_seconds


async def test_get_trade_detail_hold_duration_none_for_open(http_client: AsyncClient) -> None:
    """B-19-19: hold_duration_seconds is None for OPEN trades (last_fill_at is None)."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_detail(
        trade_row=_trade_detail_row(status="OPEN", last_fill_at=None),
        fill_rows=[_fill_row()],
        pnl_row=None,
    )
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/trades/{_TRADE_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.json()["hold_duration_seconds"] is None


async def test_get_trade_detail_instrument_name_present(http_client: AsyncClient) -> None:
    """B-19-20: instrument_name field is populated from Instrument.name (G-19-6)."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_detail(
        trade_row=_trade_detail_row(instrument_name="Reliance Industries Ltd"),
        fill_rows=[_fill_row()],
        pnl_row=_pnl_row(),
    )
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/trades/{_TRADE_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.json()["instrument_name"] == "Reliance Industries Ltd"


async def test_get_trade_detail_pnl_all_seven_charges(http_client: AsyncClient) -> None:
    """B-19-21: All 7 charge columns are present in the pnl block."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_detail(
        trade_row=_trade_detail_row(),
        fill_rows=[_fill_row()],
        pnl_row=_pnl_row(),
    )
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/trades/{_TRADE_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    pnl = response.json()["pnl"]
    assert pnl is not None
    for charge in (
        "brokerage",
        "stt",
        "exchange_charges",
        "sebi_charges",
        "stamp_duty",
        "gst",
        "ipft",
    ):
        assert charge in pnl, f"Missing charge column: {charge}"


async def test_get_trade_detail_r_multiple_none(http_client: AsyncClient) -> None:
    """B-19-22: r_multiple is null in pnl block when TradePnl.r_multiple is None."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_detail(
        trade_row=_trade_detail_row(),
        fill_rows=[_fill_row()],
        pnl_row=_pnl_row(r_multiple=None),
    )
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/trades/{_TRADE_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.json()["pnl"]["r_multiple"] is None


async def test_get_trade_detail_fills_empty(http_client: AsyncClient) -> None:
    """B-19-23: fills list is empty when trade has no associated fills."""
    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    mock_db = _make_mock_db_detail(
        trade_row=_trade_detail_row(),
        fill_rows=[],
        pnl_row=_pnl_row(),
    )
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = await http_client.get(f"/v1/trades/{_TRADE_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.json()["fills"] == []
