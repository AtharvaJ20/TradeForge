"""InstrumentRepository — lookups and upserts for the instruments table.

Used by ImportService and TradeService to resolve symbol fields → instrument_id.
Unknown instruments are auto-created on first encounter so that imports and manual
trade entries succeed without requiring a pre-seeded instrument catalogue.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.domain.import_domain.errors import InstrumentNotFoundError
from tradeforge.infrastructure.models.trade_domain import Instrument


def _derive_name(
    symbol: str,
    instrument_type: str,
    expiry_date: date | None,
    strike_price: Decimal | None,
) -> str:
    """Build a human-readable display name for an auto-created instrument."""
    if instrument_type == "EQ":
        return symbol
    if instrument_type == "FUT" and expiry_date is not None:
        return f"{symbol} {expiry_date:%d%b%y} FUT".upper()
    if instrument_type in ("CE", "PE") and expiry_date is not None and strike_price is not None:
        return f"{symbol} {expiry_date:%d%b%y} {int(strike_price)} {instrument_type}".upper()
    return symbol


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

    async def get_or_create(
        self,
        session: AsyncSession,
        symbol: str,
        exchange_segment: str,
        instrument_type: str,
        expiry_date: date | None = None,
        strike_price: Decimal | None = None,
    ) -> uuid.UUID:
        """Return the id for this instrument, inserting a new row if it does not exist.

        Uses INSERT … ON CONFLICT DO NOTHING so concurrent requests are safe.
        The auto-created name is derived from the symbol and contract details; it
        can be enriched later by a reference data feed.

        Raises:
            InstrumentNotFoundError: if instrument_type requires expiry_date or
                strike_price and they are not supplied (propagated from find_for_fill).
        """
        existing = await self.find_for_fill(
            session, symbol, exchange_segment, instrument_type, expiry_date, strike_price
        )
        if existing is not None:
            return existing

        name = _derive_name(symbol, instrument_type, expiry_date, strike_price)
        stmt = (
            pg_insert(Instrument)
            .values(
                id=uuid.uuid4(),
                symbol=symbol,
                exchange_segment=exchange_segment,
                instrument_type=instrument_type,
                expiry_date=expiry_date,
                strike_price=strike_price,
                name=name,
            )
            .on_conflict_do_nothing()
        )
        await session.execute(stmt)
        await session.flush()

        # Re-fetch: handles the concurrent-insert case where ON CONFLICT suppressed our row.
        result = await self.find_for_fill(
            session, symbol, exchange_segment, instrument_type, expiry_date, strike_price
        )
        if result is None:
            raise RuntimeError(
                f"Instrument upsert produced no row for "
                f"{symbol!r}/{exchange_segment!r}/{instrument_type!r}"
            )
        return result
