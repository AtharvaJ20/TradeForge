"""TradingAccountService — create, list, and retrieve trading accounts.

All methods are user-scoped: user_id is always taken from the session
token, never from request body. account_id in path parameters is always
validated against user_id ownership.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.domain.import_domain.errors import AccountInactiveError, AccountNotFoundError
from tradeforge.domain.import_domain.types import TradingAccount
from tradeforge.infrastructure.repositories.trading_account_repo import TradingAccountRepository

_VALID_BROKERS = frozenset({"ZERODHA", "UPSTOX", "ANGEL_ONE", "MANUAL"})
_VALID_ACCOUNT_TYPES = frozenset({"INDIVIDUAL", "HUF"})


class TradingAccountService:
    def __init__(self, account_repo: TradingAccountRepository) -> None:
        self._repo = account_repo

    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        broker: str,
        display_name: str,
        account_type: str = "INDIVIDUAL",
        base_currency: str = "INR",
    ) -> TradingAccount:
        """Create a new trading account for the user.

        Raises:
            ValueError: broker or account_type is not a supported value.
        """
        if broker not in _VALID_BROKERS:
            raise ValueError(
                f"Unsupported broker {broker!r}. Must be one of {sorted(_VALID_BROKERS)}"
            )
        if account_type not in _VALID_ACCOUNT_TYPES:
            raise ValueError(
                f"Unsupported account_type {account_type!r}. "
                f"Must be one of {sorted(_VALID_ACCOUNT_TYPES)}"
            )
        if not display_name.strip():
            raise ValueError("display_name must not be blank")

        return await self._repo.create(
            session,
            user_id=user_id,
            broker=broker,
            display_name=display_name.strip(),
            account_type=account_type,
            base_currency=base_currency,
        )

    async def list(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> list[TradingAccount]:
        """Return all trading accounts for the authenticated user."""
        return await self._repo.list_for_user(session, user_id)

    async def get(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> TradingAccount:
        """Return a single account, verified to be owned by user_id.

        Raises:
            AccountNotFoundError: account does not exist or is not owned by user.
        """
        account = await self._repo.get_for_user(session, user_id, account_id)
        if account is None:
            raise AccountNotFoundError(account_id)
        return account

    async def get_active(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> TradingAccount:
        """Like get(), but also raises AccountInactiveError if status != ACTIVE."""
        account = await self.get(session, user_id, account_id)
        if account.status != "ACTIVE":
            raise AccountInactiveError(account_id)
        return account

    async def update(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        display_name: str | None = None,
        account_type: str | None = None,
    ) -> TradingAccount:
        """Update mutable account fields.

        Raises:
            AccountNotFoundError: account does not exist or is not owned by user.
            ValueError: account_type is not a supported value.
        """
        if account_type is not None and account_type not in _VALID_ACCOUNT_TYPES:
            raise ValueError(
                f"Unsupported account_type {account_type!r}. "
                f"Must be one of {sorted(_VALID_ACCOUNT_TYPES)}"
            )
        if display_name is not None and not display_name.strip():
            raise ValueError("display_name must not be blank")

        result = await self._repo.update(
            session,
            user_id=user_id,
            account_id=account_id,
            display_name=display_name.strip() if display_name else None,
            account_type=account_type,
        )
        if result is None:
            raise AccountNotFoundError(account_id)
        return result

    async def deactivate(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> bool:
        """Soft-delete the account (status → INACTIVE). Idempotent.

        Returns True if the account was found (and deactivated), False if not found.
        """
        return await self._repo.deactivate(session, user_id=user_id, account_id=account_id)
