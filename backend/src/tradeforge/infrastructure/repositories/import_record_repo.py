"""ImportRecordRepository — read/write for import_records."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.infrastructure.models.import_record import ImportRecord


class ImportRecordRepository:
    async def exists(
        self,
        session: AsyncSession,
        file_hash: str,
        account_id: uuid.UUID,
    ) -> bool:
        """Return True if this file_hash + account_id combination already exists."""
        stmt = (
            select(ImportRecord.id)
            .where(
                ImportRecord.file_hash == file_hash,
                ImportRecord.account_id == account_id,
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        session: AsyncSession,
        *,
        account_id: uuid.UUID,
        broker: str,
        file_hash: str,
        file_name: str | None,
        row_count: int,
        error_count: int,
        status: str,
    ) -> uuid.UUID:
        """Insert a new import_records row and return its id."""
        pk = uuid.uuid4()
        now = datetime.now(UTC)
        obj = ImportRecord(
            id=pk,
            account_id=account_id,
            broker=broker,
            file_hash=file_hash,
            file_name=file_name,
            row_count=row_count,
            error_count=error_count,
            status=status,
            imported_at=now,
            created_at=now,
        )
        session.add(obj)
        await session.flush()
        return pk
