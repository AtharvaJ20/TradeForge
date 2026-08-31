"""Pure domain types for the journal annotation layer.

No I/O. No SQLAlchemy. No FastAPI. stdlib only.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PnlStatus(StrEnum):
    """Three-state P&L availability indicator.

    PENDING_STOP        — planned_stop not yet set; R-multiple impossible.
    PENDING_CALCULATION — planned_stop is set; waiting for Step 10 engine.
    AVAILABLE           — trade_pnl row exists; full P&L available.
    """

    PENDING_STOP = "PENDING_STOP"
    PENDING_CALCULATION = "PENDING_CALCULATION"
    AVAILABLE = "AVAILABLE"


class AttachmentStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


class CaptureMoment(StrEnum):
    AT_ENTRY = "AT_ENTRY"
    DURING_TRADE = "DURING_TRADE"
    AT_EXIT = "AT_EXIT"
    POST_REVIEW = "POST_REVIEW"


class MistakeType(StrEnum):
    FOMO_ENTRY = "FOMO_ENTRY"
    FOMO_EXIT = "FOMO_EXIT"
    OVERSIZED_POSITION = "OVERSIZED_POSITION"
    NO_STOP_DEFINED = "NO_STOP_DEFINED"
    MOVED_STOP_WIDER = "MOVED_STOP_WIDER"
    CUT_WINNER_EARLY = "CUT_WINNER_EARLY"
    HELD_THROUGH_STOP = "HELD_THROUGH_STOP"
    REVENGE_TRADE = "REVENGE_TRADE"
    AVERAGING_DOWN = "AVERAGING_DOWN"
    ENTRY_TOO_EARLY = "ENTRY_TOO_EARLY"
    ENTRY_TOO_LATE = "ENTRY_TOO_LATE"
    IGNORED_SIGNAL = "IGNORED_SIGNAL"
    DISTRACTED = "DISTRACTED"


class EmotionType(StrEnum):
    CALM = "CALM"
    CONFIDENT = "CONFIDENT"
    ANXIOUS = "ANXIOUS"
    FEARFUL = "FEARFUL"
    GREEDY = "GREEDY"
    FRUSTRATED = "FRUSTRATED"
    EUPHORIC = "EUPHORIC"
    BORED = "BORED"
    DISTRACTED = "DISTRACTED"
    NEUTRAL = "NEUTRAL"


# ---------------------------------------------------------------------------
# Attachment security constants (SR-ATT-001, SR-ATT-002)
# ---------------------------------------------------------------------------

ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/gif"}
)

CONTENT_TYPE_TO_EXTENSIONS: dict[str, frozenset[str]] = {
    "image/jpeg": frozenset({".jpg", ".jpeg"}),
    "image/png": frozenset({".png"}),
    "image/webp": frozenset({".webp"}),
    "image/gif": frozenset({".gif"}),
}

ATTACHMENT_MAX_BYTES: int = 15 * 1024 * 1024        # 15 MB per file (SR-ATT-002)
ATTACHMENT_PER_TRADE_MAX_BYTES: int = 75 * 1024 * 1024  # 75 MB per trade
ATTACHMENT_PER_USER_MAX_BYTES: int = 2 * 1024 * 1024 * 1024  # 2 GB per user
PRESIGN_UPLOAD_TTL_SECONDS: int = 900   # 15 min upload window (SR-ATT-007)
PRESIGN_DOWNLOAD_TTL_SECONDS: int = 3600  # 1 hr download URL TTL (SR-ATT-007)
PENDING_EXPIRY_MINUTES: int = 30  # PENDING rows expire after 30 min (SR-ATT-010)

# ---------------------------------------------------------------------------
# Filename sanitisation helpers (SR-ATT-005)
# ---------------------------------------------------------------------------

_UNSAFE_CHARS = re.compile(r"[^\w\s\-.]", re.UNICODE)
_PATH_SEPARATORS = re.compile(r"[/\\:]")


def sanitize_filename(filename: str) -> str:
    """Strip path traversal sequences and unsafe characters; limit to 255 chars."""
    name = _PATH_SEPARATORS.sub("", filename)
    name = _UNSAFE_CHARS.sub("", name)
    name = " ".join(name.split())  # collapse whitespace
    return name[:255]


def filename_extension_matches(filename: str, content_type: str) -> bool:
    """Return True iff filename extension is valid for the declared content_type."""
    lower = filename.lower()
    allowed = CONTENT_TYPE_TO_EXTENSIONS.get(content_type, frozenset())
    return any(lower.endswith(ext) for ext in allowed)


def build_s3_key(user_id: uuid.UUID, trade_id: uuid.UUID, attachment_id: uuid.UUID) -> str:
    """Return the canonical S3 object key. Server-generated; client never supplies this."""
    return f"{user_id}/{trade_id}/{attachment_id}"


# ---------------------------------------------------------------------------
# Dataclasses — service input/output contracts
# ---------------------------------------------------------------------------


@dataclass
class TradeSnapshotForJournal:
    """Minimal trade fields needed by JournalService."""

    id: uuid.UUID
    user_id: uuid.UUID
    average_entry: Decimal | None
    total_entry_quantity: Decimal


@dataclass
class JournalEntryWrite:
    """Write model — the set of fields a user may create or update."""

    planned_entry: Decimal | None = None
    planned_stop: Decimal | None = None
    planned_target: Decimal | None = None
    setup_name: str | None = None
    notes: str | None = None
    discipline_score: int | None = None
    mistakes: list[str] | None = None
    emotion_before: str | None = None
    emotion_during: str | None = None
    emotion_after: str | None = None
    change_reason: str | None = None  # recorded in audit log


@dataclass
class PnlSnapshot:
    status: PnlStatus
    net_pnl: Decimal | None = None
    gross_pnl: Decimal | None = None
    total_charges: Decimal | None = None
    r_multiple: Decimal | None = None


@dataclass
class AttachmentView:
    id: uuid.UUID
    filename: str
    content_type: str
    byte_size: int
    capture_moment: str
    caption: str | None
    status: str
    download_url: str | None
    confirmed_at: datetime | None
    created_at: datetime


@dataclass
class AuditEntry:
    id: uuid.UUID
    field_name: str
    previous_value: str | None
    new_value: str | None
    change_reason: str | None
    changed_at: datetime


@dataclass
class JournalEntryView:
    id: uuid.UUID
    trade_id: uuid.UUID
    user_id: uuid.UUID
    planned_entry: Decimal | None
    planned_stop: Decimal | None
    planned_target: Decimal | None
    planned_risk_amount: Decimal | None
    setup_name: str | None
    notes: str | None
    discipline_score: int | None
    mistakes: list[str]
    emotion_before: str | None
    emotion_during: str | None
    emotion_after: str | None
    pnl: PnlSnapshot
    attachments: list[AttachmentView]
    created_at: datetime
    updated_at: datetime


@dataclass
class PresignResult:
    attachment_id: uuid.UUID
    upload_url: str
    s3_key: str
    expires_in_seconds: int
