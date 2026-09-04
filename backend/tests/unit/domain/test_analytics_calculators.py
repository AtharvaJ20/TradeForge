"""Unit tests for domain analytics calculators.

Per ADR-001: domain layer tests run with no database, no HTTP server, no network.

Test groups:
  TC-EXP   compute_expectancy (M-3)
  TC-DD    compute_drawdown_stats (M-7/M-8)
  TC-STR   compute_streak_stats (M-12)
  TC-MC    compute_monte_carlo (N-3)
  TC-RR    Planned R:R formula correctness (G-CONF-01)
"""

import uuid
from datetime import date
from decimal import Decimal

from tradeforge.domain.analytics.calculators import (
    compute_drawdown_stats,
    compute_expectancy,
    compute_monte_carlo,
    compute_sharpe_ratio,
    compute_sortino_ratio,
    compute_streak_stats,
)
from tradeforge.domain.analytics.types import EquityCurvePoint

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_D = Decimal


def _point(net_pnl: str, cum: str) -> EquityCurvePoint:
    return EquityCurvePoint(
        trade_date=date(2024, 1, 1),
        trade_id=uuid.uuid4(),
        net_pnl=_D(net_pnl),
        cumulative_net_pnl=_D(cum),
    )


# ---------------------------------------------------------------------------
# TC-EXP: compute_expectancy
# ---------------------------------------------------------------------------


class TestComputeExpectancy:
    def test_positive_expectancy(self) -> None:
        wins = [_D("2.0"), _D("1.5"), _D("3.0")]  # avg = 2.167
        losses = [_D("-1.0"), _D("-0.8")]  # avg_abs = 0.9
        # win_rate = 3/5=0.6, loss_rate=2/5=0.4
        # expectancy = 0.6*2.167 - 0.4*0.9 = 1.300 - 0.36 = 0.94
        result = compute_expectancy(
            win_r_multiples=wins,
            loss_r_multiples=losses,
            total_count=5,
        )
        assert result.expectancy_r is not None
        assert result.expectancy_r > _D("0")
        assert result.avg_r_loss is not None
        assert result.avg_r_loss > _D("0")  # must be positive (absolute value)
        assert result.r_coverage_count == 5
        assert result.insufficient_sample is True  # < 30

    def test_insufficient_sample_flag_uses_r_coverage(self) -> None:
        """G-ADV-01: insufficient_sample is based on r_coverage_count < 30, not total_count."""
        # 35 trades total, only 20 have r_multiple populated
        wins = [_D("1.5")] * 12
        losses = [_D("-1.0")] * 8
        result = compute_expectancy(
            win_r_multiples=wins,
            loss_r_multiples=losses,
            total_count=35,
        )
        assert result.r_coverage_count == 20
        assert result.total_count == 35
        assert result.insufficient_sample is True  # 20 < 30

    def test_sufficient_sample_flag(self) -> None:
        """insufficient_sample is False when r_coverage_count >= 30."""
        wins = [_D("2.0")] * 18
        losses = [_D("-1.0")] * 12
        result = compute_expectancy(
            win_r_multiples=wins,
            loss_r_multiples=losses,
            total_count=30,
        )
        assert result.r_coverage_count == 30
        assert result.insufficient_sample is False

    def test_no_r_multiples_returns_none(self) -> None:
        result = compute_expectancy(
            win_r_multiples=[],
            loss_r_multiples=[],
            total_count=10,
        )
        assert result.expectancy_r is None
        assert result.r_coverage_count == 0
        assert result.insufficient_sample is True

    def test_only_wins(self) -> None:
        wins = [_D("2.5"), _D("1.5")]
        result = compute_expectancy(
            win_r_multiples=wins,
            loss_r_multiples=[],
            total_count=2,
        )
        assert result.expectancy_r is not None
        assert result.expectancy_r > _D("0")
        assert result.avg_r_loss is None

    def test_avg_r_loss_is_absolute_value(self) -> None:
        """avg_r_loss must be a positive number (absolute value of losses)."""
        losses = [_D("-2.0"), _D("-1.0")]
        result = compute_expectancy(
            win_r_multiples=[],
            loss_r_multiples=losses,
            total_count=2,
        )
        assert result.avg_r_loss == _D("1.5")


# ---------------------------------------------------------------------------
# TC-RR: Planned R:R formula (G-CONF-01)
# ---------------------------------------------------------------------------


class TestPlannedRR:
    """G-CONF-01: verify the planned R:R formula for LONG and SHORT trades.

    For a LONG:
        planned_rr = (planned_target - average_entry) / (average_entry - planned_stop)

    For a SHORT:
        planned_rr = (average_entry - planned_target) / (planned_stop - average_entry)

    Both formulas yield a positive ratio; the sign cancels.
    """

    def test_long_trade_rr(self) -> None:
        entry = _D("100")
        stop = _D("98")  # risk = 2
        target = _D("106")  # reward = 6
        planned_rr = (target - entry) / (entry - stop)
        assert planned_rr == _D("3")

    def test_short_trade_rr(self) -> None:
        """G-CONF-01: short-trade planned R:R formula. Sign cancels — result is positive."""
        entry = _D("100")
        stop = _D("102")  # risk = 2 (stop is above entry for short)
        target = _D("94")  # reward = 6 (target is below entry for short)
        planned_rr = (entry - target) / (stop - entry)
        assert planned_rr == _D("3")
        assert planned_rr > _D("0"), "Short planned R:R must be positive"

    def test_short_trade_rr_equals_long_same_distance(self) -> None:
        """Both directions with same 1:3 risk/reward produce identical planned_rr."""
        entry = _D("100")

        long_rr = (_D("106") - entry) / (entry - _D("98"))
        short_rr = (entry - _D("94")) / (_D("102") - entry)

        assert long_rr == short_rr == _D("3")


# ---------------------------------------------------------------------------
# TC-DD: compute_drawdown_stats
# ---------------------------------------------------------------------------


class TestComputeDrawdownStats:
    def test_empty_curve(self) -> None:
        result = compute_drawdown_stats([])
        assert result.max_drawdown_pct is None
        assert result.max_drawdown_inr is None
        assert result.avg_drawdown_pct is None
        assert result.current_drawdown_pct is None

    def test_monotone_up_no_drawdown(self) -> None:
        points = [
            _point("100", "100"),
            _point("100", "200"),
            _point("100", "300"),
        ]
        result = compute_drawdown_stats(points)
        # No drawdown ever occurred — max_drawdown_pct is None (not zero)
        assert result.max_drawdown_pct is None
        assert result.current_drawdown_pct == _D("0")

    def test_single_drawdown(self) -> None:
        # Peak=200, trough=100 → MDD = 100/200 = 50%
        points = [
            _point("100", "100"),
            _point("100", "200"),
            _point("-100", "100"),
            _point("50", "150"),
        ]
        result = compute_drawdown_stats(points)
        assert result.max_drawdown_pct is not None
        assert result.max_drawdown_pct == _D("50.0000")
        assert result.max_drawdown_inr == _D("100")

    def test_current_drawdown_at_trough(self) -> None:
        points = [
            _point("200", "200"),
            _point("-50", "150"),
        ]
        result = compute_drawdown_stats(points)
        assert result.current_drawdown_pct is not None
        assert result.current_drawdown_pct == _D("25.0000")

    def test_recovered_to_new_high(self) -> None:
        points = [
            _point("100", "100"),
            _point("-50", "50"),
            _point("100", "150"),
            _point("100", "250"),
        ]
        result = compute_drawdown_stats(points)
        assert result.current_drawdown_pct == _D("0")


# ---------------------------------------------------------------------------
# TC-STR: compute_streak_stats
# ---------------------------------------------------------------------------


class TestComputeStreakStats:
    def test_empty(self) -> None:
        result = compute_streak_stats([])
        assert result.max_win_streak == 0
        assert result.max_loss_streak == 0

    def test_all_wins(self) -> None:
        pnls = [_D("100")] * 5
        result = compute_streak_stats(pnls)
        assert result.max_win_streak == 5
        assert result.max_loss_streak == 0
        assert result.current_win_streak == 5
        assert result.current_loss_streak == 0

    def test_alternating(self) -> None:
        pnls = [_D("100"), _D("-50"), _D("100"), _D("-50")]
        result = compute_streak_stats(pnls)
        assert result.max_win_streak == 1
        assert result.max_loss_streak == 1
        assert result.current_loss_streak == 1

    def test_streak_sequence(self) -> None:
        # W W W L L W
        pnls = [_D("1"), _D("1"), _D("1"), _D("-1"), _D("-1"), _D("1")]
        result = compute_streak_stats(pnls)
        assert result.max_win_streak == 3
        assert result.max_loss_streak == 2
        assert result.current_win_streak == 1
        assert result.current_loss_streak == 0

    def test_breakeven_resets_streak(self) -> None:
        """G-CORR-01: breakeven (net_pnl = 0) resets both streaks."""
        pnls = [_D("1"), _D("1"), _D("0"), _D("1")]
        result = compute_streak_stats(pnls)
        assert result.max_win_streak == 2
        assert result.current_win_streak == 1

    def test_avg_streak(self) -> None:
        # Streaks: W(3), L(2), W(1) → avg_win = (3+1)/2=2, avg_loss=2/1=2
        pnls = [_D("1"), _D("1"), _D("1"), _D("-1"), _D("-1"), _D("1")]
        result = compute_streak_stats(pnls)
        assert result.avg_win_streak == _D("2")
        assert result.avg_loss_streak == _D("2")

    def test_g_streak_01_wwbll(self) -> None:
        """G-STREAK-01 reference case: W W B L L.

        Breakeven resets the win streak; loss streak starts fresh after it.
        Expected: max_win=2, max_loss=2, current_win=0, current_loss=2.
        """
        pnls = [_D("1"), _D("1"), _D("0"), _D("-1"), _D("-1")]
        result = compute_streak_stats(pnls)
        assert result.max_win_streak == 2
        assert result.max_loss_streak == 2
        assert result.current_win_streak == 0
        assert result.current_loss_streak == 2

    def test_breakeven_starts_no_new_streak(self) -> None:
        """G-STREAK-01: a standalone breakeven starts neither a win nor a loss streak."""
        pnls = [_D("0")]
        result = compute_streak_stats(pnls)
        assert result.current_win_streak == 0
        assert result.current_loss_streak == 0
        assert result.max_win_streak == 0
        assert result.max_loss_streak == 0


# ---------------------------------------------------------------------------
# TC-MC: compute_monte_carlo
# ---------------------------------------------------------------------------


class TestComputeMonteCarlo:
    def test_empty_series(self) -> None:
        result = compute_monte_carlo([], n_simulations=10)
        assert result.n_simulations == 0
        assert result.n_trades == 0

    def test_positive_edge_median_positive(self) -> None:
        """A series of uniformly positive r_multiples should yield positive median final R."""
        r_series = [_D("1.5")] * 50
        result = compute_monte_carlo(r_series, n_simulations=200)
        assert result.median_final_r > _D("0")
        assert result.n_simulations == 200
        assert result.n_trades == 50

    def test_percentile_order(self) -> None:
        """p5_final_r <= median_final_r <= p95_final_r for any non-trivial series."""
        import random as rnd

        rnd.seed(42)
        r_series = [_D(str(round(rnd.uniform(-1, 3), 2))) for _ in range(80)]
        result = compute_monte_carlo(r_series, n_simulations=500)
        assert result.p5_final_r <= result.median_final_r <= result.p95_final_r

    def test_risk_of_ruin_zero_for_always_positive(self) -> None:
        """A series that never goes below ruin threshold has 0% risk of ruin."""
        r_series = [_D("0.5")] * 30
        result = compute_monte_carlo(
            r_series,
            n_simulations=200,
            ruin_threshold_r=_D("-50"),
        )
        assert result.risk_of_ruin_pct == _D("0")

    def test_risk_of_ruin_high_for_always_negative(self) -> None:
        """A series of pure losses always triggers ruin."""
        r_series = [_D("-1.0")] * 60
        result = compute_monte_carlo(
            r_series,
            n_simulations=100,
            ruin_threshold_r=_D("-50"),
        )
        assert result.risk_of_ruin_pct == _D("100")


# ---------------------------------------------------------------------------
# TC-SR: compute_sharpe_ratio
# ---------------------------------------------------------------------------


class TestComputeSharpeRatio:
    def test_insufficient_sample_below_30(self) -> None:
        """G-ADV-01 pattern: fewer than 30 r_multiples → insufficient_sample."""
        r = [_D("1.5")] * 29
        result = compute_sharpe_ratio(r)
        assert result.sharpe_ratio is None
        assert result.insufficient_sample is True
        assert result.r_coverage_count == 29

    def test_sufficient_sample_returns_ratio(self) -> None:
        """30+ trades with positive edge → positive Sharpe."""
        r = [_D("1.0")] * 20 + [_D("-0.5")] * 10  # mean=0.5, std > 0
        result = compute_sharpe_ratio(r)
        assert result.insufficient_sample is False
        assert result.sharpe_ratio is not None
        assert result.sharpe_ratio > _D("0")
        assert result.r_coverage_count == 30

    def test_zero_std_returns_none(self) -> None:
        """All identical R-multiples → std = 0 → Sharpe undefined (not zero)."""
        r = [_D("1.0")] * 30
        result = compute_sharpe_ratio(r)
        assert result.sharpe_ratio is None
        assert result.std_r == _D("0")
        assert result.insufficient_sample is False

    def test_empty_series_insufficient(self) -> None:
        result = compute_sharpe_ratio([])
        assert result.sharpe_ratio is None
        assert result.insufficient_sample is True
        assert result.r_coverage_count == 0

    def test_negative_edge_yields_negative_sharpe(self) -> None:
        """A losing system produces a negative Sharpe."""
        r = [_D("-1.0")] * 20 + [_D("0.3")] * 10
        result = compute_sharpe_ratio(r)
        assert result.sharpe_ratio is not None
        assert result.sharpe_ratio < _D("0")

    def test_formula_correctness(self) -> None:
        """Verify formula: (mean / std_pop) × √252 against hand-calculated value."""
        # 15 wins at +2.0, 15 losses at -1.0
        # mean = (15×2 + 15×(-1)) / 30 = 0.5
        # deviations² from mean=0.5: (2.0-0.5)²=2.25 ×15, (-1.0-0.5)²=2.25 ×15
        # variance = (15×2.25 + 15×2.25) / 30 = 2.25; std = 1.5
        # sharpe = (0.5 / 1.5) × √252 ≈ 0.3333 × 15.8745 ≈ 5.2915
        r = [_D("2.0")] * 15 + [_D("-1.0")] * 15
        result = compute_sharpe_ratio(r, n_per_year=252)
        assert result.mean_r == _D("0.5")
        assert result.std_r == _D("1.5")
        assert result.sharpe_ratio is not None
        expected = _D("0.5") / _D("1.5") * _D("252").sqrt()
        assert abs(result.sharpe_ratio - expected) < _D("0.000001")

    def test_n_per_year_passed_through(self) -> None:
        """n_per_year is stored on the result regardless of sample size."""
        r = [_D("1.0")] * 5  # insufficient but n_per_year still stored
        result = compute_sharpe_ratio(r, n_per_year=100)
        assert result.n_per_year == 100


# ---------------------------------------------------------------------------
# TC-SO: compute_sortino_ratio
# ---------------------------------------------------------------------------


class TestComputeSortinoRatio:
    def test_insufficient_sample_below_30(self) -> None:
        r = [_D("1.0")] * 15 + [_D("-0.5")] * 14  # 29 total
        result = compute_sortino_ratio(r)
        assert result.sortino_ratio is None
        assert result.insufficient_sample is True
        assert result.r_coverage_count == 29

    def test_no_downside_trades_flag(self) -> None:
        """G-CONF-12.1-B: all wins → no downside → no_downside_trades=True."""
        r = [_D("1.5")] * 30
        result = compute_sortino_ratio(r)
        assert result.sortino_ratio is None
        assert result.no_downside_trades is True
        assert result.insufficient_sample is False
        assert result.downside_dev is None
        assert result.mean_r == _D("1.5")

    def test_positive_edge_positive_sortino(self) -> None:
        """Mixed wins and non-uniform losses, positive mean → positive Sortino."""
        # Losses must be non-uniform so downside_dev > 0.
        r = [_D("2.0")] * 20 + [_D("-0.5")] * 5 + [_D("-1.5")] * 5
        result = compute_sortino_ratio(r)
        assert result.sortino_ratio is not None
        assert result.sortino_ratio > _D("0")
        assert result.insufficient_sample is False
        assert result.no_downside_trades is False

    def test_negative_edge_negative_sortino(self) -> None:
        """More and larger non-uniform losses → negative Sortino."""
        r = [_D("0.5")] * 10 + [_D("-1.5")] * 10 + [_D("-3.0")] * 10
        result = compute_sortino_ratio(r)
        assert result.sortino_ratio is not None
        assert result.sortino_ratio < _D("0")

    def test_empty_series_insufficient(self) -> None:
        result = compute_sortino_ratio([])
        assert result.sortino_ratio is None
        assert result.insufficient_sample is True
        assert result.r_coverage_count == 0

    def test_formula_correctness(self) -> None:
        """Verify formula: (mean_r / downside_dev) × √252.

        G-CONF-12.1-B: downside_dev is pop-std of losing trades only (r < 0).

        Series: 20 wins at +2.0, 10 losses at -1.0
          mean_r = (20×2.0 + 10×(-1.0)) / 30 = 30/30 = 1.0
          downside_vals = [-1.0] × 10; mean_down = -1.0
          downside_variance = Σ(-1.0 - (-1.0))² / 10 = 0.0; downside_dev = 0.0
        That's degenerate — use mixed losses instead.

        Series: 20 wins at +2.0, 5 losses at -1.0, 5 losses at -2.0
          mean_r = (20×2.0 + 5×(-1.0) + 5×(-2.0)) / 30 = (40 - 5 - 10) / 30 = 25/30
          downside_vals = [-1.0]×5 + [-2.0]×5; mean_down = -1.5
          deviations²: (-1.0 - (-1.5))² = 0.25 ×5; (-2.0 - (-1.5))² = 0.25 ×5
          downside_variance = (5×0.25 + 5×0.25) / 10 = 0.25; downside_dev = 0.5
          sortino = (25/30) / 0.5 × √252
        """
        wins = [_D("2.0")] * 20
        losses = [_D("-1.0")] * 5 + [_D("-2.0")] * 5
        r = wins + losses
        result = compute_sortino_ratio(r, n_per_year=252)

        expected_mean = _D("25") / _D("30")
        expected_downside_dev = _D("0.5")
        expected_sortino = expected_mean / expected_downside_dev * _D("252").sqrt()

        assert result.mean_r is not None
        assert abs(result.mean_r - expected_mean) < _D("0.000001")
        assert result.downside_dev is not None
        assert abs(result.downside_dev - expected_downside_dev) < _D("0.000001")
        assert result.sortino_ratio is not None
        assert abs(result.sortino_ratio - expected_sortino) < _D("0.000001")

    def test_breakeven_excluded_from_downside(self) -> None:
        """G-CONF-12.1-B / G-CORR-01: r = 0 trades are not downside.

        30 trades: 15 wins at +1.0, 10 losses at -1.0, 5 breakevens at 0.0
        breakeven trades (r=0) should NOT appear in downside_vals.
        In practice get_r_multiple_series() excludes breakevens, so all_r
        won't contain zeros — but this test verifies the calculator is
        also correct when zeros are present.
        """
        r = [_D("1.0")] * 15 + [_D("-1.0")] * 10 + [_D("0.0")] * 5
        result = compute_sortino_ratio(r)
        assert result.no_downside_trades is False
        # downside_dev should be computed only over the 10 losing trades
        # [-1.0] × 10 → mean_down = -1.0; variance = 0; downside_dev = 0
        # → sortino_ratio is None (downside_dev == 0), but no_downside_trades=False
        assert result.sortino_ratio is None
        assert result.no_downside_trades is False
        assert result.downside_dev == _D("0")

    def test_n_per_year_passed_through(self) -> None:
        r = [_D("1.0")] * 3  # insufficient
        result = compute_sortino_ratio(r, n_per_year=200)
        assert result.n_per_year == 200
