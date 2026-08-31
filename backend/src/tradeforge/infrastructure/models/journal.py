"""ORM models for the journal annotation layer.

JournalEntry    — 1:1 annotation per trade (Layer B fields).
JournalAttachment — file attachments; PENDING → CONFIRMED lifecycle.
JournalAuditLog — append-only field-level audit trail.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, utcnow

_EMOTION_CHECK = (
    "CALM",
    "CONFIDENT",
    "ANXIOUS",
    "FEARFUL",
    "GREEDY",
    "FRUSTRATED",
    "EUPHORIC",
    "BORED",
    "DISTRACTED",
    "NEUTRAL",
)
_EMOTION_SQL = "', '".join(_EMOTION_CHECK)

_CAPTURE_MOMENTS = ("AT_ENTRY", "DURING_TRADE", "AT_EXIT", "POST_REVIEW")
_ATTACHMENT_STATUSES = ("PENDING", "CONFIRMED", "EXPIRED", "REJECTED")
_CAPTURE_MOMENT_SQL = "', '".join(_CAPTURE_MOMENTS)
_ATTACHMENT_STATUS_SQL = "', '".join(_ATTACHMENT_STATUSES)


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trades.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # Plan fields
    planned_entry: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    planned_stop: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    planned_target: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    # Computed when planned_stop is set: abs(average_entry − planned_stop) × total_entry_quantity
    planned_risk_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    setup_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Behavioral fields
    discipline_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    mistakes: Mapped[list[str] | None] = mapped_column(ARRAY(String(30)), nullable=True)
    emotion_before: Mapped[str | None] = mapped_column(String(30), nullable=True)
    emotion_during: Mapped[str | None] = mapped_column(String(30), nullable=True)
    emotion_after: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default="now()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default="now()",
    )

    attachments: Mapped[list[JournalAttachment]] = relationship(
        "JournalAttachment", back_populates="journal_entry", lazy="raise_on_sql"
    )

    __table_args__ = (
        UniqueConstraint("trade_id", name="uq_journal_entries_trade_id"),
        CheckConstraint(
            "discipline_score IS NULL OR (discipline_score >= 1 AND discipline_score <= 10)",
            name="ck_journal_discipline_score",
        ),
        CheckConstraint(
            f"emotion_before IS NULL OR emotion_before IN ('{_EMOTION_SQL}')",
            name="ck_journal_emotion_before",
        ),
        CheckConstraint(
            f"emotion_during IS NULL OR emotion_during IN ('{_EMOTION_SQL}')",
            name="ck_journal_emotion_during",
        ),
        CheckConstraint(
            f"emotion_after IS NULL OR emotion_after IN ('{_EMOTION_SQL}')",
            name="ck_journal_emotion_after",
        ),
        Index("idx_journal_entries_user_id", "user_id"),
        Index("idx_journal_entries_trade_id", "trade_id"),
    )


class JournalAttachment(Base):
    __tablename__ = "journal_attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    trade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trades.id"), nullable=False
    )
    # S3 key is server-generated: {user_id}/{trade_id}/{attachment_id} (SR-ATT-005)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    # filename is stored as display metadata only — never used in S3 key (SR-ATT-005)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    capture_moment: Mapped[str] = mapped_column(String(20), nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default="now()"
    )

    journal_entry: Mapped[JournalEntry] = relationship(
        "JournalEntry", back_populates="attachments", lazy="raise_on_sql"
    )

    __table_args__ = (
        CheckConstraint(
            f"capture_moment IN ('{_CAPTURE_MOMENT_SQL}')",
            name="ck_attachment_capture_moment",
        ),
        CheckConstraint(
            f"status IN ('{_ATTACHMENT_STATUS_SQL}')",
            name="ck_attachment_status",
        ),
        CheckConstraint("byte_size > 0", name="ck_attachment_byte_size_positive"),
        Index("idx_attachments_journal_entry_id", "journal_entry_id"),
        Index("idx_attachments_user_id", "user_id"),
        Index("idx_attachments_trade_id", "trade_id"),
    )


class JournalAuditLog(Base):
    """Append-only audit trail. Written by the Application service, never by DB triggers.

    Each row records a single field change: old value → new value with an optional reason.
    The service writes one row per changed field on every journal entry update.
    """

    __tablename__ = "journal_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    previous_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default="now()"
    )

    __table_args__ = (
        Index("idx_audit_log_journal_entry_id", "journal_entry_id"),
        Index("idx_audit_log_user_id", "user_id"),
    )
