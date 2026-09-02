"""TradeRepository — open trade lookup (with row-level lock), create, and update.

The SELECT FOR UPDATE lock is the concurrency control mechanism specified in
TRADE-RECONSTRUCTION-SPEC.md §11: only one reconstruction run may modify a
processing unit's open trade at a time.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.domain.trade.types import (
    TRADE_TYPES_FOR_FAMILY,
    OpenTradeSnapshot,
    ProductTypeFamily,
)
from tradeforge.infrastructure.models.trade_domain import Trade


class TradeRepository:
    async def get_open_trade_with_lock(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        instrument_id: uuid.UUID,
        family: ProductTypeFamily,
    ) -> OpenTradeSnapshot | None:
        """Return the open or partial trade for this processing unit and lock it.

        The FOR UPDATE advisory lock is held for the lifetime of the enclosing
        transaction. Concurrent reconstruction runs on the same processing unit
        will block at this statement until the first run commits or rolls back.

        Query (§11):
            SELECT * FROM trades
            WHERE user_id = $user_id
              AND account_id = $account_id
              AND instrument_id = $instrument_id
              AND status IN ('OPEN', 'PARTIAL')
              AND trade_type IN ($types_for_product_type_family)
            FOR UPDATE

        The account_id predicate prevents scalar_one_or_none() from failing with
        MultipleResultsFound when a user has open trades for the same instrument
        in two different accounts.
        """
        trade_types = TRADE_TYPES_FOR_FAMILY[family]
        stmt = (
            select(Trade)
            .where(
                Trade.user_id == user_id,
                Trade.account_id == account_id,
                Trade.instrument_id == instrument_id,
                Trade.status.in_(("OPEN", "PARTIAL")),
                Trade.trade_type.in_(trade_types),
            )
            .with_for_update()
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_snapshot(row) if row is not None else None

    async def create_trade(
        self,
        session: AsyncSession,
        *,
        pk: uuid.UUID,
        user_id: uuid.UUID,
        account_id: uuid.UUID | None = None,
        instrument_id: uuid.UUID,
        trade_type: str,
        direction: str,
        status: str,
        trade_date: date,
        first_fill_at: datetime,
        total_entry_quantity: Decimal,
        total_exit_quantity: Decimal,
        net_position: Decimal,
        average_entry: Decimal,
    ) -> None:
        trade = Trade(
            id=pk,
            user_id=user_id,
            account_id=account_id,
            instrument_id=instrument_id,
            trade_type=trade_type,
            direction=direction,
            status=status,
            trade_date=trade_date,
            first_fill_at=first_fill_at,
            last_fill_at=None,
            total_entry_quantity=total_entry_quantity,
            total_exit_quantity=total_exit_quantity,
            net_position=net_position,
            average_entry=average_entry,
            average_exit=None,
        )
        session.add(trade)

    async def update_trade(
        self,
        session: AsyncSession,
        trade_id: uuid.UUID,
        fields: dict[str, Any],
    ) -> None:
        stmt = update(Trade).where(Trade.id == trade_id).values(**fields)
        await session.execute(stmt)

    @staticmethod
    def _to_snapshot(row: Trade) -> OpenTradeSnapshot:
        return OpenTradeSnapshot(
            id=row.id,
            direction=row.direction,
            status=row.status,
            trade_date=row.trade_date,
            first_fill_at=row.first_fill_at,
            total_entry_quantity=Decimal(str(row.total_entry_quantity)),
            total_exit_quantity=Decimal(str(row.total_exit_quantity)),
            net_position=Decimal(str(row.net_position)),
            average_entry=Decimal(str(row.average_entry)),
            trade_type=row.trade_type,
        )
