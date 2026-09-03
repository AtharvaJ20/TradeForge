"""Pure domain calculator functions for analytics metrics.

No database, no framework imports. All functions accept stdlib/Decimal types only.
Called by AnalyticsService after fetching raw data from AnalyticsRepository.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import TypeVar

from tradeforge.domain.analytics.types import (
    DrawdownStats,
    EquityCurvePoint,
    ExpectancyResult,
    MonteCarloResult,
    SharpeResult,
    SortinoResult,
    StreakStats,
)

_T = TypeVar("_T")

_ZERO = Decimal("0")
_ONE = Decimal("1")
_HUNDRED = Decimal("100")
_TWO = Decimal("2")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pct(numerator: Decimal, denominator: Decimal, *, places: int = 4) -> Decimal:
    """Return (numerator / denominator * 100) rounded to `places`, or 0 if denominator is 0."""
    if denominator == _ZERO:
        return _ZERO
    quantize_str = Decimal("0." + "0" * places)
    return (numerator / denominator * _HUNDRED).quantize(quantize_str, rounding=ROUND_HALF_UP)


def _safe_div(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == _ZERO:
        return None
    return numerator / denominator


# ---------------------------------------------------------------------------
# M-3: Expectancy
# ---------------------------------------------------------------------------


def compute_expectancy(
    *,
    win_r_multiples: Sequence[Decimal],
    loss_r_multiples: Sequence[Decimal],
    total_count: int,
) -> ExpectancyResult:
    """Compute expectancy in R-multiples.

    G-CORR-01: win/loss classification is strict (net_pnl > 0 / < 0); breakeven trades
    carry no r_multiple and are excluded from win_r_multiples and loss_r_multiples.
    G-ADV-01: insufficient_sample flag is based on r_coverage_count < 30, not total_count.

    Args:
        win_r_multiples:  r_multiple values for winning trades (net_pnl > 0, r_multiple NOT NULL)
        loss_r_multiples: r_multiple values for losing trades (net_pnl < 0, r_multiple NOT NULL)
        total_count:      total trades in the filter (wins + losses + breakevenss)
    """
    r_coverage_count = len(win_r_multiples) + len(loss_r_multiples)
    coverage_pct = _pct(Decimal(r_coverage_count), Decimal(total_count)) if total_count else _ZERO

    if r_coverage_count == 0:
        return ExpectancyResult(
            expectancy_r=None,
            avg_r_win=None,
            avg_r_loss=None,
            r_coverage_count=0,
            total_count=total_count,
            r_coverage_pct=coverage_pct,
            insufficient_sample=True,
        )

    avg_r_win: Decimal | None = None
    avg_r_loss: Decimal | None = None

    if win_r_multiples:
        avg_r_win = sum(win_r_multiples, _ZERO) / Decimal(len(win_r_multiples))

    if loss_r_multiples:
        avg_r_loss = abs(sum(loss_r_multiples, _ZERO) / Decimal(len(loss_r_multiples)))

    win_rate = Decimal(len(win_r_multiples)) / Decimal(r_coverage_count)
    loss_rate = Decimal(len(loss_r_multiples)) / Decimal(r_coverage_count)

    if avg_r_win is not None and avg_r_loss is not None:
        expectancy_r = win_rate * avg_r_win - loss_rate * avg_r_loss
    elif avg_r_win is not None:
        expectancy_r = avg_r_win
    else:
        expectancy_r = -(avg_r_loss or _ZERO)

    return ExpectancyResult(
        expectancy_r=expectancy_r,
        avg_r_win=avg_r_win,
        avg_r_loss=avg_r_loss,
        r_coverage_count=r_coverage_count,
        total_count=total_count,
        r_coverage_pct=coverage_pct,
        insufficient_sample=r_coverage_count < 30,
    )


# ---------------------------------------------------------------------------
# M-7 / M-8: Equity curve and drawdown
# ---------------------------------------------------------------------------


def compute_drawdown_stats(points: Sequence[EquityCurvePoint]) -> DrawdownStats:
    """Compute drawdown statistics from an ordered equity curve.

    Points must be ordered by (trade_date ASC, last_fill_at ASC, id ASC) — G-CONF-03.
    """
    if not points:
        return DrawdownStats(
            max_drawdown_pct=None,
            max_drawdown_inr=None,
            avg_drawdown_pct=None,
            current_drawdown_pct=None,
        )

    peak = points[0].cumulative_net_pnl
    max_dd_inr = _ZERO
    max_dd_pct: Decimal | None = None
    current_dd_pct: Decimal | None = None

    drawdown_pcts: list[Decimal] = []

    for pt in points:
        cum = pt.cumulative_net_pnl
        if cum > peak:
            peak = cum
        if peak > _ZERO:
            dd_pct = (peak - cum) / peak * _HUNDRED
            dd_inr = peak - cum
            if dd_pct > (max_dd_pct or _ZERO):
                max_dd_pct = dd_pct
                max_dd_inr = dd_inr
            if dd_pct > _ZERO:
                drawdown_pcts.append(dd_pct)

    # Current drawdown is the drawdown from the running peak at the last point
    last_cum = points[-1].cumulative_net_pnl
    if peak > _ZERO and last_cum < peak:
        current_dd_pct = (peak - last_cum) / peak * _HUNDRED
    else:
        current_dd_pct = _ZERO

    avg_dd_pct: Decimal | None = None
    if drawdown_pcts:
        avg_dd_pct = sum(drawdown_pcts, _ZERO) / Decimal(len(drawdown_pcts))

    return DrawdownStats(
        max_drawdown_pct=max_dd_pct,
        max_drawdown_inr=max_dd_inr if max_dd_pct is not None else None,
        avg_drawdown_pct=avg_dd_pct,
        current_drawdown_pct=current_dd_pct,
    )


# ---------------------------------------------------------------------------
# M-12: Streaks
# ---------------------------------------------------------------------------


def compute_streak_stats(net_pnls: Sequence[Decimal]) -> StreakStats:
    """Compute win/loss streak statistics from an ordered sequence of net P&Ls.

    G-CORR-01: win = net_pnl > 0, loss = net_pnl < 0. Breakeven (= 0) resets both streaks.
    """
    if not net_pnls:
        return StreakStats(
            current_win_streak=0,
            current_loss_streak=0,
            max_win_streak=0,
            max_loss_streak=0,
            avg_win_streak=_ZERO,
            avg_loss_streak=_ZERO,
        )

    current_win_streak = 0
    current_loss_streak = 0
    max_win_streak = 0
    max_loss_streak = 0

    win_streaks: list[int] = []
    loss_streaks: list[int] = []

    _cw = 0
    _cl = 0

    for pnl in net_pnls:
        if pnl > _ZERO:
            _cw += 1
            if _cl > 0:
                loss_streaks.append(_cl)
                _cl = 0
        elif pnl < _ZERO:
            _cl += 1
            if _cw > 0:
                win_streaks.append(_cw)
                _cw = 0
        else:
            # breakeven — close both open streaks
            if _cw > 0:
                win_streaks.append(_cw)
                _cw = 0
            if _cl > 0:
                loss_streaks.append(_cl)
                _cl = 0

    # close trailing streaks
    if _cw > 0:
        win_streaks.append(_cw)
    if _cl > 0:
        loss_streaks.append(_cl)

    current_win_streak = _cw
    current_loss_streak = _cl
    max_win_streak = max(win_streaks, default=0)
    max_loss_streak = max(loss_streaks, default=0)

    avg_win = sum(win_streaks, 0) / Decimal(len(win_streaks)) if win_streaks else _ZERO
    avg_loss = sum(loss_streaks, 0) / Decimal(len(loss_streaks)) if loss_streaks else _ZERO

    return StreakStats(
        current_win_streak=current_win_streak,
        current_loss_streak=current_loss_streak,
        max_win_streak=max_win_streak,
        max_loss_streak=max_loss_streak,
        avg_win_streak=avg_win if isinstance(avg_win, Decimal) else Decimal(avg_win),
        avg_loss_streak=avg_loss if isinstance(avg_loss, Decimal) else Decimal(avg_loss),
    )


# ---------------------------------------------------------------------------
# M-8K / M-9K: Sharpe and Sortino (trade-based, Step 12.1)
# ---------------------------------------------------------------------------

_N_PER_YEAR_DEFAULT = 252  # G-CONF-12.1-A: NSE-aligned fixed annualization convention
_MIN_SAMPLE = 30  # Karna M-8/M-9 minimum; consistent with G-ADV-01


def compute_sharpe_ratio(
    r_multiples: Sequence[Decimal],
    *,
    n_per_year: int = _N_PER_YEAR_DEFAULT,
) -> SharpeResult:
    """Compute trade-based Sharpe Ratio.

    Formula: (mean_r / std_r) × √n_per_year  (population std-dev)
    G-CONF-12.1-A: n_per_year = 252 fixed convention.
    Returns sharpe_ratio=None when r_coverage_count < 30 or std_r == 0.
    """
    r_coverage_count = len(r_multiples)

    if r_coverage_count < _MIN_SAMPLE:
        return SharpeResult(
            sharpe_ratio=None,
            mean_r=None,
            std_r=None,
            n_per_year=n_per_year,
            r_coverage_count=r_coverage_count,
            insufficient_sample=True,
        )

    mean_r = sum(r_multiples, _ZERO) / Decimal(r_coverage_count)

    variance = sum((r - mean_r) ** _TWO for r in r_multiples) / Decimal(r_coverage_count)
    std_r = variance.sqrt()

    if std_r == _ZERO:
        return SharpeResult(
            sharpe_ratio=None,
            mean_r=mean_r,
            std_r=_ZERO,
            n_per_year=n_per_year,
            r_coverage_count=r_coverage_count,
            insufficient_sample=False,
        )

    annualization = Decimal(n_per_year).sqrt()
    sharpe_ratio = mean_r / std_r * annualization

    return SharpeResult(
        sharpe_ratio=sharpe_ratio,
        mean_r=mean_r,
        std_r=std_r,
        n_per_year=n_per_year,
        r_coverage_count=r_coverage_count,
        insufficient_sample=False,
    )


def compute_sortino_ratio(
    r_multiples: Sequence[Decimal],
    *,
    n_per_year: int = _N_PER_YEAR_DEFAULT,
) -> SortinoResult:
    """Compute trade-based Sortino Ratio.

    Formula: (mean_r / downside_dev) × √n_per_year  (population std-dev of losses)
    G-CONF-12.1-A: n_per_year = 252 fixed convention.
    G-CONF-12.1-B: downside = r_multiple < 0 strictly; MAR = 0; breakeven excluded.
    Returns sortino_ratio=None when r_coverage_count < 30 or no losing trades.
    """
    r_coverage_count = len(r_multiples)

    if r_coverage_count < _MIN_SAMPLE:
        return SortinoResult(
            sortino_ratio=None,
            mean_r=None,
            downside_dev=None,
            n_per_year=n_per_year,
            r_coverage_count=r_coverage_count,
            insufficient_sample=True,
            no_downside_trades=False,
        )

    mean_r = sum(r_multiples, _ZERO) / Decimal(r_coverage_count)

    downside_vals = [r for r in r_multiples if r < _ZERO]

    if not downside_vals:
        return SortinoResult(
            sortino_ratio=None,
            mean_r=mean_r,
            downside_dev=None,
            n_per_year=n_per_year,
            r_coverage_count=r_coverage_count,
            insufficient_sample=False,
            no_downside_trades=True,
        )

    n_down = Decimal(len(downside_vals))
    mean_down = sum(downside_vals, _ZERO) / n_down
    downside_variance = sum((r - mean_down) ** _TWO for r in downside_vals) / n_down
    downside_dev = downside_variance.sqrt()

    if downside_dev == _ZERO:
        return SortinoResult(
            sortino_ratio=None,
            mean_r=mean_r,
            downside_dev=_ZERO,
            n_per_year=n_per_year,
            r_coverage_count=r_coverage_count,
            insufficient_sample=False,
            no_downside_trades=False,
        )

    annualization = Decimal(n_per_year).sqrt()
    sortino_ratio = mean_r / downside_dev * annualization

    return SortinoResult(
        sortino_ratio=sortino_ratio,
        mean_r=mean_r,
        downside_dev=downside_dev,
        n_per_year=n_per_year,
        r_coverage_count=r_coverage_count,
        insufficient_sample=False,
        no_downside_trades=False,
    )


# ---------------------------------------------------------------------------
# N-3: Monte Carlo
# ---------------------------------------------------------------------------


def compute_monte_carlo(
    r_multiples: Sequence[Decimal],
    *,
    n_simulations: int = 1000,
    ruin_threshold_r: Decimal = Decimal("-50"),
) -> MonteCarloResult:
    """Run Monte Carlo simulation on r_multiple series.

    Uses random resampling with replacement (bootstrap). Runs synchronously — at
    ≤5,000 r_multiple values and 1,000 simulations this completes in ~30–150ms.

    Args:
        r_multiples:       historical r_multiple values (net_pnl > 0 or < 0 trades only)
        n_simulations:     number of bootstrap simulations (default 1000)
        ruin_threshold_r:  cumulative R below which a simulation is considered ruined
    """
    n_trades = len(r_multiples)
    if n_trades == 0:
        return MonteCarloResult(
            n_simulations=0,
            n_trades=0,
            median_final_r=_ZERO,
            p5_final_r=_ZERO,
            p95_final_r=_ZERO,
            p5_max_drawdown_pct=_ZERO,
            p1_max_drawdown_pct=_ZERO,
            worst_max_drawdown_pct=_ZERO,
            risk_of_ruin_pct=_ZERO,
            p95_max_consecutive_losses=0,
        )

    r_pool = list(r_multiples)

    final_rs: list[Decimal] = []
    max_drawdown_pcts: list[Decimal] = []
    max_consecutive_losses: list[int] = []
    ruin_count = 0

    for _ in range(n_simulations):
        sim = random.choices(r_pool, k=n_trades)  # noqa: S311 — non-crypto RNG intentional

        cum_r = _ZERO
        peak_r = _ZERO
        max_dd = _ZERO
        consec_losses = 0
        max_consec = 0
        ruined = False

        for r in sim:
            cum_r += r
            if cum_r > peak_r:
                peak_r = cum_r
            if peak_r > _ZERO:
                dd = (peak_r - cum_r) / peak_r * _HUNDRED
                if dd > max_dd:
                    max_dd = dd

            if r < _ZERO:
                consec_losses += 1
                if consec_losses > max_consec:
                    max_consec = consec_losses
            else:
                consec_losses = 0

            if cum_r <= ruin_threshold_r:
                ruined = True
                break

        if ruined:
            ruin_count += 1

        final_rs.append(cum_r)
        max_drawdown_pcts.append(max_dd)
        max_consecutive_losses.append(max_consec)

    final_rs.sort()
    max_drawdown_pcts.sort()
    max_consecutive_losses.sort()

    def _percentile(sorted_vals: list[_T], pct: float) -> _T:
        idx = int(len(sorted_vals) * pct / 100)
        idx = max(0, min(idx, len(sorted_vals) - 1))
        return sorted_vals[idx]

    return MonteCarloResult(
        n_simulations=n_simulations,
        n_trades=n_trades,
        median_final_r=_percentile(final_rs, 50),
        p5_final_r=_percentile(final_rs, 5),
        p95_final_r=_percentile(final_rs, 95),
        p5_max_drawdown_pct=_percentile(max_drawdown_pcts, 95),  # 5th worst = 95th percentile
        p1_max_drawdown_pct=_percentile(max_drawdown_pcts, 99),  # 1st worst = 99th percentile
        worst_max_drawdown_pct=max_drawdown_pcts[-1] if max_drawdown_pcts else _ZERO,
        risk_of_ruin_pct=Decimal(ruin_count) / Decimal(n_simulations) * _HUNDRED,
        p95_max_consecutive_losses=_percentile(max_consecutive_losses, 95),
    )
