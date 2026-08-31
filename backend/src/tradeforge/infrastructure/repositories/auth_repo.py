"""Repositories for auth tokens and the security audit log."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.infrastructure.models.auth import (
    PendingEmailVerification,
    PendingPasswordReset,
    SecurityAuditLog,
)


class PendingVerificationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, email: str, token_hash: str, expires_at: datetime) -> None:
        row = PendingEmailVerification(email=email.lower(), token_hash=token_hash, expires_at=expires_at)
        self._db.add(row)
        await self._db.flush()

    async def find_by_token_hash(self, token_hash: str) -> PendingEmailVerification | None:
        result = await self._db.execute(
            select(PendingEmailVerification).where(
                PendingEmailVerification.token_hash == token_hash
            )
        )
        return result.scalar_one_or_none()

    async def delete(self, row_id: uuid.UUID) -> None:
        await self._db.execute(
            delete(PendingEmailVerification).where(PendingEmailVerification.id == row_id)
        )

    async def delete_expired(self) -> None:
        now = datetime.now(timezone.utc)
        await self._db.execute(
            delete(PendingEmailVerification).where(PendingEmailVerification.expires_at < now)
        )


class PendingResetRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, email: str, token_hash: str, expires_at: datetime) -> None:
        row = PendingPasswordReset(email=email.lower(), token_hash=token_hash, expires_at=expires_at)
        self._db.add(row)
        await self._db.flush()

    async def find_by_token_hash(self, token_hash: str) -> PendingPasswordReset | None:
        result = await self._db.execute(
            select(PendingPasswordReset).where(
                PendingPasswordReset.token_hash == token_hash
            )
        )
        return result.scalar_one_or_none()

    async def delete(self, row_id: uuid.UUID) -> None:
        await self._db.execute(
            delete(PendingPasswordReset).where(PendingPasswordReset.id == row_id)
        )

    async def delete_by_email(self, email: str) -> None:
        """Invalidate any outstanding resets for this email before issuing a new one."""
        await self._db.execute(
            delete(PendingPasswordReset).where(
                PendingPasswordReset.email == email.lower()
            )
        )


class AuditLogRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def log(
        self,
        event_type: str,
        ip_address: str | None = None,
        *,
        user_id: uuid.UUID | None = None,
        user_agent: str | None = None,
        event_data: dict[str, Any] | None = None,
        session_id: uuid.UUID | None = None,
    ) -> None:
        row = SecurityAuditLog(
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data=event_data,
            session_id=session_id,
        )
        self._db.add(row)
        await self._db.flush()
