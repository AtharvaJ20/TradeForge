"""Unit tests for TradingAccountService."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from tradeforge.application.trading_account_service import TradingAccountService
from tradeforge.domain.import_domain.errors import AccountInactiveError, AccountNotFoundError
from tradeforge.domain.import_domain.types import TradingAccount


def _make_account(
    *,
    status: str = "ACTIVE",
    broker: str = "ZERODHA",
    account_type: str = "INDIVIDUAL",
) -> TradingAccount:
    now = datetime.now(UTC)
    return TradingAccount(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        broker=broker,
        display_name="Test Account",
        account_type=account_type,
        base_currency="INR",
        status=status,
        created_at=now,
        updated_at=now,
    )


def _make_service(account: TradingAccount | None = None) -> tuple[TradingAccountService, MagicMock]:
    repo = MagicMock()
    repo.create = AsyncMock(return_value=account or _make_account())
    repo.get_for_user = AsyncMock(return_value=account)
    repo.list_for_user = AsyncMock(return_value=[account] if account else [])
    svc = TradingAccountService(account_repo=repo)
    return svc, repo


class TestTradingAccountServiceCreate:
    @pytest.mark.asyncio
    async def test_create_valid(self):
        svc, repo = _make_service()
        session = AsyncMock()
        result = await svc.create(
            session,
            user_id=uuid.uuid4(),
            broker="ZERODHA",
            display_name="Zerodha Main",
            account_type="INDIVIDUAL",
        )
        repo.create.assert_awaited_once()
        assert isinstance(result, TradingAccount)

    @pytest.mark.asyncio
    async def test_create_invalid_broker(self):
        svc, _ = _make_service()
        with pytest.raises(ValueError, match="broker"):
            await svc.create(AsyncMock(), user_id=uuid.uuid4(), broker="UNKNOWN", display_name="X")

    @pytest.mark.asyncio
    async def test_create_invalid_account_type(self):
        svc, _ = _make_service()
        with pytest.raises(ValueError, match="account_type"):
            await svc.create(
                AsyncMock(),
                user_id=uuid.uuid4(),
                broker="ZERODHA",
                display_name="X",
                account_type="PROP",
            )

    @pytest.mark.asyncio
    async def test_create_blank_display_name(self):
        svc, _ = _make_service()
        with pytest.raises(ValueError, match="display_name"):
            await svc.create(
                AsyncMock(),
                user_id=uuid.uuid4(),
                broker="ZERODHA",
                display_name="   ",
            )

    @pytest.mark.asyncio
    async def test_display_name_stripped(self):
        account = _make_account()
        svc, repo = _make_service(account)
        await svc.create(
            AsyncMock(),
            user_id=uuid.uuid4(),
            broker="ZERODHA",
            display_name="  My Account  ",
        )
        call_kwargs = repo.create.call_args.kwargs
        assert call_kwargs["display_name"] == "My Account"


class TestTradingAccountServiceGet:
    @pytest.mark.asyncio
    async def test_get_existing(self):
        account = _make_account()
        svc, repo = _make_service(account)
        result = await svc.get(AsyncMock(), account.user_id, account.id)
        assert result == account

    @pytest.mark.asyncio
    async def test_get_not_found_raises(self):
        svc, _ = _make_service(None)
        with pytest.raises(AccountNotFoundError):
            await svc.get(AsyncMock(), uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_get_active_inactive_raises(self):
        account = _make_account(status="INACTIVE")
        svc, _ = _make_service(account)
        with pytest.raises(AccountInactiveError):
            await svc.get_active(AsyncMock(), account.user_id, account.id)

    @pytest.mark.asyncio
    async def test_get_active_succeeds_for_active(self):
        account = _make_account(status="ACTIVE")
        svc, _ = _make_service(account)
        result = await svc.get_active(AsyncMock(), account.user_id, account.id)
        assert result.status == "ACTIVE"


class TestTradingAccountServiceUpdate:
    @pytest.mark.asyncio
    async def test_update_only_display_name_changes(self):
        """B-15-15: update() with only display_name — only that column changes."""
        original = _make_account()
        updated = _make_account()
        updated_display = "Updated Name"

        repo = MagicMock()
        repo.update = AsyncMock(return_value=updated)
        svc = TradingAccountService(account_repo=repo)

        await svc.update(
            AsyncMock(),
            user_id=original.user_id,
            account_id=original.id,
            display_name=updated_display,
        )

        call_kwargs = repo.update.call_args.kwargs
        assert call_kwargs["display_name"] == updated_display
        assert call_kwargs["account_type"] is None  # not provided → None passed through

    @pytest.mark.asyncio
    async def test_update_strips_display_name_whitespace(self):
        account = _make_account()
        repo = MagicMock()
        repo.update = AsyncMock(return_value=account)
        svc = TradingAccountService(account_repo=repo)

        await svc.update(
            AsyncMock(),
            user_id=account.user_id,
            account_id=account.id,
            display_name="  Trimmed  ",
        )

        call_kwargs = repo.update.call_args.kwargs
        assert call_kwargs["display_name"] == "Trimmed"

    @pytest.mark.asyncio
    async def test_update_blank_display_name_raises(self):
        svc, _ = _make_service()
        with pytest.raises(ValueError, match="display_name"):
            await svc.update(
                AsyncMock(), user_id=uuid.uuid4(), account_id=uuid.uuid4(), display_name="  "
            )

    @pytest.mark.asyncio
    async def test_update_invalid_account_type_raises(self):
        svc, _ = _make_service()
        with pytest.raises(ValueError, match="account_type"):
            await svc.update(
                AsyncMock(), user_id=uuid.uuid4(), account_id=uuid.uuid4(), account_type="PROP"
            )

    @pytest.mark.asyncio
    async def test_update_not_found_raises(self):
        repo = MagicMock()
        repo.update = AsyncMock(return_value=None)
        svc = TradingAccountService(account_repo=repo)
        from tradeforge.domain.import_domain.errors import AccountNotFoundError

        with pytest.raises(AccountNotFoundError):
            await svc.update(AsyncMock(), user_id=uuid.uuid4(), account_id=uuid.uuid4())


class TestTradingAccountServiceDeactivate:
    @pytest.mark.asyncio
    async def test_deactivate_returns_true_for_existing(self):
        """B-15-16: deactivate() returns True for existing account."""
        repo = MagicMock()
        repo.deactivate = AsyncMock(return_value=True)
        svc = TradingAccountService(account_repo=repo)

        result = await svc.deactivate(AsyncMock(), user_id=uuid.uuid4(), account_id=uuid.uuid4())

        assert result is True
        repo.deactivate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_deactivate_returns_false_for_missing(self):
        """B-15-16: deactivate() returns False for missing account."""
        repo = MagicMock()
        repo.deactivate = AsyncMock(return_value=False)
        svc = TradingAccountService(account_repo=repo)

        result = await svc.deactivate(AsyncMock(), user_id=uuid.uuid4(), account_id=uuid.uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_deactivate_already_inactive_returns_true(self):
        """B-15-13: deactivate() returns True for an already-INACTIVE account.

        The repo UPDATE always sets updated_at=now(), so rowcount=1 regardless of
        current status — making deactivate() idempotent at the repo layer.
        The service passes that True through without checking the prior status.
        """
        repo = MagicMock()
        repo.deactivate = AsyncMock(return_value=True)
        svc = TradingAccountService(account_repo=repo)

        result = await svc.deactivate(AsyncMock(), user_id=uuid.uuid4(), account_id=uuid.uuid4())

        assert result is True
        repo.deactivate.assert_awaited_once()


class TestTradingAccountServiceList:
    @pytest.mark.asyncio
    async def test_list_returns_accounts(self):
        account = _make_account()
        svc, repo = _make_service(account)
        result = await svc.list(AsyncMock(), account.user_id)
        assert len(result) == 1
        assert result[0] == account
        repo.list_for_user.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_empty_for_new_user(self):
        svc, _ = _make_service(None)
        result = await svc.list(AsyncMock(), uuid.uuid4())
        assert result == []
