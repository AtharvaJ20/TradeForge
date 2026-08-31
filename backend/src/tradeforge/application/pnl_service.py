"""PnlService — Step 10 P&L calculation engine.

Owns all writes to trade_pnl. The journal service and reconstruction engine
are the only callers; both inject PnlService and call it directly within their
own transaction.

Responsibilities:
  calculate_and_store  — full P&L for a newly closed trade.
  recalculate_r_multiple — update only r_multiple after planned_stop is set.
  backfill_all_closed  — recalculate P&L for all CLOSED trades for a user.
"""

from __future__ import annotations

import logging
import uuid

from tradeforge.domain.pnl.calculator import compute_pnl, compute_r_multiple
from tradeforge.domain.pnl.errors import ChargeScheduleNotFoundError
from tradeforge.infrastructure.repositories.charge_schedule_repo import ChargeScheduleRepository
from tradeforge.infrastructure.repositories.pnl_repo import PnlRepository

logger = logging.getLogger(__name__)


class PnlService:
    def __init__(
        self,
        pnl_repo: PnlRepository,
        charge_schedule_repo: ChargeScheduleRepository,
    ) -> None:
        self._pnl_repo = pnl_repo
        self._cs_repo = charge_schedule_repo

    async def calculate_and_store(self, trade_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Compute full P&L for a closed trade and upsert the trade_pnl row.

        Raises ChargeScheduleNotFoundError if no charge schedule exists for the
        trade's (broker, trade_type, exchange_segment, trade_date). The caller
        should log a warning and leave the trade in PENDING_CALCULATION state.

        All DB writes occur within the caller's transaction — no session opened here.
        """
        trade = await self._pnl_repo.get_trade_snapshot(trade_id)
        if trade is None:
            logger.warning("calculate_and_store: trade %s not found or not CLOSED", trade_id)
            return

        cs = await self._cs_repo.get_for_date(
            broker=trade.broker,
            trade_type=trade.trade_type,
            exchange_segment=trade.exchange_segment,
            trade_date=trade.trade_date,
        )
        if cs is None:
            raise ChargeScheduleNotFoundError(
                broker=trade.broker,
                trade_type=trade.trade_type,
                exchange_segment=trade.exchange_segment,
                trade_date=trade.trade_date,
            )

        result = compute_pnl(trade, cs)
        await self._pnl_repo.upsert(result)
        logger.info(
            "P&L stored for trade %s: gross=%.4f net=%.4f charges=%.4f broker=%s schedule=%s",
            trade_id, result.gross_pnl, result.net_pnl, result.total_charges,
            result.broker, result.charge_schedule_version,
        )

    async def recalculate_r_multiple(self, trade_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Recalculate r_multiple after planned_stop (and thus planned_risk_amount) changes.

        No-ops if no trade_pnl row exists yet (trade not yet calculated).
        All DB writes occur within the caller's transaction.
        """
        existing = await self._pnl_repo.get_for_trade(trade_id)
        if existing is None:
            return

        planned_risk = await self._pnl_repo._get_planned_risk(trade_id)
        from decimal import Decimal
        net_pnl = Decimal(str(existing.net_pnl))
        r_multiple = compute_r_multiple(net_pnl, planned_risk)

        await self._pnl_repo.update_r_multiple(trade_id, r_multiple)
        logger.info(
            "r_multiple updated for trade %s: r=%s",
            trade_id,
            r_multiple,
        )

    async def backfill_all_closed(self, user_id: uuid.UUID) -> tuple[int, int]:
        """Recalculate P&L for all CLOSED trades for a user.

        Returns (succeeded, failed) counts. Failures are logged but do not abort
        the backfill — remaining trades continue.

        Note: opens multiple sub-queries within the caller's session.
        """
        from sqlalchemy import select

        from tradeforge.infrastructure.models.trade_domain import Trade

        stmt = select(Trade.id).where(
            Trade.user_id == user_id,
            Trade.status == "CLOSED",
        )
        result = await self._pnl_repo._db.execute(stmt)
        trade_ids = list(result.scalars().all())

        succeeded = 0
        failed = 0
        for tid in trade_ids:
            try:
                await self.calculate_and_store(tid, user_id)
                succeeded += 1
            except ChargeScheduleNotFoundError as exc:
                logger.warning("backfill: no charge schedule for trade %s — %s", tid, exc)
                failed += 1
            except Exception:
                logger.exception("backfill: unexpected error for trade %s", tid)
                failed += 1

        logger.info("backfill complete for user %s: %d ok, %d failed", user_id, succeeded, failed)
        return succeeded, failed
