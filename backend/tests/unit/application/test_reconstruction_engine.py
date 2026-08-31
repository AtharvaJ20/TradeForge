"""Application-layer unit tests for ReconstructionEngine.

ADR-001: Application | Unit tests | Domain only. Infrastructure mocked.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from tradeforge.application.trade.reconstruction import ReconstructionEngine
from tradeforge.domain.trade.errors import (
    PositionCrossingZeroError,
    ReconstructionAmbiguityError,
    ReconstructionConsistencyError,
    ReconstructionDataError,
)
from tradeforge.domain.trade.types import FillRecord, OpenTradeSnapshot
from tradeforge.infrastructure.repositories.fill_exclusion_repo import FillExclusionRepository
from tradeforge.infrastructure.repositories.fill_repo import FillRepository
from tradeforge.infrastructure.repositories.tax_lot_repo import TaxLotRepository
from tradeforge.infrastructure.repositories.trade_repo import TradeRepository

_USER = uuid.UUID("00000000-0000-0000-0000-000000000001")
_INST = uuid.UUID("00000000-0000-0000-0000-000000000002")
_TRADE_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
_TS = datetime(2026, 1, 15, 9, 30, 0, tzinfo=UTC)
_DATE = date(2026, 1, 15)
_DATE2 = date(2026, 1, 16)


def _fill(
    side,
    quantity,
    price,
    product_type="MIS",
    fill_id_str="F001",
    fill_timestamp=None,
    trade_date=None,
):
    return FillRecord(
        id=uuid.uuid4(),
        user_id=_USER,
        instrument_id=_INST,
        trade_id=None,
        fill_timestamp=fill_timestamp or _TS,
        trade_date=trade_date or _DATE,
        side=side,
        quantity=Decimal(quantity),
        price=Decimal(price),
        product_type=product_type,
        fill_id_str=fill_id_str,
        created_at=_TS,
        import_source="CSV",
    )


def _make_engine():
    fill_repo = AsyncMock(spec=FillRepository)
    trade_repo = AsyncMock(spec=TradeRepository)
    lot_repo = AsyncMock(spec=TaxLotRepository)
    excl_repo = AsyncMock(spec=FillExclusionRepository)
    engine = ReconstructionEngine(fill_repo, trade_repo, lot_repo, excl_repo)
    session = AsyncMock()
    return engine, fill_repo, trade_repo, lot_repo, session


def _open_trade_snapshot(
    direction="LONG",
    status="OPEN",
    total_entry_qty="100",
    total_exit_qty="0",
    net_position="100",
    average_entry="500.0000",
    trade_type="MIS",
    trade_date=None,
):
    return OpenTradeSnapshot(
        id=_TRADE_ID,
        direction=direction,
        status=status,
        trade_date=trade_date or _DATE,
        first_fill_at=_TS,
        total_entry_quantity=Decimal(total_entry_qty),
        total_exit_quantity=Decimal(total_exit_qty),
        net_position=Decimal(net_position),
        average_entry=Decimal(average_entry),
        trade_type=trade_type,
    )


def _make_open_lot(qty_remaining, qty_original=None, cost="500.0000"):
    lot = MagicMock()
    lot.id = uuid.uuid4()
    lot.quantity_remaining = qty_remaining
    lot.quantity_original = qty_original or qty_remaining
    lot.status = "OPEN"
    lot.cost_per_share = cost
    return lot


def _make_closed_lot():
    lot = MagicMock()
    lot.id = uuid.uuid4()
    lot.quantity_remaining = "0"
    lot.quantity_original = "100"
    lot.status = "CLOSED"
    lot.cost_per_share = "500.0000"
    return lot


class TestNoFills:
    async def test_no_unprocessed_fills_returns_zero(self):
        engine, fill_repo, trade_repo, lot_repo, session = _make_engine()
        trade_repo.get_open_trade_with_lock.return_value = None
        fill_repo.get_unprocessed_fills.return_value = []

        result = await engine.run(session, _USER, _INST, "MIS", "EQ")

        assert result.fills_processed == 0
        trade_repo.create_trade.assert_not_called()


class TestLongMISTrade:
    async def test_buy_sell_opens_and_closes(self):
        engine, fill_repo, trade_repo, lot_repo, session = _make_engine()
        trade_repo.get_open_trade_with_lock.return_value = None
        fill_repo.get_unprocessed_fills.return_value = [
            _fill("BUY", "100", "500"),
            _fill("SELL", "100", "510"),
        ]

        result = await engine.run(session, _USER, _INST, "MIS", "EQ")

        assert result.fills_processed == 2
        assert result.trades_opened == 1
        assert result.trades_closed == 1
        assert result.tax_lots_created == 0
        trade_repo.create_trade.assert_called_once()
        assert fill_repo.assign_trade.call_count == 2

    async def test_partial_exit_does_not_close(self):
        engine, fill_repo, trade_repo, lot_repo, session = _make_engine()
        trade_repo.get_open_trade_with_lock.return_value = None
        fill_repo.get_unprocessed_fills.return_value = [
            _fill("BUY", "100", "500"),
            _fill("SELL", "50", "510"),
        ]

        result = await engine.run(session, _USER, _INST, "MIS", "EQ")

        assert result.fills_processed == 2
        assert result.trades_opened == 1
        assert result.trades_closed == 0


class TestShortMISTrade:
    async def test_sell_buy_opens_and_closes(self):
        engine, fill_repo, trade_repo, lot_repo, session = _make_engine()
        trade_repo.get_open_trade_with_lock.return_value = None
        fill_repo.get_unprocessed_fills.return_value = [
            _fill("SELL", "100", "500"),
            _fill("BUY", "100", "490"),
        ]

        result = await engine.run(session, _USER, _INST, "MIS", "EQ")

        assert result.trades_opened == 1
        assert result.trades_closed == 1
        kwargs = trade_repo.create_trade.call_args.kwargs
        assert kwargs["direction"] == "SHORT"


class TestCNCTrade:
    async def test_buy_sell_creates_and_closes_lot(self):
        engine, fill_repo, trade_repo, lot_repo, session = _make_engine()
        trade_repo.get_open_trade_with_lock.return_value = None
        fill_repo.get_unprocessed_fills.return_value = [
            _fill("BUY", "100", "500", product_type="CNC"),
            _fill("SELL", "100", "510", product_type="CNC"),
        ]
        lot_repo.get_open_lot.return_value = _make_open_lot("100")
        lot_repo.get_lot_for_trade.return_value = _make_closed_lot()

        result = await engine.run(session, _USER, _INST, "CNC", "EQ")

        assert result.tax_lots_created == 1
        lot_repo.create_lot.assert_called_once()

    async def test_scale_in_updates_lot(self):
        engine, fill_repo, trade_repo, lot_repo, session = _make_engine()
        trade_repo.get_open_trade_with_lock.return_value = None

        scale_in_lot = _make_open_lot("100")
        closed_lot = _make_closed_lot()
        fill_repo.get_unprocessed_fills.return_value = [
            _fill("BUY", "100", "500", product_type="CNC"),
            _fill("BUY", "50", "490", product_type="CNC"),
            _fill("SELL", "150", "510", product_type="CNC"),
        ]
        lot_repo.get_lot_for_trade.side_effect = [scale_in_lot, closed_lot]
        lot_repo.get_open_lot.return_value = _make_open_lot("150", qty_original="150")

        result = await engine.run(session, _USER, _INST, "CNC", "EQ")

        assert result.tax_lots_updated >= 1

    async def test_cnc_same_day_finalizes_trade_type(self):
        engine, fill_repo, trade_repo, lot_repo, session = _make_engine()
        trade_repo.get_open_trade_with_lock.return_value = None
        fill_repo.get_unprocessed_fills.return_value = [
            _fill("BUY", "100", "500", product_type="CNC", trade_date=_DATE),
            _fill("SELL", "100", "510", product_type="CNC", trade_date=_DATE),
        ]
        lot_repo.get_open_lot.return_value = _make_open_lot("100")
        lot_repo.get_lot_for_trade.return_value = _make_closed_lot()

        await engine.run(session, _USER, _INST, "CNC", "EQ")

        last_update = trade_repo.update_trade.call_args_list[-1]
        assert last_update.args[2]["trade_type"] == "CNC_SAME_DAY"

    async def test_cnc_different_day_stays_cnc(self):
        engine, fill_repo, trade_repo, lot_repo, session = _make_engine()
        trade_repo.get_open_trade_with_lock.return_value = None
        fill_repo.get_unprocessed_fills.return_value = [
            _fill("BUY", "100", "500", product_type="CNC", trade_date=_DATE),
            _fill("SELL", "100", "510", product_type="CNC", trade_date=_DATE2),
        ]
        lot_repo.get_open_lot.return_value = _make_open_lot("100")
        lot_repo.get_lot_for_trade.return_value = _make_closed_lot()

        await engine.run(session, _USER, _INST, "CNC", "EQ")

        last_update = trade_repo.update_trade.call_args_list[-1]
        assert last_update.args[2]["trade_type"] == "CNC"


class TestResumePartialTrade:
    async def test_resume_and_close(self):
        engine, fill_repo, trade_repo, lot_repo, session = _make_engine()
        existing = _open_trade_snapshot(
            status="PARTIAL",
            total_entry_qty="100",
            total_exit_qty="50",
            net_position="50",
            average_entry="500.0000",
        )
        trade_repo.get_open_trade_with_lock.return_value = existing

        prior_exit_fill = _fill("SELL", "50", "505")
        fill_repo.get_exit_fills.return_value = [prior_exit_fill]
        fill_repo.get_unprocessed_fills.return_value = [
            _fill("SELL", "50", "510"),
        ]

        result = await engine.run(session, _USER, _INST, "MIS", "EQ")

        assert result.fills_processed == 1
        assert result.trades_closed == 1
        trade_repo.create_trade.assert_not_called()


class TestErrorConditions:
    async def test_e1_position_crossing_zero(self):
        engine, fill_repo, trade_repo, lot_repo, session = _make_engine()
        trade_repo.get_open_trade_with_lock.return_value = None
        fill_repo.get_unprocessed_fills.return_value = [
            _fill("BUY", "100", "500"),
            _fill("SELL", "150", "490"),
        ]

        with pytest.raises(PositionCrossingZeroError):
            await engine.run(session, _USER, _INST, "MIS", "EQ")

    async def test_e2_product_type_family_mismatch(self):
        engine, fill_repo, trade_repo, lot_repo, session = _make_engine()
        trade_repo.get_open_trade_with_lock.return_value = None
        fill_repo.get_unprocessed_fills.return_value = [
            _fill("BUY", "100", "500", product_type="MIS"),
            _fill("SELL", "100", "510", product_type="CNC"),
        ]

        with pytest.raises(ReconstructionDataError, match="family"):
            await engine.run(session, _USER, _INST, "MIS", "EQ")

    async def test_e4_missing_lot_on_exit(self):
        engine, fill_repo, trade_repo, lot_repo, session = _make_engine()
        trade_repo.get_open_trade_with_lock.return_value = None
        fill_repo.get_unprocessed_fills.return_value = [
            _fill("BUY", "100", "500", product_type="CNC"),
            _fill("SELL", "100", "510", product_type="CNC"),
        ]
        lot_repo.get_open_lot.return_value = None

        with pytest.raises(ReconstructionConsistencyError, match="E4"):
            await engine.run(session, _USER, _INST, "CNC", "EQ")

    async def test_e4_missing_lot_on_scale_in_regression(self):
        """Regression: F1 fix — scale-in with no tax lot must raise E4, not silently return."""
        engine, fill_repo, trade_repo, lot_repo, session = _make_engine()
        trade_repo.get_open_trade_with_lock.return_value = None
        fill_repo.get_unprocessed_fills.return_value = [
            _fill("BUY", "100", "500", product_type="CNC"),
            _fill("BUY", "50", "490", product_type="CNC"),
        ]
        lot_repo.get_lot_for_trade.return_value = None

        with pytest.raises(ReconstructionConsistencyError, match="E4"):
            await engine.run(session, _USER, _INST, "CNC", "EQ")

    async def test_e5_ambiguous_ordering(self):
        engine, fill_repo, trade_repo, lot_repo, session = _make_engine()
        trade_repo.get_open_trade_with_lock.return_value = None
        fill_repo.get_unprocessed_fills.return_value = [
            _fill("BUY", "100", "500", fill_id_str=None, fill_timestamp=_TS),
            _fill("BUY", "50", "490", fill_id_str=None, fill_timestamp=_TS),
        ]

        with pytest.raises(ReconstructionAmbiguityError):
            await engine.run(session, _USER, _INST, "MIS", "EQ")
