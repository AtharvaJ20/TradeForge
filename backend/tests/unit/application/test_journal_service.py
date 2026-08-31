"""Unit tests for JournalService.

ADR-001: Application-layer unit tests only. All repositories mocked with AsyncMock.
No database, no HTTP, no I/O.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tradeforge.application.journal.service import JournalService, _compute_pnl_status
from tradeforge.application.journal.storage import StubStorage
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
    ATTACHMENT_MAX_BYTES,
    ATTACHMENT_PER_TRADE_MAX_BYTES,
    JournalEntryWrite,
    PnlStatus,
)
from tradeforge.infrastructure.repositories.journal_repo import JournalRepository
from tradeforge.infrastructure.repositories.auth_repo import AuditLogRepository

_USER = uuid.UUID("00000000-0000-0000-0000-000000000001")
_TRADE = uuid.UUID("00000000-0000-0000-0000-000000000002")
_ENTRY = uuid.UUID("00000000-0000-0000-0000-000000000003")
_ATT = uuid.UUID("00000000-0000-0000-0000-000000000004")
_NOW = datetime(2026, 8, 23, 10, 0, 0, tzinfo=timezone.utc)


def _make_service() -> tuple[JournalService, AsyncMock, AsyncMock]:
    journal_repo = AsyncMock(spec=JournalRepository)
    audit_repo = AsyncMock(spec=AuditLogRepository)
    svc = JournalService(journal_repo, audit_repo, storage=StubStorage())
    return svc, journal_repo, audit_repo


def _make_entry(**overrides):
    entry = MagicMock()
    entry.id = _ENTRY
    entry.trade_id = _TRADE
    entry.user_id = _USER
    entry.planned_entry = None
    entry.planned_stop = None
    entry.planned_target = None
    entry.planned_risk_amount = None
    entry.setup_name = None
    entry.notes = None
    entry.discipline_score = None
    entry.mistakes = None
    entry.emotion_before = None
    entry.emotion_during = None
    entry.emotion_after = None
    entry.created_at = _NOW
    entry.updated_at = _NOW
    for k, v in overrides.items():
        setattr(entry, k, v)
    return entry


def _make_attachment(**overrides):
    att = MagicMock()
    att.id = _ATT
    att.journal_entry_id = _ENTRY
    att.user_id = _USER
    att.trade_id = _TRADE
    att.s3_key = f"{_USER}/{_TRADE}/{_ATT}"
    att.filename = "chart.png"
    att.content_type = "image/png"
    att.byte_size = 1024
    att.capture_moment = "AT_ENTRY"
    att.caption = None
    att.status = "PENDING"
    att.confirmed_at = None
    att.created_at = datetime.now(timezone.utc)  # fresh by default so confirm tests don't expire
    for k, v in overrides.items():
        setattr(att, k, v)
    return att


# ---------------------------------------------------------------------------
# PnlStatus computation (pure function tests)
# ---------------------------------------------------------------------------


class TestPnlStatusComputation:
    def test_no_stop_gives_pending_stop(self):
        assert _compute_pnl_status(None, False) == PnlStatus.PENDING_STOP

    def test_stop_set_no_pnl_gives_pending_calculation(self):
        assert _compute_pnl_status(Decimal("500"), False) == PnlStatus.PENDING_CALCULATION

    def test_pnl_row_gives_available(self):
        assert _compute_pnl_status(Decimal("500"), True) == PnlStatus.AVAILABLE

    def test_pnl_row_available_even_without_stop(self):
        # trade_pnl row overrides PENDING_STOP
        assert _compute_pnl_status(None, True) == PnlStatus.AVAILABLE


# ---------------------------------------------------------------------------
# get_entry
# ---------------------------------------------------------------------------


class TestGetEntry:
    async def test_raises_when_no_entry(self):
        svc, repo, _ = _make_service()
        repo.get_entry.return_value = None

        with pytest.raises(JournalEntryNotFoundError):
            await svc.get_entry(_USER, _TRADE)

    async def test_returns_entry_with_pending_stop_status(self):
        svc, repo, _ = _make_service()
        entry = _make_entry()
        repo.get_entry.return_value = entry
        repo.has_pnl_row.return_value = False
        repo.list_confirmed_attachments.return_value = []

        view = await svc.get_entry(_USER, _TRADE)

        assert view.trade_id == _TRADE
        assert view.pnl.status == PnlStatus.PENDING_STOP
        assert view.attachments == []

    async def test_returns_available_when_pnl_row_exists(self):
        svc, repo, _ = _make_service()
        entry = _make_entry(planned_stop=Decimal("490"))
        repo.get_entry.return_value = entry
        repo.has_pnl_row.return_value = True
        repo.list_confirmed_attachments.return_value = []

        view = await svc.get_entry(_USER, _TRADE)

        assert view.pnl.status == PnlStatus.AVAILABLE

    async def test_mistakes_defaults_to_empty_list(self):
        svc, repo, _ = _make_service()
        entry = _make_entry(mistakes=None)
        repo.get_entry.return_value = entry
        repo.has_pnl_row.return_value = False
        repo.list_confirmed_attachments.return_value = []

        view = await svc.get_entry(_USER, _TRADE)

        assert view.mistakes == []


# ---------------------------------------------------------------------------
# upsert_entry
# ---------------------------------------------------------------------------


class TestUpsertEntry:
    async def test_raises_when_trade_not_owned(self):
        svc, repo, _ = _make_service()
        repo.get_trade_snapshot.return_value = None

        with pytest.raises(TradeNotFoundError):
            await svc.upsert_entry(_USER, _TRADE, JournalEntryWrite())

    async def test_creates_new_entry_when_none_exists(self):
        svc, repo, _ = _make_service()
        repo.get_trade_snapshot.return_value = (
            _TRADE, _USER, Decimal("500"), Decimal("100")
        )
        repo.get_entry.return_value = None
        new_entry = _make_entry()
        repo.create_entry.return_value = new_entry
        repo.has_pnl_row.return_value = False
        repo.list_confirmed_attachments.return_value = []

        await svc.upsert_entry(_USER, _TRADE, JournalEntryWrite(setup_name="Bull flag"))

        repo.create_entry.assert_called_once()
        repo.update_entry.assert_not_called()

    async def test_updates_existing_entry(self):
        svc, repo, _ = _make_service()
        repo.get_trade_snapshot.return_value = (
            _TRADE, _USER, Decimal("500"), Decimal("100")
        )
        existing = _make_entry(setup_name="Old name")
        # get_entry returns existing on first call, updated on second (re-fetch)
        updated = _make_entry(setup_name="New name")
        repo.get_entry.side_effect = [existing, updated]
        repo.has_pnl_row.return_value = False
        repo.list_confirmed_attachments.return_value = []

        await svc.upsert_entry(_USER, _TRADE, JournalEntryWrite(setup_name="New name"))

        repo.update_entry.assert_called_once()

    async def test_writes_audit_log_for_changed_fields(self):
        svc, repo, _ = _make_service()
        repo.get_trade_snapshot.return_value = (
            _TRADE, _USER, Decimal("500"), Decimal("100")
        )
        existing = _make_entry(setup_name="Old name", notes=None)
        updated = _make_entry(setup_name="New name", notes="Some note")
        repo.get_entry.side_effect = [existing, updated]
        repo.has_pnl_row.return_value = False
        repo.list_confirmed_attachments.return_value = []

        await svc.upsert_entry(
            _USER,
            _TRADE,
            JournalEntryWrite(setup_name="New name", notes="Some note", change_reason="Corrected"),
        )

        repo.append_audit_entries.assert_called_once()
        entries = repo.append_audit_entries.call_args.args[2]
        field_names = {e["field_name"] for e in entries}
        assert "setup_name" in field_names
        assert "notes" in field_names
        assert all(e["change_reason"] == "Corrected" for e in entries)

    async def test_no_audit_log_when_nothing_changed(self):
        svc, repo, _ = _make_service()
        repo.get_trade_snapshot.return_value = (
            _TRADE, _USER, Decimal("500"), Decimal("100")
        )
        existing = _make_entry(setup_name="Same name")
        same = _make_entry(setup_name="Same name")
        repo.get_entry.side_effect = [existing, same]
        repo.has_pnl_row.return_value = False
        repo.list_confirmed_attachments.return_value = []

        await svc.upsert_entry(_USER, _TRADE, JournalEntryWrite(setup_name="Same name"))

        repo.append_audit_entries.assert_not_called()

    async def test_computes_planned_risk_amount_when_stop_set(self):
        """abs(avg_entry - planned_stop) × total_entry_quantity = abs(500 - 490) × 100 = 1000"""
        svc, repo, _ = _make_service()
        repo.get_trade_snapshot.return_value = (
            _TRADE, _USER, Decimal("500"), Decimal("100")
        )
        repo.get_entry.return_value = None
        new_entry = _make_entry(planned_stop=Decimal("490"), planned_risk_amount=Decimal("1000"))
        repo.create_entry.return_value = new_entry
        repo.has_pnl_row.return_value = False
        repo.list_confirmed_attachments.return_value = []

        await svc.upsert_entry(
            _USER, _TRADE, JournalEntryWrite(planned_stop=Decimal("490"))
        )

        called_fields = repo.create_entry.call_args.args[2]
        assert called_fields["planned_risk_amount"] == Decimal("1000")

    async def test_clears_planned_risk_amount_when_stop_removed(self):
        svc, repo, _ = _make_service()
        repo.get_trade_snapshot.return_value = (
            _TRADE, _USER, Decimal("500"), Decimal("100")
        )
        repo.get_entry.return_value = None
        new_entry = _make_entry(planned_stop=None, planned_risk_amount=None)
        repo.create_entry.return_value = new_entry
        repo.has_pnl_row.return_value = False
        repo.list_confirmed_attachments.return_value = []

        await svc.upsert_entry(
            _USER, _TRADE, JournalEntryWrite(planned_stop=None)
        )

        called_fields = repo.create_entry.call_args.args[2]
        assert called_fields["planned_risk_amount"] is None

    async def test_planned_risk_amount_none_when_average_entry_missing(self):
        """If average_entry is None (trade still opening), planned_risk_amount stays None."""
        svc, repo, _ = _make_service()
        repo.get_trade_snapshot.return_value = (
            _TRADE, _USER, None, Decimal("100")  # average_entry is None
        )
        repo.get_entry.return_value = None
        new_entry = _make_entry(planned_stop=Decimal("490"), planned_risk_amount=None)
        repo.create_entry.return_value = new_entry
        repo.has_pnl_row.return_value = False
        repo.list_confirmed_attachments.return_value = []

        await svc.upsert_entry(
            _USER, _TRADE, JournalEntryWrite(planned_stop=Decimal("490"))
        )

        called_fields = repo.create_entry.call_args.args[2]
        assert called_fields["planned_risk_amount"] is None


# ---------------------------------------------------------------------------
# Attachment presign
# ---------------------------------------------------------------------------


class TestPresignAttachment:
    async def test_rejects_disallowed_content_type(self):
        svc, repo, audit_repo = _make_service()

        with pytest.raises(AttachmentContentTypeNotAllowedError):
            await svc.presign_attachment(
                _USER, _TRADE,
                filename="script.php",
                content_type="application/x-php",
                byte_size=1024,
                capture_moment="AT_ENTRY",
                caption=None,
            )

        # Service logs a security event even for rejected types (see test_rejected_type_logs_security_event)
        audit_repo.log.assert_called()

    async def test_rejects_svg(self):
        svc, repo, _ = _make_service()

        with pytest.raises(AttachmentContentTypeNotAllowedError):
            await svc.presign_attachment(
                _USER, _TRADE,
                filename="chart.svg",
                content_type="image/svg+xml",
                byte_size=1024,
                capture_moment="AT_ENTRY",
                caption=None,
            )

    async def test_rejects_file_exceeding_size_limit(self):
        svc, repo, _ = _make_service()

        with pytest.raises(AttachmentSizeLimitExceededError):
            await svc.presign_attachment(
                _USER, _TRADE,
                filename="huge.png",
                content_type="image/png",
                byte_size=ATTACHMENT_MAX_BYTES + 1,
                capture_moment="AT_ENTRY",
                caption=None,
            )

    async def test_rejects_zero_byte_file(self):
        svc, repo, _ = _make_service()

        with pytest.raises(AttachmentSizeLimitExceededError):
            await svc.presign_attachment(
                _USER, _TRADE,
                filename="empty.png",
                content_type="image/png",
                byte_size=0,
                capture_moment="AT_ENTRY",
                caption=None,
            )

    async def test_rejects_extension_mismatch(self):
        """filename.png with content_type image/jpeg should fail. (SR-ATT-005)"""
        svc, repo, _ = _make_service()

        with pytest.raises(AttachmentFilenameExtensionMismatchError):
            await svc.presign_attachment(
                _USER, _TRADE,
                filename="chart.png",
                content_type="image/jpeg",  # mismatch: .png file declared as JPEG
                byte_size=1024,
                capture_moment="AT_ENTRY",
                caption=None,
            )

    async def test_rejects_when_trade_not_owned(self):
        svc, repo, _ = _make_service()
        repo.get_trade_snapshot.return_value = None

        with pytest.raises(TradeNotFoundError):
            await svc.presign_attachment(
                _USER, _TRADE,
                filename="chart.png",
                content_type="image/png",
                byte_size=1024,
                capture_moment="AT_ENTRY",
                caption=None,
            )

    async def test_rejects_when_per_trade_quota_exceeded(self):
        svc, repo, _ = _make_service()
        repo.get_trade_snapshot.return_value = (
            _TRADE, _USER, Decimal("500"), Decimal("100")
        )
        # Return quota-exceeding value (1 byte less than the new file would push it over)
        repo.sum_confirmed_bytes_for_trade.return_value = ATTACHMENT_PER_TRADE_MAX_BYTES

        with pytest.raises(AttachmentStorageQuotaExceededError):
            await svc.presign_attachment(
                _USER, _TRADE,
                filename="chart.png",
                content_type="image/png",
                byte_size=1024,
                capture_moment="AT_ENTRY",
                caption=None,
            )

    async def test_happy_path_returns_presign_result(self):
        svc, repo, _ = _make_service()
        repo.get_trade_snapshot.return_value = (
            _TRADE, _USER, Decimal("500"), Decimal("100")
        )
        repo.sum_confirmed_bytes_for_trade.return_value = 0
        repo.sum_confirmed_bytes_for_user.return_value = 0
        existing_entry = _make_entry()
        repo.get_entry.return_value = existing_entry
        repo.create_attachment.return_value = _make_attachment()

        result = await svc.presign_attachment(
            _USER, _TRADE,
            filename="chart.png",
            content_type="image/png",
            byte_size=2048,
            capture_moment="AT_ENTRY",
            caption="Entry chart",
        )

        assert result.expires_in_seconds == 900
        assert "stub-s3.local" in result.upload_url
        repo.create_attachment.assert_called_once()

    async def test_s3_key_contains_user_and_trade_ids(self):
        """S3 key must be {user_id}/{trade_id}/{attachment_id} (SR-ATT-005)."""
        svc, repo, _ = _make_service()
        repo.get_trade_snapshot.return_value = (
            _TRADE, _USER, Decimal("500"), Decimal("100")
        )
        repo.sum_confirmed_bytes_for_trade.return_value = 0
        repo.sum_confirmed_bytes_for_user.return_value = 0
        existing_entry = _make_entry()
        repo.get_entry.return_value = existing_entry
        repo.create_attachment.return_value = _make_attachment()

        result = await svc.presign_attachment(
            _USER, _TRADE,
            filename="entry.jpeg",
            content_type="image/jpeg",
            byte_size=512,
            capture_moment="AT_ENTRY",
            caption=None,
        )

        # Key format: {user_id}/{trade_id}/{new_uuid}
        parts = result.s3_key.split("/")
        assert parts[0] == str(_USER)
        assert parts[1] == str(_TRADE)
        # Third segment is the server-generated attachment_id
        uuid.UUID(parts[2])  # must be a valid UUID — raises ValueError if not


# ---------------------------------------------------------------------------
# Attachment confirm
# ---------------------------------------------------------------------------


class TestConfirmAttachment:
    async def test_raises_when_pending_not_found(self):
        svc, repo, _ = _make_service()
        repo.get_pending_attachment.return_value = None

        with pytest.raises(AttachmentNotFoundError):
            await svc.confirm_attachment(_USER, _ATT)

    async def test_raises_when_pending_is_expired(self):
        svc, repo, _ = _make_service()
        old_created = datetime.now(timezone.utc) - timedelta(minutes=31)
        att = _make_attachment(created_at=old_created, status="PENDING")
        repo.get_pending_attachment.return_value = att

        with pytest.raises(AttachmentExpiredError):
            await svc.confirm_attachment(_USER, _ATT)

        repo.update_attachment_status.assert_called_once_with(_ATT, "EXPIRED")

    async def test_marks_confirmed_on_success(self):
        svc, repo, _ = _make_service()
        fresh_att = _make_attachment(status="PENDING")
        repo.get_pending_attachment.return_value = fresh_att

        view = await svc.confirm_attachment(_USER, _ATT)

        repo.update_attachment_status.assert_called_once()
        call_args = repo.update_attachment_status.call_args
        assert call_args.args[0] == _ATT
        assert call_args.args[1] == "CONFIRMED"
        assert view.status == "CONFIRMED"

    async def test_returns_download_url_on_confirm(self):
        svc, repo, _ = _make_service()
        fresh_att = _make_attachment(status="PENDING")
        repo.get_pending_attachment.return_value = fresh_att

        view = await svc.confirm_attachment(_USER, _ATT)

        assert view.download_url is not None
        assert "stub-s3.local" in view.download_url


# ---------------------------------------------------------------------------
# Attachment delete
# ---------------------------------------------------------------------------


class TestDeleteAttachment:
    async def test_raises_when_not_found(self):
        svc, repo, _ = _make_service()
        repo.get_confirmed_attachment.return_value = None

        with pytest.raises(AttachmentNotFoundError):
            await svc.delete_attachment(_USER, _ATT)

    async def test_soft_deletes_confirmed_attachment(self):
        svc, repo, _ = _make_service()
        att = _make_attachment(status="CONFIRMED")
        repo.get_confirmed_attachment.return_value = att

        await svc.delete_attachment(_USER, _ATT)

        repo.soft_delete_attachment.assert_called_once_with(_ATT)


# ---------------------------------------------------------------------------
# Audit security events
# ---------------------------------------------------------------------------


class TestAuditSecurityEvents:
    async def test_presign_logs_security_event(self):
        svc, repo, audit_repo = _make_service()
        repo.get_trade_snapshot.return_value = (
            _TRADE, _USER, Decimal("500"), Decimal("100")
        )
        repo.sum_confirmed_bytes_for_trade.return_value = 0
        repo.sum_confirmed_bytes_for_user.return_value = 0
        existing_entry = _make_entry()
        repo.get_entry.return_value = existing_entry
        repo.create_attachment.return_value = _make_attachment()

        await svc.presign_attachment(
            _USER, _TRADE,
            filename="chart.png",
            content_type="image/png",
            byte_size=1024,
            capture_moment="AT_ENTRY",
            caption=None,
        )

        audit_repo.log.assert_called()
        call_kwargs = audit_repo.log.call_args
        assert call_kwargs.args[0] == "ATTACHMENT_PRESIGN_REQUESTED"

    async def test_rejected_type_logs_security_event(self):
        svc, repo, audit_repo = _make_service()

        with pytest.raises(AttachmentContentTypeNotAllowedError):
            await svc.presign_attachment(
                _USER, _TRADE,
                filename="script.php",
                content_type="application/x-php",
                byte_size=1024,
                capture_moment="AT_ENTRY",
                caption=None,
            )

        audit_repo.log.assert_called()
        assert audit_repo.log.call_args.args[0] == "ATTACHMENT_REJECTED_TYPE"

    async def test_confirm_logs_confirmed_event(self):
        svc, repo, audit_repo = _make_service()
        fresh_att = _make_attachment(status="PENDING")
        repo.get_pending_attachment.return_value = fresh_att

        await svc.confirm_attachment(_USER, _ATT)

        audit_repo.log.assert_called()
        assert audit_repo.log.call_args.args[0] == "ATTACHMENT_CONFIRMED"
