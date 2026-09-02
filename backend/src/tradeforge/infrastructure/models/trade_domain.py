"""ORM models for the trade domain.

Covers: instruments, trades, execution fills, management events, tax lots, fill exclusions.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, utcnow


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    exchange_segment: Mapped[str] = mapped_column(String(20), nullable=False)
    instrument_type: Mapped[str] = mapped_column(String(10), nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    strike_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
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
        CheckConstraint(
            "exchange_segment IN ('NSE_EQ', 'NSE_FO', 'BSE_EQ')",
            name="ck_instruments_exchange_segment",
        ),
        CheckConstraint(
            "instrument_type IN ('EQ', 'FUT', 'CE', 'PE')",
            name="ck_instruments_instrument_type",
        ),
        # Partial unique indexes are defined in the migration (DDL-level) rather than
        # here, because SQLAlchemy's Index() doesn't support partial unique constraints
        # with WHERE clauses that need to interact with CHECK constraints correctly.
    )


class LotSizeHistory(Base):
    __tablename__ = "lot_size_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False
    )
    lot_size: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default="now()"
    )

    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "effective_from", name="uq_lsh_instrument_effective_from"
        ),
        CheckConstraint("lot_size > 0", name="ck_lsh_lot_size_positive"),
        CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from",
            name="ck_lsh_until_after_from",
        ),
        Index("idx_lsh_instrument_until", "instrument_id", "effective_until"),
    )


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trading_accounts.id"), nullable=True
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False
    )
    trade_type: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str] = mapped_column(String(5), nullable=False)
    status: Mapped[str] = mapped_column(String(15), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    first_fill_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_fill_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_entry_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_exit_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, server_default="0"
    )
    net_position: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    average_entry: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    average_exit: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    planned_entry: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    planned_stop: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    planned_target: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    planned_risk_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    setup_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    # Declared so the ORM unit-of-work correctly sequences Trade INSERT before
    # TaxLot INSERT (FK trades.id ← tax_lots.trade_id). lazy="raise_on_sql"
    # prevents accidental lazy loading in async sessions.
    tax_lot: Mapped[TaxLot | None] = relationship(
        "TaxLot",
        back_populates="trade",
        uselist=False,
        lazy="raise_on_sql",
    )

    __table_args__ = (
        CheckConstraint(
            "trade_type IN ('MIS', 'CNC', 'CNC_SAME_DAY', 'NRML_FUT', 'NRML_OPT')",
            name="ck_trades_trade_type",
        ),
        CheckConstraint("direction IN ('LONG', 'SHORT')", name="ck_trades_direction"),
        CheckConstraint("status IN ('OPEN', 'PARTIAL', 'CLOSED')", name="ck_trades_status"),
        CheckConstraint("net_position >= 0", name="ck_trades_net_position_gte0"),
        CheckConstraint("total_entry_quantity >= 0", name="ck_trades_total_entry_gte0"),
        CheckConstraint("total_exit_quantity >= 0", name="ck_trades_total_exit_gte0"),
        CheckConstraint(
            "total_exit_quantity <= total_entry_quantity",
            name="ck_trades_exit_lte_entry",
        ),
        Index("idx_trades_user_status", "user_id", "status"),
        Index("idx_trades_user_date", "user_id", "trade_date"),
        Index("idx_trades_user_instrument_status", "user_id", "instrument_id", "status"),
        Index("idx_trades_instrument_id", "instrument_id"),
    )


class ExecutionFill(Base):
    __tablename__ = "execution_fills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trading_accounts.id"), nullable=True
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False
    )
    trade_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trades.id"), nullable=True
    )
    fill_role: Mapped[str | None] = mapped_column(String(5), nullable=True)
    fill_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    session: Mapped[str] = mapped_column(String(15), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    product_type: Mapped[str] = mapped_column(String(10), nullable=False)
    exit_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fill_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    broker: Mapped[str] = mapped_column(String(20), nullable=False)
    import_source: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default="now()"
    )

    __table_args__ = (
        CheckConstraint(
            "session IN ('PRE_OPEN', 'REGULAR', 'POST_CLOSE')",
            name="ck_fills_session",
        ),
        CheckConstraint("side IN ('BUY', 'SELL')", name="ck_fills_side"),
        CheckConstraint(
            "fill_role IN ('ENTRY', 'EXIT') OR fill_role IS NULL",
            name="ck_fills_fill_role",
        ),
        CheckConstraint("product_type IN ('MIS', 'CNC', 'NRML')", name="ck_fills_product_type"),
        CheckConstraint("quantity > 0", name="ck_fills_quantity_positive"),
        CheckConstraint("price > 0", name="ck_fills_price_positive"),
        CheckConstraint(
            "broker IN ('ZERODHA', 'UPSTOX', 'ANGEL_ONE', 'MANUAL')",
            name="ck_fills_broker",
        ),
        CheckConstraint(
            "trade_id IS NOT NULL OR fill_role IS NULL",
            name="ck_fills_role_requires_trade",
        ),
        CheckConstraint(
            "exit_type IS NULL OR fill_role = 'EXIT' OR fill_role IS NULL",
            name="ck_fills_exit_type_requires_exit_role",
        ),
        Index("idx_fills_trade_id", "trade_id"),
        Index("idx_fills_user_instrument_date", "user_id", "instrument_id", "trade_date"),
        Index("idx_fills_user_date", "user_id", "trade_date"),
        # Partial unique index for idempotent re-import is defined in the migration
        # (WHERE clause not supported by SQLAlchemy Index() for unique constraints).
    )


class ManagementEvent(Base):
    __tablename__ = "management_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trades.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price_level: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrects_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("management_events.id"), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default="now()"
    )

    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'STOP_MOVED_BREAKEVEN', 'STOP_TIGHTENED', 'STOP_WIDENED', "
            "'TARGET_ADJUSTED', 'SCALE_IN', 'DEFENSIVE_SCALE_OUT', "
            "'OVERNIGHT_HOLD_NOTED', 'NOTE_ADDED'"
            ")",
            name="ck_mgmt_event_type",
        ),
        Index("idx_mgmt_trade_id", "trade_id"),
        Index("idx_mgmt_user_occurred", "user_id", "occurred_at"),
        # Partial index on corrects_event_id defined in the migration (WHERE IS NOT NULL).
    )


class TaxLot(Base):
    __tablename__ = "tax_lots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trades.id"), nullable=False, unique=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False
    )
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity_original: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    quantity_remaining: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    cost_per_share: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
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

    # Back-reference to Trade — completes the relationship declared on Trade.tax_lot.
    trade: Mapped[Trade] = relationship(
        "Trade",
        back_populates="tax_lot",
        lazy="raise_on_sql",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN', 'PARTIALLY_CLOSED', 'CLOSED')",
            name="ck_taxlots_status",
        ),
        CheckConstraint("quantity_remaining >= 0", name="ck_taxlots_remaining_gte0"),
        CheckConstraint(
            "quantity_remaining <= quantity_original",
            name="ck_taxlots_remaining_lte_original",
        ),
        CheckConstraint("quantity_original > 0", name="ck_taxlots_original_positive"),
        CheckConstraint("cost_per_share > 0", name="ck_taxlots_cost_positive"),
        Index("idx_taxlots_fifo", "user_id", "instrument_id", "status", "purchase_date"),
    )


class FillExclusion(Base):
    __tablename__ = "fill_exclusions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("execution_fills.id"), nullable=False, unique=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    replacement_fill_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default="ARRAY[]::uuid[]"
    )
    excluded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    excluded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default="now()"
    )

    __table_args__ = (
        UniqueConstraint("fill_id", name="uq_fill_exclusions_fill_id"),
        Index("idx_fill_exclusions_excluded_by", "excluded_by"),
    )
