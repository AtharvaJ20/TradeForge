"""Trades REST API — v1 routes (Step 16: Manual Trade Entry).

Routes:
  POST   /v1/trades                     — create a new trade from manual fills
  POST   /v1/trades/{trade_id}/fills    — add a fill to an existing trade
  DELETE /v1/trades/{trade_id}          — soft-delete a manually entered trade

Security: all routes require an authenticated session (get_current_user_id).
          user_id is sourced from the session — never from request body or URL params.

Router is thin: parse input, call TradeService, serialize output. No domain logic here.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.api.v1.deps import get_current_user_id
from tradeforge.application.trade_service import (
    FillTimestampBeforeTradeOpenError,
    InstrumentNotFoundError,
    PlannedStopWrongSideError,
    ReconstructionFailedError,
    TradeAlreadyClosedError,
    TradeNotFoundError,
    TradeNotManualError,
    TradeNotOwnedError,
    TradeService,
)
from tradeforge.application.trading_account_service import TradingAccountService
from tradeforge.domain.import_domain.errors import AccountNotFoundError
from tradeforge.infrastructure.db import get_db
from tradeforge.infrastructure.models.trade_domain import Instrument, Trade
from tradeforge.infrastructure.models.trade_pnl import TradePnl
from tradeforge.infrastructure.repositories.trading_account_repo import TradingAccountRepository

router = APIRouter(prefix="/trades", tags=["trades"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class FillInput(BaseModel):
    model_config = {"extra": "forbid"}

    side: Literal["BUY", "SELL"]
    quantity: Decimal = Field(..., gt=0)
    price: Decimal = Field(..., gt=0)
    fill_timestamp: datetime  # must be timezone-aware (UTC-offset accepted; stored as UTC)


class InstrumentInput(BaseModel):
    model_config = {"extra": "forbid"}

    symbol: str = Field(..., min_length=1, max_length=50, description="Uppercase NSE/BSE symbol")
    exchange_segment: Literal["NSE_EQ", "NSE_FO", "BSE_EQ"]
    instrument_type: Literal["EQ", "FUT", "CE", "PE"]
    expiry_date: date | None = None  # required for FUT, CE, PE
    strike_price: Decimal | None = None  # required for CE, PE; gt=0


class CreateTradeRequest(BaseModel):
    model_config = {"extra": "forbid"}

    account_id: uuid.UUID
    instrument: InstrumentInput
    product_type: Literal["MIS", "CNC", "NRML"]
    fills: list[FillInput] = Field(..., min_length=1, max_length=20)
    planned_stop: Decimal | None = Field(default=None, gt=0)
    planned_target: Decimal | None = Field(default=None, gt=0)


class AddFillRequest(BaseModel):
    model_config = {"extra": "forbid"}

    fill: FillInput


class TradeOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    account_id: uuid.UUID | None
    instrument_id: uuid.UUID
    trade_type: str
    direction: str
    status: str
    trade_date: date
    first_fill_at: datetime
    last_fill_at: datetime | None
    total_entry_quantity: Decimal
    total_exit_quantity: Decimal
    net_position: Decimal
    average_entry: Decimal | None
    average_exit: Decimal | None
    planned_stop: Decimal | None
    planned_target: Decimal | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


class TradeListItemOut(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID | None
    symbol: str
    instrument_type: str
    direction: str
    status: str
    trade_date: date
    last_fill_at: datetime | None
    net_pnl: Decimal | None
    r_multiple: Decimal | None


# ---------------------------------------------------------------------------
# Sort whitelist (D-18-1: no string interpolation into ORDER BY)
# ---------------------------------------------------------------------------

_SORT_COLUMNS = {
    "last_fill_at": Trade.last_fill_at,
    "trade_date": Trade.trade_date,
    "net_pnl": TradePnl.net_pnl,
    "r_multiple": TradePnl.r_multiple,
}

_VALID_STATUSES = frozenset({"OPEN", "CLOSED", "PARTIAL"})


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_create_request(body: CreateTradeRequest) -> None:
    """Apply request-level validation before calling any service."""

    # All fill_timestamps must be timezone-aware.
    for fill in body.fills:
        if fill.fill_timestamp.tzinfo is None:
            raise HTTPException(
                status_code=422,
                detail="FILL_TIMESTAMP_NOT_TZ_AWARE",
            )

    # Fills must be in strictly ascending timestamp order.
    for i in range(1, len(body.fills)):
        if body.fills[i].fill_timestamp <= body.fills[i - 1].fill_timestamp:
            raise HTTPException(
                status_code=422,
                detail="FILLS_NOT_CHRONOLOGICAL",
            )

    instr = body.instrument

    # expiry_date required for FUT, CE, PE.
    if instr.instrument_type in ("FUT", "CE", "PE") and instr.expiry_date is None:
        raise HTTPException(status_code=422, detail="EXPIRY_DATE_REQUIRED")

    # strike_price required for CE, PE.
    if instr.instrument_type in ("CE", "PE") and instr.strike_price is None:
        raise HTTPException(status_code=422, detail="STRIKE_PRICE_REQUIRED")

    # product_type valid for instrument_type (D1 — Ganesha).
    # EQ → MIS or CNC only (not NRML).
    if instr.instrument_type == "EQ" and body.product_type == "NRML":
        raise HTTPException(status_code=422, detail="INVALID_PRODUCT_TYPE_FOR_INSTRUMENT")

    # FUT, CE, PE → MIS or NRML only (not CNC).
    if instr.instrument_type in ("FUT", "CE", "PE") and body.product_type == "CNC":
        raise HTTPException(status_code=422, detail="INVALID_PRODUCT_TYPE_FOR_INSTRUMENT")


def _validate_add_fill_request(fill: FillInput) -> None:
    """Validate a single fill input before calling service."""
    if fill.fill_timestamp.tzinfo is None:
        raise HTTPException(
            status_code=422,
            detail="FILL_TIMESTAMP_NOT_TZ_AWARE",
        )


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------


def get_trade_service(db: AsyncSession = Depends(get_db)) -> TradeService:
    return TradeService(session=db)


def get_account_service() -> TradingAccountService:
    return TradingAccountService(account_repo=TradingAccountRepository())


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=list[TradeListItemOut])
async def list_trades(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    _svc: TradingAccountService = Depends(get_account_service),
    status: str | None = Query(default=None),
    account_id: uuid.UUID | None = Query(default=None),
    sort_by: str = Query(default="last_fill_at"),
    sort_dir: str = Query(default="desc"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[TradeListItemOut]:
    if status is not None and status not in _VALID_STATUSES:
        raise HTTPException(status_code=422, detail="INVALID_STATUS")

    sort_col = _SORT_COLUMNS.get(sort_by, Trade.last_fill_at)
    ordered_col = sort_col.asc() if sort_dir == "asc" else sort_col.desc()

    stmt = (
        select(
            Trade.id,
            Trade.account_id,
            Trade.direction,
            Trade.status,
            Trade.trade_date,
            Trade.last_fill_at,
            Instrument.symbol,
            Instrument.instrument_type,
            TradePnl.net_pnl,
            TradePnl.r_multiple,
        )
        .select_from(Trade)
        .join(Instrument, Instrument.id == Trade.instrument_id)
        .outerjoin(TradePnl, TradePnl.trade_id == Trade.id)
        .where(Trade.user_id == user_id, Trade.is_deleted.is_(False))
    )
    if status is not None:
        stmt = stmt.where(Trade.status == status)
    if account_id is not None:
        stmt = stmt.where(Trade.account_id == account_id)

    stmt = stmt.order_by(ordered_col).limit(limit).offset(offset)

    result = await db.execute(stmt)
    rows = result.all()

    return [
        TradeListItemOut(
            id=row.id,
            account_id=row.account_id,
            symbol=row.symbol,
            instrument_type=row.instrument_type,
            direction=row.direction,
            status=row.status,
            trade_date=row.trade_date,
            last_fill_at=row.last_fill_at,
            net_pnl=row.net_pnl,
            r_multiple=row.r_multiple,
        )
        for row in rows
    ]


@router.post("", response_model=TradeOut, status_code=201)
async def create_trade(
    body: CreateTradeRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    svc: TradeService = Depends(get_trade_service),
    db: AsyncSession = Depends(get_db),
) -> TradeOut:
    """Create a new trade from manual fills.

    Returns 201 with TradeOut for the affected trade (the trade created or last
    operated on by reconstruction — for multi-cycle BUY→SELL→BUY the response
    contains the second OPEN trade, not the closed first trade).
    """
    _validate_create_request(body)

    try:
        trade = await svc.create_trade(
            user_id=user_id,
            account_id=body.account_id,
            instrument_symbol=body.instrument.symbol.upper(),
            exchange_segment=body.instrument.exchange_segment,
            instrument_type=body.instrument.instrument_type,
            product_type=body.product_type,
            fills=[
                {
                    "side": f.side,
                    "quantity": f.quantity,
                    "price": f.price,
                    "fill_timestamp": f.fill_timestamp,
                }
                for f in body.fills
            ],
            expiry_date=body.instrument.expiry_date,
            strike_price=body.instrument.strike_price,
            planned_stop=body.planned_stop,
            planned_target=body.planned_target,
        )
        await db.commit()
    except AccountNotFoundError:
        raise HTTPException(status_code=404, detail="ACCOUNT_NOT_FOUND")
    except InstrumentNotFoundError:
        raise HTTPException(status_code=422, detail="INSTRUMENT_NOT_FOUND")
    except PlannedStopWrongSideError:
        raise HTTPException(status_code=422, detail="PLANNED_STOP_WRONG_SIDE")
    except ReconstructionFailedError as exc:
        raise HTTPException(status_code=422, detail=f"RECONSTRUCTION_FAILED: {exc.detail}")

    return TradeOut.model_validate(trade)


@router.post("/{trade_id}/fills", response_model=TradeOut, status_code=200)
async def add_fill(
    trade_id: uuid.UUID,
    body: AddFillRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    svc: TradeService = Depends(get_trade_service),
    db: AsyncSession = Depends(get_db),
) -> TradeOut:
    """Add a fill to an existing OPEN or PARTIAL trade.

    Permits adding manual fills to trades of any origin (D3 — mixed provenance).
    The primary use case is gap-repair: adding a missing fill to a CSV-imported
    trade where the broker export was incomplete.

    Ownership verification uses a direct query on trading_accounts without
    checking account status (REQ-6). A trade on a deactivated account can still
    receive fills — the account's administrative status does not mean the
    position was closed.
    """
    _validate_add_fill_request(body.fill)

    try:
        trade = await svc.add_fill(
            user_id=user_id,
            trade_id=trade_id,
            fill_side=body.fill.side,
            fill_quantity=body.fill.quantity,
            fill_price=body.fill.price,
            fill_timestamp=body.fill.fill_timestamp,
        )
        await db.commit()
    except TradeNotFoundError:
        raise HTTPException(status_code=404, detail="TRADE_NOT_FOUND")
    except TradeNotOwnedError:
        raise HTTPException(status_code=403, detail="TRADE_NOT_OWNED")
    except TradeAlreadyClosedError:
        raise HTTPException(status_code=422, detail="TRADE_ALREADY_CLOSED")
    except FillTimestampBeforeTradeOpenError:
        raise HTTPException(status_code=422, detail="FILL_TIMESTAMP_BEFORE_TRADE_OPEN")
    except PlannedStopWrongSideError:
        raise HTTPException(status_code=422, detail="PLANNED_STOP_WRONG_SIDE")
    except ReconstructionFailedError as exc:
        raise HTTPException(status_code=422, detail=f"RECONSTRUCTION_FAILED: {exc.detail}")

    return TradeOut.model_validate(trade)


@router.delete("/{trade_id}", status_code=204)
async def soft_delete_trade(
    trade_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    svc: TradeService = Depends(get_trade_service),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a manually entered trade.

    Sets is_deleted = true on the trade row; does NOT change trade.status.
    All fills are excluded from future reconstruction via fill_exclusions.

    Restricted to trades where ALL fills have import_source='MANUAL' (D2).
    CSV-imported trades must be disputed via the fill exclusion mechanism.

    Ownership verification uses a direct query on trading_accounts without
    checking account status (A-16-4). A deactivated account does not revoke
    the user's right to delete their own manually entered trade.
    """
    try:
        await svc.soft_delete_trade(user_id=user_id, trade_id=trade_id)
        await db.commit()
    except TradeNotFoundError:
        raise HTTPException(status_code=404, detail="TRADE_NOT_FOUND")
    except TradeNotOwnedError:
        raise HTTPException(status_code=403, detail="TRADE_NOT_OWNED")
    except TradeNotManualError:
        raise HTTPException(status_code=422, detail="TRADE_NOT_MANUAL")
