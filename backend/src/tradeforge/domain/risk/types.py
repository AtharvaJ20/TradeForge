"""Domain types for Step 13 — Basic Risk Metrics."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class DailyRiskResult:
    as_of_date: str  # ISO date in IST (response timestamp, not a filter)
    open_trade_count: int  # all open/partial trades regardless of trade_date
    total_at_risk_inr: Decimal | None  # None when no open trades have planned_risk_amount
    daily_loss_inr: Decimal  # 0.00 when no losing trades today
    daily_loss_trade_count: int


@dataclass
class RiskSummaryResult:
    # Historical metrics — sourced from analytics service (no new SQL)
    max_drawdown_inr: Decimal | None
    max_drawdown_pct: Decimal | None
    current_drawdown_inr: Decimal | None
    current_drawdown_pct: Decimal | None
    max_loss_streak: int
    current_loss_streak: int  # 0 when last closed trade was a win

    # Daily metrics — always today, scoped to the filter's user/accounts
    daily_loss_inr: Decimal
    daily_loss_trade_count: int
    total_at_risk_inr: Decimal | None
    open_trade_count: int  # all open/partial trades regardless of trade_date
    as_of_date: str
