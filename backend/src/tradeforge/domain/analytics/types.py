"""Domain types for the Step 12 analytics layer.

No imports outside stdlib. Zero framework dependencies (ADR-001).
AnalyticsFilter is frozen + uses tuples → hashable for future cache keying.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class AnalyticsFilter:
    """9-dimension filter applied to every analytics query.

    user_id is always required. All other dimensions default to no-filter (empty tuple / None).
    """

    user_id: UUID
    date_from: date | None = None
    date_to: date | None = None
    account_ids: tuple[UUID, ...] = field(default_factory=tuple)
    instrument_types: tuple[str, ...] = field(default_factory=tuple)  # EQ | FUT | CE | PE
    exchange_segments: tuple[str, ...] = field(default_factory=tuple)  # NSE_EQ | NSE_FO | BSE_EQ
    trade_types: tuple[str, ...] = field(default_factory=tuple)  # MIS | CNC | NRML_FUT …
    directions: tuple[str, ...] = field(default_factory=tuple)  # LONG | SHORT
    setup_names: tuple[str, ...] = field(default_factory=tuple)
    brokers: tuple[str, ...] = field(default_factory=tuple)  # ZERODHA | UPSTOX …


# ---------------------------------------------------------------------------
# Per-metric result dataclasses (returned by AnalyticsService)
# ---------------------------------------------------------------------------


@dataclass
class PnlSummary:
    """M-1: Total P&L."""

    total_trades: int
    gross_pnl: Decimal
    net_pnl: Decimal
    total_charges: Decimal


@dataclass
class OutcomeDistribution:
    """M-2: Win/loss/breakeven counts and rates.

    G-CORR-01: strict classification — win = net_pnl > 0, loss = net_pnl < 0, breakeven neutral.
    """

    win_count: int
    loss_count: int
    breakeven_count: int
    total_n: int
    win_rate: Decimal
    loss_rate: Decimal
    breakeven_rate: Decimal


@dataclass
class ExpectancyResult:
    """M-3: Expectancy in R-multiples.

    G-CORR-01: win/loss rates from strict classification.
    G-ADV-01: insufficient_sample flag uses r_coverage_count < 30 (not total_n).
    """

    expectancy_r: Decimal | None
    avg_r_win: Decimal | None
    avg_r_loss: Decimal | None  # absolute value (positive)
    r_coverage_count: int
    total_count: int
    r_coverage_pct: Decimal
    insufficient_sample: bool


@dataclass
class ProfitFactorResult:
    """M-4: Gross profit / gross loss. None when no losing trades."""

    profit_factor: Decimal | None
    gross_profit: Decimal
    gross_loss: Decimal


@dataclass
class PlannedRRResult:
    """M-5: Average planned risk/reward ratio."""

    avg_planned_rr: Decimal | None
    trade_count_with_rr: int
    total_count: int
    coverage_pct: Decimal


@dataclass
class RBucket:
    label: str
    lower: Decimal | None
    upper: Decimal | None
    count: int


@dataclass
class RMultipleDistribution:
    """M-6: R-multiple distribution."""

    mean_r: Decimal | None
    median_r: Decimal | None
    stddev_r: Decimal | None
    p25_r: Decimal | None
    p75_r: Decimal | None
    coverage_count: int
    total_count: int
    coverage_pct: Decimal
    insufficient_sample: bool
    buckets: list[RBucket]


@dataclass
class EquityCurvePoint:
    """M-7: One row per closed trade, ordered by trade_date, last_fill_at, id."""

    trade_date: date
    trade_id: UUID
    net_pnl: Decimal
    cumulative_net_pnl: Decimal


@dataclass
class DrawdownStats:
    """M-8: Drawdown statistics derived from the equity curve."""

    max_drawdown_pct: Decimal | None
    max_drawdown_inr: Decimal | None
    avg_drawdown_pct: Decimal | None
    current_drawdown_pct: Decimal | None


@dataclass
class ChargesBreakdown:
    """M-11: Charges breakdown.

    G-CORR-03: charge_drag_pct is None when gross_pnl <= 0. In that case
    charges_added_to_loss carries the absolute charge total for UI display.
    """

    total_brokerage: Decimal
    total_stt: Decimal
    total_exchange_charges: Decimal
    total_sebi_charges: Decimal
    total_stamp_duty: Decimal
    total_gst: Decimal
    total_ipft: Decimal
    total_charges: Decimal
    total_gross_pnl: Decimal
    charge_drag_pct: Decimal | None
    charges_added_to_loss: Decimal | None


@dataclass
class SetupPerformanceRow:
    """M-9: Performance aggregated by setup_name."""

    setup_name: str | None
    trade_count: int
    win_count: int
    loss_count: int
    breakeven_count: int
    win_rate: Decimal
    avg_net_pnl: Decimal
    total_net_pnl: Decimal
    avg_r_multiple: Decimal | None
    expectancy_r: Decimal | None
    profit_factor: Decimal | None


@dataclass
class DirectionPerformanceRow:
    """M-10: Performance aggregated by direction."""

    direction: str
    trade_count: int
    win_count: int
    loss_count: int
    breakeven_count: int
    win_rate: Decimal
    avg_net_pnl: Decimal
    total_net_pnl: Decimal
    avg_r_multiple: Decimal | None


@dataclass
class StreakStats:
    """M-12: Win/loss streak statistics."""

    current_win_streak: int
    current_loss_streak: int
    max_win_streak: int
    max_loss_streak: int
    avg_win_streak: Decimal
    avg_loss_streak: Decimal


@dataclass
class HoldDurationBucket:
    bucket: str
    bucket_order: int
    count: int
    avg_net_pnl: Decimal
    win_rate: Decimal


@dataclass
class HoldDurationDistribution:
    """M-13: Hold duration distribution across buckets."""

    buckets: list[HoldDurationBucket]
    avg_duration_minutes: Decimal | None
    median_duration_minutes: Decimal | None


@dataclass
class ExitTypeRow:
    """M-14: Performance aggregated by exit type.

    G-CORR-02: exit_type is the type of the last EXIT fill by timestamp.
    A NULL exit_type means the adapter did not populate it — 'untagged' exits.
    """

    exit_type: str | None
    trade_count: int
    win_rate: Decimal
    avg_net_pnl: Decimal
    avg_r_multiple: Decimal | None


@dataclass
class MonteCarloResult:
    """N-3: Monte Carlo simulation results."""

    n_simulations: int
    n_trades: int
    median_final_r: Decimal
    p5_final_r: Decimal
    p95_final_r: Decimal
    p5_max_drawdown_pct: Decimal
    p1_max_drawdown_pct: Decimal
    worst_max_drawdown_pct: Decimal
    risk_of_ruin_pct: Decimal
    p95_max_consecutive_losses: int


@dataclass(frozen=True)
class SharpeResult:
    """M-8K: Trade-based Sharpe Ratio.

    G-CONF-12.1-A: n_per_year = 252 (NSE-aligned fixed convention).
    sharpe_ratio is None when insufficient_sample or std_r == 0 (undefined, not zero).
    """

    sharpe_ratio: Decimal | None
    mean_r: Decimal | None
    std_r: Decimal | None
    n_per_year: int
    r_coverage_count: int
    insufficient_sample: bool


@dataclass(frozen=True)
class SortinoResult:
    """M-9K: Trade-based Sortino Ratio.

    G-CONF-12.1-A: n_per_year = 252.
    G-CONF-12.1-B: downside = trades where r_multiple < 0; MAR = 0; breakeven excluded.
    sortino_ratio is None when insufficient_sample or no_downside_trades.
    no_downside_trades is a distinct flag — the frontend should display a specific message.
    """

    sortino_ratio: Decimal | None
    mean_r: Decimal | None
    downside_dev: Decimal | None
    n_per_year: int
    r_coverage_count: int
    insufficient_sample: bool
    no_downside_trades: bool


@dataclass(frozen=True)
class RiskAdjustedResult:
    """Container for Sharpe and Sortino. Embedded in AnalyticsSummary."""

    sharpe: SharpeResult
    sortino: SortinoResult


@dataclass
class AccountDimension:
    """One entry in the /filters/accounts dimension list."""

    id: UUID
    label: str


@dataclass
class AnalyticsSummary:
    """Composite response for GET /v1/analytics/summary.

    Bundles scalar metrics to minimise round-trips for the dashboard.
    """

    pnl: PnlSummary
    outcome: OutcomeDistribution
    expectancy: ExpectancyResult
    profit_factor: ProfitFactorResult
    planned_rr: PlannedRRResult
    drawdown: DrawdownStats
    direction: list[DirectionPerformanceRow]
    charges: ChargesBreakdown
    risk_adjusted: RiskAdjustedResult
