"""Users REST API — /v1/users/* endpoints.

Routes:
  GET   /v1/users/me   — return authenticated user's full profile
  PATCH /v1/users/me   — update profile fields (display_name, time_zone, base_currency)

Security: user_id always sourced from the session; never from the request body or URL.

Note: do NOT add `from __future__ import annotations` to this file — FastAPI
introspects dependency signatures at runtime and deferred annotation evaluation
breaks subscripted types in dependency functions.
"""

import uuid
import zoneinfo
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.api.v1.deps import get_current_user_id
from tradeforge.infrastructure.db import get_db
from tradeforge.infrastructure.repositories.user_repo import UserRepository

router = APIRouter(prefix="/users", tags=["users"])

_SUPPORTED_CURRENCIES = frozenset({"INR"})


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class UserProfileOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    display_name: str | None
    time_zone: str
    base_currency: str
    is_email_verified: bool
    is_admin: bool
    created_at: datetime


class UpdateProfileRequest(BaseModel):
    model_config = {"extra": "forbid"}

    display_name: str | None = Field(default=None, max_length=100)
    time_zone: str | None = Field(default=None)
    base_currency: str | None = Field(default=None)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserProfileOut)
async def get_profile(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserProfileOut:
    user = await UserRepository(db).find_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="USER_NOT_FOUND")
    return UserProfileOut.model_validate(user)


@router.patch("/me", response_model=UserProfileOut)
async def update_profile(
    body: UpdateProfileRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserProfileOut:
    # Validate before touching the DB
    if body.display_name is not None and not body.display_name.strip():
        raise HTTPException(status_code=422, detail="DISPLAY_NAME_BLANK")

    if body.time_zone is not None and body.time_zone not in zoneinfo.available_timezones():
        raise HTTPException(status_code=422, detail="INVALID_TIMEZONE")

    if body.base_currency is not None and body.base_currency not in _SUPPORTED_CURRENCIES:
        raise HTTPException(status_code=422, detail="UNSUPPORTED_CURRENCY")

    # Only pass fields that were explicitly set in the request body.
    # Omitted fields use _UNSET as default → UserRepository leaves them unchanged.
    # display_name=None is valid (clears the field); time_zone/base_currency cannot be None.
    kwargs: dict[str, Any] = {}
    if "display_name" in body.model_fields_set:
        kwargs["display_name"] = body.display_name
    if body.time_zone is not None:
        kwargs["time_zone"] = body.time_zone
    if body.base_currency is not None:
        kwargs["base_currency"] = body.base_currency

    repo = UserRepository(db)
    user = await repo.update_profile(user_id, **kwargs)
    if user is None:
        raise HTTPException(status_code=401, detail="USER_NOT_FOUND")

    await db.commit()
    return UserProfileOut.model_validate(user)
