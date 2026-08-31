"""ChargeScheduleRepository — effective-date lookup for broker charge rates."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.domain.pnl.types import ChargeScheduleRow
from tradeforge.infrastructure.models.charge_schedule import ChargeSchedule


class ChargeScheduleRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_for_date(
        self,
        broker: str,
        trade_type: str,
        exchange_segment: str,
        trade_date: date,
    ) -> ChargeScheduleRow | None:
        """Return the charge schedule row effective on trade_date.

        Selects the row with the latest effective_from <= trade_date for the
        given (broker, trade_type, exchange_segment) combination.
        Returns None if no row exists (caller raises ChargeScheduleNotFoundError).
        """
        stmt = (
            select(ChargeSchedule)
            .where(
                ChargeSchedule.broker == broker,
                ChargeSchedule.trade_type == trade_type,
                ChargeSchedule.exchange_segment == exchange_segment,
                ChargeSchedule.effective_from <= trade_date,
            )
            .order_by(ChargeSchedule.effective_from.desc())
            .limit(1)
        )
        result = await self._db.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    @staticmethod
    def _to_domain(row: ChargeSchedule) -> ChargeScheduleRow:
        def d(v: object) -> Decimal:
            return Decimal(str(v))

        def dn(v: object) -> Decimal | None:
            return Decimal(str(v)) if v is not None else None

        return ChargeScheduleRow(
            id=row.id,
            broker=row.broker,
            trade_type=row.trade_type,
            exchange_segment=row.exchange_segment,
            effective_from=row.effective_from,
            brokerage_type=row.brokerage_type,
            brokerage_flat_per_order=dn(row.brokerage_flat_per_order),
            brokerage_pct=dn(row.brokerage_pct),
            brokerage_cap_per_order=dn(row.brokerage_cap_per_order),
            stt_buy_rate=d(row.stt_buy_rate),
            stt_sell_rate=d(row.stt_sell_rate),
            stt_base=row.stt_base,
            exchange_charge_rate=d(row.exchange_charge_rate),
            exchange_charge_base=row.exchange_charge_base,
            sebi_charge_rate=d(row.sebi_charge_rate),
            stamp_duty_rate=d(row.stamp_duty_rate),
            stamp_duty_base=row.stamp_duty_base,
            gst_rate=d(row.gst_rate),
            ipft_rate=d(row.ipft_rate),
            ipft_base=row.ipft_base,
        )
