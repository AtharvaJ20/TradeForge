"""InstrumentRepository — read-only lookups for the instruments table.

Used by ImportService to resolve NormalizedFill symbol fields → instrument_id.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.domain.import_domain.errors import InstrumentNotFoundError
from tradeforge.infrastructure.models.trade_domain import Instrument


class InstrumentRepository:
    async def find_eq(
        self,
        session: AsyncSession,
        symbol: str,
        exchange_segment: str,
    ) -> uuid.UUID | None:
        """Look up an EQ instrument by symbol and exchange_segment."""
        stmt = (
            select(Instrument.id)
            .where(
                Instrument.symbol == symbol,
                Instrument.exchange_segment == exchange_segment,
                Instrument.instrument_type == "EQ",
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_futures(
        self,
        session: AsyncSession,
        symbol: str,
        exchange_segment: str,
        expiry_date: date,
    ) -> uuid.UUID | None:
        """Look up a FUT instrument by symbol, exchange_segment, and expiry_date."""
        stmt = (
            select(Instrument.id)
            .where(
                Instrument.symbol == symbol,
                Instrument.exchange_segment == exchange_segment,
                Instrument.instrument_type == "FUT",
                Instrument.expiry_date == expiry_date,
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_option(
        self,
        session: AsyncSession,
        symbol: str,
        exchange_segment: str,
        instrument_type: str,  # "CE" or "PE"
        expiry_date: date,
        strike_price: Decimal,
    ) -> uuid.UUID | None:
        """Look up a CE/PE instrument by all option identifiers."""
        stmt = (
            select(Instrument.id)
            .where(
                Instrument.symbol == symbol,
                Instrument.exchange_segment == exchange_segment,
                Instrument.instrument_type == instrument_type,
                Instrument.expiry_date == expiry_date,
                Instrument.strike_price == strike_price,
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_for_fill(
        self,
        session: AsyncSession,
        symbol: str,
        exchange_segment: str,
        instrument_type: str,
        expiry_date: date | None,
        strike_price: Decimal | None,
    ) -> uuid.UUID | None:
        """Dispatch to the correct lookup based on instrument_type."""
        if instrument_type == "EQ":
            return await self.find_eq(session, symbol, exchange_segment)
        if instrument_type == "FUT":
            if expiry_date is None:
                raise InstrumentNotFoundError(symbol, exchange_segment, instrument_type)
            return await self.find_futures(session, symbol, exchange_segment, expiry_date)
        if instrument_type in ("CE", "PE"):
            if expiry_date is None or strike_price is None:
                raise InstrumentNotFoundError(symbol, exchange_segment, instrument_type)
            return await self.find_option(
                session, symbol, exchange_segment, instrument_type, expiry_date, strike_price
            )
        return None
