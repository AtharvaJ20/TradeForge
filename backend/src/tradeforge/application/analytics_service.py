"""AnalyticsService — application-layer orchestrator for Step 12 analytics.

ADR-007:
  - Orchestrates AnalyticsRepository (SQL) + domain calculators (pure Python).
  - Owns G-CORR-03: charge_drag_pct suppression when gross_pnl <= 0.
  - Contains zero SQL. All data access goes through AnalyticsRepository.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from tradeforge.domain.analytics.calculators import (
    compute_drawdown_stats,
    compute_expectancy,
    compute_monte_carlo,
    compute_sharpe_ratio,
    compute_sortino_ratio,
    compute_streak_stats,
)
from tradeforge.domain.analytics.types import (
    AccountDimension,
    AnalyticsFilter,
    AnalyticsSummary,
    ChargesBreakdown,
    DimensionBreakdown,
    DirectionPerformanceRow,
    EquityCurvePoint,
    ExitTypeRow,
    HoldDurationDistribution,
    MonteCarloResult,
    RiskAdjustedResult,
    RMultipleDistribution,
    SetupPerformanceRow,
    StreakStats,
)
from tradeforge.infrastructure.repositories.analytics_repo import AnalyticsRepository

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")


class AnalyticsService:
    def __init__(self, repo: AnalyticsRepository) -> None:
        self._repo = repo

    # ------------------------------------------------------------------
    # Composite summary (M-1, M-2, M-3, M-4, M-5, M-8, M-10, M-11)
    # ------------------------------------------------------------------

    async def get_summary(self, f: AnalyticsFilter) -> AnalyticsSummary:
        pnl = await self._repo.get_pnl_summary(f)
        outcome = await self._repo.get_outcome_distribution(f)
        profit_factor = await self._repo.get_profit_factor(f)
        planned_rr = await self._repo.get_planned_rr(f)

        win_r, loss_r = await self._repo.get_r_multiple_series(f)
        expectancy = compute_expectancy(
            win_r_multiples=win_r,
            loss_r_multiples=loss_r,
            total_count=outcome.total_n,
        )

        # Sharpe and Sortino reuse the already-fetched r_multiple series —
        # no additional DB query (ADR-007A §Decision 2).
        all_r = list(win_r) + list(loss_r)
        sharpe = compute_sharpe_ratio(all_r)
        sortino = compute_sortino_ratio(all_r)
        risk_adjusted = RiskAdjustedResult(sharpe=sharpe, sortino=sortino)

        curve = await self._repo.get_equity_curve(f)
        drawdown = compute_drawdown_stats(curve)

        direction_raw = await self._repo.get_by_direction(f)
        direction = _build_direction_rows(direction_raw)

        charges_raw = await self._repo.get_charges_breakdown(f)
        charges = _apply_charge_drag_suppression(charges_raw)

        return AnalyticsSummary(
            pnl=pnl,
            outcome=outcome,
            expectancy=expectancy,
            profit_factor=profit_factor,
            planned_rr=planned_rr,
            drawdown=drawdown,
            direction=direction,
            charges=charges,
            risk_adjusted=risk_adjusted,
        )

    # ------------------------------------------------------------------
    # M-7 equity curve
    # ------------------------------------------------------------------

    async def get_equity_curve(self, f: AnalyticsFilter) -> list[EquityCurvePoint]:
        return await self._repo.get_equity_curve(f)

    # ------------------------------------------------------------------
    # M-6 R-multiple distribution
    # ------------------------------------------------------------------

    async def get_r_distribution(self, f: AnalyticsFilter) -> RMultipleDistribution:
        stats = await self._repo.get_r_distribution_stats(f)
        buckets = await self._repo.get_r_distribution_buckets(f)

        coverage_count = stats.get("coverage_count") or 0
        total_count = stats.get("total_count") or 0
        coverage_pct = (
            Decimal(coverage_count) / Decimal(total_count) * _HUNDRED if total_count else _ZERO
        )

        return RMultipleDistribution(
            mean_r=stats.get("mean_r"),
            median_r=stats.get("median_r"),
            stddev_r=stats.get("stddev_r"),
            p25_r=stats.get("p25_r"),
            p75_r=stats.get("p75_r"),
            coverage_count=coverage_count,
            total_count=total_count,
            coverage_pct=coverage_pct,
            # G-ADV-M6: insufficient_sample when fewer than 5 trades have a non-null
            # r_multiple — below this threshold the distribution is too sparse to be
            # meaningful (Step 12.6 spec; G-ADV-01 uses 30 for expectancy, 5 for distribution).
            insufficient_sample=coverage_count < 5,
            buckets=buckets,
        )

    # ------------------------------------------------------------------
    # M-9 by setup
    # ------------------------------------------------------------------

    async def get_by_setup(self, f: AnalyticsFilter) -> list[SetupPerformanceRow]:
        return await self._repo.get_by_setup(f)

    # ------------------------------------------------------------------
    # M-12 streaks
    # ------------------------------------------------------------------

    async def get_streaks(self, f: AnalyticsFilter) -> StreakStats:
        net_pnls = await self._repo.get_net_pnl_series(f)
        return compute_streak_stats(net_pnls)

    # ------------------------------------------------------------------
    # M-13 hold duration
    # ------------------------------------------------------------------

    async def get_hold_duration(self, f: AnalyticsFilter) -> HoldDurationDistribution:
        return await self._repo.get_hold_duration_distribution(f)

    # ------------------------------------------------------------------
    # M-14 by exit type
    # ------------------------------------------------------------------

    async def get_by_exit_type(self, f: AnalyticsFilter) -> list[ExitTypeRow]:
        return await self._repo.get_by_exit_type(f)

    # ------------------------------------------------------------------
    # M-10 dimension breakdown (Step 12.6)
    # ------------------------------------------------------------------

    async def get_dimension_breakdown(
        self,
        f: AnalyticsFilter,
        *,
        dimension: str,
    ) -> DimensionBreakdown:
        """Return per-group performance metrics for the requested dimension.

        Allowed dimensions: direction | setup | instrument | trade_type | segment.
        NULL setup_name groups as "(no setup)" (consistent with filter dimension convention).
        NULL r_multiple values are excluded from avg_r_multiple (not treated as 0);
        groups where all trades have NULL r_multiple return avg_r_multiple=None.
        """
        rows = await self._repo.get_dimension_breakdown(f, dimension=dimension)
        return DimensionBreakdown(dimension=dimension, groups=rows)

    # ------------------------------------------------------------------
    # N-3 Monte Carlo
    # ------------------------------------------------------------------

    async def get_monte_carlo(
        self,
        f: AnalyticsFilter,
        *,
        n_simulations: int = 1000,
    ) -> MonteCarloResult:
        r_multiples = await self._repo.get_r_multiples_for_monte_carlo(f)
        return compute_monte_carlo(r_multiples, n_simulations=n_simulations)

    # ------------------------------------------------------------------
    # Filter dimension pass-throughs (B-5)
    # ------------------------------------------------------------------

    async def get_filter_accounts(self, user_id: UUID) -> list[AccountDimension]:
        return await self._repo.get_distinct_accounts(user_id)

    async def get_filter_setups(self, user_id: UUID) -> list[str]:
        return await self._repo.get_distinct_setups(user_id)

    async def get_filter_brokers(self, user_id: UUID) -> list[str]:
        return await self._repo.get_distinct_brokers(user_id)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _apply_charge_drag_suppression(raw: ChargesBreakdown) -> ChargesBreakdown:
    """G-CORR-03: suppress charge_drag_pct when gross_pnl <= 0.

    When gross P&L is zero or negative, expressing charges as a percentage of
    gross P&L is undefined or misleading. Surface charges_added_to_loss (the
    absolute charge total) in INR for UI display instead.
    """
    if raw.total_gross_pnl > _ZERO:
        charge_drag_pct = raw.total_charges / raw.total_gross_pnl * _HUNDRED
        charges_added_to_loss = None
    else:
        charge_drag_pct = None
        charges_added_to_loss = raw.total_charges

    return ChargesBreakdown(
        total_brokerage=raw.total_brokerage,
        total_stt=raw.total_stt,
        total_exchange_charges=raw.total_exchange_charges,
        total_sebi_charges=raw.total_sebi_charges,
        total_stamp_duty=raw.total_stamp_duty,
        total_gst=raw.total_gst,
        total_ipft=raw.total_ipft,
        total_charges=raw.total_charges,
        total_gross_pnl=raw.total_gross_pnl,
        charge_drag_pct=charge_drag_pct,
        charges_added_to_loss=charges_added_to_loss,
    )


def _build_direction_rows(raw: list[dict]) -> list[DirectionPerformanceRow]:  # type: ignore[type-arg]
    rows: list[DirectionPerformanceRow] = []
    for r in raw:
        tc = r.get("trade_count") or 0
        wc = r.get("win_count") or 0
        lc = r.get("loss_count") or 0
        bc = r.get("breakeven_count") or 0
        rows.append(
            DirectionPerformanceRow(
                direction=r["direction"] or "UNKNOWN",
                trade_count=tc,
                win_count=wc,
                loss_count=lc,
                breakeven_count=bc,
                win_rate=(Decimal(wc) / Decimal(tc) * _HUNDRED) if tc else _ZERO,
                avg_net_pnl=r.get("avg_net_pnl") or _ZERO,
                total_net_pnl=r.get("total_net_pnl") or _ZERO,
                avg_r_multiple=r.get("avg_r"),
            )
        )
    return rows
