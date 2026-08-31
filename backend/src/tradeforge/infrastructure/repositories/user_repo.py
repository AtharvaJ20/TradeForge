"""UserRepository — all queries include a user_id ownership filter (SR-AUTH-021 Rule E)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.infrastructure.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_email(self, email: str) -> User | None:
        result = await self._db.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def find_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        password_hash: str,
    ) -> User:
        user = User(email=email.lower(), password_hash=password_hash)
        self._db.add(user)
        await self._db.flush()
        return user

    async def update_password(self, user_id: uuid.UUID, new_hash: str) -> None:
        await self._db.execute(
            update(User)
            .where(User.id == user_id)
            .values(password_hash=new_hash, updated_at=datetime.utcnow())
        )

    async def set_email_verified(self, user_id: uuid.UUID) -> None:
        await self._db.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_email_verified=True, updated_at=datetime.now(UTC))
        )

    async def set_locked(self, user_id: uuid.UUID, *, locked: bool) -> None:
        await self._db.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_locked=locked, updated_at=datetime.utcnow())
        )
