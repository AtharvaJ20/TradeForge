"""Analytics API router — GET /v1/analytics/*

ADR-007: all 8 analytics endpoints plus the monte-carlo endpoint.
Bhima lesson: NO `from __future__ import annotations` in this file —
it breaks FastAPI dependency injection via inspect.get_annotations(eval_str=True).
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.api.v1.deps import get_current_user_id
from tradeforge.application.analytics_service import AnalyticsService
from tradeforge.domain.analytics.types import AnalyticsFilter
from tradeforge.infrastructure.db import get_db
from tradeforge.infrastructure.repositories.analytics_repo import AnalyticsRepository

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ---------------------------------------------------------------------------
# Dependency: build AnalyticsService from request context
# ---------------------------------------------------------------------------


def get_analytics_service(db: AsyncSession = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(AnalyticsRepository(db))


# ---------------------------------------------------------------------------
# Shared filter dependency
# ---------------------------------------------------------------------------


def get_analytics_filter(
    user_id: UUID = Depends(get_current_user_id),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    account_ids: list[UUID] = Query(default=[]),
    instrument_types: list[str] = Query(default=[]),
    exchange_segments: list[str] = Query(default=[]),
    trade_types: list[str] = Query(default=[]),
    directions: list[str] = Query(default=[]),
    setup_names: list[str] = Query(default=[]),
    brokers: list[str] = Query(default=[]),
) -> AnalyticsFilter:
    return AnalyticsFilter(
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        account_ids=tuple(account_ids),
        instrument_types=tuple(instrument_types),
        exchange_segments=tuple(exchange_segments),
        trade_types=tuple(trade_types),
        directions=tuple(directions),
        setup_names=tuple(setup_names),
        brokers=tuple(brokers),
    )


# ---------------------------------------------------------------------------
# Pydantic response schemas
# ---------------------------------------------------------------------------


class PnlSummaryResponse(BaseModel):
    model_config = {"from_attributes": True}

    total_trades: int
    gross_pnl: Decimal
    net_pnl: Decimal
    total_charges: Decimal


class OutcomeDistributionResponse(BaseModel):
    model_config = {"from_attributes": True}

    win_count: int
    loss_count: int
    breakeven_count: int
    total_n: int
    win_rate: Decimal
    loss_rate: Decimal
    breakeven_rate: Decimal


class ExpectancyResultResponse(BaseModel):
    model_config = {"from_attributes": True}

    expectancy_r: Decimal | None
    avg_r_win: Decimal | None
    avg_r_loss: Decimal | None
    r_coverage_count: int
    total_count: int
    r_coverage_pct: Decimal
    insufficient_sample: bool


class ProfitFactorResponse(BaseModel):
    model_config = {"from_attributes": True}

    profit_factor: Decimal | None
    gross_profit: Decimal
    gross_loss: Decimal


class PlannedRRResponse(BaseModel):
    model_config = {"from_attributes": True}

    avg_planned_rr: Decimal | None
    trade_count_with_rr: int
    total_count: int
    coverage_pct: Decimal


class DrawdownStatsResponse(BaseModel):
    model_config = {"from_attributes": True}

    max_drawdown_pct: Decimal | None
    max_drawdown_inr: Decimal | None
    avg_drawdown_pct: Decimal | None
    current_drawdown_pct: Decimal | None


class DirectionPerformanceResponse(BaseModel):
    model_config = {"from_attributes": True}

    direction: str
    trade_count: int
    win_count: int
    loss_count: int
    breakeven_count: int
    win_rate: Decimal
    avg_net_pnl: Decimal
    total_net_pnl: Decimal
    avg_r_multiple: Decimal | None


class ChargesBreakdownResponse(BaseModel):
    model_config = {"from_attributes": True}

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


class SharpeResultResponse(BaseModel):
    model_config = {"from_attributes": True}

    sharpe_ratio: Decimal | None
    mean_r: Decimal | None
    std_r: Decimal | None
    n_per_year: int
    r_coverage_count: int
    insufficient_sample: bool


class SortinoResultResponse(BaseModel):
    model_config = {"from_attributes": True}

    sortino_ratio: Decimal | None
    mean_r: Decimal | None
    downside_dev: Decimal | None
    n_per_year: int
    r_coverage_count: int
    insufficient_sample: bool
    no_downside_trades: bool


class RiskAdjustedResultResponse(BaseModel):
    model_config = {"from_attributes": True}

    sharpe: SharpeResultResponse
    sortino: SortinoResultResponse


class AnalyticsSummaryResponse(BaseModel):
    pnl: PnlSummaryResponse
    outcome: OutcomeDistributionResponse
    expectancy: ExpectancyResultResponse
    profit_factor: ProfitFactorResponse
    planned_rr: PlannedRRResponse
    drawdown: DrawdownStatsResponse
    direction: list[DirectionPerformanceResponse]
    charges: ChargesBreakdownResponse
    risk_adjusted: RiskAdjustedResultResponse


class EquityCurvePointResponse(BaseModel):
    model_config = {"from_attributes": True}

    trade_date: date
    trade_id: UUID
    net_pnl: Decimal
    cumulative_net_pnl: Decimal


class RBucketResponse(BaseModel):
    model_config = {"from_attributes": True}

    label: str
    lower: Decimal | None
    upper: Decimal | None
    count: int


class RDistributionResponse(BaseModel):
    model_config = {"from_attributes": True}

    mean_r: Decimal | None
    median_r: Decimal | None
    stddev_r: Decimal | None
    p25_r: Decimal | None
    p75_r: Decimal | None
    coverage_count: int
    total_count: int
    coverage_pct: Decimal
    insufficient_sample: bool
    buckets: list[RBucketResponse]


class SetupPerformanceResponse(BaseModel):
    model_config = {"from_attributes": True}

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


class StreakStatsResponse(BaseModel):
    model_config = {"from_attributes": True}

    current_win_streak: int
    current_loss_streak: int
    max_win_streak: int
    max_loss_streak: int
    avg_win_streak: Decimal
    avg_loss_streak: Decimal


class HoldDurationBucketResponse(BaseModel):
    model_config = {"from_attributes": True}

    bucket: str
    bucket_order: int
    count: int
    avg_net_pnl: Decimal
    win_rate: Decimal


class HoldDurationResponse(BaseModel):
    model_config = {"from_attributes": True}

    buckets: list[HoldDurationBucketResponse]
    avg_duration_minutes: Decimal | None
    median_duration_minutes: Decimal | None


class ExitTypeRowResponse(BaseModel):
    model_config = {"from_attributes": True}

    exit_type: str | None
    trade_count: int
    win_rate: Decimal
    avg_net_pnl: Decimal
    avg_r_multiple: Decimal | None


class MonteCarloResponse(BaseModel):
    model_config = {"from_attributes": True}

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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def get_summary(
    f: AnalyticsFilter = Depends(get_analytics_filter),
    svc: AnalyticsService = Depends(get_analytics_service),
) -> AnalyticsSummaryResponse:
    result = await svc.get_summary(f)
    ra = result.risk_adjusted
    return AnalyticsSummaryResponse(
        pnl=PnlSummaryResponse.model_validate(result.pnl),
        outcome=OutcomeDistributionResponse.model_validate(result.outcome),
        expectancy=ExpectancyResultResponse.model_validate(result.expectancy),
        profit_factor=ProfitFactorResponse.model_validate(result.profit_factor),
        planned_rr=PlannedRRResponse.model_validate(result.planned_rr),
        drawdown=DrawdownStatsResponse.model_validate(result.drawdown),
        direction=[DirectionPerformanceResponse.model_validate(d) for d in result.direction],
        charges=ChargesBreakdownResponse.model_validate(result.charges),
        risk_adjusted=RiskAdjustedResultResponse(
            sharpe=SharpeResultResponse.model_validate(ra.sharpe),
            sortino=SortinoResultResponse.model_validate(ra.sortino),
        ),
    )


@router.get("/equity-curve", response_model=list[EquityCurvePointResponse])
async def get_equity_curve(
    f: AnalyticsFilter = Depends(get_analytics_filter),
    svc: AnalyticsService = Depends(get_analytics_service),
) -> list[EquityCurvePointResponse]:
    points = await svc.get_equity_curve(f)
    return [EquityCurvePointResponse.model_validate(p) for p in points]


@router.get("/r-distribution", response_model=RDistributionResponse)
async def get_r_distribution(
    f: AnalyticsFilter = Depends(get_analytics_filter),
    svc: AnalyticsService = Depends(get_analytics_service),
) -> RDistributionResponse:
    result = await svc.get_r_distribution(f)
    return RDistributionResponse(
        mean_r=result.mean_r,
        median_r=result.median_r,
        stddev_r=result.stddev_r,
        p25_r=result.p25_r,
        p75_r=result.p75_r,
        coverage_count=result.coverage_count,
        total_count=result.total_count,
        coverage_pct=result.coverage_pct,
        insufficient_sample=result.insufficient_sample,
        buckets=[RBucketResponse.model_validate(b) for b in result.buckets],
    )


@router.get("/by-setup", response_model=list[SetupPerformanceResponse])
async def get_by_setup(
    f: AnalyticsFilter = Depends(get_analytics_filter),
    svc: AnalyticsService = Depends(get_analytics_service),
) -> list[SetupPerformanceResponse]:
    rows = await svc.get_by_setup(f)
    return [SetupPerformanceResponse.model_validate(r) for r in rows]


@router.get("/streaks", response_model=StreakStatsResponse)
async def get_streaks(
    f: AnalyticsFilter = Depends(get_analytics_filter),
    svc: AnalyticsService = Depends(get_analytics_service),
) -> StreakStatsResponse:
    result = await svc.get_streaks(f)
    return StreakStatsResponse.model_validate(result)


@router.get("/hold-duration", response_model=HoldDurationResponse)
async def get_hold_duration(
    f: AnalyticsFilter = Depends(get_analytics_filter),
    svc: AnalyticsService = Depends(get_analytics_service),
) -> HoldDurationResponse:
    result = await svc.get_hold_duration(f)
    return HoldDurationResponse(
        buckets=[HoldDurationBucketResponse.model_validate(b) for b in result.buckets],
        avg_duration_minutes=result.avg_duration_minutes,
        median_duration_minutes=result.median_duration_minutes,
    )


@router.get("/by-exit-type", response_model=list[ExitTypeRowResponse])
async def get_by_exit_type(
    f: AnalyticsFilter = Depends(get_analytics_filter),
    svc: AnalyticsService = Depends(get_analytics_service),
) -> list[ExitTypeRowResponse]:
    rows = await svc.get_by_exit_type(f)
    return [ExitTypeRowResponse.model_validate(r) for r in rows]


@router.get("/monte-carlo", response_model=MonteCarloResponse)
async def get_monte_carlo(
    f: AnalyticsFilter = Depends(get_analytics_filter),
    svc: AnalyticsService = Depends(get_analytics_service),
    n_simulations: int = Query(default=1000, ge=100, le=10000),
) -> MonteCarloResponse:
    result = await svc.get_monte_carlo(f, n_simulations=n_simulations)
    return MonteCarloResponse.model_validate(result)
