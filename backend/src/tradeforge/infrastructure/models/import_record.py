"""ORM model for import_records — one row per broker CSV import run."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


class ImportRecord(Base):
    __tablename__ = "import_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trading_accounts.id"), nullable=False
    )
    broker: Mapped[str] = mapped_column(String(20), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default="now()"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default="now()"
    )

    __table_args__ = (
        CheckConstraint(
            "broker IN ('ZERODHA', 'UPSTOX', 'ANGEL_ONE', 'MANUAL')",
            name="ck_import_records_broker",
        ),
        CheckConstraint(
            "status IN ('COMPLETE', 'PARTIAL', 'EMPTY', 'FAILED')",
            name="ck_import_records_status",
        ),
        UniqueConstraint("file_hash", "account_id", name="uq_import_records_hash_account"),
        Index("idx_import_records_account_id", "account_id"),
    )
