"""API-layer tests for CSRF middleware — verify HTTP behaviour without a real DB.

The middleware's audit logging is best-effort (wrapped in try/except), so these
tests verify HTTP contract only.  DB persistence is verified by the integration
test in tests/integration/test_auth_flows.py.
"""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from tradeforge.application.auth.service import AuthService


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def mock_auth() -> AsyncMock:
    return AsyncMock(spec=AuthService)


@pytest.fixture(autouse=True)
def override_auth_service(mock_auth: AsyncMock) -> None:
    """Suppress real auth service for every test in this module."""
    from tradeforge.api.v1.deps import get_auth_service
    from tradeforge.main import app

    app.dependency_overrides[get_auth_service] = lambda: mock_auth
    yield
    app.dependency_overrides.pop(get_auth_service, None)


# ------------------------------------------------------------------
# CSRF blocking
# ------------------------------------------------------------------


async def test_post_with_foreign_origin_returns_403(http_client: AsyncClient) -> None:
    """A POST bearing an Origin not in ALLOWED_ORIGINS must be rejected."""
    response = await http_client.post(
        "/v1/auth/register",
        json={"email": "x@x.com", "password": "StrongPass123!"},
        headers={"Origin": "https://evil.example.com"},
    )
    assert response.status_code == 403


async def test_csrf_rejection_body_contains_expected_detail(http_client: AsyncClient) -> None:
    """Rejected CSRF requests return CSRF_VALIDATION_FAILED in the detail field."""
    response = await http_client.post(
        "/v1/auth/register",
        json={"email": "x@x.com", "password": "StrongPass123!"},
        headers={"Origin": "https://evil.example.com"},
    )
    assert response.json()["detail"] == "CSRF_VALIDATION_FAILED"


async def test_put_with_foreign_origin_is_blocked(http_client: AsyncClient) -> None:
    """PUT requests are subject to the same CSRF check as POST."""
    response = await http_client.put(
        "/v1/auth/register",
        json={},
        headers={"Origin": "https://evil.example.com"},
    )
    assert response.status_code == 403


async def test_delete_with_foreign_origin_is_blocked(http_client: AsyncClient) -> None:
    """DELETE requests are subject to the same CSRF check as POST."""
    response = await http_client.delete(
        "/v1/auth/logout",
        headers={"Origin": "https://evil.example.com"},
    )
    assert response.status_code == 403


# ------------------------------------------------------------------
# CSRF pass-through
# ------------------------------------------------------------------


async def test_get_with_foreign_origin_is_not_blocked(http_client: AsyncClient) -> None:
    """GET requests are read-only and must not be blocked by CSRF middleware."""
    response = await http_client.get(
        "/health",
        headers={"Origin": "https://evil.example.com"},
    )
    assert response.status_code == 200


async def test_post_with_no_origin_header_is_not_blocked(
    http_client: AsyncClient, mock_auth: AsyncMock
) -> None:
    """Requests with no Origin header (same-origin browser requests) must proceed."""
    mock_auth.register.return_value = None
    response = await http_client.post(
        "/v1/auth/register",
        json={"email": "x@x.com", "password": "StrongPass123!"},
    )
    assert response.status_code != 403


async def test_post_with_allowed_origin_is_not_blocked(
    http_client: AsyncClient, mock_auth: AsyncMock
) -> None:
    """A POST from an origin in ALLOWED_ORIGINS must not be rejected."""
    from tradeforge.settings import get_settings

    allowed_origin = get_settings().allowed_origins_list()[0]
    mock_auth.register.return_value = None
    response = await http_client.post(
        "/v1/auth/register",
        json={"email": "x@x.com", "password": "StrongPass123!"},
        headers={"Origin": allowed_origin},
    )
    assert response.status_code != 403
