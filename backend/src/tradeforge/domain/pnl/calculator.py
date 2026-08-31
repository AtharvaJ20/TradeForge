"""Pure P&L calculation functions.

No I/O. No SQLAlchemy. No FastAPI. All inputs are plain Python types.
Implements formulas from CHARGE-SCHEDULES-SPEC.md §6 and Ganesha FIFO ruling.
"""

from __future__ import annotations

from decimal import Decimal

from tradeforge.domain.decimal_config import CHARGE_STORED, R_MULTIPLE, ZERO
from tradeforge.domain.pnl.types import (
    PNL_ENGINE_VERSION,
    ChargeBreakdown,
    ChargeScheduleRow,
    PnlResult,
    TradeSnapshot,
)


def _brokerage_per_side(turnover: Decimal, cs: ChargeScheduleRow) -> Decimal:
    if cs.brokerage_type == "ZERO":
        return ZERO
    if cs.brokerage_type == "FLAT":
        assert cs.brokerage_flat_per_order is not None
        return cs.brokerage_flat_per_order
    # PERCENT_CAP
    assert cs.brokerage_pct is not None and cs.brokerage_cap_per_order is not None
    return min(cs.brokerage_pct * turnover, cs.brokerage_cap_per_order)


def compute_gross_pnl(trade: TradeSnapshot) -> Decimal:
    """Gross P&L before any charges.

    Formula per Ganesha FIFO ruling:
      LONG:  (avg_exit - avg_entry) * total_entry_quantity
      SHORT: (avg_entry - avg_exit) * total_entry_quantity
    """
    if trade.direction == "LONG":
        return (trade.average_exit - trade.average_entry) * trade.total_entry_quantity
    return (trade.average_entry - trade.average_exit) * trade.total_entry_quantity


def compute_charges(trade: TradeSnapshot, cs: ChargeScheduleRow) -> ChargeBreakdown:
    """Compute all seven charge components per CHARGE-SCHEDULES-SPEC.md §6.

    All arithmetic runs at full Decimal precision. Each component is quantized
    once at the end to CHARGE_STORED (NUMERIC(18,4), ROUND_HALF_UP).
    total_charges is re-summed from the already-quantized components to satisfy
    the DB CHECK constraint (§6.10 critical re-summation pattern).
    """
    entry_turnover = trade.average_entry * trade.total_entry_quantity
    exit_turnover = trade.average_exit * trade.total_entry_quantity

    # §6.2 Brokerage — per order side
    brokerage = _brokerage_per_side(entry_turnover, cs) + _brokerage_per_side(exit_turnover, cs)

    # §6.3 STT — base is TURNOVER or PREMIUM (same formula; distinction is in avg_entry meaning)
    stt = cs.stt_buy_rate * entry_turnover + cs.stt_sell_rate * exit_turnover

    # §6.4 Exchange charges — both sides
    if cs.exchange_charge_base == "TURNOVER":
        total_base = entry_turnover + exit_turnover
    else:  # PREMIUM
        total_base = entry_turnover + exit_turnover  # formula identical; alias per spec §6.1
    exchange_charges = cs.exchange_charge_rate * total_base

    # §6.5 SEBI — same base as exchange_charge_base
    sebi_charges = cs.sebi_charge_rate * total_base

    # §6.6 Stamp duty — buy side only
    stamp_duty = cs.stamp_duty_rate * entry_turnover  # same formula regardless of _base per §6.6

    # §6.7 GST — on brokerage + exchange + sebi only (NOT on STT or stamp_duty — statutory)
    gst = cs.gst_rate * (brokerage + exchange_charges + sebi_charges)

    # §6.8 IPFT
    ipft = cs.ipft_rate * total_base

    # §6.10 Quantize each component independently (ROUND_HALF_UP, 4dp)
    q_brokerage = brokerage.quantize(*CHARGE_STORED)
    q_stt = stt.quantize(*CHARGE_STORED)
    q_exchange_charges = exchange_charges.quantize(*CHARGE_STORED)
    q_sebi_charges = sebi_charges.quantize(*CHARGE_STORED)
    q_stamp_duty = stamp_duty.quantize(*CHARGE_STORED)
    q_gst = gst.quantize(*CHARGE_STORED)
    q_ipft = ipft.quantize(*CHARGE_STORED)

    # §6.10 Re-sum from quantized values — never from pre-quantization intermediates
    total_charges = (
        q_brokerage + q_stt + q_exchange_charges + q_sebi_charges + q_stamp_duty + q_gst + q_ipft
    )

    return ChargeBreakdown(
        brokerage=q_brokerage,
        stt=q_stt,
        exchange_charges=q_exchange_charges,
        sebi_charges=q_sebi_charges,
        stamp_duty=q_stamp_duty,
        gst=q_gst,
        ipft=q_ipft,
        total_charges=total_charges,
    )


def compute_r_multiple(net_pnl: Decimal, planned_risk_amount: Decimal | None) -> Decimal | None:
    """R-multiple = net_pnl / planned_risk_amount, or None if risk is unknown/zero."""
    if planned_risk_amount is None or planned_risk_amount == ZERO:
        return None
    return (net_pnl / planned_risk_amount).quantize(*R_MULTIPLE)


def compute_pnl(
    trade: TradeSnapshot,
    cs: ChargeScheduleRow,
) -> PnlResult:
    """Full P&L result for a closed trade.

    gross_pnl and net_pnl are stored at CHARGE_STORED precision (4dp) to match
    the NUMERIC(18,4) schema of trade_pnl.gross_pnl / net_pnl.
    """
    gross_pnl = compute_gross_pnl(trade).quantize(*CHARGE_STORED)
    charges = compute_charges(trade, cs)
    net_pnl = (gross_pnl - charges.total_charges).quantize(*CHARGE_STORED)
    r_multiple = compute_r_multiple(net_pnl, trade.planned_risk_amount)

    charge_schedule_version = (
        f"{cs.broker}_{cs.trade_type}_{cs.exchange_segment}_{cs.effective_from:%Y%m%d}"
    )

    return PnlResult(
        trade_id=trade.trade_id,
        user_id=trade.user_id,
        gross_pnl=gross_pnl,
        net_pnl=net_pnl,
        r_multiple=r_multiple,
        brokerage=charges.brokerage,
        stt=charges.stt,
        exchange_charges=charges.exchange_charges,
        sebi_charges=charges.sebi_charges,
        stamp_duty=charges.stamp_duty,
        gst=charges.gst,
        ipft=charges.ipft,
        total_charges=charges.total_charges,
        broker=trade.broker,
        charge_schedule_version=charge_schedule_version,
        engine_version=PNL_ENGINE_VERSION,
    )
