"""Unit tests for TradeService — B-16-22, B-16-23, B-16-35, B-16-37.

TradeService.__init__ constructs all repositories internally. Tests replace
the repo attributes with AsyncMocks after construction to avoid patching at
the class level and to maintain full control over return values.

These tests do not hit any external process (no DB, no Redis, no network).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from tradeforge.application.trade_service import TradeService
from tradeforge.domain.import_domain.types import TradingAccount
from tradeforge.domain.trade.types import ReconstructionResult
from tradeforge.infrastructure.models.trade_domain import ExecutionFill, Trade

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_USER_ID = uuid.uuid4()
_ACCOUNT_ID = uuid.uuid4()
_INSTRUMENT_ID = uuid.uuid4()
_TRADE_ID = uuid.uuid4()
_FILL_ID_1 = uuid.uuid4()
_FILL_ID_2 = uuid.uuid4()
_UTC = UTC
_IST = timezone(timedelta(hours=5, minutes=30))
_NOW = datetime(2026, 9, 7, 4, 45, 0, tzinfo=UTC)  # 10:15 IST
_FILL_TS = datetime(2026, 9, 7, 4, 45, 0, tzinfo=UTC)  # 10:15 IST
_FILL_TS2 = datetime(2026, 9, 7, 5, 0, 0, tzinfo=UTC)  # 10:30 IST


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_account() -> TradingAccount:
    return TradingAccount(
        id=_ACCOUNT_ID,
        user_id=_USER_ID,
        broker="MANUAL",
        display_name="Test",
        account_type="INDIVIDUAL",
        base_currency="INR",
        status="ACTIVE",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_trade_orm(
    *,
    status: str = "OPEN",
    direction: str = "LONG",
    trade_type: str = "CNC",
    planned_stop: Decimal | None = None,
    is_deleted: bool = False,
    average_entry: Decimal | None = Decimal("2500.00"),
    total_entry_quantity: Decimal = Decimal("10"),
    net_position: Decimal = Decimal("10"),
) -> MagicMock:
    trade = MagicMock(spec=Trade)
    trade.id = _TRADE_ID
    trade.account_id = _ACCOUNT_ID
    trade.instrument_id = _INSTRUMENT_ID
    trade.trade_type = trade_type
    trade.direction = direction
    trade.status = status
    trade.trade_date = date(2026, 9, 7)
    trade.first_fill_at = _FILL_TS
    trade.last_fill_at = None
    trade.total_entry_quantity = average_entry  # reused
    trade.total_entry_quantity = total_entry_quantity
    trade.total_exit_quantity = Decimal("0")
    trade.net_position = net_position
    trade.average_entry = average_entry
    trade.average_exit = None
    trade.planned_stop = planned_stop
    trade.planned_target = None
    trade.planned_risk_amount = None
    trade.is_deleted = is_deleted
    trade.created_at = _NOW
    trade.updated_at = _NOW
    return trade


def _make_fill_orm(fill_id: uuid.UUID, import_source: str = "MANUAL") -> MagicMock:
    fill = MagicMock(spec=ExecutionFill)
    fill.id = fill_id
    fill.trade_id = _TRADE_ID
    fill.import_source = import_source
    fill.fill_role = "ENTRY"
    fill.side = "BUY"
    fill.quantity = Decimal("10")
    fill.price = Decimal("2500.00")
    fill.fill_timestamp = _FILL_TS
    return fill


def _make_service() -> TradeService:
    """Construct a TradeService with a fake session; replace all repos with mocks."""
    mock_session = AsyncMock()

    # Patch TaxLotRepository, ChargeScheduleRepository, PnlRepository constructors
    # so they don't need real DB drivers. The repos are set on the instance after.
    with (
        patch("tradeforge.application.trade_service.TaxLotRepository"),
        patch("tradeforge.application.trade_service.ChargeScheduleRepository"),
        patch("tradeforge.application.trade_service.PnlRepository"),
        patch("tradeforge.application.trade_service.TradingAccountService"),
        patch("tradeforge.application.trade_service.ReconstructionEngine"),
        patch("tradeforge.application.trade_service.PnlService"),
    ):
        svc = TradeService(session=mock_session)

    # Replace all internal attributes with full AsyncMocks.
    svc._session = mock_session
    svc._account_svc = AsyncMock()
    svc._instrument_repo = AsyncMock()
    svc._fill_repo = AsyncMock()
    svc._fill_exclusion_repo = AsyncMock()
    svc._trade_repo = AsyncMock()
    svc._pnl_service = AsyncMock()
    svc._engine = AsyncMock()
    return svc


# ---------------------------------------------------------------------------
# B-16-22: create_trade() resolves instrument, inserts fills, runs reconstruction
# ---------------------------------------------------------------------------


async def test_create_trade_calls_repos_and_engine() -> None:
    """B-16-22: create_trade() resolves instrument, inserts fills, calls engine, returns Trade."""
    svc = _make_service()

    # Account mock
    account = _make_account()
    svc._account_svc.get_active = AsyncMock(return_value=account)

    # Instrument repo mock — returns a valid instrument_id
    svc._instrument_repo.find_for_fill = AsyncMock(return_value=_INSTRUMENT_ID)

    # Fill repo mock — insert succeeds (returns None)
    svc._fill_repo.insert_normalized_fill = AsyncMock(return_value=None)

    # Session flush mock
    svc._session.flush = AsyncMock()

    # Reconstruction engine mock — returns a result with affected_trade_id set
    rr = ReconstructionResult(
        trades_opened=1,
        trades_closed=0,
        fills_processed=1,
        affected_trade_id=_TRADE_ID,
    )
    svc._engine.run = AsyncMock(return_value=rr)

    # Trade row mock returned by session.get
    trade_orm = _make_trade_orm(status="OPEN")
    svc._session.get = AsyncMock(return_value=trade_orm)
    svc._session.refresh = AsyncMock()

    # PnlService — not called since no trades closed
    svc._pnl_service.backfill_all_closed = AsyncMock()

    # TradeRepo update_trade — not called since no planned_stop
    svc._trade_repo.update_trade = AsyncMock()

    result = await svc.create_trade(
        user_id=_USER_ID,
        account_id=_ACCOUNT_ID,
        instrument_symbol="RELIANCE",
        exchange_segment="NSE_EQ",
        instrument_type="EQ",
        product_type="CNC",
        fills=[
            {
                "side": "BUY",
                "quantity": Decimal("10"),
                "price": Decimal("2500.00"),
                "fill_timestamp": _FILL_TS,
            }
        ],
    )

    # Instrument was resolved
    svc._instrument_repo.find_for_fill.assert_awaited_once()

    # Fill was inserted (one fill)
    svc._fill_repo.insert_normalized_fill.assert_awaited_once()

    # Engine was called
    svc._engine.run.assert_awaited_once()

    # PnlService was NOT called (no closed trades)
    svc._pnl_service.backfill_all_closed.assert_not_awaited()

    # Returned the Trade ORM row
    assert result is trade_orm


# ---------------------------------------------------------------------------
# B-16-23: soft_delete_trade() excludes fills and sets is_deleted
# ---------------------------------------------------------------------------


async def test_soft_delete_trade_excludes_fills_and_marks_deleted() -> None:
    """B-16-23: soft_delete_trade() creates fill_exclusion records and sets is_deleted=True."""
    svc = _make_service()

    # Trade exists and is not soft-deleted
    trade_orm = _make_trade_orm(is_deleted=False)
    svc._session.get = AsyncMock(return_value=trade_orm)

    # Ownership query returns a row → user owns the trade
    ownership_result = MagicMock()
    ownership_result.one_or_none.return_value = (_ACCOUNT_ID,)
    svc._session.execute = AsyncMock(side_effect=_make_execute_side_effect(ownership_result))

    # Both fills are MANUAL
    fill1 = _make_fill_orm(_FILL_ID_1, import_source="MANUAL")
    fill2 = _make_fill_orm(_FILL_ID_2, import_source="MANUAL")

    # scalars().all() returns the fills list
    fills_result = MagicMock()
    fills_result.scalars.return_value.all.return_value = [fill1, fill2]

    # Batch exclusion query — no fills already excluded
    svc._fill_exclusion_repo.get_excluded_fill_ids_for_trade = AsyncMock(return_value=set())
    svc._fill_exclusion_repo.create_exclusion = AsyncMock(return_value=uuid.uuid4())
    svc._trade_repo.update_trade = AsyncMock()

    # Patch session.execute to return fills on second call
    exec_calls = [ownership_result, fills_result]
    exec_idx = [0]

    async def _execute_side_effect(*args, **kwargs):
        idx = exec_idx[0]
        exec_idx[0] += 1
        return exec_calls[idx]

    svc._session.execute = _execute_side_effect  # type: ignore[method-assign]

    await svc.soft_delete_trade(user_id=_USER_ID, trade_id=_TRADE_ID)

    # Both fills must have exclusion records created
    assert svc._fill_exclusion_repo.create_exclusion.await_count == 2

    # Trade must be marked is_deleted=True (and status unchanged)
    svc._trade_repo.update_trade.assert_awaited_once_with(
        svc._session, _TRADE_ID, {"is_deleted": True}
    )


# ---------------------------------------------------------------------------
# B-16-35: add_fill() recomputes planned_risk_amount after reconstruction (BLK-3)
# ---------------------------------------------------------------------------


async def test_add_fill_recomputes_planned_risk_amount_after_scale_in() -> None:
    """B-16-35: add_fill() calls update_trade with abs(new_avg_entry - stop) * new_qty.

    BLK-3 (Dhanvantari): after scale-in reconstruction updates average_entry and
    total_entry_quantity, planned_risk_amount must be recomputed and written back
    before backfill_all_closed runs. This unit test is the regression guard referenced
    by the mock-tier API test (test_trades_api.py::test_add_fill_recomputes_planned_risk_after_scale_in).
    """
    svc = _make_service()

    # Initial trade: LONG, stop=2450, avg_entry=2500, qty=10
    trade_row = _make_trade_orm(
        direction="LONG",
        planned_stop=Decimal("2450.00"),
        average_entry=Decimal("2500.00"),
        total_entry_quantity=Decimal("10"),
        status="OPEN",
    )
    trade_row.first_fill_at = _FILL_TS
    trade_row.status = "OPEN"

    # After reconstruction: scaled in at 2480 → avg_entry=2490, qty=20
    updated_trade = _make_trade_orm(
        direction="LONG",
        planned_stop=Decimal("2450.00"),
        average_entry=Decimal("2490.00"),
        total_entry_quantity=Decimal("20"),
        status="OPEN",
    )

    trade_final = _make_trade_orm(status="OPEN")
    trade_final.planned_risk_amount = Decimal("800.00")

    get_sequence = [trade_row, updated_trade, trade_final]
    get_idx = [0]

    async def _get(model, pk):
        i = get_idx[0]
        get_idx[0] += 1
        return get_sequence[i]

    svc._session.get = _get

    ownership_result = MagicMock()
    ownership_result.one_or_none.return_value = (_ACCOUNT_ID,)
    instrument_result = MagicMock()
    instrument_result.scalar_one_or_none.return_value = "EQ"

    exec_sequence = [ownership_result, instrument_result]
    exec_idx = [0]

    async def _execute(*args, **kwargs):
        i = exec_idx[0]
        exec_idx[0] += 1
        return exec_sequence[i]

    svc._session.execute = _execute
    svc._session.flush = AsyncMock()
    svc._fill_repo.insert_normalized_fill = AsyncMock(return_value=None)

    rr = ReconstructionResult(
        trades_opened=0, trades_closed=0, fills_processed=1, affected_trade_id=_TRADE_ID
    )
    svc._engine.run = AsyncMock(return_value=rr)
    svc._trade_repo.update_trade = AsyncMock()
    svc._pnl_service.backfill_all_closed = AsyncMock()

    await svc.add_fill(
        user_id=_USER_ID,
        trade_id=_TRADE_ID,
        fill_side="BUY",
        fill_quantity=Decimal("10"),
        fill_price=Decimal("2480.00"),
        fill_timestamp=_FILL_TS2,
    )

    # BLK-3: abs(2490 - 2450) * 20 = 800
    svc._trade_repo.update_trade.assert_awaited_once_with(
        svc._session, _TRADE_ID, {"planned_risk_amount": Decimal("800.00")}
    )
    # Ordering constraint: flush must be called after update_trade (before backfill)
    svc._pnl_service.backfill_all_closed.assert_not_awaited()


# ---------------------------------------------------------------------------
# B-16-37: add_fill() step 2 uses ownership-only SQL — no account status filter (REQ-6)
# ---------------------------------------------------------------------------


async def test_add_fill_ownership_query_does_not_filter_on_account_status() -> None:
    """B-16-37: add_fill() ownership SQL checks only user_id, NOT account status.

    REQ-6 (Dhanvantari): the raw SQL at step 2 must not include any account status
    filter. Using TradingAccountService.get_active() would block fills on trades whose
    account has since been deactivated — which is incorrect behaviour. A user with an
    open position on a deactivated account must still be able to add corrective fills.

    This unit test is the regression guard referenced by the mock-tier API test
    (test_trades_api.py::test_add_fill_inactive_account_returns_200). The mock-tier
    test confirms the HTTP response; this test confirms the SQL contract.
    """
    svc = _make_service()

    trade_row = _make_trade_orm(direction="LONG", status="OPEN")
    trade_row.first_fill_at = _FILL_TS
    trade_row.planned_stop = None

    trade_final = _make_trade_orm(status="OPEN")

    get_sequence = [trade_row, trade_final]
    get_idx = [0]

    async def _get(model, pk):
        i = get_idx[0]
        get_idx[0] += 1
        return get_sequence[i]

    svc._session.get = _get

    captured_execute_args: list = []

    ownership_result = MagicMock()
    ownership_result.one_or_none.return_value = (_ACCOUNT_ID,)
    instrument_result = MagicMock()
    instrument_result.scalar_one_or_none.return_value = "EQ"

    exec_sequence = [ownership_result, instrument_result]
    exec_idx = [0]

    async def _execute(*args, **kwargs):
        captured_execute_args.append(args)
        i = exec_idx[0]
        exec_idx[0] += 1
        return exec_sequence[i]

    svc._session.execute = _execute
    svc._session.flush = AsyncMock()
    svc._fill_repo.insert_normalized_fill = AsyncMock(return_value=None)

    rr = ReconstructionResult(
        trades_opened=0, trades_closed=0, fills_processed=1, affected_trade_id=_TRADE_ID
    )
    svc._engine.run = AsyncMock(return_value=rr)
    svc._trade_repo.update_trade = AsyncMock()
    svc._pnl_service.backfill_all_closed = AsyncMock()

    result = await svc.add_fill(
        user_id=_USER_ID,
        trade_id=_TRADE_ID,
        fill_side="BUY",
        fill_quantity=Decimal("10"),
        fill_price=Decimal("2480.00"),
        fill_timestamp=_FILL_TS2,
    )

    # Fill succeeded — ownership confirmed even when account status is not checked
    assert result is trade_final

    # REQ-6: the ownership SQL must not contain 'status' or 'active'
    assert len(captured_execute_args) >= 1
    ownership_sql = str(captured_execute_args[0][0]).lower()
    assert "status" not in ownership_sql, (
        f"Ownership query must NOT filter on account status (REQ-6). "
        f"Found 'status' in: {ownership_sql}"
    )
    assert "active" not in ownership_sql, (
        f"Ownership query must NOT filter on 'active' status (REQ-6). "
        f"Found 'active' in: {ownership_sql}"
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_execute_side_effect(ownership_result):
    """Return the ownership_result mock only on the first execute() call."""

    async def _side_effect(*args, **kwargs):
        return ownership_result

    return _side_effect
