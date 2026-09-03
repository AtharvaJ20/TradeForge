"""Accounts REST API — v1 routes.

Routes:
  POST   /v1/accounts                          — create trading account
  GET    /v1/accounts                          — list trading accounts for user
  GET    /v1/accounts/{account_id}             — get single trading account
  POST   /v1/accounts/{account_id}/import      — import broker CSV fills

Security: all routes require an authenticated session (get_current_user_id).
          user_id is sourced from the session — never from request body or URL params.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.api.v1.deps import get_current_user_id
from tradeforge.application.import_service import ImportService, ImportSummary
from tradeforge.application.pnl_service import PnlService
from tradeforge.application.trade.reconstruction import ReconstructionEngine
from tradeforge.application.trading_account_service import TradingAccountService
from tradeforge.domain.import_domain.errors import (
    AccountInactiveError,
    AccountNotFoundError,
    DuplicateImportError,
    EmptyFileError,
    MissingProductTypeError,
    UnrecognizedFileError,
)
from tradeforge.infrastructure.adapters.zerodha_adapter import ZerodhaAdapter
from tradeforge.infrastructure.db import get_db
from tradeforge.infrastructure.repositories.charge_schedule_repo import ChargeScheduleRepository
from tradeforge.infrastructure.repositories.fill_exclusion_repo import FillExclusionRepository
from tradeforge.infrastructure.repositories.fill_repo import FillRepository
from tradeforge.infrastructure.repositories.import_record_repo import ImportRecordRepository
from tradeforge.infrastructure.repositories.instrument_repo import InstrumentRepository
from tradeforge.infrastructure.repositories.pnl_repo import PnlRepository
from tradeforge.infrastructure.repositories.tax_lot_repo import TaxLotRepository
from tradeforge.infrastructure.repositories.trade_repo import TradeRepository
from tradeforge.infrastructure.repositories.trading_account_repo import TradingAccountRepository

router = APIRouter(prefix="/accounts", tags=["accounts"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateAccountRequest(BaseModel):
    model_config = {"extra": "forbid"}

    broker: str = Field(..., description="Broker identifier: ZERODHA, UPSTOX, ANGEL_ONE, MANUAL")
    display_name: str = Field(..., min_length=1, max_length=100)
    account_type: str = Field(default="INDIVIDUAL", description="INDIVIDUAL or HUF")
    base_currency: str = Field(default="INR", min_length=3, max_length=3)


class AccountOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    broker: str
    display_name: str
    account_type: str
    base_currency: str
    status: str
    created_at: datetime
    updated_at: datetime


class ImportSummaryOut(BaseModel):
    import_record_id: uuid.UUID
    fills_ingested: int
    fills_skipped: int
    row_errors: int
    trades_created: int
    trades_closed: int
    pnl_succeeded: int
    pnl_failed: int


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_account_service() -> TradingAccountService:
    return TradingAccountService(account_repo=TradingAccountRepository())


def get_import_service(db: AsyncSession = Depends(get_db)) -> ImportService:
    return ImportService(
        account_service=TradingAccountService(account_repo=TradingAccountRepository()),
        import_record_repo=ImportRecordRepository(),
        instrument_repo=InstrumentRepository(),
        fill_repo=FillRepository(),
        reconstruction_engine=ReconstructionEngine(
            fill_repo=FillRepository(),
            trade_repo=TradeRepository(),
            tax_lot_repo=TaxLotRepository(),
            fill_exclusion_repo=FillExclusionRepository(),
        ),
        pnl_service=PnlService(
            pnl_repo=PnlRepository(db),
            charge_schedule_repo=ChargeScheduleRepository(db),
        ),
        adapters=[ZerodhaAdapter()],
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("", response_model=AccountOut, status_code=201)
async def create_account(
    body: CreateAccountRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    svc: TradingAccountService = Depends(get_account_service),
) -> AccountOut:
    try:
        account = await svc.create(
            db,
            user_id=user_id,
            broker=body.broker,
            display_name=body.display_name,
            account_type=body.account_type,
            base_currency=body.base_currency,
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return AccountOut.model_validate(account)


@router.get("", response_model=list[AccountOut])
async def list_accounts(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    svc: TradingAccountService = Depends(get_account_service),
) -> list[AccountOut]:
    accounts = await svc.list(db, user_id)
    return [AccountOut.model_validate(a) for a in accounts]


@router.get("/{account_id}", response_model=AccountOut)
async def get_account(
    account_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    svc: TradingAccountService = Depends(get_account_service),
) -> AccountOut:
    try:
        account = await svc.get(db, user_id, account_id)
    except AccountNotFoundError:
        raise HTTPException(status_code=404, detail="ACCOUNT_NOT_FOUND")
    return AccountOut.model_validate(account)


@router.post("/{account_id}/import", response_model=ImportSummaryOut)
async def import_fills(
    account_id: uuid.UUID,
    file: UploadFile = File(..., description="Broker tradebook CSV"),
    product_type_hint: str | None = Form(default=None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    svc: ImportService = Depends(get_import_service),
) -> ImportSummaryOut:
    file_content = await file.read()
    try:
        summary: ImportSummary = await svc.import_fills(
            db,
            user_id=user_id,
            account_id=account_id,
            file_content=file_content,
            product_type_hint=product_type_hint,
            file_name=file.filename,
        )
        await db.commit()
    except AccountNotFoundError:
        raise HTTPException(status_code=404, detail="ACCOUNT_NOT_FOUND")
    except AccountInactiveError:
        raise HTTPException(status_code=422, detail="ACCOUNT_INACTIVE")
    except DuplicateImportError:
        raise HTTPException(status_code=409, detail="DUPLICATE_IMPORT")
    except UnrecognizedFileError:
        raise HTTPException(status_code=422, detail="UNRECOGNIZED_FILE_FORMAT")
    except MissingProductTypeError:
        raise HTTPException(status_code=422, detail="MISSING_PRODUCT_TYPE")
    except EmptyFileError:
        raise HTTPException(status_code=422, detail="EMPTY_FILE")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return ImportSummaryOut(
        import_record_id=summary.import_record_id,
        fills_ingested=summary.fills_ingested,
        fills_skipped=summary.fills_skipped,
        row_errors=summary.row_errors,
        trades_created=summary.trades_created,
        trades_closed=summary.trades_closed,
        pnl_succeeded=summary.pnl_succeeded,
        pnl_failed=summary.pnl_failed,
    )
