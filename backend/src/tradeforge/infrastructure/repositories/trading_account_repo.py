"""TradingAccountRepository — CRUD for the trading_accounts table."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.domain.import_domain.types import TradingAccount as TradingAccountDomain
from tradeforge.infrastructure.models.trading_account import TradingAccount


class TradingAccountRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        broker: str,
        display_name: str,
        account_type: str,
        base_currency: str = "INR",
    ) -> TradingAccountDomain:
        pk = uuid.uuid4()
        obj = TradingAccount(
            id=pk,
            user_id=user_id,
            broker=broker,
            display_name=display_name,
            account_type=account_type,
            base_currency=base_currency,
            status="ACTIVE",
        )
        session.add(obj)
        await session.flush()
        await session.refresh(obj)
        return self._to_domain(obj)

    async def get_for_user(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> TradingAccountDomain | None:
        """Return the account only if it is owned by user_id."""
        stmt = select(TradingAccount).where(
            TradingAccount.id == account_id,
            TradingAccount.user_id == user_id,
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    async def list_for_user(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> list[TradingAccountDomain]:
        stmt = (
            select(TradingAccount)
            .where(TradingAccount.user_id == user_id)
            .order_by(TradingAccount.created_at.asc())
        )
        result = await session.execute(stmt)
        return [self._to_domain(r) for r in result.scalars().all()]

    async def update(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        display_name: str | None = None,
        account_type: str | None = None,
    ) -> TradingAccountDomain | None:
        """Update mutable account fields.  Returns None if not found / not owned."""
        values: dict[str, object] = {"updated_at": datetime.now(UTC)}
        if display_name is not None:
            values["display_name"] = display_name
        if account_type is not None:
            values["account_type"] = account_type

        await session.execute(
            update(TradingAccount)
            .where(TradingAccount.id == account_id, TradingAccount.user_id == user_id)
            .values(**values)
        )
        return await self.get_for_user(session, user_id, account_id)

    async def deactivate(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> bool:
        """Soft-delete: set status to INACTIVE.  Idempotent — returns True if found."""
        result = await session.execute(
            update(TradingAccount)
            .where(TradingAccount.id == account_id, TradingAccount.user_id == user_id)
            .values(status="INACTIVE", updated_at=datetime.now(UTC))
        )
        return result.rowcount > 0  # type: ignore[return-value]

    @staticmethod
    def _to_domain(row: TradingAccount) -> TradingAccountDomain:
        return TradingAccountDomain(
            id=row.id,
            user_id=row.user_id,
            broker=row.broker,
            display_name=row.display_name,
            account_type=row.account_type,
            base_currency=row.base_currency,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
