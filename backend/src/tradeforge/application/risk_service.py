"""RiskService — Step 13 Basic Risk Metrics.

Phase 1 coupling note: RiskService calls AnalyticsService for historical
drawdown and streak metrics to avoid re-implementing existing SQL. Refactor
to shared query utilities in Phase 2 when the analytics layer is decoupled.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.application.analytics_service import AnalyticsService
from tradeforge.domain.analytics.types import AnalyticsFilter
from tradeforge.domain.risk.types import DailyRiskResult, RiskSummaryResult

_ZERO = Decimal("0")
_IST = timezone(timedelta(hours=5, minutes=30))

# ---------------------------------------------------------------------------
# SQL templates — single-account scope (GET /v1/risk/daily-summary)
# account_id scoping; no JOIN ambiguity issues.
# ---------------------------------------------------------------------------

# G-RISK-01-A: include PARTIAL — partially-exited position is still open and at risk.
# Dhanvantari: no trade_date filter on open trades — trades from prior days are at risk.
_AT_RISK_BY_ACCOUNT = """
SELECT
    COUNT(*)                 AS open_trade_count,
    SUM(planned_risk_amount) AS total_at_risk_inr
FROM trades
WHERE account_id = :account_id
  AND status IN ('OPEN', 'PARTIAL')
"""

# Dhanvantari Phase 1: trade_date = today in IST. MIS traders open/close same day.
# Swing/CNC positions closed on a different date than opened may be excluded.
# t. prefix on all trades columns avoids ambiguity in the trade_pnl JOIN.
_DAILY_LOSS_BY_ACCOUNT = """
SELECT
    COALESCE(SUM(tp.net_pnl), 0) AS daily_loss_inr,
    COUNT(*)                      AS daily_loss_trade_count
FROM trades t
JOIN trade_pnl tp ON tp.trade_id = t.id
WHERE t.account_id = :account_id
  AND t.trade_date = (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date
  AND tp.net_pnl < 0
"""

# ---------------------------------------------------------------------------
# SQL templates — user/filter scope (GET /v1/risk/summary)
# Extra {account_clause} is injected when account_ids are specified.
# ---------------------------------------------------------------------------

_AT_RISK_BY_USER = """
SELECT
    COUNT(*)                 AS open_trade_count,
    SUM(planned_risk_amount) AS total_at_risk_inr
FROM trades
WHERE user_id = :user_id
  AND status IN ('OPEN', 'PARTIAL')
  {account_clause}
"""

_DAILY_LOSS_BY_USER = """
SELECT
    COALESCE(SUM(tp.net_pnl), 0) AS daily_loss_inr,
    COUNT(*)                      AS daily_loss_trade_count
FROM trades t
JOIN trade_pnl tp ON tp.trade_id = t.id
WHERE t.user_id = :user_id
  AND t.trade_date = (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date
  AND tp.net_pnl < 0
  {account_clause}
"""


def _build_filter_params(f: AnalyticsFilter) -> tuple[str, dict]:
    """Build the optional account_id IN (...) clause + params for filter-based queries.

    Returns (account_clause, params). account_clause is "" when account_ids is empty.
    """
    params: dict = {"user_id": str(f.user_id)}
    if f.account_ids:
        placeholders = ", ".join(f":aid_{i}" for i in range(len(f.account_ids)))
        # Use t. prefix for the joined daily-loss query; the at-risk query (no JOIN)
        # will also match because account_id is unambiguous there.
        account_clause = f"AND t.account_id IN ({placeholders})"
        for i, aid in enumerate(f.account_ids):
            params[f"aid_{i}"] = str(aid)
    else:
        account_clause = ""
    return account_clause, params


class RiskService:
    def __init__(self, db: AsyncSession, analytics_svc: AnalyticsService) -> None:
        self._db = db
        self._analytics_svc = analytics_svc

    async def get_daily_risk(self, account_id: UUID) -> DailyRiskResult:
        """Compute today's open-trade exposure for a single account."""
        params = {"account_id": str(account_id)}

        at_risk_row = (await self._db.execute(text(_AT_RISK_BY_ACCOUNT), params)).one()

        daily_loss_row = (await self._db.execute(text(_DAILY_LOSS_BY_ACCOUNT), params)).one()

        return DailyRiskResult(
            as_of_date=datetime.now(_IST).date().isoformat(),
            open_trade_count=int(at_risk_row.open_trade_count or 0),
            total_at_risk_inr=at_risk_row.total_at_risk_inr,
            daily_loss_inr=Decimal(str(daily_loss_row.daily_loss_inr or "0")),
            daily_loss_trade_count=int(daily_loss_row.daily_loss_trade_count or 0),
        )

    async def get_summary(self, f: AnalyticsFilter) -> RiskSummaryResult:
        """Compute the full risk picture: historical analytics + today's daily risk."""
        analytics_summary = await self._analytics_svc.get_summary(f)
        drawdown = analytics_summary.drawdown
        streaks = await self._analytics_svc.get_streaks(f)

        account_clause, params = _build_filter_params(f)

        # The at-risk query (no JOIN) can use "account_id" without table alias;
        # replace t.account_id with account_id for the unaliased trades query.
        at_risk_clause = account_clause.replace("t.account_id", "account_id")

        at_risk_row = (
            await self._db.execute(
                text(_AT_RISK_BY_USER.format(account_clause=at_risk_clause)),
                params,
            )
        ).one()

        daily_loss_row = (
            await self._db.execute(
                text(_DAILY_LOSS_BY_USER.format(account_clause=account_clause)),
                params,
            )
        ).one()

        return RiskSummaryResult(
            max_drawdown_inr=drawdown.max_drawdown_inr,
            max_drawdown_pct=drawdown.max_drawdown_pct,
            current_drawdown_inr=drawdown.current_drawdown_inr,
            current_drawdown_pct=drawdown.current_drawdown_pct,
            max_loss_streak=streaks.max_loss_streak,
            current_loss_streak=streaks.current_loss_streak,
            daily_loss_inr=Decimal(str(daily_loss_row.daily_loss_inr or "0")),
            daily_loss_trade_count=int(daily_loss_row.daily_loss_trade_count or 0),
            total_at_risk_inr=at_risk_row.total_at_risk_inr,
            open_trade_count=int(at_risk_row.open_trade_count or 0),
            as_of_date=datetime.now(_IST).date().isoformat(),
        )
