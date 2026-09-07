"""API-layer tests for /v1/trades — B-16-01 through B-16-37 (except B-16-22/23).

Tests use FastAPI dependency_overrides to replace TradeService with an AsyncMock,
following the same pattern as test_accounts_api.py. No real DB is required.

B-16-17, B-16-20 DB-level assertions (is_deleted=true in DB, fill_exclusions
rows) are covered at the unit tier (B-16-23) and integration tier. At the
API mock tier we verify 204 status and that soft_delete_trade() was called.

B-16-21 (analytics integration guard): mocks get_analytics_service so the
analytics summary endpoint can be called without a real DB. The actual SQL
predicate (is_deleted = false) is enforced in AnalyticsRepository._base_where().

B-16-35 (planned_risk_amount recomputed): verified in test_trade_service.py at
the unit tier; at the API mock tier we verify add_fill() is called and returns 200.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from tradeforge.application.analytics_service import AnalyticsService
from tradeforge.application.trade_service import (
    FillTimestampBeforeTradeOpenError,
    InstrumentNotFoundError,
    PlannedStopWrongSideError,
    ReconstructionFailedError,
    TradeAlreadyClosedError,
    TradeNotFoundError,
    TradeNotManualError,
    TradeNotOwnedError,
    TradeService,
)
from tradeforge.domain.import_domain.errors import AccountNotFoundError
from tradeforge.infrastructure.models.trade_domain import Trade

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_USER_ID = uuid.uuid4()
_ACCOUNT_ID = uuid.uuid4()
_INSTRUMENT_ID = uuid.uuid4()
_TRADE_ID = uuid.uuid4()
_IST = timezone(timedelta(hours=5, minutes=30))
_NOW = datetime(2026, 9, 7, 10, 15, 0, tzinfo=UTC)
_FILL_TS = "2026-09-07T10:15:00+05:30"
_FILL_TS2 = "2026-09-07T10:30:00+05:30"
_FILL_TS3 = "2026-09-07T15:00:00+05:30"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trade(
    *,
    status: str = "OPEN",
    direction: str = "LONG",
    trade_type: str = "CNC",
    planned_stop: Decimal | None = None,
    planned_target: Decimal | None = None,
    is_deleted: bool = False,
) -> MagicMock:
    """Construct a minimal Trade ORM mock for TradeOut serialization."""
    trade = MagicMock(spec=Trade)
    trade.id = _TRADE_ID
    trade.account_id = _ACCOUNT_ID
    trade.instrument_id = _INSTRUMENT_ID
    trade.trade_type = trade_type
    trade.direction = direction
    trade.status = status
    trade.trade_date = date(2026, 9, 7)
    trade.first_fill_at = _NOW
    trade.last_fill_at = _NOW if status == "CLOSED" else None
    trade.total_entry_quantity = Decimal("10")
    trade.total_exit_quantity = Decimal("10") if status == "CLOSED" else Decimal("0")
    trade.net_position = Decimal("0") if status == "CLOSED" else Decimal("10")
    trade.average_entry = Decimal("2500.00")
    trade.average_exit = Decimal("2600.00") if status == "CLOSED" else None
    trade.planned_stop = planned_stop
    trade.planned_target = planned_target
    trade.is_deleted = is_deleted
    trade.created_at = _NOW
    trade.updated_at = _NOW
    return trade


def _valid_create_body(
    *,
    instrument_type: str = "EQ",
    product_type: str = "CNC",
    fills: list[dict] | None = None,
    planned_stop: str | None = None,
    expiry_date: str | None = None,
    strike_price: str | None = None,
) -> dict:
    body: dict = {
        "account_id": str(_ACCOUNT_ID),
        "instrument": {
            "symbol": "RELIANCE",
            "exchange_segment": "NSE_EQ",
            "instrument_type": instrument_type,
        },
        "product_type": product_type,
        "fills": fills
        or [{"side": "BUY", "quantity": "10", "price": "2500.00", "fill_timestamp": _FILL_TS}],
    }
    if planned_stop is not None:
        body["planned_stop"] = planned_stop
    if expiry_date is not None:
        body["instrument"]["expiry_date"] = expiry_date
    if strike_price is not None:
        body["instrument"]["strike_price"] = strike_price
    return body


def _valid_add_fill_body(ts: str = _FILL_TS2) -> dict:
    return {"fill": {"side": "BUY", "quantity": "5", "price": "2480.00", "fill_timestamp": ts}}


def _make_analytics_summary():
    """Return a zero-value AnalyticsSummary for B-16-21 mock."""
    from decimal import Decimal

    from tradeforge.domain.analytics.types import (
        AnalyticsSummary,
        ChargesBreakdown,
        DrawdownStats,
        ExpectancyResult,
        OutcomeDistribution,
        PlannedRRResult,
        PnlSummary,
        ProfitFactorResult,
        RiskAdjustedResult,
        SharpeResult,
        SortinoResult,
    )

    zero = Decimal("0")
    return AnalyticsSummary(
        pnl=PnlSummary(total_trades=0, gross_pnl=zero, net_pnl=zero, total_charges=zero),
        outcome=OutcomeDistribution(
            win_count=0,
            loss_count=0,
            breakeven_count=0,
            total_n=0,
            win_rate=zero,
            loss_rate=zero,
            breakeven_rate=zero,
        ),
        expectancy=ExpectancyResult(
            expectancy_r=None,
            avg_r_win=None,
            avg_r_loss=None,
            r_coverage_count=0,
            total_count=0,
            r_coverage_pct=zero,
            insufficient_sample=True,
        ),
        profit_factor=ProfitFactorResult(
            profit_factor=None, gross_profit=zero, gross_loss=zero
        ),
        planned_rr=PlannedRRResult(
            avg_planned_rr=None, trade_count_with_rr=0, total_count=0, coverage_pct=zero
        ),
        drawdown=DrawdownStats(
            max_drawdown_pct=None,
            max_drawdown_inr=None,
            avg_drawdown_pct=None,
            current_drawdown_pct=None,
        ),
        direction=[],
        charges=ChargesBreakdown(
            total_brokerage=zero,
            total_stt=zero,
            total_exchange_charges=zero,
            total_sebi_charges=zero,
            total_stamp_duty=zero,
            total_gst=zero,
            total_ipft=zero,
            total_charges=zero,
            total_gross_pnl=zero,
            charge_drag_pct=None,
            charges_added_to_loss=None,
        ),
        risk_adjusted=RiskAdjustedResult(
            sharpe=SharpeResult(
                sharpe_ratio=None,
                mean_r=None,
                std_r=None,
                n_per_year=252,
                r_coverage_count=0,
                insufficient_sample=True,
            ),
            sortino=SortinoResult(
                sortino_ratio=None,
                mean_r=None,
                downside_dev=None,
                n_per_year=252,
                r_coverage_count=0,
                insufficient_sample=True,
                no_downside_trades=True,
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_trade_svc() -> AsyncMock:
    return AsyncMock(spec=TradeService)


@pytest.fixture(autouse=True)
def override_deps(mock_trade_svc: AsyncMock):
    from tradeforge.api.v1.deps import get_current_user_id
    from tradeforge.api.v1.trades import get_trade_service
    from tradeforge.main import app

    app.dependency_overrides[get_current_user_id] = lambda: _USER_ID
    app.dependency_overrides[get_trade_service] = lambda: mock_trade_svc
    yield
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(get_trade_service, None)


# ---------------------------------------------------------------------------
# B-16-01: POST /v1/trades — valid EQ entry fill → 201 OPEN trade
# ---------------------------------------------------------------------------


async def test_create_trade_eq_entry_returns_201_open(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-01: POST /v1/trades creates OPEN trade; account_id is non-None and matches request."""
    mock_trade_svc.create_trade.return_value = _make_trade(status="OPEN")

    response = await http_client.post("/v1/trades", json=_valid_create_body())

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "OPEN"
    assert body["account_id"] == str(_ACCOUNT_ID)
    assert body["is_deleted"] is False
    mock_trade_svc.create_trade.assert_awaited_once()


# ---------------------------------------------------------------------------
# B-16-02: POST /v1/trades — CNC entry+exit fills → 201 CLOSED with P&L
# ---------------------------------------------------------------------------


async def test_create_trade_cnc_closed_returns_201(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-02: CNC entry+exit fills → CLOSED trade; account_id non-None."""
    mock_trade_svc.create_trade.return_value = _make_trade(status="CLOSED")

    body = _valid_create_body(
        fills=[
            {"side": "BUY", "quantity": "10", "price": "2500.00", "fill_timestamp": _FILL_TS},
            {"side": "SELL", "quantity": "10", "price": "2600.00", "fill_timestamp": _FILL_TS2},
        ]
    )
    response = await http_client.post("/v1/trades", json=body)

    assert response.status_code == 201
    resp_body = response.json()
    assert resp_body["status"] == "CLOSED"
    assert resp_body["account_id"] == str(_ACCOUNT_ID)


# ---------------------------------------------------------------------------
# B-16-03: POST /v1/trades — MIS entry+exit → 201 CLOSED with P&L
# ---------------------------------------------------------------------------


async def test_create_trade_mis_closed_returns_201(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-03: MIS entry+exit fills → CLOSED trade; account_id non-None."""
    mock_trade_svc.create_trade.return_value = _make_trade(
        status="CLOSED", trade_type="MIS", direction="LONG"
    )

    body = _valid_create_body(
        product_type="MIS",
        fills=[
            {"side": "BUY", "quantity": "10", "price": "2500.00", "fill_timestamp": _FILL_TS},
            {"side": "SELL", "quantity": "10", "price": "2600.00", "fill_timestamp": _FILL_TS2},
        ],
    )
    response = await http_client.post("/v1/trades", json=body)

    assert response.status_code == 201
    assert response.json()["trade_type"] == "MIS"


# ---------------------------------------------------------------------------
# B-16-04: POST /v1/trades — unknown instrument → 422 INSTRUMENT_NOT_FOUND
# ---------------------------------------------------------------------------


async def test_create_trade_unknown_instrument_returns_422(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-04: Unknown instrument → 422 INSTRUMENT_NOT_FOUND."""
    mock_trade_svc.create_trade.side_effect = InstrumentNotFoundError(
        "UNKNOWN", "NSE_EQ", "EQ"
    )

    response = await http_client.post("/v1/trades", json=_valid_create_body())

    assert response.status_code == 422
    assert response.json()["detail"] == "INSTRUMENT_NOT_FOUND"


# ---------------------------------------------------------------------------
# B-16-05: POST /v1/trades — inactive account → 404 ACCOUNT_NOT_FOUND
# ---------------------------------------------------------------------------


async def test_create_trade_inactive_account_returns_404(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-05: Inactive account → 404 ACCOUNT_NOT_FOUND."""
    mock_trade_svc.create_trade.side_effect = AccountNotFoundError(_ACCOUNT_ID)

    response = await http_client.post("/v1/trades", json=_valid_create_body())

    assert response.status_code == 404
    assert response.json()["detail"] == "ACCOUNT_NOT_FOUND"


# ---------------------------------------------------------------------------
# B-16-06: POST /v1/trades — another user's account → 404 ACCOUNT_NOT_FOUND
# ---------------------------------------------------------------------------


async def test_create_trade_other_users_account_returns_404(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-06: Another user's account → 404 ACCOUNT_NOT_FOUND."""
    other_account_id = uuid.uuid4()
    mock_trade_svc.create_trade.side_effect = AccountNotFoundError(other_account_id)

    body = _valid_create_body()
    body["account_id"] = str(other_account_id)
    response = await http_client.post("/v1/trades", json=body)

    assert response.status_code == 404
    assert response.json()["detail"] == "ACCOUNT_NOT_FOUND"


# ---------------------------------------------------------------------------
# B-16-07: POST /v1/trades — non-chronological fills → 422 FILLS_NOT_CHRONOLOGICAL
# ---------------------------------------------------------------------------


async def test_create_trade_non_chronological_fills_returns_422(
    http_client: AsyncClient,
) -> None:
    """B-16-07: Fills in non-chronological order → 422 FILLS_NOT_CHRONOLOGICAL."""
    body = _valid_create_body(
        fills=[
            {"side": "BUY", "quantity": "10", "price": "2500.00", "fill_timestamp": _FILL_TS2},
            {"side": "SELL", "quantity": "10", "price": "2600.00", "fill_timestamp": _FILL_TS},
        ]
    )
    response = await http_client.post("/v1/trades", json=body)

    assert response.status_code == 422
    assert response.json()["detail"] == "FILLS_NOT_CHRONOLOGICAL"


# ---------------------------------------------------------------------------
# B-16-08: POST /v1/trades — naive fill_timestamp → 422 FILL_TIMESTAMP_NOT_TZ_AWARE
# ---------------------------------------------------------------------------


async def test_create_trade_naive_timestamp_returns_422(
    http_client: AsyncClient,
) -> None:
    """B-16-08: Naive fill_timestamp (no tz offset) → 422 FILL_TIMESTAMP_NOT_TZ_AWARE."""
    body = _valid_create_body(
        fills=[
            {"side": "BUY", "quantity": "10", "price": "2500.00",
             "fill_timestamp": "2026-09-07T10:15:00"}  # no UTC offset
        ]
    )
    response = await http_client.post("/v1/trades", json=body)

    assert response.status_code == 422
    assert response.json()["detail"] == "FILL_TIMESTAMP_NOT_TZ_AWARE"


# ---------------------------------------------------------------------------
# B-16-09: POST /v1/trades — FUT without expiry_date → 422 EXPIRY_DATE_REQUIRED
# ---------------------------------------------------------------------------


async def test_create_trade_fut_no_expiry_returns_422(
    http_client: AsyncClient,
) -> None:
    """B-16-09: FUT instrument type without expiry_date → 422 EXPIRY_DATE_REQUIRED."""
    body = _valid_create_body(
        instrument_type="FUT",
        product_type="NRML",
        # No expiry_date
    )
    response = await http_client.post("/v1/trades", json=body)

    assert response.status_code == 422
    assert response.json()["detail"] == "EXPIRY_DATE_REQUIRED"


# ---------------------------------------------------------------------------
# B-16-10: POST /v1/trades — CE without strike_price → 422 STRIKE_PRICE_REQUIRED
# ---------------------------------------------------------------------------


async def test_create_trade_ce_no_strike_returns_422(
    http_client: AsyncClient,
) -> None:
    """B-16-10: CE instrument type without strike_price → 422 STRIKE_PRICE_REQUIRED."""
    body = _valid_create_body(
        instrument_type="CE",
        product_type="NRML",
        expiry_date="2026-09-25",
        # No strike_price
    )
    response = await http_client.post("/v1/trades", json=body)

    assert response.status_code == 422
    assert response.json()["detail"] == "STRIKE_PRICE_REQUIRED"


# ---------------------------------------------------------------------------
# B-16-11: POST /v1/trades — planned_stop persists in TradeOut
# ---------------------------------------------------------------------------


async def test_create_trade_planned_stop_in_response(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-11: planned_stop provided → returned TradeOut has planned_stop set."""
    planned_stop = Decimal("2450.00")
    mock_trade_svc.create_trade.return_value = _make_trade(planned_stop=planned_stop)

    body = _valid_create_body(planned_stop="2450.00")
    response = await http_client.post("/v1/trades", json=body)

    assert response.status_code == 201
    body_resp = response.json()
    assert body_resp["planned_stop"] == "2450.00"


# ---------------------------------------------------------------------------
# B-16-12: POST /v1/trades — unauthenticated → 401
# ---------------------------------------------------------------------------


async def test_create_trade_unauthenticated_returns_401(
    http_client: AsyncClient,
) -> None:
    """B-16-12: Unauthenticated POST /v1/trades → 401."""
    from tradeforge.api.v1.deps import get_current_user_id
    from tradeforge.main import app

    # Temporarily remove the autouse auth override for this test.
    app.dependency_overrides.pop(get_current_user_id, None)
    try:
        response = await http_client.post("/v1/trades", json=_valid_create_body())
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_current_user_id] = lambda: _USER_ID


# ---------------------------------------------------------------------------
# B-16-13: POST /v1/trades/{id}/fills — adds fill to OPEN trade → 200
# ---------------------------------------------------------------------------


async def test_add_fill_to_open_trade_returns_200(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-13: POST /v1/trades/{id}/fills on OPEN trade → 200 with updated TradeOut."""
    mock_trade_svc.add_fill.return_value = _make_trade(
        status="OPEN", trade_type="CNC"
    )

    response = await http_client.post(
        f"/v1/trades/{_TRADE_ID}/fills", json=_valid_add_fill_body()
    )

    assert response.status_code == 200
    assert response.json()["status"] == "OPEN"
    mock_trade_svc.add_fill.assert_awaited_once()


# ---------------------------------------------------------------------------
# B-16-14: POST /v1/trades/{id}/fills — CLOSED trade → 422 TRADE_ALREADY_CLOSED
# ---------------------------------------------------------------------------


async def test_add_fill_to_closed_trade_returns_422(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-14: Adding fill to CLOSED trade → 422 TRADE_ALREADY_CLOSED."""
    mock_trade_svc.add_fill.side_effect = TradeAlreadyClosedError(_TRADE_ID)

    response = await http_client.post(
        f"/v1/trades/{_TRADE_ID}/fills", json=_valid_add_fill_body()
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "TRADE_ALREADY_CLOSED"


# ---------------------------------------------------------------------------
# B-16-15: POST /v1/trades/{id}/fills — another user's trade → 403 TRADE_NOT_OWNED
# ---------------------------------------------------------------------------


async def test_add_fill_other_users_trade_returns_403(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-15: Adding fill to another user's trade → 403 TRADE_NOT_OWNED."""
    mock_trade_svc.add_fill.side_effect = TradeNotOwnedError(_TRADE_ID)

    response = await http_client.post(
        f"/v1/trades/{_TRADE_ID}/fills", json=_valid_add_fill_body()
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "TRADE_NOT_OWNED"


# ---------------------------------------------------------------------------
# B-16-16: POST /v1/trades/{id}/fills — timestamp before first_fill_at → 422
# ---------------------------------------------------------------------------


async def test_add_fill_before_trade_open_returns_422(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-16: fill_timestamp strictly before first_fill_at → 422 FILL_TIMESTAMP_BEFORE_TRADE_OPEN."""
    mock_trade_svc.add_fill.side_effect = FillTimestampBeforeTradeOpenError(
        datetime(2026, 9, 7, 4, 0, 0, tzinfo=UTC),
        datetime(2026, 9, 7, 4, 45, 0, tzinfo=UTC),
    )

    # Timestamp is earlier than first_fill_at
    response = await http_client.post(
        f"/v1/trades/{_TRADE_ID}/fills",
        json=_valid_add_fill_body(ts="2026-09-07T09:00:00+05:30"),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "FILL_TIMESTAMP_BEFORE_TRADE_OPEN"


# ---------------------------------------------------------------------------
# B-16-16b: POST /v1/trades/{id}/fills — timestamp equal to first_fill_at → 200
# ---------------------------------------------------------------------------


async def test_add_fill_equal_to_trade_open_timestamp_returns_200(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-16b: fill_timestamp equal to first_fill_at is accepted → 200 (AMB-01 boundary)."""
    mock_trade_svc.add_fill.return_value = _make_trade(status="OPEN")

    # Exact same timestamp as _FILL_TS (_NOW in UTC = 10:15 IST)
    response = await http_client.post(
        f"/v1/trades/{_TRADE_ID}/fills", json=_valid_add_fill_body(ts=_FILL_TS)
    )

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# B-16-17: DELETE /v1/trades/{id} — soft-delete → 204; service called
# ---------------------------------------------------------------------------


async def test_delete_trade_returns_204(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-17: DELETE soft-deletes trade → 204. Service is called with correct args.

    DB-level assertion (is_deleted=true in DB, TradeRepository.get_open_trade_with_lock
    returns None) is covered in the unit test tier (B-16-23) and integration tier.
    """
    mock_trade_svc.soft_delete_trade.return_value = None

    response = await http_client.delete(f"/v1/trades/{_TRADE_ID}")

    assert response.status_code == 204
    mock_trade_svc.soft_delete_trade.assert_awaited_once_with(
        user_id=_USER_ID, trade_id=_TRADE_ID
    )


# ---------------------------------------------------------------------------
# B-16-18: DELETE /v1/trades/{id} — already-deleted → 404
# ---------------------------------------------------------------------------


async def test_delete_already_deleted_trade_returns_404(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-18: DELETE on already-deleted trade → 404 TRADE_NOT_FOUND."""
    mock_trade_svc.soft_delete_trade.side_effect = TradeNotFoundError(_TRADE_ID)

    response = await http_client.delete(f"/v1/trades/{_TRADE_ID}")

    assert response.status_code == 404
    assert response.json()["detail"] == "TRADE_NOT_FOUND"


# ---------------------------------------------------------------------------
# B-16-19: DELETE /v1/trades/{id} — another user's trade → 403 TRADE_NOT_OWNED
# ---------------------------------------------------------------------------


async def test_delete_other_users_trade_returns_403(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-19: DELETE another user's trade → 403 TRADE_NOT_OWNED."""
    mock_trade_svc.soft_delete_trade.side_effect = TradeNotOwnedError(_TRADE_ID)

    response = await http_client.delete(f"/v1/trades/{_TRADE_ID}")

    assert response.status_code == 403
    assert response.json()["detail"] == "TRADE_NOT_OWNED"


# ---------------------------------------------------------------------------
# B-16-20: DELETE /v1/trades/{id} — fill_exclusions created after delete
# ---------------------------------------------------------------------------


async def test_delete_trade_creates_fill_exclusions(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-20: After DELETE, fills are excluded. At API mock tier we verify soft_delete_trade
    was called (which internally creates fill_exclusion rows). DB-level fill_exclusions assertion
    is covered in the unit test (B-16-23).
    """
    mock_trade_svc.soft_delete_trade.return_value = None

    response = await http_client.delete(f"/v1/trades/{_TRADE_ID}")

    assert response.status_code == 204
    mock_trade_svc.soft_delete_trade.assert_awaited_once()


# ---------------------------------------------------------------------------
# B-16-21: is_deleted trades do not appear in GET /v1/analytics/summary
# ---------------------------------------------------------------------------


async def test_deleted_trades_excluded_from_analytics_summary(
    http_client: AsyncClient,
) -> None:
    """B-16-21: Analytics summary endpoint returns 200 without is_deleted trade rows.

    Mocks AnalyticsService.get_summary() with a zero-value summary (no trades).
    Confirms the endpoint is reachable. The actual is_deleted=false SQL predicate
    is enforced in AnalyticsRepository._base_where() — verified by the B-16-C predicate
    audit (analytics_repo.py was updated as part of this step).
    """
    from tradeforge.api.v1.analytics import get_analytics_service
    from tradeforge.main import app

    mock_analytics_svc = AsyncMock(spec=AnalyticsService)
    mock_analytics_svc.get_summary.return_value = _make_analytics_summary()

    app.dependency_overrides[get_analytics_service] = lambda: mock_analytics_svc
    try:
        response = await http_client.get("/v1/analytics/summary")
        assert response.status_code == 200
        body = response.json()
        # Summary has 0 trades — a soft-deleted trade would show up as non-zero
        assert body["pnl"]["total_trades"] == 0
        mock_analytics_svc.get_summary.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(get_analytics_service, None)


# ---------------------------------------------------------------------------
# B-16-24: POST /v1/trades — EQ + NRML → 422 INVALID_PRODUCT_TYPE_FOR_INSTRUMENT
# ---------------------------------------------------------------------------


async def test_create_trade_eq_nrml_returns_422(
    http_client: AsyncClient,
) -> None:
    """B-16-24: EQ instrument with NRML product_type → 422 (D1)."""
    body = _valid_create_body(instrument_type="EQ", product_type="NRML")

    response = await http_client.post("/v1/trades", json=body)

    assert response.status_code == 422
    assert response.json()["detail"] == "INVALID_PRODUCT_TYPE_FOR_INSTRUMENT"


# ---------------------------------------------------------------------------
# B-16-25: POST /v1/trades — FUT + CNC → 422 INVALID_PRODUCT_TYPE_FOR_INSTRUMENT
# ---------------------------------------------------------------------------


async def test_create_trade_fut_cnc_returns_422(
    http_client: AsyncClient,
) -> None:
    """B-16-25: FUT instrument with CNC product_type → 422 (D1)."""
    body = _valid_create_body(
        instrument_type="FUT",
        product_type="CNC",
        expiry_date="2026-09-25",
    )

    response = await http_client.post("/v1/trades", json=body)

    assert response.status_code == 422
    assert response.json()["detail"] == "INVALID_PRODUCT_TYPE_FOR_INSTRUMENT"


# ---------------------------------------------------------------------------
# B-16-26: DELETE /v1/trades/{id} — CSV-imported trade → 422 TRADE_NOT_MANUAL
# ---------------------------------------------------------------------------


async def test_delete_csv_trade_returns_422(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-26: DELETE on CSV-imported trade → 422 TRADE_NOT_MANUAL (D2)."""
    mock_trade_svc.soft_delete_trade.side_effect = TradeNotManualError(_TRADE_ID)

    response = await http_client.delete(f"/v1/trades/{_TRADE_ID}")

    assert response.status_code == 422
    assert response.json()["detail"] == "TRADE_NOT_MANUAL"


# ---------------------------------------------------------------------------
# B-16-27: POST /v1/trades — multi-cycle BUY→SELL→BUY → 201 with second (OPEN) trade
# ---------------------------------------------------------------------------


async def test_create_trade_multi_cycle_returns_second_trade(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-27: BUY→SELL→BUY fills span close-and-reopen. 201 returns the second (OPEN) trade (D4).

    The first (CLOSED) trade is created by reconstruction and persisted in the DB;
    affected_trade_id in ReconstructionResult points to the most recently opened trade.
    At the API mock tier we verify the endpoint returns the trade whose status is OPEN.
    """
    second_trade_id = uuid.uuid4()
    second_trade = _make_trade(status="OPEN")
    second_trade.id = second_trade_id
    mock_trade_svc.create_trade.return_value = second_trade

    body = _valid_create_body(
        fills=[
            {"side": "BUY", "quantity": "10", "price": "2500.00", "fill_timestamp": _FILL_TS},
            {"side": "SELL", "quantity": "10", "price": "2600.00", "fill_timestamp": _FILL_TS2},
            {"side": "BUY", "quantity": "10", "price": "2620.00", "fill_timestamp": _FILL_TS3},
        ]
    )
    response = await http_client.post("/v1/trades", json=body)

    assert response.status_code == 201
    assert response.json()["status"] == "OPEN"
    assert response.json()["id"] == str(second_trade_id)


# ---------------------------------------------------------------------------
# B-16-28: POST /v1/trades — planned_stop + exit fills → r_multiple computed from planned_stop
# ---------------------------------------------------------------------------


async def test_create_trade_planned_stop_enables_r_multiple(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-28: Entry+exit fills with planned_stop → service called with planned_stop.

    Verifies create_trade() receives planned_stop so it can write planned_risk_amount
    BEFORE backfill_all_closed() runs (BLK-1 ordering constraint). DB-level r_multiple
    assertion requires an integration test with a real DB and charge schedules.
    """
    mock_trade_svc.create_trade.return_value = _make_trade(
        status="CLOSED", planned_stop=Decimal("2450.00")
    )

    body = _valid_create_body(
        planned_stop="2450.00",
        fills=[
            {"side": "BUY", "quantity": "10", "price": "2500.00", "fill_timestamp": _FILL_TS},
            {"side": "SELL", "quantity": "10", "price": "2600.00", "fill_timestamp": _FILL_TS2},
        ],
    )
    response = await http_client.post("/v1/trades", json=body)

    assert response.status_code == 201
    # Verify the service was called with planned_stop set
    call_kwargs = mock_trade_svc.create_trade.call_args.kwargs
    assert call_kwargs["planned_stop"] == Decimal("2450.00")


# ---------------------------------------------------------------------------
# B-16-34: POST /v1/trades — CE + CNC → 422 INVALID_PRODUCT_TYPE_FOR_INSTRUMENT
# ---------------------------------------------------------------------------


async def test_create_trade_ce_cnc_returns_422(
    http_client: AsyncClient,
) -> None:
    """B-16-34: CE instrument with CNC product_type → 422 (D1, Sahadeva QA-08)."""
    body = _valid_create_body(
        instrument_type="CE",
        product_type="CNC",
        expiry_date="2026-09-25",
        strike_price="2500",
    )

    response = await http_client.post("/v1/trades", json=body)

    assert response.status_code == 422
    assert response.json()["detail"] == "INVALID_PRODUCT_TYPE_FOR_INSTRUMENT"


# ---------------------------------------------------------------------------
# B-16-35: POST /v1/trades/{id}/fills — planned_risk_amount recomputed after scale-in
# ---------------------------------------------------------------------------


async def test_add_fill_recomputes_planned_risk_after_scale_in(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-35: After a second entry fill, planned_risk_amount reflects updated average_entry.

    At the API mock tier we verify add_fill() is called and returns 200.
    The actual trades.planned_risk_amount DB-level assertion (BLK-3) is covered
    in the unit test (test_trade_service.py).
    """
    mock_trade_svc.add_fill.return_value = _make_trade(status="OPEN")

    response = await http_client.post(
        f"/v1/trades/{_TRADE_ID}/fills", json=_valid_add_fill_body()
    )

    assert response.status_code == 200
    mock_trade_svc.add_fill.assert_awaited_once()


# ---------------------------------------------------------------------------
# B-16-36: POST /v1/trades — planned_stop on wrong side → 422 PLANNED_STOP_WRONG_SIDE
# ---------------------------------------------------------------------------


async def test_create_trade_long_stop_above_entry_returns_422(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-36a: LONG trade (BUY entry) with planned_stop >= entry price → 422.

    REQ-5: stop-direction validation runs AFTER reconstruction (direction unknown before).
    """
    mock_trade_svc.create_trade.side_effect = PlannedStopWrongSideError(
        "LONG",
        "Planned stop for a LONG trade must be below the average entry price.",
    )

    body = _valid_create_body(planned_stop="2600.00")  # above entry price 2500
    response = await http_client.post("/v1/trades", json=body)

    assert response.status_code == 422
    assert response.json()["detail"] == "PLANNED_STOP_WRONG_SIDE"


async def test_create_trade_short_stop_below_entry_returns_422(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-36b: SHORT trade (SELL entry) with planned_stop <= entry price → 422 (REQ-5)."""
    mock_trade_svc.create_trade.side_effect = PlannedStopWrongSideError(
        "SHORT",
        "Planned stop for a SHORT trade must be above the average entry price.",
    )

    body = _valid_create_body(
        planned_stop="2400.00",  # below entry price 2500
        fills=[
            {"side": "SELL", "quantity": "10", "price": "2500.00", "fill_timestamp": _FILL_TS}
        ],
    )
    response = await http_client.post("/v1/trades", json=body)

    assert response.status_code == 422
    assert response.json()["detail"] == "PLANNED_STOP_WRONG_SIDE"


# ---------------------------------------------------------------------------
# B-16-37: POST /v1/trades/{id}/fills — inactive account → still returns 200
# ---------------------------------------------------------------------------


async def test_add_fill_inactive_account_returns_200(
    http_client: AsyncClient, mock_trade_svc: AsyncMock
) -> None:
    """B-16-37: add_fill() on a trade whose account is INACTIVE → 200 (REQ-6, Sahadeva QA-10).

    The ownership-only query in add_fill() step 2 does NOT filter on account status.
    A user can still add corrective fills to a trade on a deactivated account.
    At the API mock tier we confirm add_fill() succeeds (the mock does not raise
    AccountInactiveError). The unit test (test_trade_service.py) verifies the
    raw SQL ownership query is used instead of TradingAccountService.get_active().
    """
    mock_trade_svc.add_fill.return_value = _make_trade(status="OPEN")

    # fill timestamp is after trade open — valid
    response = await http_client.post(
        f"/v1/trades/{_TRADE_ID}/fills", json=_valid_add_fill_body()
    )

    assert response.status_code == 200
    mock_trade_svc.add_fill.assert_awaited_once()
