"""PnlRepository — data access for trade_pnl and trade data assembly for P&L calculation."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.domain.pnl.types import PnlResult, TradeSnapshot
from tradeforge.infrastructure.models.journal import JournalEntry
from tradeforge.infrastructure.models.trade_domain import ExecutionFill, Instrument, Trade
from tradeforge.infrastructure.models.trade_pnl import TradePnl

logger = logging.getLogger(__name__)


class PnlRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Trade data assembly
    # ------------------------------------------------------------------

    async def get_trade_snapshot(self, trade_id: uuid.UUID) -> TradeSnapshot | None:
        """Load a closed trade + instrument exchange_segment + broker from fills.

        Returns None if the trade doesn't exist or is not CLOSED.
        """
        stmt = (
            select(Trade, Instrument.exchange_segment)
            .join(Instrument, Trade.instrument_id == Instrument.id)
            .where(Trade.id == trade_id, Trade.status == "CLOSED")
        )
        result = await self._db.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None

        trade, exchange_segment = row

        broker = await self._get_broker_for_trade(trade_id)
        if broker is None:
            return None

        planned_risk = await self.get_planned_risk(trade_id)

        missing = (
            trade.average_entry is None
            or trade.average_exit is None
            or trade.total_entry_quantity is None
        )
        if missing:
            logger.warning(
                "get_trade_snapshot: trade %s has NULL price/quantity fields — skipping",
                trade_id,
            )
            return None

        def d(v: object) -> Decimal:
            return Decimal(str(v))

        return TradeSnapshot(
            trade_id=trade.id,
            user_id=trade.user_id,
            account_id=trade.account_id,
            trade_type=trade.trade_type,
            trade_date=trade.trade_date,
            direction=trade.direction,
            average_entry=d(trade.average_entry),
            average_exit=d(trade.average_exit),
            total_entry_quantity=d(trade.total_entry_quantity),
            exchange_segment=exchange_segment,
            broker=broker,
            planned_risk_amount=planned_risk,
        )

    async def _get_broker_for_trade(self, trade_id: uuid.UUID) -> str | None:
        """Return the broker string from the first ENTRY fill for this trade."""
        stmt = (
            select(ExecutionFill.broker)
            .where(
                ExecutionFill.trade_id == trade_id,
                ExecutionFill.fill_role == "ENTRY",
                ExecutionFill.broker.isnot(None),
            )
            .order_by(ExecutionFill.fill_timestamp.asc())
            .limit(1)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_planned_risk(self, trade_id: uuid.UUID) -> Decimal | None:
        """Return planned_risk_amount from journal_entries for this trade."""
        stmt = select(JournalEntry.planned_risk_amount).where(
            JournalEntry.trade_id == trade_id,
            JournalEntry.deleted_at.is_(None),
        )
        result = await self._db.execute(stmt)
        value = result.scalar_one_or_none()
        return Decimal(str(value)) if value is not None else None

    # ------------------------------------------------------------------
    # trade_pnl write
    # ------------------------------------------------------------------

    async def upsert(self, result: PnlResult) -> None:
        """Insert or update trade_pnl for the given trade.

        Uses PostgreSQL INSERT ... ON CONFLICT DO UPDATE (upsert) on the
        trade_id unique constraint so this is safe to call multiple times.
        """
        now = datetime.now(UTC)
        values: dict[str, Any] = {
            "trade_id": result.trade_id,
            "user_id": result.user_id,
            "account_id": result.account_id,
            "gross_pnl": result.gross_pnl,
            "net_pnl": result.net_pnl,
            "total_charges": result.total_charges,
            "r_multiple": result.r_multiple,
            "brokerage": result.brokerage,
            "stt": result.stt,
            "exchange_charges": result.exchange_charges,
            "sebi_charges": result.sebi_charges,
            "stamp_duty": result.stamp_duty,
            "gst": result.gst,
            "ipft": result.ipft,
            "broker": result.broker,
            "charge_schedule_version": result.charge_schedule_version,
            "engine_version": result.engine_version,
            "calculated_at": now,
            "updated_at": now,
        }
        stmt = (
            pg_insert(TradePnl)
            .values(id=uuid.uuid4(), created_at=now, **values)
            .on_conflict_do_update(
                constraint="uq_trade_pnl_trade_id",
                set_={k: v for k, v in values.items() if k not in ("trade_id", "user_id")},
            )
        )
        await self._db.execute(stmt)

    async def get_for_trade(self, trade_id: uuid.UUID) -> TradePnl | None:
        """Load an existing trade_pnl row (used when recalculating r_multiple)."""
        stmt = select(TradePnl).where(TradePnl.trade_id == trade_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_r_multiple(self, trade_id: uuid.UUID, r_multiple: Decimal | None) -> None:
        """Update only the r_multiple field on an existing trade_pnl row."""
        now = datetime.now(UTC)
        stmt = (
            update(TradePnl)
            .where(TradePnl.trade_id == trade_id)
            .values(r_multiple=r_multiple, updated_at=now)
        )
        await self._db.execute(stmt)
