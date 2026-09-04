"""Unit tests for RiskService — Step 13 Basic Risk Metrics.

Tests U-13-01 through U-13-06 as specified in STEP-13-EXECUTION-PLAN.md.
No DB or framework dependencies — AnalyticsService and AsyncSession are mocked.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from tradeforge.application.analytics_service import AnalyticsService
from tradeforge.application.risk_service import RiskService
from tradeforge.domain.analytics.types import AnalyticsFilter, DrawdownStats, StreakStats

_ZERO = Decimal("0")
_ACCOUNT_ID = uuid.uuid4()
_USER_ID = uuid.uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(at_risk_row: MagicMock, daily_loss_row: MagicMock) -> AsyncMock:
    """Build an AsyncSession mock that returns preset rows for two execute calls."""
    db = AsyncMock()

    result1 = MagicMock()
    result1.one.return_value = at_risk_row

    result2 = MagicMock()
    result2.one.return_value = daily_loss_row

    db.execute.side_effect = [result1, result2]
    return db


def _make_analytics_svc(
    drawdown: DrawdownStats | None = None,
    streaks: StreakStats | None = None,
) -> AsyncMock:
    svc = AsyncMock(spec=AnalyticsService)
    summary = MagicMock()
    summary.drawdown = drawdown or DrawdownStats(
        max_drawdown_pct=None,
        max_drawdown_inr=None,
        avg_drawdown_pct=None,
        current_drawdown_pct=None,
        current_drawdown_inr=None,
    )
    svc.get_summary.return_value = summary
    svc.get_streaks.return_value = streaks or StreakStats(
        current_win_streak=0,
        current_loss_streak=0,
        max_win_streak=0,
        max_loss_streak=0,
        avg_win_streak=_ZERO,
        avg_loss_streak=_ZERO,
    )
    return svc


def _at_risk_row(count: int = 0, total: Decimal | None = None) -> MagicMock:
    row = MagicMock()
    row.open_trade_count = count
    row.total_at_risk_inr = total
    return row


def _daily_loss_row(loss: Decimal = _ZERO, count: int = 0) -> MagicMock:
    row = MagicMock()
    row.daily_loss_inr = loss
    row.daily_loss_trade_count = count
    return row


# ---------------------------------------------------------------------------
# U-13-01: get_daily_risk — correct at-risk total for 2 open trades
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_daily_risk_sums_planned_risk_for_two_open_trades() -> None:
    """U-13-01: 2 open trades with planned_risk_amount → correct total_at_risk_inr."""
    ar = _at_risk_row(count=2, total=Decimal("7500"))
    dl = _daily_loss_row()
    db = _make_db(ar, dl)
    svc = RiskService(db, _make_analytics_svc())

    result = await svc.get_daily_risk(_ACCOUNT_ID)

    assert result.open_trade_count == 2
    assert result.total_at_risk_inr == Decimal("7500")
    assert result.daily_loss_inr == _ZERO
    assert result.daily_loss_trade_count == 0


# ---------------------------------------------------------------------------
# U-13-02: get_daily_risk — total_at_risk_inr=None when no planned_risk_amount
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_daily_risk_returns_none_when_no_planned_risk() -> None:
    """U-13-02: SUM(planned_risk_amount) on trades with NULL → total_at_risk_inr=None."""
    ar = _at_risk_row(count=1, total=None)
    dl = _daily_loss_row()
    db = _make_db(ar, dl)
    svc = RiskService(db, _make_analytics_svc())

    result = await svc.get_daily_risk(_ACCOUNT_ID)

    assert result.total_at_risk_inr is None
    assert result.open_trade_count == 1


# ---------------------------------------------------------------------------
# U-13-03: get_daily_risk — daily_loss_inr=0.00 when no losing trades today
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_daily_risk_zero_loss_when_no_losing_trades_today() -> None:
    """U-13-03: No closed losing trades today → daily_loss_inr=0.00."""
    ar = _at_risk_row()
    dl = _daily_loss_row(loss=_ZERO, count=0)
    db = _make_db(ar, dl)
    svc = RiskService(db, _make_analytics_svc())

    result = await svc.get_daily_risk(_ACCOUNT_ID)

    assert result.daily_loss_inr == Decimal("0")
    assert result.daily_loss_trade_count == 0


# ---------------------------------------------------------------------------
# U-13-04: get_summary — aggregates drawdown and streak from analytics service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_summary_aggregates_drawdown_and_streaks() -> None:
    """U-13-04: get_summary pulls drawdown and streak fields from analytics service."""
    drawdown = DrawdownStats(
        max_drawdown_pct=Decimal("8.50"),
        max_drawdown_inr=Decimal("42500"),
        avg_drawdown_pct=Decimal("4.00"),
        current_drawdown_pct=Decimal("2.80"),
        current_drawdown_inr=Decimal("14000"),
    )
    streaks = StreakStats(
        current_win_streak=0,
        current_loss_streak=3,
        max_win_streak=5,
        max_loss_streak=4,
        avg_win_streak=Decimal("2.5"),
        avg_loss_streak=Decimal("1.8"),
    )
    analytics_svc = _make_analytics_svc(drawdown=drawdown, streaks=streaks)

    ar = _at_risk_row(count=1, total=Decimal("5000"))
    dl = _daily_loss_row(loss=Decimal("2500"), count=2)
    db = _make_db(ar, dl)
    db.execute.side_effect = [
        MagicMock(**{"one.return_value": ar}),
        MagicMock(**{"one.return_value": dl}),
    ]

    f = AnalyticsFilter(user_id=_USER_ID)
    svc = RiskService(db, analytics_svc)
    result = await svc.get_summary(f)

    assert result.max_drawdown_pct == Decimal("8.50")
    assert result.max_drawdown_inr == Decimal("42500")
    assert result.current_drawdown_pct == Decimal("2.80")
    assert result.current_drawdown_inr == Decimal("14000")
    assert result.max_loss_streak == 4
    assert result.current_loss_streak == 3
    assert result.daily_loss_inr == Decimal("2500")
    assert result.open_trade_count == 1
    assert result.total_at_risk_inr == Decimal("5000")


# ---------------------------------------------------------------------------
# U-13-05: get_summary — max_drawdown_inr=None when analytics returns no data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_summary_none_drawdown_when_analytics_returns_none() -> None:
    """U-13-05: Analytics returns None drawdown (< 2 closed trades) → all drawdown fields None."""
    drawdown = DrawdownStats(
        max_drawdown_pct=None,
        max_drawdown_inr=None,
        avg_drawdown_pct=None,
        current_drawdown_pct=None,
        current_drawdown_inr=None,
    )
    analytics_svc = _make_analytics_svc(drawdown=drawdown)

    ar = _at_risk_row()
    dl = _daily_loss_row()
    db = AsyncMock()
    db.execute.side_effect = [
        MagicMock(**{"one.return_value": ar}),
        MagicMock(**{"one.return_value": dl}),
    ]

    f = AnalyticsFilter(user_id=_USER_ID)
    svc = RiskService(db, analytics_svc)
    result = await svc.get_summary(f)

    assert result.max_drawdown_inr is None
    assert result.max_drawdown_pct is None
    assert result.current_drawdown_inr is None
    assert result.current_drawdown_pct is None


# ---------------------------------------------------------------------------
# U-13-06: get_daily_risk — PARTIAL trade included (G-RISK-01-A)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_daily_risk_includes_partial_trade_in_count_and_at_risk() -> None:
    """U-13-06: 1 OPEN + 1 PARTIAL trade → open_trade_count=2, at-risk = sum of both.

    G-RISK-01-A: PARTIAL trades (partially-exited open position) are still at risk
    and must be counted. The SQL uses status IN ('OPEN', 'PARTIAL').
    """
    # The DB returns both trades because the SQL includes PARTIAL status
    ar = _at_risk_row(count=2, total=Decimal("10000"))
    dl = _daily_loss_row()
    db = _make_db(ar, dl)
    svc = RiskService(db, _make_analytics_svc())

    result = await svc.get_daily_risk(_ACCOUNT_ID)

    assert result.open_trade_count == 2
    assert result.total_at_risk_inr == Decimal("10000")

    # Confirm the executed SQL contains the PARTIAL status guard
    call_args = db.execute.call_args_list[0]
    executed_sql = str(call_args[0][0])
    assert "PARTIAL" in executed_sql
