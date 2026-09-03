"""Unit tests for AnalyticsService filter-dimension pass-throughs (Step 12.4, B-5).

Verifies that each service method delegates to the correct repo method and returns
the value unchanged. No DB or framework dependencies.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from tradeforge.application.analytics_service import AnalyticsService
from tradeforge.domain.analytics.types import AccountDimension


@pytest.fixture()
def repo() -> MagicMock:
    r = MagicMock()
    r.get_distinct_accounts = AsyncMock()
    r.get_distinct_setups = AsyncMock()
    r.get_distinct_brokers = AsyncMock()
    return r


@pytest.fixture()
def svc(repo: MagicMock) -> AnalyticsService:
    return AnalyticsService(repo)


@pytest.mark.asyncio
async def test_get_filter_accounts_delegates_to_repo(
    svc: AnalyticsService, repo: MagicMock
) -> None:
    uid = uuid.uuid4()
    expected = [
        AccountDimension(id=uuid.uuid4(), label="Zerodha Primary"),
        AccountDimension(id=uuid.uuid4(), label="Upstox Secondary"),
    ]
    repo.get_distinct_accounts.return_value = expected

    result = await svc.get_filter_accounts(uid)

    repo.get_distinct_accounts.assert_awaited_once_with(uid)
    assert result == expected


@pytest.mark.asyncio
async def test_get_filter_accounts_returns_empty_list(
    svc: AnalyticsService, repo: MagicMock
) -> None:
    repo.get_distinct_accounts.return_value = []
    result = await svc.get_filter_accounts(uuid.uuid4())
    assert result == []


@pytest.mark.asyncio
async def test_get_filter_setups_delegates_to_repo(svc: AnalyticsService, repo: MagicMock) -> None:
    uid = uuid.uuid4()
    expected = ["Breakout", "VWAP Reversion", "(no setup)"]
    repo.get_distinct_setups.return_value = expected

    result = await svc.get_filter_setups(uid)

    repo.get_distinct_setups.assert_awaited_once_with(uid)
    assert result == expected


@pytest.mark.asyncio
async def test_get_filter_setups_returns_empty_list(svc: AnalyticsService, repo: MagicMock) -> None:
    repo.get_distinct_setups.return_value = []
    result = await svc.get_filter_setups(uuid.uuid4())
    assert result == []


@pytest.mark.asyncio
async def test_get_filter_brokers_delegates_to_repo(svc: AnalyticsService, repo: MagicMock) -> None:
    uid = uuid.uuid4()
    expected = ["ANGEL_ONE", "UPSTOX", "ZERODHA"]
    repo.get_distinct_brokers.return_value = expected

    result = await svc.get_filter_brokers(uid)

    repo.get_distinct_brokers.assert_awaited_once_with(uid)
    assert result == expected


@pytest.mark.asyncio
async def test_get_filter_brokers_returns_empty_list(
    svc: AnalyticsService, repo: MagicMock
) -> None:
    repo.get_distinct_brokers.return_value = []
    result = await svc.get_filter_brokers(uuid.uuid4())
    assert result == []
