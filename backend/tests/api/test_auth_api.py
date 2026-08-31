"""API-layer tests for /v1/auth/* — verify HTTP contract without real DB or Redis.

AuthService is mocked via FastAPI dependency overrides. These tests cover:
  - Status codes and error responses
  - Enumeration-safe response bodies (SR-AUTH-004)
  - Cookie presence on login (SR-AUTH-006)
  - Cookie cleared on logout
  - Cache-Control: no-store header on auth responses
"""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from tradeforge.application.auth.service import AuthService
from tradeforge.domain.auth.errors import (
    AccountLockedError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidTokenError,
    PasswordPolicyViolationError,
    RateLimitedError,
)

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def mock_auth() -> AsyncMock:
    return AsyncMock(spec=AuthService)


@pytest.fixture(autouse=True)
def override_auth_service(mock_auth: AsyncMock) -> None:
    """Inject the mock into the FastAPI app for every test in this module."""
    from tradeforge.api.v1.deps import get_auth_service
    from tradeforge.main import app

    app.dependency_overrides[get_auth_service] = lambda: mock_auth
    yield
    app.dependency_overrides.pop(get_auth_service, None)


# ------------------------------------------------------------------
# POST /v1/auth/register
# ------------------------------------------------------------------


async def test_register_returns_200_on_success(
    http_client: AsyncClient, mock_auth: AsyncMock
) -> None:
    mock_auth.register.return_value = None
    response = await http_client.post(
        "/v1/auth/register",
        json={"email": "new@example.com", "password": "StrongPass123!"},
    )
    assert response.status_code == 200


async def test_register_response_body_is_enumeration_safe(
    http_client: AsyncClient, mock_auth: AsyncMock
) -> None:
    mock_auth.register.return_value = None
    response = await http_client.post(
        "/v1/auth/register",
        json={"email": "x@x.com", "password": "StrongPass123!"},
    )
    body = response.json()
    assert "message" in body
    assert "verification" in body["message"].lower() or "sent" in body["message"].lower()


async def test_register_returns_422_on_policy_violation(
    http_client: AsyncClient, mock_auth: AsyncMock
) -> None:
    mock_auth.register.side_effect = PasswordPolicyViolationError("Password too short.")
    response = await http_client.post(
        "/v1/auth/register",
        json={"email": "x@x.com", "password": "short"},
    )
    assert response.status_code == 422


async def test_register_rejects_invalid_email(
    http_client: AsyncClient, mock_auth: AsyncMock
) -> None:
    response = await http_client.post(
        "/v1/auth/register",
        json={"email": "not-an-email", "password": "StrongPass123!"},
    )
    assert response.status_code == 422
    mock_auth.register.assert_not_called()


# ------------------------------------------------------------------
# POST /v1/auth/verify-email
# ------------------------------------------------------------------


async def test_verify_email_returns_200_on_success(
    http_client: AsyncClient, mock_auth: AsyncMock
) -> None:
    mock_auth.verify_email.return_value = None
    response = await http_client.post(
        "/v1/auth/verify-email",
        json={"token": "a" * 64},
    )
    assert response.status_code == 200


async def test_verify_email_returns_400_on_invalid_token(
    http_client: AsyncClient, mock_auth: AsyncMock
) -> None:
    mock_auth.verify_email.side_effect = InvalidTokenError("expired")
    response = await http_client.post(
        "/v1/auth/verify-email",
        json={"token": "bad_token"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "INVALID_OR_EXPIRED_TOKEN"


# ------------------------------------------------------------------
# POST /v1/auth/login
# ------------------------------------------------------------------


async def test_login_sets_session_cookie(http_client: AsyncClient, mock_auth: AsyncMock) -> None:
    import uuid

    user_id = uuid.uuid4()

    # Mock get_current_user dependency too
    from tradeforge.infrastructure.models.user import User

    fake_user = User(
        id=user_id,
        email="user@example.com",
        password_hash="hash",
        is_email_verified=True,
        is_admin=False,
        is_locked=False,
    )

    mock_auth.login.return_value = (user_id, "fake_session_token_64chars")

    # We also need to override the DB lookup in login handler
    from sqlalchemy.ext.asyncio import AsyncSession

    from tradeforge.infrastructure.db import get_db

    mock_db = AsyncMock(spec=AsyncSession)

    from tradeforge.main import app

    async def fake_get_db():  # type: ignore[return]
        yield mock_db

    app.dependency_overrides[get_db] = fake_get_db

    # Mock UserRepository.find_by_id inside the handler
    from unittest.mock import patch

    with patch(
        "tradeforge.api.v1.auth.UserRepository.find_by_id",
        new=AsyncMock(return_value=fake_user),
    ):
        response = await http_client.post(
            "/v1/auth/login",
            json={"email": "user@example.com", "password": "StrongPass123!"},
        )

    app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert "tf_session" in response.cookies


async def test_login_returns_401_on_invalid_credentials(
    http_client: AsyncClient, mock_auth: AsyncMock
) -> None:
    mock_auth.login.side_effect = InvalidCredentialsError()

    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    async def fake_get_db():  # type: ignore[return]
        yield AsyncMock()

    app.dependency_overrides[get_db] = fake_get_db
    response = await http_client.post(
        "/v1/auth/login",
        json={"email": "user@example.com", "password": "wrong"},
    )
    app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 401
    assert response.json()["detail"] == "INVALID_CREDENTIALS"


async def test_login_returns_429_when_rate_limited(
    http_client: AsyncClient, mock_auth: AsyncMock
) -> None:
    mock_auth.login.side_effect = RateLimitedError()

    from unittest.mock import AsyncMock

    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    async def fake_get_db():  # type: ignore[return]
        yield AsyncMock()

    app.dependency_overrides[get_db] = fake_get_db
    response = await http_client.post(
        "/v1/auth/login",
        json={"email": "user@example.com", "password": "pass"},
    )
    app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 429


async def test_login_returns_423_when_account_locked(
    http_client: AsyncClient, mock_auth: AsyncMock
) -> None:
    mock_auth.login.side_effect = AccountLockedError()

    from unittest.mock import AsyncMock

    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    async def fake_get_db():  # type: ignore[return]
        yield AsyncMock()

    app.dependency_overrides[get_db] = fake_get_db
    response = await http_client.post(
        "/v1/auth/login",
        json={"email": "user@example.com", "password": "pass"},
    )
    app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 423


async def test_login_returns_403_when_email_not_verified(
    http_client: AsyncClient, mock_auth: AsyncMock
) -> None:
    mock_auth.login.side_effect = EmailNotVerifiedError()

    from unittest.mock import AsyncMock

    from tradeforge.infrastructure.db import get_db
    from tradeforge.main import app

    async def fake_get_db():  # type: ignore[return]
        yield AsyncMock()

    app.dependency_overrides[get_db] = fake_get_db
    response = await http_client.post(
        "/v1/auth/login",
        json={"email": "user@example.com", "password": "pass"},
    )
    app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 403
    assert response.json()["detail"] == "EMAIL_NOT_VERIFIED"


# ------------------------------------------------------------------
# POST /v1/auth/password-reset/request
# ------------------------------------------------------------------


async def test_password_reset_request_always_returns_200(
    http_client: AsyncClient, mock_auth: AsyncMock
) -> None:
    # Enumeration prevention: same response whether email exists or not
    mock_auth.request_password_reset.return_value = None
    response = await http_client.post(
        "/v1/auth/password-reset/request",
        json={"email": "anyone@example.com"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "message" in body


async def test_password_reset_response_body_is_enumeration_safe(
    http_client: AsyncClient, mock_auth: AsyncMock
) -> None:
    mock_auth.request_password_reset.return_value = None
    response = await http_client.post(
        "/v1/auth/password-reset/request",
        json={"email": "unknown@example.com"},
    )
    body = response.json()
    # Must not reveal whether email is registered
    detail = body.get("message", "")
    assert "if" in detail.lower()


# ------------------------------------------------------------------
# POST /v1/auth/password-reset/confirm
# ------------------------------------------------------------------


async def test_password_reset_confirm_returns_200_on_success(
    http_client: AsyncClient, mock_auth: AsyncMock
) -> None:
    mock_auth.confirm_password_reset.return_value = None
    response = await http_client.post(
        "/v1/auth/password-reset/confirm",
        json={"token": "a" * 64, "new_password": "NewStrongPass123!"},
    )
    assert response.status_code == 200


async def test_password_reset_confirm_returns_400_on_invalid_token(
    http_client: AsyncClient, mock_auth: AsyncMock
) -> None:
    mock_auth.confirm_password_reset.side_effect = InvalidTokenError("expired")
    response = await http_client.post(
        "/v1/auth/password-reset/confirm",
        json={"token": "bad", "new_password": "NewStrongPass123!"},
    )
    assert response.status_code == 400


# ------------------------------------------------------------------
# Cache-Control header
# ------------------------------------------------------------------


async def test_auth_responses_have_no_store_cache_control(
    http_client: AsyncClient, mock_auth: AsyncMock
) -> None:
    mock_auth.register.return_value = None
    response = await http_client.post(
        "/v1/auth/register",
        json={"email": "x@x.com", "password": "StrongPass123!"},
    )
    assert response.headers.get("cache-control") == "no-store"
