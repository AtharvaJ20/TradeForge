"""Imports REST API — v1 routes.

Routes:
  GET /v1/imports   — list import history for a trading account

Security: all routes require an authenticated session (get_current_user_id).
          account ownership is verified via TradingAccountService.get() —
          ACTIVE status is NOT required; users can view history for inactive accounts.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.api.v1.deps import get_current_user_id
from tradeforge.application.trading_account_service import TradingAccountService
from tradeforge.domain.import_domain.errors import AccountNotFoundError
from tradeforge.infrastructure.db import get_db
from tradeforge.infrastructure.repositories.import_record_repo import ImportRecordRepository
from tradeforge.infrastructure.repositories.trading_account_repo import TradingAccountRepository

router = APIRouter(prefix="/imports", tags=["imports"])


class ImportRecordOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    account_id: uuid.UUID
    broker: str
    file_name: str | None
    row_count: int
    error_count: int
    status: str
    imported_at: datetime
    created_at: datetime


def get_account_service() -> TradingAccountService:
    return TradingAccountService(account_repo=TradingAccountRepository())


def get_import_record_repo() -> ImportRecordRepository:
    return ImportRecordRepository()


@router.get("", response_model=list[ImportRecordOut])
async def list_imports(
    account_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    account_svc: TradingAccountService = Depends(get_account_service),
    import_record_repo: ImportRecordRepository = Depends(get_import_record_repo),
) -> list[ImportRecordOut]:
    try:
        await account_svc.get(db, user_id, account_id)
    except AccountNotFoundError:
        raise HTTPException(status_code=404, detail="ACCOUNT_NOT_FOUND")
    records = await import_record_repo.list_by_account(db, account_id)
    return [ImportRecordOut.model_validate(r) for r in records]
