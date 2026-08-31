"""Auth router — /v1/auth/* endpoints.

Thin handlers: parse input, call AuthService, set/clear cookies, return response.
No business logic lives here. Error mapping from domain errors to HTTP codes is
the only coupling between the API and domain layers.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.api.v1.deps import (
    SESSION_COOKIE,
    get_auth_service,
    get_client_ip,
    get_current_user,
    get_current_user_id,
)
from tradeforge.infrastructure.db import get_db
from tradeforge.infrastructure.repositories.user_repo import UserRepository
from tradeforge.application.auth.service import AuthService
from tradeforge.domain.auth.errors import (
    AccountLockedError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidTokenError,
    PasswordPolicyViolationError,
    RateLimitedError,
    RedisUnavailableError,
)
from tradeforge.infrastructure.models.user import User
from tradeforge.settings import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_MAX_AGE = 30 * 24 * 60 * 60  # 30 days in seconds



def _set_session_cookie(response: Response, token: str) -> None:
    secure = get_settings().secure_cookies
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="strict",
        secure=secure,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE, path="/", samesite="strict")


# ------------------------------------------------------------------
# Request / response schemas
# ------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()


class VerifyEmailRequest(BaseModel):
    token: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()


class PasswordResetRequestBody(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str


class MessageResponse(BaseModel):
    message: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    is_email_verified: bool
    is_admin: bool


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.post("/register", response_model=MessageResponse)
async def register(
    body: RegisterRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    ip = get_client_ip(request)
    try:
        await auth.register(email=body.email, password=body.password, ip=ip)
    except RateLimitedError:
        raise HTTPException(status_code=429, detail="RATE_LIMITED")
    except PasswordPolicyViolationError as exc:
        raise HTTPException(status_code=422, detail=exc.message)
    except RedisUnavailableError:
        raise HTTPException(status_code=503, detail="SERVICE_UNAVAILABLE")
    await db.commit()
    # Enumeration-safe message (SR-AUTH-004)
    return MessageResponse(
        message="If this email address is new, a verification link has been sent."
    )


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    body: VerifyEmailRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    ip = get_client_ip(request)
    try:
        await auth.verify_email(raw_token=body.token, ip=ip)
    except RateLimitedError:
        raise HTTPException(status_code=429, detail="RATE_LIMITED")
    except InvalidTokenError:
        raise HTTPException(status_code=400, detail="INVALID_OR_EXPIRED_TOKEN")
    except RedisUnavailableError:
        raise HTTPException(status_code=503, detail="SERVICE_UNAVAILABLE")
    await db.commit()
    return MessageResponse(message="Email verified successfully.")


@router.post("/login", response_model=UserResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    auth: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    ip = get_client_ip(request)
    ua = request.headers.get("User-Agent")
    try:
        user_id, token = await auth.login(
            email=body.email, password=body.password, ip=ip, user_agent=ua
        )
    except RateLimitedError:
        raise HTTPException(status_code=429, detail="RATE_LIMITED")
    except AccountLockedError:
        raise HTTPException(status_code=423, detail="ACCOUNT_LOCKED")
    except EmailNotVerifiedError:
        raise HTTPException(status_code=403, detail="EMAIL_NOT_VERIFIED")
    except InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")
    except RedisUnavailableError:
        raise HTTPException(status_code=503, detail="SERVICE_UNAVAILABLE")

    _set_session_cookie(response, token)

    user = await UserRepository(db).find_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=500, detail="USER_NOT_FOUND_AFTER_LOGIN")

    await db.commit()
    return UserResponse(
        id=user.id,
        email=user.email,
        is_email_verified=user.is_email_verified,
        is_admin=user.is_admin,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    user_id: uuid.UUID = Depends(get_current_user_id),
    auth: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    token = request.cookies.get(SESSION_COOKIE, "")
    ip = get_client_ip(request)
    try:
        await auth.logout(session_token=token, user_id=user_id, ip=ip)
    except RedisUnavailableError:
        raise HTTPException(status_code=503, detail="SERVICE_UNAVAILABLE")
    await db.commit()
    _clear_session_cookie(response)
    return MessageResponse(message="Logged out successfully.")


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        is_email_verified=user.is_email_verified,
        is_admin=user.is_admin,
    )


@router.post("/password-reset/request", response_model=MessageResponse)
async def password_reset_request(
    body: PasswordResetRequestBody,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    ip = get_client_ip(request)
    try:
        await auth.request_password_reset(email=body.email, ip=ip)
    except RateLimitedError:
        raise HTTPException(status_code=429, detail="RATE_LIMITED")
    except RedisUnavailableError:
        raise HTTPException(status_code=503, detail="SERVICE_UNAVAILABLE")
    await db.commit()
    # Enumeration-safe message (SR-AUTH-004)
    return MessageResponse(
        message="If this email address is registered, a password reset link has been sent."
    )


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def password_reset_confirm(
    body: PasswordResetConfirmRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    ip = get_client_ip(request)
    try:
        await auth.confirm_password_reset(
            raw_token=body.token, new_password=body.new_password, ip=ip
        )
    except InvalidTokenError:
        raise HTTPException(status_code=400, detail="INVALID_OR_EXPIRED_TOKEN")
    except PasswordPolicyViolationError as exc:
        raise HTTPException(status_code=422, detail=exc.message)
    except RedisUnavailableError:
        raise HTTPException(status_code=503, detail="SERVICE_UNAVAILABLE")
    await db.commit()
    return MessageResponse(message="Password reset successfully. Please log in with your new password.")
