"""FillExclusionRepository — append-only operations on fill_exclusions.

fill_exclusions is a permanent audit log. INSERT is the only permitted operation;
UPDATE and DELETE are blocked unconditionally by database triggers. These
operations are not exposed here.

See TRADE-RECONSTRUCTION-SPEC.md §12 (E1) for the full exclusion workflow.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.infrastructure.models.trade_domain import ExecutionFill, FillExclusion


class FillExclusionRepository:
    async def exists_by_fill_id(
        self,
        session: AsyncSession,
        fill_id: uuid.UUID,
    ) -> bool:
        """Check whether a fill has already been permanently excluded."""
        stmt = select(FillExclusion.id).where(FillExclusion.fill_id == fill_id).limit(1)
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_excluded_fill_ids_for_trade(
        self,
        session: AsyncSession,
        trade_id: uuid.UUID,
    ) -> set[uuid.UUID]:
        """Return the set of fill UUIDs already excluded for this trade.

        Issues a single batch query rather than N per-fill exists_by_fill_id()
        calls (A-16-5 — Mayasura). Used by soft_delete_trade() to compute which
        fills still need exclusion records, avoiding the O(N) query amplification
        pattern.

        Query:
            SELECT fe.fill_id
            FROM fill_exclusions fe
            JOIN execution_fills ef ON ef.id = fe.fill_id
            WHERE ef.trade_id = :trade_id
        """
        stmt = (
            select(FillExclusion.fill_id)
            .join(ExecutionFill, ExecutionFill.id == FillExclusion.fill_id)
            .where(ExecutionFill.trade_id == trade_id)
        )
        result = await session.execute(stmt)
        return set(result.scalars().all())

    async def create_exclusion(
        self,
        session: AsyncSession,
        *,
        fill_id: uuid.UUID,
        reason: str,
        replacement_fill_ids: list[uuid.UUID],
        excluded_by: uuid.UUID,
    ) -> uuid.UUID:
        """Record that a fill is permanently excluded from reconstruction.

        Returns the new exclusion's UUID for audit reference.
        Once inserted this row is permanent — the database trigger blocks any
        attempt to UPDATE or DELETE it.
        """
        exclusion_id = uuid.uuid4()
        exclusion = FillExclusion(
            id=exclusion_id,
            fill_id=fill_id,
            reason=reason,
            replacement_fill_ids=replacement_fill_ids,
            excluded_by=excluded_by,
        )
        session.add(exclusion)
        return exclusion_id
