"""ORM model for trade_pnl — populated by the Step 10 P&L engine.

The journal service LEFT JOINs this table to determine pnl_status; it never writes here.
All writes belong to PnlService (Step 10+).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


class TradePnl(Base):
    __tablename__ = "trade_pnl"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trades.id"), nullable=False, unique=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trading_accounts.id"), nullable=True
    )
    # Core P&L
    gross_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    net_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_charges: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    r_multiple: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    # Charge breakdown
    brokerage: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stt: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    exchange_charges: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    sebi_charges: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stamp_duty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    gst: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    ipft: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    # Engine metadata
    broker: Mapped[str] = mapped_column(String(20), nullable=False)
    charge_schedule_version: Mapped[str] = mapped_column(String(50), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(20), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default="now()"
    )
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default="now()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default="now()",
    )

    __table_args__ = (
        UniqueConstraint("trade_id", name="uq_trade_pnl_trade_id"),
        CheckConstraint(
            "total_charges = brokerage + stt + exchange_charges"
            " + sebi_charges + stamp_duty + gst + ipft",
            name="ck_trade_pnl_total_charges_identity",
        ),
        CheckConstraint(
            "brokerage >= 0 AND stt >= 0 AND exchange_charges >= 0 AND sebi_charges >= 0"
            " AND stamp_duty >= 0 AND gst >= 0 AND ipft >= 0",
            name="ck_trade_pnl_charges_non_negative",
        ),
    )
