"""FillRepository — queries and mutations for execution_fills.

The ONLY permitted mutation is assign_trade(), which sets trade_id and fill_role
together in a single atomic UPDATE. All other columns on execution_fills are
immutable (enforced by a database trigger).

See TRADE-RECONSTRUCTION-SPEC.md §2 for the unprocessed-fill query specification.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.domain.import_domain.types import NormalizedFill
from tradeforge.domain.trade.types import FillRecord
from tradeforge.infrastructure.models.trade_domain import ExecutionFill, FillExclusion


class FillRepository:
    async def get_unprocessed_fills(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        instrument_id: uuid.UUID,
        product_type: str,
    ) -> list[FillRecord]:
        """Return fills for this processing unit that need reconstruction.

        Query (§2):
            SELECT * FROM execution_fills
            WHERE user_id = $user_id
              AND account_id = $account_id
              AND instrument_id = $instrument_id
              AND product_type = $product_type
              AND trade_id IS NULL
              AND id NOT IN (SELECT fill_id FROM fill_exclusions)
            ORDER BY fill_timestamp ASC, fill_id ASC NULLS LAST, created_at ASC

        The account_id predicate ensures fills from different accounts owned by
        the same user are never mixed during reconstruction.
        The fill_exclusions subquery is evaluated once by PostgreSQL. The ordering
        satisfies the deterministic fill-ordering guarantee (§3) and gives the engine
        the correct sequence without additional in-process sorting.
        """
        excluded_fill_ids = select(FillExclusion.fill_id)

        stmt = (
            select(ExecutionFill)
            .where(
                ExecutionFill.user_id == user_id,
                ExecutionFill.account_id == account_id,
                ExecutionFill.instrument_id == instrument_id,
                ExecutionFill.product_type == product_type,
                ExecutionFill.trade_id.is_(None),
                ExecutionFill.id.not_in(excluded_fill_ids),
            )
            .order_by(
                ExecutionFill.fill_timestamp.asc(),
                ExecutionFill.fill_id.asc().nulls_last(),
                ExecutionFill.created_at.asc(),
            )
        )
        result = await session.execute(stmt)
        return [self._to_record(r) for r in result.scalars().all()]

    async def get_exit_fills(
        self,
        session: AsyncSession,
        trade_id: uuid.UUID,
    ) -> list[FillRecord]:
        """Return all EXIT fills already assigned to a trade.

        Used when resuming a PARTIAL trade to reconstruct the running exit_fills
        list needed for computing average_exit at final close.
        """
        stmt = (
            select(ExecutionFill)
            .where(
                ExecutionFill.trade_id == trade_id,
                ExecutionFill.fill_role == "EXIT",
            )
            .order_by(ExecutionFill.fill_timestamp.asc())
        )
        result = await session.execute(stmt)
        return [self._to_record(r) for r in result.scalars().all()]

    async def fill_exists(
        self,
        session: AsyncSession,
        broker_trade_id: str,
        account_id: uuid.UUID,
    ) -> bool:
        """Return True if a fill with this broker trade_id already exists for the account.

        Used by ImportService for fill-level deduplication before insertion.
        """
        stmt = (
            select(ExecutionFill.id)
            .where(
                ExecutionFill.fill_id == broker_trade_id,
                ExecutionFill.account_id == account_id,
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def insert_normalized_fill(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        instrument_id: uuid.UUID,
        fill: NormalizedFill,
    ) -> uuid.UUID:
        """Insert one NormalizedFill into execution_fills.  Returns the new row PK.

        The caller is responsible for dedup-checking via fill_exists() before calling
        this method. No ON CONFLICT logic here — a duplicate insert will raise IntegrityError
        from the partial unique index (uq_fills_broker_trade_account).
        """
        pk = uuid.uuid4()
        obj = ExecutionFill(
            id=pk,
            user_id=user_id,
            account_id=account_id,
            instrument_id=instrument_id,
            fill_timestamp=fill.fill_timestamp,
            trade_date=fill.trade_date,
            session=fill.session,
            side=fill.side,
            quantity=fill.quantity,
            price=fill.price,
            product_type=fill.product_type,
            broker=fill.broker,
            import_source=fill.import_source,
            fill_id=fill.broker_trade_id,
            order_id=fill.broker_order_id,
            exit_type="EXPIRY_SQUAREOFF" if fill.is_expiry_squareoff else None,
        )
        session.add(obj)
        return pk

    async def assign_trade(
        self,
        session: AsyncSession,
        fill_id: uuid.UUID,
        trade_id: uuid.UUID,
        fill_role: str,
    ) -> None:
        """Atomic assignment of trade_id and fill_role to an unassigned fill.

        This is the only write path for execution_fills in the reconstruction engine.
        trade_id and fill_role are always set together — partial assignment is
        never permitted (enforced by the DB check constraint).
        """
        stmt = (
            update(ExecutionFill)
            .where(ExecutionFill.id == fill_id)
            .values(trade_id=trade_id, fill_role=fill_role)
        )
        await session.execute(stmt)

    @staticmethod
    def _to_record(row: ExecutionFill) -> FillRecord:
        return FillRecord(
            id=row.id,
            user_id=row.user_id,
            instrument_id=row.instrument_id,
            trade_id=row.trade_id,
            fill_timestamp=row.fill_timestamp,
            trade_date=row.trade_date,
            side=row.side,
            quantity=Decimal(str(row.quantity)),
            price=Decimal(str(row.price)),
            product_type=row.product_type,
            fill_id_str=row.fill_id,  # the broker fill ID string (nullable)
            created_at=row.created_at,
            import_source=row.import_source,
            account_id=row.account_id,
        )
