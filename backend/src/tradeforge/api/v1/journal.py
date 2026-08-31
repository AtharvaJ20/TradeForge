"""Journal REST API — v1 routes.

Routes:
  GET    /v1/journal/trades/{trade_id}                              — get journal entry
  PUT    /v1/journal/trades/{trade_id}                              — upsert journal entry
  GET    /v1/journal/trades/{trade_id}/audit                        — audit history
  POST   /v1/journal/trades/{trade_id}/attachments/presign          — request upload URL
  POST   /v1/journal/trades/{trade_id}/attachments/{att_id}/confirm — confirm upload
  DELETE /v1/journal/trades/{trade_id}/attachments/{att_id}         — soft-delete

Security: all routes require an authenticated session (get_current_user_id).
          user_id is sourced from the session — never from request body or URL params.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.api.v1.deps import get_client_ip, get_current_user_id
from tradeforge.application.journal.service import JournalService
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
    CaptureMoment,
    EmotionType,
    MistakeType,
)
from tradeforge.infrastructure.db import get_db
from tradeforge.infrastructure.repositories.auth_repo import AuditLogRepository
from tradeforge.infrastructure.repositories.journal_repo import JournalRepository

router = APIRouter(prefix="/journal", tags=["journal"])


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------


async def get_journal_service(
    db: AsyncSession = Depends(get_db),
) -> JournalService:
    return JournalService(
        journal_repo=JournalRepository(db),
        audit_repo=AuditLogRepository(db),
        storage=StubStorage(),
    )


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------


class JournalEntryRequest(BaseModel):
    planned_entry: Decimal | None = Field(None, gt=0)
    planned_stop: Decimal | None = Field(None, gt=0)
    planned_target: Decimal | None = Field(None, gt=0)
    setup_name: str | None = Field(None, max_length=100)
    notes: str | None = None
    discipline_score: int | None = Field(None, ge=1, le=10)
    mistakes: list[str] | None = None
    emotion_before: str | None = None
    emotion_during: str | None = None
    emotion_after: str | None = None
    change_reason: str | None = Field(None, max_length=500)

    model_config = {"extra": "forbid"}

    @field_validator("planned_entry", "planned_stop", "planned_target", mode="before")
    @classmethod
    def price_must_be_positive(cls, v: object) -> object:
        # None is always valid (optional field); positivity enforced by Field(gt=0) above.
        return v

    @field_validator("emotion_before", "emotion_during", "emotion_after", mode="after")
    @classmethod
    def emotion_must_be_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in EmotionType.__members__:
            allowed = ", ".join(EmotionType.__members__)
            raise ValueError(f"Invalid emotion value '{v}'. Allowed: {allowed}")
        return v

    @field_validator("mistakes", mode="after")
    @classmethod
    def mistakes_must_be_valid(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            invalid = [m for m in v if m not in MistakeType.__members__]
            if invalid:
                allowed = ", ".join(MistakeType.__members__)
                raise ValueError(
                    f"Invalid mistake value(s): {invalid}. Allowed: {allowed}"
                )
        return v


class PnlSnapshotOut(BaseModel):
    status: str
    net_pnl: Decimal | None = None
    gross_pnl: Decimal | None = None
    total_charges: Decimal | None = None
    r_multiple: Decimal | None = None


class AttachmentOut(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    byte_size: int
    capture_moment: str
    caption: str | None
    status: str
    download_url: str | None
    confirmed_at: str | None
    created_at: str


class JournalEntryOut(BaseModel):
    id: uuid.UUID
    trade_id: uuid.UUID
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
    pnl: PnlSnapshotOut
    attachments: list[AttachmentOut]
    created_at: str
    updated_at: str


class PresignRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str
    byte_size: int = Field(..., gt=0)
    capture_moment: str
    caption: str | None = Field(None, max_length=500)

    model_config = {"extra": "forbid"}

    @field_validator("capture_moment", mode="after")
    @classmethod
    def capture_moment_must_be_valid(cls, v: str) -> str:
        if v not in CaptureMoment.__members__:
            allowed = ", ".join(CaptureMoment.__members__)
            raise ValueError(f"Invalid capture_moment '{v}'. Allowed: {allowed}")
        return v


class PresignOut(BaseModel):
    attachment_id: uuid.UUID
    upload_url: str
    s3_key: str
    expires_in_seconds: int


class AttachmentConfirmOut(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    byte_size: int
    status: str
    download_url: str | None
    confirmed_at: str | None


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _dt_str(dt: Any) -> str:
    return dt.isoformat() if dt is not None else ""


def _attachment_out(a: Any) -> AttachmentOut:
    return AttachmentOut(
        id=a.id,
        filename=a.filename,
        content_type=a.content_type,
        byte_size=a.byte_size,
        capture_moment=a.capture_moment,
        caption=a.caption,
        status=a.status,
        download_url=a.download_url,
        confirmed_at=_dt_str(a.confirmed_at) if a.confirmed_at else None,
        created_at=_dt_str(a.created_at),
    )


def _entry_out(view: Any) -> JournalEntryOut:
    return JournalEntryOut(
        id=view.id,
        trade_id=view.trade_id,
        planned_entry=view.planned_entry,
        planned_stop=view.planned_stop,
        planned_target=view.planned_target,
        planned_risk_amount=view.planned_risk_amount,
        setup_name=view.setup_name,
        notes=view.notes,
        discipline_score=view.discipline_score,
        mistakes=view.mistakes,
        emotion_before=view.emotion_before,
        emotion_during=view.emotion_during,
        emotion_after=view.emotion_after,
        pnl=PnlSnapshotOut(
            status=view.pnl.status,
            net_pnl=view.pnl.net_pnl,
            gross_pnl=view.pnl.gross_pnl,
            total_charges=view.pnl.total_charges,
            r_multiple=view.pnl.r_multiple,
        ),
        attachments=[_attachment_out(a) for a in view.attachments],
        created_at=_dt_str(view.created_at),
        updated_at=_dt_str(view.updated_at),
    )


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def _handle_journal_error(exc: Exception) -> JSONResponse:
    if isinstance(exc, (JournalEntryNotFoundError, TradeNotFoundError, AttachmentNotFoundError)):
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    if isinstance(exc, (
        AttachmentContentTypeNotAllowedError,
        AttachmentSizeLimitExceededError,
        AttachmentStorageQuotaExceededError,
        AttachmentFilenameExtensionMismatchError,
        AttachmentExpiredError,
    )):
        return JSONResponse(status_code=422, content={"detail": str(exc)})
    raise exc  # re-raise unexpected errors


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/trades/{trade_id}", response_model=JournalEntryOut)
async def get_journal_entry(
    trade_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    svc: JournalService = Depends(get_journal_service),
) -> Any:
    try:
        view = await svc.get_entry(user_id, trade_id)
    except (JournalEntryNotFoundError, TradeNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _entry_out(view)


@router.put("/trades/{trade_id}", response_model=JournalEntryOut)
async def upsert_journal_entry(
    trade_id: uuid.UUID,
    body: JournalEntryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
    svc: JournalService = Depends(get_journal_service),
) -> Any:
    from tradeforge.domain.journal.types import JournalEntryWrite

    data = JournalEntryWrite(
        planned_entry=body.planned_entry,
        planned_stop=body.planned_stop,
        planned_target=body.planned_target,
        setup_name=body.setup_name,
        notes=body.notes,
        discipline_score=body.discipline_score,
        mistakes=body.mistakes,
        emotion_before=body.emotion_before,
        emotion_during=body.emotion_during,
        emotion_after=body.emotion_after,
        change_reason=body.change_reason,
    )
    try:
        view = await svc.upsert_entry(
            user_id, trade_id, data, ip_address=get_client_ip(request)
        )
    except TradeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await db.commit()
    return _entry_out(view)


@router.get("/trades/{trade_id}/audit")
async def get_audit_history(
    trade_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    svc: JournalService = Depends(get_journal_service),
) -> Any:
    try:
        entries = await svc.get_audit_history(user_id, trade_id)
    except JournalEntryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return [
        {
            "id": str(e.id),
            "field_name": e.field_name,
            "previous_value": e.previous_value,
            "new_value": e.new_value,
            "change_reason": e.change_reason,
            "changed_at": _dt_str(e.changed_at),
        }
        for e in entries
    ]


@router.post("/trades/{trade_id}/attachments/presign", response_model=PresignOut, status_code=201)
async def presign_attachment(
    trade_id: uuid.UUID,
    body: PresignRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
    svc: JournalService = Depends(get_journal_service),
) -> Any:
    try:
        result = await svc.presign_attachment(
            user_id=user_id,
            trade_id=trade_id,
            filename=body.filename,
            content_type=body.content_type,
            byte_size=body.byte_size,
            capture_moment=body.capture_moment,
            caption=body.caption,
            ip_address=get_client_ip(request),
        )
    except (TradeNotFoundError, JournalEntryNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (
        AttachmentContentTypeNotAllowedError,
        AttachmentSizeLimitExceededError,
        AttachmentStorageQuotaExceededError,
        AttachmentFilenameExtensionMismatchError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await db.commit()
    return PresignOut(
        attachment_id=result.attachment_id,
        upload_url=result.upload_url,
        s3_key=result.s3_key,
        expires_in_seconds=result.expires_in_seconds,
    )


@router.post(
    "/trades/{trade_id}/attachments/{attachment_id}/confirm",
    response_model=AttachmentConfirmOut,
)
async def confirm_attachment(
    trade_id: uuid.UUID,
    attachment_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
    svc: JournalService = Depends(get_journal_service),
) -> Any:
    try:
        view = await svc.confirm_attachment(
            user_id=user_id,
            attachment_id=attachment_id,
            ip_address=get_client_ip(request),
        )
    except AttachmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except AttachmentExpiredError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await db.commit()
    return AttachmentConfirmOut(
        id=view.id,
        filename=view.filename,
        content_type=view.content_type,
        byte_size=view.byte_size,
        status=view.status,
        download_url=view.download_url,
        confirmed_at=_dt_str(view.confirmed_at) if view.confirmed_at else None,
    )


@router.delete(
    "/trades/{trade_id}/attachments/{attachment_id}",
    status_code=204,
)
async def delete_attachment(
    trade_id: uuid.UUID,
    attachment_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
    svc: JournalService = Depends(get_journal_service),
) -> None:
    try:
        await svc.delete_attachment(
            user_id=user_id,
            attachment_id=attachment_id,
            ip_address=get_client_ip(request),
        )
    except AttachmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await db.commit()
