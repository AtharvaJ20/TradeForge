"""AnalyticsRepository — all SQL for the Step 12 analytics layer.

ADR-001: no business logic in this layer. Only data retrieval and parameterisation.
ADR-007: all analytics SQL is confined to this class. AnalyticsService must not contain SQL.

Base query pattern:
  FROM  trades t
  JOIN  trade_pnl tp ON tp.trade_id = t.id
  WHERE t.user_id = :uid AND t.status = 'CLOSED'
  AND   optional filters from AnalyticsFilter
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import Integer, case, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.domain.analytics.types import (
    AnalyticsFilter,
    ChargesBreakdown,
    EquityCurvePoint,
    ExitTypeRow,
    HoldDurationBucket,
    HoldDurationDistribution,
    OutcomeDistribution,
    PlannedRRResult,
    PnlSummary,
    ProfitFactorResult,
    RBucket,
    SetupPerformanceRow,
)
from tradeforge.infrastructure.models.trade_domain import ExecutionFill, Instrument, Trade
from tradeforge.infrastructure.models.trade_pnl import TradePnl

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")


class AnalyticsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _base_where(self, f: AnalyticsFilter) -> list[Any]:
        """Build the common WHERE predicates from an AnalyticsFilter.

        Returns a list of SQLAlchemy clause elements. Callers pass to .where(*clauses).
        The instruments JOIN is appended separately when dimension filters require it.
        """
        clauses: list[Any] = [
            Trade.user_id == f.user_id,
            Trade.status == "CLOSED",
        ]
        if f.date_from is not None:
            clauses.append(Trade.trade_date >= f.date_from)
        if f.date_to is not None:
            clauses.append(Trade.trade_date <= f.date_to)
        if f.account_ids:
            clauses.append(Trade.account_id.in_(list(f.account_ids)))
        if f.trade_types:
            clauses.append(Trade.trade_type.in_(list(f.trade_types)))
        if f.directions:
            clauses.append(Trade.direction.in_(list(f.directions)))
        if f.setup_names:
            clauses.append(Trade.setup_name.in_(list(f.setup_names)))
        if f.brokers:
            clauses.append(TradePnl.broker.in_(list(f.brokers)))
        return clauses

    def _needs_instrument_join(self, f: AnalyticsFilter) -> bool:
        return bool(f.instrument_types or f.exchange_segments)

    def _apply_instrument_clauses(self, stmt: Any, f: AnalyticsFilter) -> Any:
        if f.instrument_types:
            stmt = stmt.where(Instrument.instrument_type.in_(list(f.instrument_types)))
        if f.exchange_segments:
            stmt = stmt.where(Instrument.exchange_segment.in_(list(f.exchange_segments)))
        return stmt

    # ------------------------------------------------------------------
    # M-1: Total P&L
    # ------------------------------------------------------------------

    async def get_pnl_summary(self, f: AnalyticsFilter) -> PnlSummary:
        stmt = (
            select(
                func.count(Trade.id).label("total_trades"),
                func.coalesce(func.sum(TradePnl.gross_pnl), _ZERO).label("gross_pnl"),
                func.coalesce(func.sum(TradePnl.net_pnl), _ZERO).label("net_pnl"),
                func.coalesce(func.sum(TradePnl.total_charges), _ZERO).label("total_charges"),
            )
            .select_from(Trade)
            .join(TradePnl, TradePnl.trade_id == Trade.id)
            .where(*self._base_where(f))
        )
        if self._needs_instrument_join(f):
            stmt = stmt.join(Instrument, Trade.instrument_id == Instrument.id)
            stmt = self._apply_instrument_clauses(stmt, f)

        row = (await self._db.execute(stmt)).one()
        return PnlSummary(
            total_trades=row.total_trades or 0,
            gross_pnl=row.gross_pnl or _ZERO,
            net_pnl=row.net_pnl or _ZERO,
            total_charges=row.total_charges or _ZERO,
        )

    # ------------------------------------------------------------------
    # M-2: Outcome distribution
    # ------------------------------------------------------------------

    async def get_outcome_distribution(self, f: AnalyticsFilter) -> OutcomeDistribution:
        """G-CORR-01: strict classification — win = net_pnl > 0, loss < 0, breakeven = 0."""
        stmt = (
            select(
                func.count(Trade.id).label("total_n"),
                func.count().filter(TradePnl.net_pnl > 0).label("win_count"),
                func.count().filter(TradePnl.net_pnl < 0).label("loss_count"),
                func.count().filter(TradePnl.net_pnl == 0).label("breakeven_count"),
            )
            .select_from(Trade)
            .join(TradePnl, TradePnl.trade_id == Trade.id)
            .where(*self._base_where(f))
        )
        if self._needs_instrument_join(f):
            stmt = stmt.join(Instrument, Trade.instrument_id == Instrument.id)
            stmt = self._apply_instrument_clauses(stmt, f)

        row = (await self._db.execute(stmt)).one()
        total_n = row.total_n or 0
        win_count = row.win_count or 0
        loss_count = row.loss_count or 0
        breakeven_count = row.breakeven_count or 0

        def _rate(n: int) -> Decimal:
            return (Decimal(n) / Decimal(total_n) * _HUNDRED) if total_n else _ZERO

        return OutcomeDistribution(
            win_count=win_count,
            loss_count=loss_count,
            breakeven_count=breakeven_count,
            total_n=total_n,
            win_rate=_rate(win_count),
            loss_rate=_rate(loss_count),
            breakeven_rate=_rate(breakeven_count),
        )

    # ------------------------------------------------------------------
    # M-3: R-multiple components (returned to AnalyticsService for calc)
    # ------------------------------------------------------------------

    async def get_r_multiple_series(
        self,
        f: AnalyticsFilter,
    ) -> tuple[list[Decimal], list[Decimal]]:
        """Return (win_r_multiples, loss_r_multiples) — G-CORR-01 strict classification.

        Breakeven trades (net_pnl = 0) are excluded. Trades without an r_multiple
        are also excluded (NULL r_multiple means planned_risk_amount was not set).
        """
        stmt = (
            select(TradePnl.r_multiple, TradePnl.net_pnl)
            .select_from(Trade)
            .join(TradePnl, TradePnl.trade_id == Trade.id)
            .where(
                *self._base_where(f),
                TradePnl.r_multiple.is_not(None),
                TradePnl.net_pnl != 0,
            )
        )
        if self._needs_instrument_join(f):
            stmt = stmt.join(Instrument, Trade.instrument_id == Instrument.id)
            stmt = self._apply_instrument_clauses(stmt, f)

        rows = (await self._db.execute(stmt)).all()
        win_r = [r.r_multiple for r in rows if r.net_pnl > 0]
        loss_r = [r.r_multiple for r in rows if r.net_pnl < 0]
        return win_r, loss_r

    # ------------------------------------------------------------------
    # M-4: Profit factor
    # ------------------------------------------------------------------

    async def get_profit_factor(self, f: AnalyticsFilter) -> ProfitFactorResult:
        stmt = (
            select(
                func.coalesce(
                    func.sum(TradePnl.net_pnl).filter(TradePnl.net_pnl > 0), _ZERO
                ).label("gross_profit"),
                func.coalesce(
                    func.sum(TradePnl.net_pnl).filter(TradePnl.net_pnl < 0), _ZERO
                ).label("gross_loss"),
            )
            .select_from(Trade)
            .join(TradePnl, TradePnl.trade_id == Trade.id)
            .where(*self._base_where(f))
        )
        if self._needs_instrument_join(f):
            stmt = stmt.join(Instrument, Trade.instrument_id == Instrument.id)
            stmt = self._apply_instrument_clauses(stmt, f)

        row = (await self._db.execute(stmt)).one()
        gross_profit = row.gross_profit or _ZERO
        gross_loss = row.gross_loss or _ZERO  # negative number

        pf: Decimal | None = None
        if gross_loss < _ZERO:
            pf = gross_profit / abs(gross_loss)

        return ProfitFactorResult(
            profit_factor=pf,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
        )

    # ------------------------------------------------------------------
    # M-5: Planned R:R
    # ------------------------------------------------------------------

    async def get_planned_rr(self, f: AnalyticsFilter) -> PlannedRRResult:
        """Compute planned R:R for LONG and SHORT trades.

        G-CONF-01: both directions use sign-cancelling formulas that yield positive ratios.
          LONG:  (planned_target - average_entry) / (average_entry - planned_stop)
          SHORT: (average_entry - planned_target) / (planned_stop - average_entry)
        """
        rr_expr = case(
            (
                Trade.direction == "LONG",
                (Trade.planned_target - Trade.average_entry)
                / (Trade.average_entry - Trade.planned_stop),
            ),
            (
                Trade.direction == "SHORT",
                (Trade.average_entry - Trade.planned_target)
                / (Trade.planned_stop - Trade.average_entry),
            ),
            else_=None,
        )
        stmt = (
            select(
                func.count(Trade.id).label("total_count"),
                func.count(rr_expr).label("rr_count"),
                func.avg(rr_expr).label("avg_rr"),
            )
            .select_from(Trade)
            .join(TradePnl, TradePnl.trade_id == Trade.id)
            .where(
                *self._base_where(f),
                Trade.planned_target.is_not(None),
                Trade.planned_stop.is_not(None),
                Trade.average_entry.is_not(None),
            )
        )
        if self._needs_instrument_join(f):
            stmt = stmt.join(Instrument, Trade.instrument_id == Instrument.id)
            stmt = self._apply_instrument_clauses(stmt, f)

        # total_count without the planned_* filter
        total_stmt = (
            select(func.count(Trade.id))
            .select_from(Trade)
            .join(TradePnl, TradePnl.trade_id == Trade.id)
            .where(*self._base_where(f))
        )
        total_count = (await self._db.execute(total_stmt)).scalar_one() or 0

        row = (await self._db.execute(stmt)).one()
        rr_count = row.rr_count or 0
        coverage_pct = (
            (Decimal(rr_count) / Decimal(total_count) * _HUNDRED) if total_count else _ZERO
        )

        return PlannedRRResult(
            avg_planned_rr=row.avg_rr,
            trade_count_with_rr=rr_count,
            total_count=total_count,
            coverage_pct=coverage_pct,
        )

    # ------------------------------------------------------------------
    # M-6: R-multiple distribution (stats + buckets)
    # ------------------------------------------------------------------

    async def get_r_distribution_stats(self, f: AnalyticsFilter) -> dict[str, Any]:
        """Return raw stats for RMultipleDistribution; bucketing done in service."""
        stmt = (
            select(
                func.count(TradePnl.r_multiple).label("coverage_count"),
                func.count(Trade.id).label("total_count"),
                func.avg(TradePnl.r_multiple).label("mean_r"),
                func.percentile_cont(Decimal("0.5"))
                .within_group(TradePnl.r_multiple)
                .label("median_r"),
                func.percentile_cont(Decimal("0.25"))
                .within_group(TradePnl.r_multiple)
                .label("p25_r"),
                func.percentile_cont(Decimal("0.75"))
                .within_group(TradePnl.r_multiple)
                .label("p75_r"),
                func.stddev(TradePnl.r_multiple).label("stddev_r"),
            )
            .select_from(Trade)
            .join(TradePnl, TradePnl.trade_id == Trade.id)
            .where(*self._base_where(f))
        )
        if self._needs_instrument_join(f):
            stmt = stmt.join(Instrument, Trade.instrument_id == Instrument.id)
            stmt = self._apply_instrument_clauses(stmt, f)

        row = (await self._db.execute(stmt)).one()
        return dict(row._mapping)

    async def get_r_distribution_buckets(self, f: AnalyticsFilter) -> list[RBucket]:
        """Return histogram buckets for R-multiple distribution."""
        # Buckets: < -2, -2 to -1, -1 to 0, 0 to 1, 1 to 2, > 2
        bucket_defs: list[tuple[str, Decimal | None, Decimal | None]] = [
            ("< -2R", None, Decimal("-2")),
            ("-2R to -1R", Decimal("-2"), Decimal("-1")),
            ("-1R to 0R", Decimal("-1"), Decimal("0")),
            ("0R to 1R", Decimal("0"), Decimal("1")),
            ("1R to 2R", Decimal("1"), Decimal("2")),
            ("> 2R", Decimal("2"), None),
        ]
        buckets: list[RBucket] = []
        for label, lower, upper in bucket_defs:
            stmt = (
                select(func.count(TradePnl.r_multiple).label("cnt"))
                .select_from(Trade)
                .join(TradePnl, TradePnl.trade_id == Trade.id)
                .where(*self._base_where(f), TradePnl.r_multiple.is_not(None))
            )
            if lower is not None:
                stmt = stmt.where(TradePnl.r_multiple >= lower)
            if upper is not None:
                stmt = stmt.where(TradePnl.r_multiple < upper)
            if self._needs_instrument_join(f):
                stmt = stmt.join(Instrument, Trade.instrument_id == Instrument.id)
                stmt = self._apply_instrument_clauses(stmt, f)

            cnt = (await self._db.execute(stmt)).scalar_one() or 0
            buckets.append(RBucket(label=label, lower=lower, upper=upper, count=cnt))

        return buckets

    # ------------------------------------------------------------------
    # M-7: Equity curve
    # ------------------------------------------------------------------

    async def get_equity_curve(self, f: AnalyticsFilter) -> list[EquityCurvePoint]:
        """Return ordered equity curve rows with cumulative net P&L.

        G-CONF-03: deterministic ordering — trade_date ASC, last_fill_at ASC, id ASC.
        """
        stmt = (
            select(
                Trade.id.label("trade_id"),
                Trade.trade_date,
                TradePnl.net_pnl,
                func.sum(TradePnl.net_pnl)
                .over(order_by=[Trade.trade_date, Trade.last_fill_at, Trade.id])
                .label("cumulative_net_pnl"),
            )
            .select_from(Trade)
            .join(TradePnl, TradePnl.trade_id == Trade.id)
            .where(*self._base_where(f))
            .order_by(Trade.trade_date, Trade.last_fill_at, Trade.id)
        )
        if self._needs_instrument_join(f):
            stmt = stmt.join(Instrument, Trade.instrument_id == Instrument.id)
            stmt = self._apply_instrument_clauses(stmt, f)

        rows = (await self._db.execute(stmt)).all()
        return [
            EquityCurvePoint(
                trade_date=r.trade_date,
                trade_id=r.trade_id,
                net_pnl=r.net_pnl,
                cumulative_net_pnl=r.cumulative_net_pnl,
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # M-9: By setup
    # ------------------------------------------------------------------

    async def get_by_setup(self, f: AnalyticsFilter) -> list[SetupPerformanceRow]:
        stmt = (
            select(
                Trade.setup_name,
                func.count(Trade.id).label("trade_count"),
                func.count().filter(TradePnl.net_pnl > 0).label("win_count"),
                func.count().filter(TradePnl.net_pnl < 0).label("loss_count"),
                func.count().filter(TradePnl.net_pnl == 0).label("breakeven_count"),
                func.coalesce(func.avg(TradePnl.net_pnl), _ZERO).label("avg_net_pnl"),
                func.coalesce(func.sum(TradePnl.net_pnl), _ZERO).label("total_net_pnl"),
                func.avg(TradePnl.r_multiple).label("avg_r"),
            )
            .select_from(Trade)
            .join(TradePnl, TradePnl.trade_id == Trade.id)
            .where(*self._base_where(f))
            .group_by(Trade.setup_name)
            .order_by(func.sum(TradePnl.net_pnl).desc())
        )
        if self._needs_instrument_join(f):
            stmt = stmt.join(Instrument, Trade.instrument_id == Instrument.id)
            stmt = self._apply_instrument_clauses(stmt, f)

        rows = (await self._db.execute(stmt)).all()
        result: list[SetupPerformanceRow] = []
        for r in rows:
            tc = r.trade_count or 0
            wc = r.win_count or 0
            lc = r.loss_count or 0
            result.append(
                SetupPerformanceRow(
                    setup_name=r.setup_name,
                    trade_count=tc,
                    win_count=wc,
                    loss_count=lc,
                    breakeven_count=r.breakeven_count or 0,
                    win_rate=(Decimal(wc) / Decimal(tc) * _HUNDRED) if tc else _ZERO,
                    avg_net_pnl=r.avg_net_pnl or _ZERO,
                    total_net_pnl=r.total_net_pnl or _ZERO,
                    avg_r_multiple=r.avg_r,
                    expectancy_r=None,   # service computes from r_multiple series
                    profit_factor=None,  # service computes
                )
            )
        return result

    # ------------------------------------------------------------------
    # M-10: By direction
    # ------------------------------------------------------------------

    async def get_by_direction(
        self, f: AnalyticsFilter
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                Trade.direction,
                func.count(Trade.id).label("trade_count"),
                func.count().filter(TradePnl.net_pnl > 0).label("win_count"),
                func.count().filter(TradePnl.net_pnl < 0).label("loss_count"),
                func.count().filter(TradePnl.net_pnl == 0).label("breakeven_count"),
                func.coalesce(func.avg(TradePnl.net_pnl), _ZERO).label("avg_net_pnl"),
                func.coalesce(func.sum(TradePnl.net_pnl), _ZERO).label("total_net_pnl"),
                func.avg(TradePnl.r_multiple).label("avg_r"),
            )
            .select_from(Trade)
            .join(TradePnl, TradePnl.trade_id == Trade.id)
            .where(*self._base_where(f))
            .group_by(Trade.direction)
        )
        if self._needs_instrument_join(f):
            stmt = stmt.join(Instrument, Trade.instrument_id == Instrument.id)
            stmt = self._apply_instrument_clauses(stmt, f)

        rows = (await self._db.execute(stmt)).all()
        return [dict(r._mapping) for r in rows]

    # ------------------------------------------------------------------
    # M-11: Charges breakdown
    # ------------------------------------------------------------------

    async def get_charges_breakdown(self, f: AnalyticsFilter) -> ChargesBreakdown:
        """Fetch aggregate charge columns. G-CORR-03 suppression is done in service."""
        stmt = (
            select(
                func.coalesce(func.sum(TradePnl.brokerage), _ZERO).label("brokerage"),
                func.coalesce(func.sum(TradePnl.stt), _ZERO).label("stt"),
                func.coalesce(func.sum(TradePnl.exchange_charges), _ZERO).label("exchange_charges"),
                func.coalesce(func.sum(TradePnl.sebi_charges), _ZERO).label("sebi_charges"),
                func.coalesce(func.sum(TradePnl.stamp_duty), _ZERO).label("stamp_duty"),
                func.coalesce(func.sum(TradePnl.gst), _ZERO).label("gst"),
                func.coalesce(func.sum(TradePnl.ipft), _ZERO).label("ipft"),
                func.coalesce(func.sum(TradePnl.total_charges), _ZERO).label("total_charges"),
                func.coalesce(func.sum(TradePnl.gross_pnl), _ZERO).label("gross_pnl"),
            )
            .select_from(Trade)
            .join(TradePnl, TradePnl.trade_id == Trade.id)
            .where(*self._base_where(f))
        )
        if self._needs_instrument_join(f):
            stmt = stmt.join(Instrument, Trade.instrument_id == Instrument.id)
            stmt = self._apply_instrument_clauses(stmt, f)

        row = (await self._db.execute(stmt)).one()
        # G-CORR-03 charge_drag_pct and charges_added_to_loss are computed in AnalyticsService
        return ChargesBreakdown(
            total_brokerage=row.brokerage,
            total_stt=row.stt,
            total_exchange_charges=row.exchange_charges,
            total_sebi_charges=row.sebi_charges,
            total_stamp_duty=row.stamp_duty,
            total_gst=row.gst,
            total_ipft=row.ipft,
            total_charges=row.total_charges,
            total_gross_pnl=row.gross_pnl,
            charge_drag_pct=None,   # suppression logic in service
            charges_added_to_loss=None,
        )

    # ------------------------------------------------------------------
    # M-12: Streak net_pnl series (ordered)
    # ------------------------------------------------------------------

    async def get_net_pnl_series(self, f: AnalyticsFilter) -> list[Decimal]:
        """Return net_pnl values ordered by (trade_date, last_fill_at, id) for streak calc."""
        stmt = (
            select(TradePnl.net_pnl)
            .select_from(Trade)
            .join(TradePnl, TradePnl.trade_id == Trade.id)
            .where(*self._base_where(f))
            .order_by(Trade.trade_date, Trade.last_fill_at, Trade.id)
        )
        if self._needs_instrument_join(f):
            stmt = stmt.join(Instrument, Trade.instrument_id == Instrument.id)
            stmt = self._apply_instrument_clauses(stmt, f)

        rows = (await self._db.execute(stmt)).scalars().all()
        return list(rows)

    # ------------------------------------------------------------------
    # M-13: Hold duration distribution
    # ------------------------------------------------------------------

    async def get_hold_duration_distribution(
        self, f: AnalyticsFilter
    ) -> HoldDurationDistribution:
        """Bucket hold durations by EXTRACT(EPOCH FROM last_fill_at - first_fill_at) / 60."""
        duration_minutes = func.extract(
            "epoch",
            Trade.last_fill_at - Trade.first_fill_at,
        ) / 60

        bucket_expr = case(
            (duration_minutes < 15, literal("< 15 min")),
            (duration_minutes < 60, literal("15 min – 1 hr")),
            (duration_minutes < 240, literal("1 – 4 hr")),
            (duration_minutes < 1440, literal("4 – 24 hr")),
            (duration_minutes < 10080, literal("1 – 7 days")),
            else_=literal("> 7 days"),
        )
        bucket_order_expr = case(
            (duration_minutes < 15, literal(1).cast(Integer)),
            (duration_minutes < 60, literal(2).cast(Integer)),
            (duration_minutes < 240, literal(3).cast(Integer)),
            (duration_minutes < 1440, literal(4).cast(Integer)),
            (duration_minutes < 10080, literal(5).cast(Integer)),
            else_=literal(6).cast(Integer),
        )

        stmt = (
            select(
                bucket_expr.label("bucket"),
                bucket_order_expr.label("bucket_order"),
                func.count(Trade.id).label("bucket_count"),
                func.coalesce(func.avg(TradePnl.net_pnl), _ZERO).label("avg_net_pnl"),
                func.count().filter(TradePnl.net_pnl > 0).label("win_count"),
            )
            .select_from(Trade)
            .join(TradePnl, TradePnl.trade_id == Trade.id)
            .where(*self._base_where(f))
            .group_by(bucket_expr, bucket_order_expr)
            .order_by(bucket_order_expr)
        )
        if self._needs_instrument_join(f):
            stmt = stmt.join(Instrument, Trade.instrument_id == Instrument.id)
            stmt = self._apply_instrument_clauses(stmt, f)

        duration_agg_stmt = (
            select(
                func.avg(duration_minutes).label("avg_dur"),
                func.percentile_cont(Decimal("0.5"))
                .within_group(duration_minutes)
                .label("median_dur"),
            )
            .select_from(Trade)
            .join(TradePnl, TradePnl.trade_id == Trade.id)
            .where(
                *self._base_where(f),
                Trade.first_fill_at.is_not(None),
                Trade.last_fill_at.is_not(None),
            )
        )

        rows = (await self._db.execute(stmt)).all()
        agg = (await self._db.execute(duration_agg_stmt)).one()

        buckets = [
            HoldDurationBucket(
                bucket=r.bucket,
                bucket_order=r.bucket_order,
                count=r.bucket_count,
                avg_net_pnl=r.avg_net_pnl,
                win_rate=(
                    Decimal(r.win_count) / Decimal(r.bucket_count) * _HUNDRED
                    if r.bucket_count else _ZERO
                ),
            )
            for r in rows
        ]

        return HoldDurationDistribution(
            buckets=buckets,
            avg_duration_minutes=agg.avg_dur,
            median_duration_minutes=agg.median_dur,
        )

    # ------------------------------------------------------------------
    # M-14: By exit type (G-CORR-02)
    # ------------------------------------------------------------------

    async def get_by_exit_type(self, f: AnalyticsFilter) -> list[ExitTypeRow]:
        """G-CORR-02: exit_type derived from the last EXIT fill by fill_timestamp DESC.

        Uses DISTINCT ON (trade_id) ORDER BY trade_id, fill_timestamp DESC on the
        execution_fills table filtered to fill_role = 'EXIT'.
        """
        # CTE: last EXIT fill per trade
        exit_fill_cte = (
            select(
                ExecutionFill.trade_id.label("trade_id"),
                ExecutionFill.exit_type.label("exit_type"),
            )
            .distinct(ExecutionFill.trade_id)
            .where(ExecutionFill.fill_role == "EXIT")
            .order_by(ExecutionFill.trade_id, ExecutionFill.fill_timestamp.desc())
            .cte("last_exit_fill")
        )

        stmt = (
            select(
                exit_fill_cte.c.exit_type,
                func.count(Trade.id).label("trade_count"),
                func.count().filter(TradePnl.net_pnl > 0).label("win_count"),
                func.coalesce(func.avg(TradePnl.net_pnl), _ZERO).label("avg_net_pnl"),
                func.avg(TradePnl.r_multiple).label("avg_r"),
            )
            .select_from(Trade)
            .join(TradePnl, TradePnl.trade_id == Trade.id)
            .outerjoin(exit_fill_cte, exit_fill_cte.c.trade_id == Trade.id)
            .where(*self._base_where(f))
            .group_by(exit_fill_cte.c.exit_type)
            .order_by(func.count(Trade.id).desc())
        )
        if self._needs_instrument_join(f):
            stmt = stmt.join(Instrument, Trade.instrument_id == Instrument.id)
            stmt = self._apply_instrument_clauses(stmt, f)

        rows = (await self._db.execute(stmt)).all()
        return [
            ExitTypeRow(
                exit_type=r.exit_type,
                trade_count=r.trade_count,
                win_rate=(
                    Decimal(r.win_count) / Decimal(r.trade_count) * _HUNDRED
                    if r.trade_count else _ZERO
                ),
                avg_net_pnl=r.avg_net_pnl,
                avg_r_multiple=r.avg_r,
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # N-3: Monte Carlo r_multiple series
    # ------------------------------------------------------------------

    async def get_r_multiples_for_monte_carlo(self, f: AnalyticsFilter) -> list[Decimal]:
        """Return all non-null r_multiple values for Monte Carlo simulation."""
        stmt = (
            select(TradePnl.r_multiple)
            .select_from(Trade)
            .join(TradePnl, TradePnl.trade_id == Trade.id)
            .where(*self._base_where(f), TradePnl.r_multiple.is_not(None))
        )
        if self._needs_instrument_join(f):
            stmt = stmt.join(Instrument, Trade.instrument_id == Instrument.id)
            stmt = self._apply_instrument_clauses(stmt, f)

        return [r for r in (await self._db.execute(stmt)).scalars() if r is not None]
