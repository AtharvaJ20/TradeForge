"""JournalService — application-layer orchestration for the journal annotation layer.

Security requirements implemented here:
  SR-ATT-001  Content type allowlist enforced before presign
  SR-ATT-002  File size limits enforced before presign (byte_size declared at presign)
  SR-ATT-005  S3 key is server-generated; filename sanitised and stored as metadata only
  SR-ATT-006  Ownership verified in repository WHERE clause (user_id from session)
  SR-ATT-009  Attachment events logged to security_audit_log
  SR-ATT-010  PENDING rows older than PENDING_EXPIRY_MINUTES are transitioned to EXPIRED

Architecture (ADR-002):
  - Journal service never writes to trade_pnl (owned by Step 10 P&L engine).
  - planned_risk_amount is computed here and stored in journal_entries.
  - Audit log is written by the service layer (not DB triggers).
  - user_id always comes from the verified session — never from request data.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tradeforge.application.pnl_service import PnlService

from tradeforge.application.journal.storage import StoragePort, StubStorage
from tradeforge.domain.journal.errors import (
    AttachmentContentTypeNotAllowedError,
    AttachmentExpiredError,
    AttachmentFilenameExtensionMismatchError,
    AttachmentNotFoundError,
    AttachmentSizeLimitExceededError,
    AttachmentStorageQuotaExceededError,
    JournalEntryNotFoundError,
    TradeNotFoundError,
)
from tradeforge.domain.journal.types import (
    ALLOWED_CONTENT_TYPES,
    ATTACHMENT_MAX_BYTES,
    ATTACHMENT_PER_TRADE_MAX_BYTES,
    ATTACHMENT_PER_USER_MAX_BYTES,
    PENDING_EXPIRY_MINUTES,
    PRESIGN_DOWNLOAD_TTL_SECONDS,
    PRESIGN_UPLOAD_TTL_SECONDS,
    AttachmentView,
    AuditEntry,
    JournalEntryView,
    JournalEntryWrite,
    PnlSnapshot,
    PnlStatus,
    PresignResult,
    build_s3_key,
    filename_extension_matches,
    sanitize_filename,
)
from tradeforge.infrastructure.repositories.auth_repo import AuditLogRepository
from tradeforge.infrastructure.repositories.journal_repo import JournalRepository

# Fields that are tracked in journal_audit_log on every update
_AUDITABLE_FIELDS: tuple[str, ...] = (
    "planned_entry",
    "planned_stop",
    "planned_target",
    "setup_name",
    "notes",
    "discipline_score",
    "mistakes",
    "emotion_before",
    "emotion_during",
    "emotion_after",
)


def _str_value(v: Any) -> str | None:
    """Serialize a field value to a text string for audit log storage."""
    if v is None:
        return None
    if isinstance(v, list):
        return ",".join(str(x) for x in v)
    return str(v)


def _compute_pnl_status(planned_stop: Decimal | None, has_pnl: bool) -> PnlStatus:
    if has_pnl:
        return PnlStatus.AVAILABLE
    if planned_stop is not None:
        return PnlStatus.PENDING_CALCULATION
    return PnlStatus.PENDING_STOP


def _compute_planned_risk_amount(
    planned_stop: Decimal | None,
    average_entry: Decimal | None,
    total_entry_quantity: Decimal,
) -> Decimal | None:
    """Compute abs(average_entry − planned_stop) × total_entry_quantity."""
    if planned_stop is None or average_entry is None:
        return None
    return abs(average_entry - planned_stop) * total_entry_quantity


class JournalService:
    def __init__(
        self,
        journal_repo: JournalRepository,
        audit_repo: AuditLogRepository,
        storage: StoragePort | None = None,
        pnl_service: PnlService | None = None,
    ) -> None:
        self._repo = journal_repo
        self._audit_repo = audit_repo
        self._storage: StoragePort = storage or StubStorage()
        self._pnl_service: PnlService | None = pnl_service

    # ------------------------------------------------------------------
    # Journal entry — read
    # ------------------------------------------------------------------

    async def get_entry(self, user_id: uuid.UUID, trade_id: uuid.UUID) -> JournalEntryView:
        entry = await self._repo.get_entry(trade_id, user_id)
        if entry is None:
            raise JournalEntryNotFoundError(trade_id)

        has_pnl = await self._repo.has_pnl_row(trade_id)
        pnl_status = _compute_pnl_status(entry.planned_stop, has_pnl)

        raw_attachments = await self._repo.list_confirmed_attachments(entry.id)
        attachment_views = [await self._build_attachment_view(att) for att in raw_attachments]

        return self._build_entry_view(entry, pnl_status, attachment_views)

    # ------------------------------------------------------------------
    # Journal entry — upsert
    # ------------------------------------------------------------------

    async def upsert_entry(
        self,
        user_id: uuid.UUID,
        trade_id: uuid.UUID,
        data: JournalEntryWrite,
        ip_address: str | None = None,
    ) -> JournalEntryView:
        # Verify trade ownership and load fields needed for risk computation (SR-ATT-006)
        trade_row = await self._repo.get_trade_snapshot(trade_id, user_id)
        if trade_row is None:
            raise TradeNotFoundError(trade_id)

        _, _, average_entry, total_entry_quantity = trade_row

        planned_risk_amount = _compute_planned_risk_amount(
            data.planned_stop, average_entry, Decimal(str(total_entry_quantity))
        )

        fields: dict[str, Any] = {
            "planned_entry": data.planned_entry,
            "planned_stop": data.planned_stop,
            "planned_target": data.planned_target,
            "planned_risk_amount": planned_risk_amount,
            "setup_name": data.setup_name,
            "notes": data.notes,
            "discipline_score": data.discipline_score,
            "mistakes": data.mistakes,
            "emotion_before": data.emotion_before,
            "emotion_during": data.emotion_during,
            "emotion_after": data.emotion_after,
        }

        existing = await self._repo.get_entry(trade_id, user_id)

        if existing is None:
            entry = await self._repo.create_entry(trade_id, user_id, fields)
        else:
            audit_entries = self._diff_for_audit(existing, fields, data.change_reason)
            await self._repo.update_entry(existing.id, fields)
            if audit_entries:
                await self._repo.append_audit_entries(existing.id, user_id, audit_entries)
            # Re-fetch to pick up updated_at
            entry = await self._repo.get_entry(trade_id, user_id)
            assert entry is not None  # just updated, cannot be None

        has_pnl = await self._repo.has_pnl_row(trade_id)
        pnl_status = _compute_pnl_status(entry.planned_stop, has_pnl)

        # Recalculate r_multiple when planned_stop is set and P&L already exists.
        if self._pnl_service is not None and has_pnl and data.planned_stop is not None:
            try:
                await self._pnl_service.recalculate_r_multiple(trade_id, user_id)
            except Exception:
                import logging as _logging

                _logging.getLogger(__name__).warning(
                    "r_multiple recalculation failed for trade %s — continuing",
                    trade_id,
                    exc_info=True,
                )

        raw_attachments = await self._repo.list_confirmed_attachments(entry.id)
        attachment_views = [await self._build_attachment_view(att) for att in raw_attachments]

        return self._build_entry_view(entry, pnl_status, attachment_views)

    # ------------------------------------------------------------------
    # Audit history
    # ------------------------------------------------------------------

    async def get_audit_history(self, user_id: uuid.UUID, trade_id: uuid.UUID) -> list[AuditEntry]:
        entry = await self._repo.get_entry(trade_id, user_id)
        if entry is None:
            raise JournalEntryNotFoundError(trade_id)

        rows = await self._repo.get_audit_log(entry.id, user_id)
        return [
            AuditEntry(
                id=row.id,
                field_name=row.field_name,
                previous_value=row.previous_value,
                new_value=row.new_value,
                change_reason=row.change_reason,
                changed_at=row.changed_at,
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Attachments — presign (SR-ATT-001, SR-ATT-002, SR-ATT-005)
    # ------------------------------------------------------------------

    async def presign_attachment(
        self,
        user_id: uuid.UUID,
        trade_id: uuid.UUID,
        filename: str,
        content_type: str,
        byte_size: int,
        capture_moment: str,
        caption: str | None,
        ip_address: str | None = None,
    ) -> PresignResult:
        # SR-ATT-001: content type allowlist
        if content_type not in ALLOWED_CONTENT_TYPES:
            await self._log_attachment_event(
                "ATTACHMENT_REJECTED_TYPE",
                user_id=user_id,
                trade_id=trade_id,
                ip=ip_address,
                content_type=content_type,
                byte_size=byte_size,
            )
            raise AttachmentContentTypeNotAllowedError(content_type)

        # SR-ATT-002: file size limit
        if byte_size <= 0 or byte_size > ATTACHMENT_MAX_BYTES:
            await self._log_attachment_event(
                "ATTACHMENT_REJECTED_SIZE",
                user_id=user_id,
                trade_id=trade_id,
                ip=ip_address,
                content_type=content_type,
                byte_size=byte_size,
            )
            raise AttachmentSizeLimitExceededError(byte_size, ATTACHMENT_MAX_BYTES)

        # SR-ATT-005: filename extension must match content_type
        safe_name = sanitize_filename(filename)
        if not filename_extension_matches(safe_name, content_type):
            raise AttachmentFilenameExtensionMismatchError(safe_name, content_type)

        # SR-ATT-006: verify trade ownership
        trade_row = await self._repo.get_trade_snapshot(trade_id, user_id)
        if trade_row is None:
            raise TradeNotFoundError(trade_id)

        # SR-ATT-002: per-trade storage quota
        trade_used = await self._repo.sum_confirmed_bytes_for_trade(trade_id, user_id)
        if trade_used + byte_size > ATTACHMENT_PER_TRADE_MAX_BYTES:
            await self._log_attachment_event(
                "ATTACHMENT_REJECTED_QUOTA",
                user_id=user_id,
                trade_id=trade_id,
                ip=ip_address,
                content_type=content_type,
                byte_size=byte_size,
            )
            raise AttachmentStorageQuotaExceededError("this trade")

        # SR-ATT-002: per-user storage quota
        user_used = await self._repo.sum_confirmed_bytes_for_user(user_id)
        if user_used + byte_size > ATTACHMENT_PER_USER_MAX_BYTES:
            await self._log_attachment_event(
                "ATTACHMENT_REJECTED_QUOTA",
                user_id=user_id,
                trade_id=trade_id,
                ip=ip_address,
                content_type=content_type,
                byte_size=byte_size,
            )
            raise AttachmentStorageQuotaExceededError("your account")

        # Ensure a journal entry exists to attach to
        entry = await self._repo.get_entry(trade_id, user_id)
        if entry is None:
            entry = await self._repo.create_entry(
                trade_id,
                user_id,
                {},  # blank entry — fields filled by future upsert_entry
            )

        # Server-generated attachment ID and S3 key (SR-ATT-005)
        attachment_id = uuid.uuid4()
        s3_key = build_s3_key(user_id, trade_id, attachment_id)

        await self._repo.create_attachment(
            journal_entry_id=entry.id,
            user_id=user_id,
            trade_id=trade_id,
            s3_key=s3_key,
            filename=safe_name,
            content_type=content_type,
            byte_size=byte_size,
            capture_moment=capture_moment,
            caption=caption,
            attachment_id=attachment_id,
        )

        upload_url = await self._storage.presign_put(
            key=s3_key,
            content_type=content_type,
            byte_size=byte_size,
            ttl_seconds=PRESIGN_UPLOAD_TTL_SECONDS,
        )

        await self._log_attachment_event(
            "ATTACHMENT_PRESIGN_REQUESTED",
            user_id=user_id,
            trade_id=trade_id,
            attachment_id=attachment_id,
            ip=ip_address,
            content_type=content_type,
            byte_size=byte_size,
        )

        return PresignResult(
            attachment_id=attachment_id,
            upload_url=upload_url,
            s3_key=s3_key,
            expires_in_seconds=PRESIGN_UPLOAD_TTL_SECONDS,
        )

    # ------------------------------------------------------------------
    # Attachments — confirm (SR-ATT-007, SR-ATT-010)
    # ------------------------------------------------------------------

    async def confirm_attachment(
        self,
        user_id: uuid.UUID,
        attachment_id: uuid.UUID,
        ip_address: str | None = None,
    ) -> AttachmentView:
        att = await self._repo.get_pending_attachment(attachment_id, user_id)
        if att is None:
            raise AttachmentNotFoundError(attachment_id)

        # SR-ATT-010: PENDING rows older than PENDING_EXPIRY_MINUTES are expired
        expiry_cutoff = datetime.now(UTC) - timedelta(minutes=PENDING_EXPIRY_MINUTES)
        created_at = att.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        if created_at < expiry_cutoff:
            await self._repo.update_attachment_status(attachment_id, "EXPIRED")
            raise AttachmentExpiredError(attachment_id)

        # HeadObject to verify the upload completed (SR-ATT-008 — server never reads body)
        head = await self._storage.head_object(att.s3_key)
        if head is None:
            await self._repo.update_attachment_status(attachment_id, "REJECTED")
            await self._log_attachment_event(
                "ATTACHMENT_CONFIRM_FAILED",
                user_id=user_id,
                trade_id=att.trade_id,
                attachment_id=attachment_id,
                ip=ip_address,
                content_type=att.content_type,
                byte_size=att.byte_size,
            )
            raise AttachmentNotFoundError(attachment_id)

        now = datetime.now(UTC)
        await self._repo.update_attachment_status(attachment_id, "CONFIRMED", confirmed_at=now)

        await self._log_attachment_event(
            "ATTACHMENT_CONFIRMED",
            user_id=user_id,
            trade_id=att.trade_id,
            attachment_id=attachment_id,
            ip=ip_address,
            content_type=att.content_type,
            byte_size=att.byte_size,
        )

        download_url = await self._storage.presign_get(
            key=att.s3_key,
            filename=att.filename,
            content_type=att.content_type,
            ttl_seconds=PRESIGN_DOWNLOAD_TTL_SECONDS,
        )

        return AttachmentView(
            id=att.id,
            filename=att.filename,
            content_type=att.content_type,
            byte_size=att.byte_size,
            capture_moment=att.capture_moment,
            caption=att.caption,
            status="CONFIRMED",
            download_url=download_url,
            confirmed_at=now,
            created_at=att.created_at,
        )

    # ------------------------------------------------------------------
    # Attachments — delete (soft delete)
    # ------------------------------------------------------------------

    async def delete_attachment(
        self,
        user_id: uuid.UUID,
        attachment_id: uuid.UUID,
        ip_address: str | None = None,
    ) -> None:
        att = await self._repo.get_confirmed_attachment(attachment_id, user_id)
        if att is None:
            raise AttachmentNotFoundError(attachment_id)

        await self._repo.soft_delete_attachment(attachment_id)

        await self._log_attachment_event(
            "ATTACHMENT_DELETED",
            user_id=user_id,
            trade_id=att.trade_id,
            attachment_id=attachment_id,
            ip=ip_address,
            content_type=att.content_type,
            byte_size=att.byte_size,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _diff_for_audit(
        self,
        existing: Any,
        new_fields: dict[str, Any],
        change_reason: str | None,
    ) -> list[dict[str, Any]]:
        """Return audit log entries for fields that changed between existing and new."""
        entries = []
        for field in _AUDITABLE_FIELDS:
            old_val = getattr(existing, field, None)
            new_val = new_fields.get(field)
            old_str = _str_value(old_val)
            new_str = _str_value(new_val)
            if old_str != new_str:
                entries.append(
                    {
                        "field_name": field,
                        "previous_value": old_str,
                        "new_value": new_str,
                        "change_reason": change_reason,
                    }
                )
        return entries

    async def _build_attachment_view(self, att: Any) -> AttachmentView:
        download_url = await self._storage.presign_get(
            key=att.s3_key,
            filename=att.filename,
            content_type=att.content_type,
            ttl_seconds=PRESIGN_DOWNLOAD_TTL_SECONDS,
        )
        return AttachmentView(
            id=att.id,
            filename=att.filename,
            content_type=att.content_type,
            byte_size=att.byte_size,
            capture_moment=att.capture_moment,
            caption=att.caption,
            status=att.status,
            download_url=download_url,
            confirmed_at=att.confirmed_at,
            created_at=att.created_at,
        )

    def _build_entry_view(
        self,
        entry: Any,
        pnl_status: PnlStatus,
        attachments: list[AttachmentView],
    ) -> JournalEntryView:
        return JournalEntryView(
            id=entry.id,
            trade_id=entry.trade_id,
            user_id=entry.user_id,
            planned_entry=entry.planned_entry,
            planned_stop=entry.planned_stop,
            planned_target=entry.planned_target,
            planned_risk_amount=entry.planned_risk_amount,
            setup_name=entry.setup_name,
            notes=entry.notes,
            discipline_score=entry.discipline_score,
            mistakes=entry.mistakes or [],
            emotion_before=entry.emotion_before,
            emotion_during=entry.emotion_during,
            emotion_after=entry.emotion_after,
            pnl=PnlSnapshot(status=pnl_status),
            attachments=attachments,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )

    async def _log_attachment_event(
        self,
        event_type: str,
        *,
        user_id: uuid.UUID,
        trade_id: uuid.UUID,
        ip: str | None,
        content_type: str,
        byte_size: int,
        attachment_id: uuid.UUID | None = None,
    ) -> None:
        """Write an attachment security event to security_audit_log (SR-ATT-009)."""
        event_data: dict[str, Any] = {
            "trade_id": str(trade_id),
            "declared_content_type": content_type,
            "declared_byte_size": byte_size,
        }
        if attachment_id is not None:
            event_data["attachment_id"] = str(attachment_id)

        await self._audit_repo.log(
            event_type,
            ip_address=ip,
            user_id=user_id,
            event_data=event_data,
        )
