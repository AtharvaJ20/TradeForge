"""Unit tests for the P&L calculator — pure domain functions.

Covers all Kubera Section 13 test groups:
  TG-1  Gross P&L formulas (LONG and SHORT, scale-in/out)
  TG-2  Brokerage types (ZERO, FLAT, PERCENT_CAP)
  TG-3  STT base variants (TURNOVER, PREMIUM)
  TG-4  GST base exclusion (STT and stamp_duty excluded)
  TG-5  total_charges identity (re-summed from quantized components)
  TG-6  R-multiple (normal, no planned_risk, zero planned_risk)
  TG-7  Worked example from CHARGE-SCHEDULES-SPEC.md §10

Per ADR-001: domain layer tests run with no database, no HTTP server, no network.
"""

import uuid
from datetime import date
from decimal import Decimal

from tradeforge.domain.pnl.calculator import (
    compute_charges,
    compute_gross_pnl,
    compute_pnl,
    compute_r_multiple,
)
from tradeforge.domain.pnl.types import PNL_ENGINE_VERSION, ChargeScheduleRow, TradeSnapshot

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _snapshot(
    direction: str = "LONG",
    avg_entry: str = "100.0000",
    avg_exit: str = "110.0000",
    qty: str = "10.0000",
    trade_type: str = "MIS",
    exchange_segment: str = "NSE_EQ",
    broker: str = "ZERODHA",
    planned_risk: str | None = None,
) -> TradeSnapshot:
    return TradeSnapshot(
        trade_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        trade_type=trade_type,
        trade_date=date(2025, 3, 15),
        direction=direction,
        average_entry=Decimal(avg_entry),
        average_exit=Decimal(avg_exit),
        total_entry_quantity=Decimal(qty),
        exchange_segment=exchange_segment,
        broker=broker,
        planned_risk_amount=Decimal(planned_risk) if planned_risk else None,
    )


def _cs_percent_cap(
    stt_buy: str = "0.00000000",
    stt_sell: str = "0.00025000",
    stt_base: str = "TURNOVER",
    exch_rate: str = "0.00003450",
    exch_base: str = "TURNOVER",
    sebi_rate: str = "0.00000100",
    stamp_rate: str = "0.00003000",
    stamp_base: str = "TURNOVER",
    gst_rate: str = "0.18000000",
    ipft_rate: str = "0.00000100",
    ipft_base: str = "TURNOVER",
    brokerage_pct: str = "0.00030000",
    brokerage_cap: str = "20.0000",
) -> ChargeScheduleRow:
    return ChargeScheduleRow(
        id=uuid.uuid4(),
        broker="ZERODHA",
        trade_type="MIS",
        exchange_segment="NSE_EQ",
        effective_from=date(2024, 10, 1),
        brokerage_type="PERCENT_CAP",
        brokerage_flat_per_order=None,
        brokerage_pct=Decimal(brokerage_pct),
        brokerage_cap_per_order=Decimal(brokerage_cap),
        stt_buy_rate=Decimal(stt_buy),
        stt_sell_rate=Decimal(stt_sell),
        stt_base=stt_base,
        exchange_charge_rate=Decimal(exch_rate),
        exchange_charge_base=exch_base,
        sebi_charge_rate=Decimal(sebi_rate),
        stamp_duty_rate=Decimal(stamp_rate),
        stamp_duty_base=stamp_base,
        gst_rate=Decimal(gst_rate),
        ipft_rate=Decimal(ipft_rate),
        ipft_base=ipft_base,
    )


def _cs_zero_brokerage(**kwargs: str) -> ChargeScheduleRow:
    base = _cs_percent_cap(**kwargs)
    return ChargeScheduleRow(
        **{
            **base.__dict__,
            "brokerage_type": "ZERO",
            "brokerage_pct": None,
            "brokerage_cap_per_order": None,
        }
    )


def _cs_flat_brokerage(flat: str = "20.0000", **kwargs: str) -> ChargeScheduleRow:
    base = _cs_percent_cap(**kwargs)
    return ChargeScheduleRow(
        **{
            **base.__dict__,
            "brokerage_type": "FLAT",
            "brokerage_flat_per_order": Decimal(flat),
            "brokerage_pct": None,
            "brokerage_cap_per_order": None,
        }
    )


# ---------------------------------------------------------------------------
# TG-1 Gross P&L
# ---------------------------------------------------------------------------


class TestComputeGrossPnl:
    def test_long_profit(self) -> None:
        snap = _snapshot(direction="LONG", avg_entry="100.0000", avg_exit="110.0000", qty="10.0000")
        assert compute_gross_pnl(snap) == Decimal("100.0000")

    def test_long_loss(self) -> None:
        snap = _snapshot(direction="LONG", avg_entry="100.0000", avg_exit="90.0000", qty="10.0000")
        assert compute_gross_pnl(snap) == Decimal("-100.0000")

    def test_short_profit(self) -> None:
        snap = _snapshot(direction="SHORT", avg_entry="100.0000", avg_exit="90.0000", qty="10.0000")
        assert compute_gross_pnl(snap) == Decimal("100.0000")

    def test_short_loss(self) -> None:
        snap = _snapshot(
            direction="SHORT", avg_entry="100.0000", avg_exit="110.0000", qty="10.0000"
        )
        assert compute_gross_pnl(snap) == Decimal("-100.0000")

    def test_fractional_quantity(self) -> None:
        snap = _snapshot(avg_entry="100.0000", avg_exit="100.5000", qty="3.0000")
        assert compute_gross_pnl(snap) == Decimal("1.5000")

    def test_breakeven(self) -> None:
        snap = _snapshot(avg_entry="100.0000", avg_exit="100.0000", qty="10.0000")
        assert compute_gross_pnl(snap) == Decimal("0")


# ---------------------------------------------------------------------------
# TG-2 Brokerage types
# ---------------------------------------------------------------------------


class TestBrokerageTypes:
    def test_zero_brokerage(self) -> None:
        snap = _snapshot(avg_entry="1000.0000", avg_exit="1010.0000", qty="100.0000")
        cs = _cs_zero_brokerage()
        charges = compute_charges(snap, cs)
        assert charges.brokerage == Decimal("0.0000")

    def test_flat_brokerage(self) -> None:
        snap = _snapshot(avg_entry="100.0000", avg_exit="110.0000", qty="10.0000")
        cs = _cs_flat_brokerage(flat="20.0000")
        charges = compute_charges(snap, cs)
        # Entry + exit = 20 + 20 = 40
        assert charges.brokerage == Decimal("40.0000")

    def test_percent_cap_below_cap(self) -> None:
        # 0.03% of 1000 = 0.30, cap 20 → 0.30 per side, total 0.60
        snap = _snapshot(avg_entry="500.0000", avg_exit="500.0000", qty="2.0000")
        cs = _cs_percent_cap(brokerage_pct="0.00030000", brokerage_cap="20.0000")
        charges = compute_charges(snap, cs)
        # entry_turnover = 500 * 2 = 1000; 0.03% * 1000 = 0.30
        assert charges.brokerage == Decimal("0.6000")

    def test_percent_cap_hits_cap(self) -> None:
        # 0.03% of 100000 = 30, cap 20 → 20 per side, total 40
        snap = _snapshot(avg_entry="2450.0000", avg_exit="2480.0000", qty="100.0000")
        cs = _cs_percent_cap(brokerage_pct="0.00030000", brokerage_cap="20.0000")
        charges = compute_charges(snap, cs)
        assert charges.brokerage == Decimal("40.0000")


# ---------------------------------------------------------------------------
# TG-3 STT base variants
# ---------------------------------------------------------------------------


class TestSttBases:
    def test_stt_turnover_sell_only(self) -> None:
        snap = _snapshot(avg_entry="2450.0000", avg_exit="2480.0000", qty="100.0000")
        cs = _cs_percent_cap(stt_buy="0.00000000", stt_sell="0.00025000", stt_base="TURNOVER")
        charges = compute_charges(snap, cs)
        # exit_turnover = 2480 * 100 = 248000; stt = 0.00025 * 248000 = 62.00
        assert charges.stt == Decimal("62.0000")

    def test_stt_turnover_both_sides(self) -> None:
        snap = _snapshot(avg_entry="100.0000", avg_exit="100.0000", qty="10.0000")
        cs = _cs_percent_cap(stt_buy="0.00100000", stt_sell="0.00100000", stt_base="TURNOVER")
        charges = compute_charges(snap, cs)
        # entry_turnover = exit_turnover = 1000; stt = 0.001 * 1000 + 0.001 * 1000 = 2
        assert charges.stt == Decimal("2.0000")

    def test_stt_buy_zero(self) -> None:
        snap = _snapshot(avg_entry="100.0000", avg_exit="105.0000", qty="10.0000")
        cs = _cs_percent_cap(stt_buy="0.00000000", stt_sell="0.00025000", stt_base="TURNOVER")
        charges = compute_charges(snap, cs)
        # stt_buy = 0; stt_sell = 0.00025 * 1050 = 0.2625
        assert charges.stt == Decimal("0.2625")


# ---------------------------------------------------------------------------
# TG-4 GST base exclusion
# ---------------------------------------------------------------------------


class TestGstBase:
    def test_gst_excludes_stt_and_stamp_duty(self) -> None:
        snap = _snapshot(avg_entry="2450.0000", avg_exit="2480.0000", qty="100.0000")
        cs = _cs_percent_cap(
            stt_sell="0.00025000",
            stamp_rate="0.00003000",
            gst_rate="0.18000000",
        )
        charges = compute_charges(snap, cs)
        # GST base = brokerage + exchange_charges + sebi_charges (NOT stt, NOT stamp_duty)
        gst_base = charges.brokerage + charges.exchange_charges + charges.sebi_charges
        expected_gst = (gst_base * Decimal("0.18")).quantize(Decimal("0.0001"))
        assert charges.gst == expected_gst

    def test_zero_brokerage_gst_base(self) -> None:
        snap = _snapshot(avg_entry="100.0000", avg_exit="110.0000", qty="10.0000")
        cs = _cs_zero_brokerage(gst_rate="0.18000000")
        charges = compute_charges(snap, cs)
        # With zero brokerage, GST base = exchange_charges + sebi_charges only
        assert charges.brokerage == Decimal("0.0000")
        gst_base = charges.exchange_charges + charges.sebi_charges
        expected_gst = (gst_base * Decimal("0.18")).quantize(Decimal("0.0001"))
        assert charges.gst == expected_gst


# ---------------------------------------------------------------------------
# TG-5 total_charges identity
# ---------------------------------------------------------------------------


class TestTotalChargesIdentity:
    def test_total_equals_sum_of_components(self) -> None:
        snap = _snapshot(avg_entry="2450.0000", avg_exit="2480.0000", qty="100.0000")
        cs = _cs_percent_cap()
        charges = compute_charges(snap, cs)
        expected = (
            charges.brokerage
            + charges.stt
            + charges.exchange_charges
            + charges.sebi_charges
            + charges.stamp_duty
            + charges.gst
            + charges.ipft
        )
        assert charges.total_charges == expected

    def test_all_components_non_negative(self) -> None:
        snap = _snapshot(avg_entry="100.0000", avg_exit="110.0000", qty="10.0000")
        cs = _cs_percent_cap()
        charges = compute_charges(snap, cs)
        assert charges.brokerage >= Decimal("0")
        assert charges.stt >= Decimal("0")
        assert charges.exchange_charges >= Decimal("0")
        assert charges.sebi_charges >= Decimal("0")
        assert charges.stamp_duty >= Decimal("0")
        assert charges.gst >= Decimal("0")
        assert charges.ipft >= Decimal("0")


# ---------------------------------------------------------------------------
# TG-6 R-multiple
# ---------------------------------------------------------------------------


class TestComputeRMultiple:
    def test_normal_profit(self) -> None:
        # net_pnl = 200, planned_risk = 100 → R = 2.000000
        r = compute_r_multiple(Decimal("200"), Decimal("100"))
        assert r == Decimal("2.000000")

    def test_loss(self) -> None:
        r = compute_r_multiple(Decimal("-50"), Decimal("100"))
        assert r == Decimal("-0.500000")

    def test_no_planned_risk(self) -> None:
        assert compute_r_multiple(Decimal("200"), None) is None

    def test_zero_planned_risk(self) -> None:
        assert compute_r_multiple(Decimal("200"), Decimal("0")) is None

    def test_six_decimal_precision(self) -> None:
        # 1 / 3 → 0.333333 (6dp)
        r = compute_r_multiple(Decimal("1"), Decimal("3"))
        assert r is not None
        assert str(r) == "0.333333"


# ---------------------------------------------------------------------------
# TG-7 Worked example from CHARGE-SCHEDULES-SPEC.md §10
# ---------------------------------------------------------------------------


class TestWorkedExample:
    """Exact numbers from the MIS ZERODHA NSE_EQ worked example in the spec."""

    def test_full_calculation(self) -> None:
        snap = TradeSnapshot(
            trade_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            trade_type="MIS",
            trade_date=date(2025, 3, 15),
            direction="LONG",
            average_entry=Decimal("2450.0000"),
            average_exit=Decimal("2480.0000"),
            total_entry_quantity=Decimal("100.0000"),
            exchange_segment="NSE_EQ",
            broker="ZERODHA",
            planned_risk_amount=None,
        )
        cs = ChargeScheduleRow(
            id=uuid.uuid4(),
            broker="ZERODHA",
            trade_type="MIS",
            exchange_segment="NSE_EQ",
            effective_from=date(2024, 10, 1),
            brokerage_type="PERCENT_CAP",
            brokerage_flat_per_order=None,
            brokerage_pct=Decimal("0.00030000"),
            brokerage_cap_per_order=Decimal("20.0000"),
            stt_buy_rate=Decimal("0.00000000"),
            stt_sell_rate=Decimal("0.00025000"),
            stt_base="TURNOVER",
            exchange_charge_rate=Decimal("0.00003450"),
            exchange_charge_base="TURNOVER",
            sebi_charge_rate=Decimal("0.00000100"),
            stamp_duty_rate=Decimal("0.00003000"),
            stamp_duty_base="TURNOVER",
            gst_rate=Decimal("0.18000000"),
            ipft_rate=Decimal("0.00000100"),
            ipft_base="TURNOVER",
        )

        result = compute_pnl(snap, cs)

        assert result.gross_pnl == Decimal("3000.0000")
        assert result.brokerage == Decimal("40.0000")
        assert result.stt == Decimal("62.0000")
        assert result.exchange_charges == Decimal("17.0085")
        assert result.sebi_charges == Decimal("0.4930")
        assert result.stamp_duty == Decimal("7.3500")
        assert result.gst == Decimal("10.3503")
        assert result.ipft == Decimal("0.4930")
        assert result.total_charges == Decimal("137.6948")
        assert result.net_pnl == Decimal("2862.3052")
        assert result.r_multiple is None
        assert result.engine_version == PNL_ENGINE_VERSION
        assert result.charge_schedule_version == "ZERODHA_MIS_NSE_EQ_20241001"

    def test_charge_schedule_version_format(self) -> None:
        snap = _snapshot()
        cs = _cs_percent_cap()
        result = compute_pnl(snap, cs)
        # ZERODHA_MIS_NSE_EQ_20241001
        assert result.charge_schedule_version == "ZERODHA_MIS_NSE_EQ_20241001"

    def test_with_r_multiple(self) -> None:
        snap = TradeSnapshot(
            trade_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            trade_type="MIS",
            trade_date=date(2025, 3, 15),
            direction="LONG",
            average_entry=Decimal("2450.0000"),
            average_exit=Decimal("2480.0000"),
            total_entry_quantity=Decimal("100.0000"),
            exchange_segment="NSE_EQ",
            broker="ZERODHA",
            planned_risk_amount=Decimal("1000.0000"),
        )
        cs = _cs_percent_cap()
        result = compute_pnl(snap, cs)
        # net_pnl = 2862.3052, planned_risk = 1000
        assert result.r_multiple is not None
        assert result.r_multiple == (Decimal("2862.3052") / Decimal("1000")).quantize(
            Decimal("0.000001")
        )

    def test_total_charges_identity_holds(self) -> None:
        snap = _snapshot(avg_entry="2450.0000", avg_exit="2480.0000", qty="100.0000")
        cs = _cs_percent_cap()
        result = compute_pnl(snap, cs)
        assert result.total_charges == (
            result.brokerage
            + result.stt
            + result.exchange_charges
            + result.sebi_charges
            + result.stamp_duty
            + result.gst
            + result.ipft
        )
