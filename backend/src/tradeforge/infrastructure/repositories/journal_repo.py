"""Repository for all journal domain persistence.

Owns: journal_entries, journal_attachments, journal_audit_log.
Read-only access to trades (trade snapshot) and trade_pnl (pnl status check).

Security invariant (SR-ATT-005, SR-ATT-006):
  - Every ownership check uses user_id from the verified session (passed in by the service).
  - user_id is never accepted from request body or URL parameters.
  - Ownership is enforced inside the SQL WHERE clause — not as a post-retrieval Python check.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.infrastructure.models.journal import (
    JournalAttachment,
    JournalAuditLog,
    JournalEntry,
)
from tradeforge.infrastructure.models.trade_domain import Trade
from tradeforge.infrastructure.models.trade_pnl import TradePnl


class JournalRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Trade snapshot (journal-specific query, avoids importing TradeRepo)
    # ------------------------------------------------------------------

    async def get_trade_snapshot(
        self, trade_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[uuid.UUID, uuid.UUID, Any, Any] | None:
        """Return (id, user_id, average_entry, total_entry_quantity) for the trade, or None."""
        result = await self._db.execute(
            select(
                Trade.id,
                Trade.user_id,
                Trade.average_entry,
                Trade.total_entry_quantity,
            ).where(Trade.id == trade_id, Trade.user_id == user_id)
        )
        return result.one_or_none()

    # ------------------------------------------------------------------
    # Journal entry CRUD
    # ------------------------------------------------------------------

    async def get_entry(
        self, trade_id: uuid.UUID, user_id: uuid.UUID
    ) -> JournalEntry | None:
        result = await self._db.execute(
            select(JournalEntry).where(
                JournalEntry.trade_id == trade_id,
                JournalEntry.user_id == user_id,
                JournalEntry.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create_entry(
        self,
        trade_id: uuid.UUID,
        user_id: uuid.UUID,
        fields: dict[str, Any],
    ) -> JournalEntry:
        entry = JournalEntry(trade_id=trade_id, user_id=user_id, **fields)
        self._db.add(entry)
        await self._db.flush()
        return entry

    async def update_entry(
        self, entry_id: uuid.UUID, updates: dict[str, Any]
    ) -> None:
        await self._db.execute(
            update(JournalEntry)
            .where(JournalEntry.id == entry_id)
            .values(**updates)
        )
        await self._db.flush()

    # ------------------------------------------------------------------
    # P&L status check (LEFT JOIN on trade_pnl)
    # ------------------------------------------------------------------

    async def has_pnl_row(self, trade_id: uuid.UUID) -> bool:
        result = await self._db.execute(
            select(TradePnl.id).where(TradePnl.trade_id == trade_id).limit(1)
        )
        return result.scalar_one_or_none() is not None

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    async def append_audit_entries(
        self,
        journal_entry_id: uuid.UUID,
        user_id: uuid.UUID,
        entries: list[dict[str, Any]],
    ) -> None:
        """Append one row per changed field to journal_audit_log."""
        for e in entries:
            row = JournalAuditLog(
                journal_entry_id=journal_entry_id,
                user_id=user_id,
                field_name=e["field_name"],
                previous_value=e.get("previous_value"),
                new_value=e.get("new_value"),
                change_reason=e.get("change_reason"),
            )
            self._db.add(row)
        if entries:
            await self._db.flush()

    async def get_audit_log(
        self, journal_entry_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[JournalAuditLog]:
        result = await self._db.execute(
            select(JournalAuditLog)
            .where(
                JournalAuditLog.journal_entry_id == journal_entry_id,
                JournalAuditLog.user_id == user_id,
            )
            .order_by(JournalAuditLog.changed_at.asc())
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Attachments — quota checks (SR-ATT-002)
    # ------------------------------------------------------------------

    async def sum_confirmed_bytes_for_trade(
        self, trade_id: uuid.UUID, user_id: uuid.UUID
    ) -> int:
        result = await self._db.execute(
            select(func.coalesce(func.sum(JournalAttachment.byte_size), 0)).where(
                JournalAttachment.trade_id == trade_id,
                JournalAttachment.user_id == user_id,
                JournalAttachment.status == "CONFIRMED",
                JournalAttachment.deleted_at.is_(None),
            )
        )
        return int(result.scalar_one())

    async def sum_confirmed_bytes_for_user(self, user_id: uuid.UUID) -> int:
        result = await self._db.execute(
            select(func.coalesce(func.sum(JournalAttachment.byte_size), 0)).where(
                JournalAttachment.user_id == user_id,
                JournalAttachment.status == "CONFIRMED",
                JournalAttachment.deleted_at.is_(None),
            )
        )
        return int(result.scalar_one())

    # ------------------------------------------------------------------
    # Attachments — CRUD
    # ------------------------------------------------------------------

    async def create_attachment(
        self,
        journal_entry_id: uuid.UUID,
        user_id: uuid.UUID,
        trade_id: uuid.UUID,
        s3_key: str,
        filename: str,
        content_type: str,
        byte_size: int,
        capture_moment: str,
        caption: str | None,
        attachment_id: uuid.UUID,
    ) -> JournalAttachment:
        att = JournalAttachment(
            id=attachment_id,
            journal_entry_id=journal_entry_id,
            user_id=user_id,
            trade_id=trade_id,
            s3_key=s3_key,
            filename=filename,
            content_type=content_type,
            byte_size=byte_size,
            capture_moment=capture_moment,
            caption=caption,
            status="PENDING",
        )
        self._db.add(att)
        await self._db.flush()
        return att

    async def get_pending_attachment(
        self, attachment_id: uuid.UUID, user_id: uuid.UUID
    ) -> JournalAttachment | None:
        """Return a PENDING attachment owned by user_id, or None. (SR-ATT-006)"""
        result = await self._db.execute(
            select(JournalAttachment).where(
                JournalAttachment.id == attachment_id,
                JournalAttachment.user_id == user_id,
                JournalAttachment.status == "PENDING",
            )
        )
        return result.scalar_one_or_none()

    async def get_confirmed_attachment(
        self, attachment_id: uuid.UUID, user_id: uuid.UUID
    ) -> JournalAttachment | None:
        """Return a CONFIRMED, non-deleted attachment owned by user_id, or None. (SR-ATT-006)"""
        result = await self._db.execute(
            select(JournalAttachment).where(
                JournalAttachment.id == attachment_id,
                JournalAttachment.user_id == user_id,
                JournalAttachment.status == "CONFIRMED",
                JournalAttachment.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def update_attachment_status(
        self,
        attachment_id: uuid.UUID,
        status: str,
        *,
        confirmed_at: datetime | None = None,
    ) -> None:
        values: dict[str, Any] = {"status": status}
        if confirmed_at is not None:
            values["confirmed_at"] = confirmed_at
        await self._db.execute(
            update(JournalAttachment)
            .where(JournalAttachment.id == attachment_id)
            .values(**values)
        )
        await self._db.flush()

    async def soft_delete_attachment(self, attachment_id: uuid.UUID) -> None:
        await self._db.execute(
            update(JournalAttachment)
            .where(JournalAttachment.id == attachment_id)
            .values(deleted_at=datetime.now(timezone.utc))
        )
        await self._db.flush()

    async def list_confirmed_attachments(
        self, journal_entry_id: uuid.UUID
    ) -> list[JournalAttachment]:
        result = await self._db.execute(
            select(JournalAttachment)
            .where(
                JournalAttachment.journal_entry_id == journal_entry_id,
                JournalAttachment.status == "CONFIRMED",
                JournalAttachment.deleted_at.is_(None),
            )
            .order_by(JournalAttachment.created_at.asc())
        )
        return list(result.scalars().all())
