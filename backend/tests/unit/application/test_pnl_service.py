"""Unit tests for PnlService application logic.

Tests use async mocks so no database is required (ADR-001: domain layer has
zero framework imports; application layer is tested with lightweight mocks).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from tradeforge.application.pnl_service import PnlService


@pytest.mark.asyncio
async def test_recalculate_r_multiple_noop_when_no_pnl_row() -> None:
    """recalculate_r_multiple must return silently when no trade_pnl row exists."""
    pnl_repo = MagicMock()
    pnl_repo.get_for_trade = AsyncMock(return_value=None)
    pnl_repo.get_planned_risk = AsyncMock()
    pnl_repo.update_r_multiple = AsyncMock()

    cs_repo = MagicMock()
    svc = PnlService(pnl_repo=pnl_repo, charge_schedule_repo=cs_repo)

    trade_id = uuid.uuid4()
    user_id = uuid.uuid4()

    await svc.recalculate_r_multiple(trade_id, user_id)

    pnl_repo.get_for_trade.assert_awaited_once_with(trade_id)
    pnl_repo.get_planned_risk.assert_not_awaited()
    pnl_repo.update_r_multiple.assert_not_awaited()
