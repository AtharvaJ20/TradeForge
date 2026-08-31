"""Pure domain types for the P&L engine.

No I/O. No SQLAlchemy. No FastAPI. stdlib only.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

PNL_ENGINE_VERSION: str = "1.0.0"


@dataclass(frozen=True)
class ChargeScheduleRow:
    """Value object mapping a charge_schedules DB row.

    Decimal fields are already converted from DB Numeric.
    """

    id: uuid.UUID
    broker: str
    trade_type: str
    exchange_segment: str
    effective_from: date
    brokerage_type: str
    brokerage_flat_per_order: Decimal | None
    brokerage_pct: Decimal | None
    brokerage_cap_per_order: Decimal | None
    stt_buy_rate: Decimal
    stt_sell_rate: Decimal
    stt_base: str
    exchange_charge_rate: Decimal
    exchange_charge_base: str
    sebi_charge_rate: Decimal
    stamp_duty_rate: Decimal
    stamp_duty_base: str
    gst_rate: Decimal
    ipft_rate: Decimal
    ipft_base: str


@dataclass(frozen=True)
class TradeSnapshot:
    """All fields the P&L engine needs for a single closed trade.

    Assembled by PnlRepository from trades + instruments + execution_fills.
    Step 10 reads average_entry, average_exit, total_entry_quantity as
    authoritative (Ganesha FIFO ruling — no lot attribution in Step 10).
    """

    trade_id: uuid.UUID
    user_id: uuid.UUID
    trade_type: str
    trade_date: date
    direction: str
    average_entry: Decimal
    average_exit: Decimal
    total_entry_quantity: Decimal
    exchange_segment: str
    broker: str
    planned_risk_amount: Decimal | None


@dataclass(frozen=True)
class ChargeBreakdown:
    """Seven quantized charge components plus their sum.

    total_charges == brokerage + stt + exchange_charges + sebi_charges
                   + stamp_duty + gst + ipft  (enforced by DB CHECK constraint).
    """

    brokerage: Decimal
    stt: Decimal
    exchange_charges: Decimal
    sebi_charges: Decimal
    stamp_duty: Decimal
    gst: Decimal
    ipft: Decimal
    total_charges: Decimal


@dataclass(frozen=True)
class PnlResult:
    """Complete P&L calculation output — written to trade_pnl."""

    trade_id: uuid.UUID
    user_id: uuid.UUID
    gross_pnl: Decimal
    net_pnl: Decimal
    r_multiple: Decimal | None
    brokerage: Decimal
    stt: Decimal
    exchange_charges: Decimal
    sebi_charges: Decimal
    stamp_duty: Decimal
    gst: Decimal
    ipft: Decimal
    total_charges: Decimal
    broker: str
    charge_schedule_version: str
    engine_version: str
