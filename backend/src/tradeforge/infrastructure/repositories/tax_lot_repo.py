"""TaxLotRepository — create and update tax lots for CNC (DELIVERY) trades.

Phase 1 uses the aggregated trade lot model: one tax_lots row per CNC trade.
cost_per_share tracks trades.average_entry (updated on each scale-in).
FIFO is trivially satisfied because at most one lot is open per instrument at
any given time under the Phase 1 reconstruction rules.

See TRADE-RECONSTRUCTION-SPEC.md §10 for the full tax lot interaction spec.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.infrastructure.models.trade_domain import TaxLot


class TaxLotRepository:
    async def create_lot(
        self,
        session: AsyncSession,
        *,
        pk: uuid.UUID,
        trade_id: uuid.UUID,
        user_id: uuid.UUID,
        instrument_id: uuid.UUID,
        purchase_date: date,
        quantity_original: Decimal,
        quantity_remaining: Decimal,
        cost_per_share: Decimal,
    ) -> None:
        """Create the aggregated tax lot for a new CNC trade.

        Called atomically with the Trade INSERT so that the lot and the trade
        exist or are rolled back together.
        """
        lot = TaxLot(
            id=pk,
            trade_id=trade_id,
            user_id=user_id,
            instrument_id=instrument_id,
            purchase_date=purchase_date,
            quantity_original=quantity_original,
            quantity_remaining=quantity_remaining,
            cost_per_share=cost_per_share,
            status="OPEN",
        )
        session.add(lot)

    async def get_lot_for_trade(
        self,
        session: AsyncSession,
        trade_id: uuid.UUID,
    ) -> TaxLot | None:
        """Get the single tax lot associated with a specific trade.

        Used for scale-in updates (§10 — scale-in after partial exit).
        """
        stmt = select(TaxLot).where(TaxLot.trade_id == trade_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_open_lot(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        instrument_id: uuid.UUID,
    ) -> TaxLot | None:
        """Return the oldest open/partially-closed lot for FIFO exit allocation.

        Phase 1 scope: at most one non-CLOSED lot exists per (user, instrument)
        at any time. The LIMIT 1 ORDER BY purchase_date ASC satisfies Rule 4.1
        and is ready for multi-lot scenarios when Unresolved 4 is resolved.

        Query (§10):
            SELECT * FROM tax_lots
            WHERE user_id = $user_id
              AND instrument_id = $instrument_id
              AND status != 'CLOSED'
            ORDER BY purchase_date ASC
            LIMIT 1
        """
        stmt = (
            select(TaxLot)
            .where(
                TaxLot.user_id == user_id,
                TaxLot.instrument_id == instrument_id,
                TaxLot.status != "CLOSED",
            )
            .order_by(TaxLot.purchase_date.asc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_lot(
        self,
        session: AsyncSession,
        lot_id: uuid.UUID,
        fields: dict[str, Any],
    ) -> None:
        stmt = update(TaxLot).where(TaxLot.id == lot_id).values(**fields)
        await session.execute(stmt)
