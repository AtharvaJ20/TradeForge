"""Trades REST API — v1 routes.

Routes:
  GET    /v1/trades                     — paginated, filtered, sorted trade list (B-18-C, B-19-A)
  GET    /v1/trades/{trade_id}          — full trade detail with fills + P&L (B-19-B)
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
from sqlalchemy import func, select
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
from tradeforge.domain.import_domain.errors import AccountNotFoundError
from tradeforge.infrastructure.db import get_db
from tradeforge.infrastructure.models.trade_domain import ExecutionFill, Instrument, Trade
from tradeforge.infrastructure.models.trade_pnl import TradePnl

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


class TradeListPageOut(BaseModel):
    items: list[TradeListItemOut]
    total: int
    limit: int
    offset: int


class FillItemOut(BaseModel):
    id: uuid.UUID
    side: str
    quantity: Decimal
    price: Decimal
    fill_role: str | None
    fill_timestamp: datetime
    import_source: str
    broker: str


class PnlBreakdownOut(BaseModel):
    gross_pnl: Decimal
    net_pnl: Decimal
    total_charges: Decimal
    brokerage: Decimal
    stt: Decimal
    exchange_charges: Decimal
    sebi_charges: Decimal
    stamp_duty: Decimal
    gst: Decimal
    ipft: Decimal
    r_multiple: Decimal | None


class TradeDetailOut(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID | None
    symbol: str
    instrument_name: str
    exchange_segment: str
    instrument_type: str
    expiry_date: date | None
    strike_price: Decimal | None
    direction: str
    trade_type: str
    status: str
    trade_date: date
    first_fill_at: datetime
    last_fill_at: datetime | None
    total_entry_quantity: Decimal
    total_exit_quantity: Decimal
    average_entry: Decimal | None
    average_exit: Decimal | None
    planned_stop: Decimal | None
    planned_target: Decimal | None
    planned_risk_amount: Decimal | None
    setup_name: str | None
    hold_duration_seconds: int | None
    fills: list[FillItemOut]
    pnl: PnlBreakdownOut | None


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
_VALID_DIRECTIONS = frozenset({"LONG", "SHORT"})
_VALID_TRADE_TYPES = frozenset({"MIS", "CNC", "CNC_SAME_DAY", "NRML_FUT", "NRML_OPT"})


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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=TradeListPageOut)
async def list_trades(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    status: str | None = Query(default=None),
    account_id: uuid.UUID | None = Query(default=None),
    direction: str | None = Query(default=None),
    trade_type: str | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    instrument: str | None = Query(default=None, max_length=50),
    sort_by: str = Query(default="last_fill_at"),
    sort_dir: str = Query(default="desc"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> TradeListPageOut:
    if status is not None and status not in _VALID_STATUSES:
        raise HTTPException(status_code=422, detail="INVALID_STATUS")
    if direction is not None and direction not in _VALID_DIRECTIONS:
        raise HTTPException(status_code=422, detail="INVALID_DIRECTION")
    if trade_type is not None and trade_type not in _VALID_TRADE_TYPES:
        raise HTTPException(status_code=422, detail="INVALID_TRADE_TYPE")
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(status_code=422, detail="INVALID_DATE_RANGE")

    # Build shared WHERE conditions for both COUNT and data queries.
    base_where = [Trade.user_id == user_id, Trade.is_deleted.is_(False)]
    if status is not None:
        base_where.append(Trade.status == status)
    if account_id is not None:
        base_where.append(Trade.account_id == account_id)
    if direction is not None:
        base_where.append(Trade.direction == direction)
    if trade_type is not None:
        base_where.append(Trade.trade_type == trade_type)
    if from_date is not None:
        base_where.append(Trade.trade_date >= from_date)
    if to_date is not None:
        base_where.append(Trade.trade_date <= to_date)
    if instrument is not None:
        instrument_upper = instrument.strip().upper()
        if instrument_upper:
            # D-19-1: autoescape=True prevents % and _ in user input acting as wildcards.
            base_where.append(
                func.upper(Instrument.symbol).startswith(instrument_upper, autoescape=True)
            )

    joins = (
        select(func.count(Trade.id))
        .select_from(Trade)
        .join(Instrument, Instrument.id == Trade.instrument_id)
        .outerjoin(TradePnl, TradePnl.trade_id == Trade.id)
        .where(*base_where)
    )
    count_result = await db.execute(joins)
    total = count_result.scalar_one()

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
        .where(*base_where)
        .order_by(ordered_col)
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return TradeListPageOut(
        items=[
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
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{trade_id}", response_model=TradeDetailOut)
async def get_trade_detail(
    trade_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> TradeDetailOut:
    # Step 1: Trade + Instrument JOIN. user_id in WHERE enforces ownership at query time (A-19-1).
    stmt = (
        select(
            Trade.id,
            Trade.account_id,
            Trade.direction,
            Trade.trade_type,
            Trade.status,
            Trade.trade_date,
            Trade.first_fill_at,
            Trade.last_fill_at,
            Trade.total_entry_quantity,
            Trade.total_exit_quantity,
            Trade.average_entry,
            Trade.average_exit,
            Trade.planned_stop,
            Trade.planned_target,
            Trade.planned_risk_amount,
            Trade.setup_name,
            Instrument.symbol,
            Instrument.name.label("instrument_name"),
            Instrument.exchange_segment,
            Instrument.instrument_type,
            Instrument.expiry_date,
            Instrument.strike_price,
        )
        .select_from(Trade)
        .join(Instrument, Instrument.id == Trade.instrument_id)
        .where(
            Trade.id == trade_id,
            Trade.user_id == user_id,
            Trade.is_deleted.is_(False),
        )
    )
    result = await db.execute(stmt)
    trade_row = result.one_or_none()
    if trade_row is None:
        raise HTTPException(status_code=404, detail="TRADE_NOT_FOUND")

    # Step 2: Fills ordered ASC by fill_timestamp.
    fills_stmt = (
        select(
            ExecutionFill.id,
            ExecutionFill.side,
            ExecutionFill.quantity,
            ExecutionFill.price,
            ExecutionFill.fill_role,
            ExecutionFill.fill_timestamp,
            ExecutionFill.import_source,
            ExecutionFill.broker,
        )
        .where(ExecutionFill.trade_id == trade_id)
        .order_by(ExecutionFill.fill_timestamp.asc())
    )
    fills_result = await db.execute(fills_stmt)
    fill_rows = fills_result.all()

    # Step 3: P&L row (absent for OPEN/PARTIAL trades).
    pnl_stmt = select(TradePnl).where(TradePnl.trade_id == trade_id)
    pnl_result = await db.execute(pnl_stmt)
    pnl_row = pnl_result.scalar_one_or_none()

    # Step 4: hold_duration_seconds — None for OPEN trades where last_fill_at is null.
    hold_duration_seconds: int | None = None
    if trade_row.last_fill_at is not None:
        hold_duration_seconds = int(
            (trade_row.last_fill_at - trade_row.first_fill_at).total_seconds()
        )

    pnl: PnlBreakdownOut | None = None
    if pnl_row is not None:
        pnl = PnlBreakdownOut(
            gross_pnl=pnl_row.gross_pnl,
            net_pnl=pnl_row.net_pnl,
            total_charges=pnl_row.total_charges,
            brokerage=pnl_row.brokerage,
            stt=pnl_row.stt,
            exchange_charges=pnl_row.exchange_charges,
            sebi_charges=pnl_row.sebi_charges,
            stamp_duty=pnl_row.stamp_duty,
            gst=pnl_row.gst,
            ipft=pnl_row.ipft,
            r_multiple=pnl_row.r_multiple,
        )

    return TradeDetailOut(
        id=trade_row.id,
        account_id=trade_row.account_id,
        symbol=trade_row.symbol,
        instrument_name=trade_row.instrument_name,
        exchange_segment=trade_row.exchange_segment,
        instrument_type=trade_row.instrument_type,
        expiry_date=trade_row.expiry_date,
        strike_price=trade_row.strike_price,
        direction=trade_row.direction,
        trade_type=trade_row.trade_type,
        status=trade_row.status,
        trade_date=trade_row.trade_date,
        first_fill_at=trade_row.first_fill_at,
        last_fill_at=trade_row.last_fill_at,
        total_entry_quantity=trade_row.total_entry_quantity,
        total_exit_quantity=trade_row.total_exit_quantity,
        average_entry=trade_row.average_entry,
        average_exit=trade_row.average_exit,
        planned_stop=trade_row.planned_stop,
        planned_target=trade_row.planned_target,
        planned_risk_amount=trade_row.planned_risk_amount,
        setup_name=trade_row.setup_name,
        hold_duration_seconds=hold_duration_seconds,
        fills=[
            FillItemOut(
                id=f.id,
                side=f.side,
                quantity=f.quantity,
                price=f.price,
                fill_role=f.fill_role,
                fill_timestamp=f.fill_timestamp,
                import_source=f.import_source,
                broker=f.broker,
            )
            for f in fill_rows
        ],
        pnl=pnl,
    )


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
