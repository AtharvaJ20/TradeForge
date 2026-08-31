"""ORM model for charge_schedules — broker/trade-type/exchange-segment charge rates.

Effective-date versioning: the P&L engine looks up the row with the latest
effective_from <= trade_date for a given (broker, trade_type, exchange_segment).

Phase 1: no account_id column (ADR-005). Phase 2 extension: additive column addition.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ChargeSchedule(Base):
    __tablename__ = "charge_schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    broker: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_type: Mapped[str] = mapped_column(String(20), nullable=False)
    exchange_segment: Mapped[str] = mapped_column(String(20), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date(), nullable=False)
    # Brokerage
    brokerage_type: Mapped[str] = mapped_column(String(20), nullable=False)
    brokerage_flat_per_order: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    brokerage_pct: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    brokerage_cap_per_order: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    # STT
    stt_buy_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    stt_sell_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    stt_base: Mapped[str] = mapped_column(String(10), nullable=False)
    # Exchange charges
    exchange_charge_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    exchange_charge_base: Mapped[str] = mapped_column(String(10), nullable=False)
    # SEBI
    sebi_charge_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    # Stamp duty
    stamp_duty_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    stamp_duty_base: Mapped[str] = mapped_column(String(10), nullable=False)
    # GST
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    # IPFT
    ipft_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    ipft_base: Mapped[str] = mapped_column(String(10), nullable=False)
    # Audit
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    __table_args__ = (
        UniqueConstraint(
            "broker",
            "trade_type",
            "exchange_segment",
            "effective_from",
            name="uq_charge_schedules_lookup",
        ),
        CheckConstraint(
            "broker IN ('ZERODHA', 'UPSTOX', 'ANGEL_ONE', 'MANUAL')",
            name="ck_charge_schedules_broker",
        ),
        CheckConstraint(
            "trade_type IN ('MIS', 'CNC', 'CNC_SAME_DAY', 'NRML_FUT', 'NRML_OPT')",
            name="ck_charge_schedules_trade_type",
        ),
        CheckConstraint(
            "exchange_segment IN ('NSE_EQ', 'NSE_FO', 'BSE_EQ')",
            name="ck_charge_schedules_exchange_segment",
        ),
        CheckConstraint(
            "brokerage_type IN ('ZERO', 'FLAT', 'PERCENT_CAP')",
            name="ck_charge_schedules_brokerage_type",
        ),
        CheckConstraint(
            "stt_base IN ('TURNOVER', 'PREMIUM')",
            name="ck_charge_schedules_stt_base",
        ),
        CheckConstraint(
            "exchange_charge_base IN ('TURNOVER', 'PREMIUM')",
            name="ck_charge_schedules_exchange_base",
        ),
        CheckConstraint(
            "stamp_duty_base IN ('TURNOVER', 'PREMIUM')",
            name="ck_charge_schedules_stamp_duty_base",
        ),
        CheckConstraint(
            "ipft_base IN ('TURNOVER', 'PREMIUM')",
            name="ck_charge_schedules_ipft_base",
        ),
        CheckConstraint(
            """(
                (brokerage_type = 'ZERO'
                     AND brokerage_flat_per_order IS NULL
                     AND brokerage_pct IS NULL
                     AND brokerage_cap_per_order IS NULL)
                OR
                (brokerage_type = 'FLAT'
                     AND brokerage_flat_per_order IS NOT NULL
                     AND brokerage_pct IS NULL
                     AND brokerage_cap_per_order IS NULL)
                OR
                (brokerage_type = 'PERCENT_CAP'
                     AND brokerage_flat_per_order IS NULL
                     AND brokerage_pct IS NOT NULL
                     AND brokerage_cap_per_order IS NOT NULL)
            )""",
            name="ck_charge_schedules_brokerage_cols",
        ),
        CheckConstraint(
            "stt_buy_rate >= 0 AND stt_sell_rate >= 0 AND exchange_charge_rate >= 0"
            " AND sebi_charge_rate >= 0 AND stamp_duty_rate >= 0"
            " AND gst_rate >= 0 AND ipft_rate >= 0",
            name="ck_charge_schedules_rates_non_negative",
        ),
    )
