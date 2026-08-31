"""API-layer tests for BLOCKER-3 rate limiting on register / verify-email / reset.

AuthService is mocked; these tests verify the HTTP contract only: when
AuthService raises RateLimitedError the handler must return 429 RATE_LIMITED.
"""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from tradeforge.application.auth.service import AuthService
from tradeforge.domain.auth.errors import RateLimitedError


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def mock_auth() -> AsyncMock:
    return AsyncMock(spec=AuthService)


@pytest.fixture(autouse=True)
def override_auth_service(mock_auth: AsyncMock) -> None:
    from tradeforge.api.v1.deps import get_auth_service
    from tradeforge.main import app

    app.dependency_overrides[get_auth_service] = lambda: mock_auth
    yield
    app.dependency_overrides.pop(get_auth_service, None)


# ------------------------------------------------------------------
# POST /v1/auth/register
# ------------------------------------------------------------------


async def test_register_returns_429_when_rate_limited(
    http_client: AsyncClient, mock_auth: AsyncMock
) -> None:
    """A rate-limited registration attempt must return 429."""
    mock_auth.register.side_effect = RateLimitedError("Too many registration attempts.")
    response = await http_client.post(
        "/v1/auth/register",
        json={"email": "x@x.com", "password": "StrongPass123!"},
    )
    assert response.status_code == 429
    assert response.json()["detail"] == "RATE_LIMITED"


# ------------------------------------------------------------------
# POST /v1/auth/verify-email
# ------------------------------------------------------------------


async def test_verify_email_returns_429_when_rate_limited(
    http_client: AsyncClient, mock_auth: AsyncMock
) -> None:
    """A rate-limited email-verification attempt must return 429."""
    mock_auth.verify_email.side_effect = RateLimitedError("Too many requests.")
    response = await http_client.post(
        "/v1/auth/verify-email",
        json={"token": "a" * 64},
    )
    assert response.status_code == 429
    assert response.json()["detail"] == "RATE_LIMITED"


# ------------------------------------------------------------------
# POST /v1/auth/password-reset/request
# ------------------------------------------------------------------


async def test_password_reset_request_returns_429_when_rate_limited(
    http_client: AsyncClient, mock_auth: AsyncMock
) -> None:
    """A rate-limited password-reset request must return 429."""
    mock_auth.request_password_reset.side_effect = RateLimitedError("Too many requests.")
    response = await http_client.post(
        "/v1/auth/password-reset/request",
        json={"email": "x@x.com"},
    )
    assert response.status_code == 429
    assert response.json()["detail"] == "RATE_LIMITED"
