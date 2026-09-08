"""Dashboard REST API — v1 routes (Step 18).

Routes:
  GET /v1/dashboard/summary   — aggregated P&L summary for the authenticated user

Security: all routes require an authenticated session (get_current_user_id).
          user_id is sourced from the session — never from request body or URL params.

NOTE: this file intentionally omits `from __future__ import annotations`.
      FastAPI's dependency inspection calls inspect.get_annotations(eval_str=True)
      at route registration time; deferred annotations break subscripted types that
      are not subscriptable at runtime (see Bhima skill: FastAPI future-annotations).
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.api.v1.deps import get_current_user_id
from tradeforge.infrastructure.db import get_db
from tradeforge.infrastructure.models.trade_domain import Trade
from tradeforge.infrastructure.models.trade_pnl import TradePnl

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_IST = ZoneInfo("Asia/Kolkata")


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class DashboardSummaryResponse(BaseModel):
    all_time_pnl: Decimal
    mtd_pnl: Decimal
    wtd_pnl: Decimal
    total_closed: int
    open_count: int


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=DashboardSummaryResponse)
async def dashboard_summary(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummaryResponse:
    today_ist = datetime.now(_IST).date()
    mtd_start = today_ist.replace(day=1)
    wtd_start = today_ist - timedelta(days=today_ist.weekday())

    stmt = (
        select(
            func.coalesce(func.sum(TradePnl.net_pnl), 0).label("all_time_pnl"),
            func.coalesce(
                func.sum(
                    case(
                        (Trade.trade_date >= mtd_start, TradePnl.net_pnl),
                        else_=0,
                    )
                ),
                0,
            ).label("mtd_pnl"),
            func.coalesce(
                func.sum(
                    case(
                        (Trade.trade_date >= wtd_start, TradePnl.net_pnl),
                        else_=0,
                    )
                ),
                0,
            ).label("wtd_pnl"),
            func.count(case((Trade.status == "CLOSED", 1))).label("total_closed"),
            func.count(
                case((Trade.status.in_(["OPEN", "PARTIAL"]), 1))
            ).label("open_count"),
        )
        .select_from(Trade)
        .outerjoin(TradePnl, TradePnl.trade_id == Trade.id)
        .where(Trade.user_id == user_id, Trade.is_deleted.is_(False))
    )

    result = await db.execute(stmt)
    row = result.one()

    return DashboardSummaryResponse(
        all_time_pnl=Decimal(str(row.all_time_pnl)),
        mtd_pnl=Decimal(str(row.mtd_pnl)),
        wtd_pnl=Decimal(str(row.wtd_pnl)),
        total_closed=int(row.total_closed),
        open_count=int(row.open_count),
    )
