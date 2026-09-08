"""Dashboard REST API — v1 routes (Step 18).

Routes:
  GET /v1/dashboard/summary   — aggregated P&L summary for the authenticated user

Security: all routes require an authenticated session (get_current_user_id).
          user_id is sourced from the session — never from request body or URL params.
          account_id is accepted as a required query param and validated against the
          authenticated user's owned accounts before any data is returned.

NOTE: this file intentionally omits `from __future__ import annotations`.
      FastAPI's dependency inspection calls inspect.get_annotations(eval_str=True)
      at route registration time; deferred annotations break subscripted types that
      are not subscriptable at runtime (see Bhima skill: FastAPI future-annotations).
"""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.api.v1.deps import get_current_user_id
from tradeforge.infrastructure.db import get_db
from tradeforge.infrastructure.models.trade_domain import Trade
from tradeforge.infrastructure.models.trade_pnl import TradePnl
from tradeforge.infrastructure.models.trading_account import TradingAccount

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_IST = ZoneInfo("Asia/Kolkata")


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class DashboardSummaryResponse(BaseModel):
    account_id: str
    as_of_date: date
    all_time_net_pnl: Decimal
    mtd_net_pnl: Decimal
    wtd_net_pnl: Decimal
    starting_capital: Decimal | None
    realized_equity: Decimal | None
    total_closed_trades: int
    open_trade_count: int


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=DashboardSummaryResponse)
async def dashboard_summary(
    account_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummaryResponse:
    today_ist = datetime.now(_IST).date()
    mtd_start = today_ist.replace(day=1)
    wtd_start = today_ist - timedelta(days=today_ist.weekday())

    # Scalar subquery: starting_capital from the account (null if account not found
    # or capital not configured).  The WHERE on user_id prevents cross-user access.
    capital_sq = (
        select(TradingAccount.starting_capital)
        .where(
            TradingAccount.id == account_id,
            TradingAccount.user_id == user_id,
        )
        .scalar_subquery()
    )

    stmt = (
        select(
            func.coalesce(func.sum(TradePnl.net_pnl), 0).label("all_time_net_pnl"),
            func.coalesce(
                func.sum(
                    case(
                        (Trade.trade_date >= mtd_start, TradePnl.net_pnl),
                        else_=0,
                    )
                ),
                0,
            ).label("mtd_net_pnl"),
            func.coalesce(
                func.sum(
                    case(
                        (Trade.trade_date >= wtd_start, TradePnl.net_pnl),
                        else_=0,
                    )
                ),
                0,
            ).label("wtd_net_pnl"),
            func.count(case((Trade.status == "CLOSED", 1))).label("total_closed_trades"),
            func.count(
                case((Trade.status.in_(["OPEN", "PARTIAL"]), 1))
            ).label("open_trade_count"),
            capital_sq.label("starting_capital"),
        )
        .select_from(Trade)
        .outerjoin(TradePnl, TradePnl.trade_id == Trade.id)
        .where(
            Trade.user_id == user_id,
            Trade.account_id == account_id,
            Trade.is_deleted.is_(False),
        )
    )

    result = await db.execute(stmt)
    row = result.one()

    all_time_net_pnl = Decimal(str(row.all_time_net_pnl))
    starting_capital = (
        Decimal(str(row.starting_capital)) if row.starting_capital is not None else None
    )
    realized_equity = (
        starting_capital + all_time_net_pnl if starting_capital is not None else None
    )

    return DashboardSummaryResponse(
        account_id=str(account_id),
        as_of_date=today_ist,
        all_time_net_pnl=all_time_net_pnl,
        mtd_net_pnl=Decimal(str(row.mtd_net_pnl)),
        wtd_net_pnl=Decimal(str(row.wtd_net_pnl)),
        starting_capital=starting_capital,
        realized_equity=realized_equity,
        total_closed_trades=int(row.total_closed_trades),
        open_trade_count=int(row.open_trade_count),
    )
