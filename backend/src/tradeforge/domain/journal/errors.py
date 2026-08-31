"""Typed domain errors for the journal layer."""

from __future__ import annotations

import uuid


class JournalDomainError(Exception):
    """Base class for all journal domain errors."""


class TradeNotFoundError(JournalDomainError):
    def __init__(self, trade_id: uuid.UUID) -> None:
        self.trade_id = trade_id
        super().__init__(f"Trade {trade_id} not found or not owned by this user.")


class JournalEntryNotFoundError(JournalDomainError):
    def __init__(self, trade_id: uuid.UUID) -> None:
        self.trade_id = trade_id
        super().__init__(f"No journal entry found for trade {trade_id}.")


class AttachmentNotFoundError(JournalDomainError):
    def __init__(self, attachment_id: uuid.UUID) -> None:
        self.attachment_id = attachment_id
        super().__init__(f"Attachment {attachment_id} not found or not owned by this user.")


class AttachmentExpiredError(JournalDomainError):
    def __init__(self, attachment_id: uuid.UUID) -> None:
        self.attachment_id = attachment_id
        super().__init__(
            f"Attachment {attachment_id} upload window has expired. Request a new presign URL."
        )


class AttachmentContentTypeNotAllowedError(JournalDomainError):
    def __init__(self, content_type: str) -> None:
        self.content_type = content_type
        super().__init__(
            f"Content type {content_type!r} is not permitted. "
            "Allowed: image/jpeg, image/png, image/webp, image/gif."
        )


class AttachmentSizeLimitExceededError(JournalDomainError):
    def __init__(self, byte_size: int, limit: int) -> None:
        self.byte_size = byte_size
        self.limit = limit
        super().__init__(
            f"File size {byte_size:,} bytes exceeds the per-file limit of {limit:,} bytes."
        )


class AttachmentStorageQuotaExceededError(JournalDomainError):
    def __init__(self, scope: str) -> None:
        self.scope = scope
        super().__init__(f"Attachment storage limit reached for {scope}.")


class AttachmentFilenameExtensionMismatchError(JournalDomainError):
    def __init__(self, filename: str, content_type: str) -> None:
        self.filename = filename
        self.content_type = content_type
        super().__init__(
            f"Filename {filename!r} extension does not match declared content type {content_type!r}."
        )
