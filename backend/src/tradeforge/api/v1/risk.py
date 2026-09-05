"""Risk API router — GET /v1/risk/*

Step 13: Basic Risk Metrics.
NO `from __future__ import annotations` — breaks FastAPI dependency injection.
"""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.api.v1.analytics import get_analytics_filter, get_analytics_service
from tradeforge.api.v1.deps import get_current_user_id
from tradeforge.application.analytics_service import AnalyticsService
from tradeforge.application.risk_service import RiskService
from tradeforge.domain.analytics.types import AnalyticsFilter
from tradeforge.infrastructure.db import get_db

router = APIRouter(prefix="/risk", tags=["risk"])


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------


def get_risk_service(
    db: AsyncSession = Depends(get_db),
    analytics_svc: AnalyticsService = Depends(get_analytics_service),
) -> RiskService:
    return RiskService(db, analytics_svc)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class DailyRiskResponse(BaseModel):
    as_of_date: str
    open_trade_count: int
    total_at_risk_inr: Decimal | None
    daily_loss_inr: Decimal
    daily_loss_trade_count: int


class RiskSummaryResponse(BaseModel):
    max_drawdown_inr: Decimal | None
    max_drawdown_pct: Decimal | None
    current_drawdown_inr: Decimal | None
    current_drawdown_pct: Decimal | None
    max_loss_streak: int
    current_loss_streak: int
    daily_loss_inr: Decimal
    daily_loss_trade_count: int
    total_at_risk_inr: Decimal | None
    open_trade_count: int
    as_of_date: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/daily-summary", response_model=DailyRiskResponse)
async def get_daily_summary(
    account_id: UUID = Query(...),
    user_id: UUID = Depends(get_current_user_id),
    svc: RiskService = Depends(get_risk_service),
) -> DailyRiskResponse:
    """Today's open-trade risk for one account.

    account_id is required. The account must belong to the authenticated user;
    the service's SQL is scoped to account_id, and account ownership is enforced
    by the session-level user_id guard.
    """
    result = await svc.get_daily_risk(account_id)
    return DailyRiskResponse(
        as_of_date=result.as_of_date,
        open_trade_count=result.open_trade_count,
        total_at_risk_inr=result.total_at_risk_inr,
        daily_loss_inr=result.daily_loss_inr,
        daily_loss_trade_count=result.daily_loss_trade_count,
    )


@router.get("/summary", response_model=RiskSummaryResponse)
async def get_summary(
    f: AnalyticsFilter = Depends(get_analytics_filter),
    svc: RiskService = Depends(get_risk_service),
) -> RiskSummaryResponse:
    """Full risk picture: historical drawdown and streak + today's daily risk.

    Historical metrics respect the analytics filter (date range, account_ids, etc.).
    Daily metrics always use today's date in IST regardless of filter date range.
    """
    result = await svc.get_summary(f)
    return RiskSummaryResponse(
        max_drawdown_inr=result.max_drawdown_inr,
        max_drawdown_pct=result.max_drawdown_pct,
        current_drawdown_inr=result.current_drawdown_inr,
        current_drawdown_pct=result.current_drawdown_pct,
        max_loss_streak=result.max_loss_streak,
        current_loss_streak=result.current_loss_streak,
        daily_loss_inr=result.daily_loss_inr,
        daily_loss_trade_count=result.daily_loss_trade_count,
        total_at_risk_inr=result.total_at_risk_inr,
        open_trade_count=result.open_trade_count,
        as_of_date=result.as_of_date,
    )
