"""API-layer tests for /v1/users/* — B-15-01 through B-15-08.

UserRepository is patched at the class level so route handlers that instantiate
it directly (UserRepository(db)) receive the mock without requiring a real DB.
get_current_user_id is overridden via FastAPI dependency overrides.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import AsyncClient

from tradeforge.infrastructure.models.user import User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_ID = uuid.uuid4()
_NOW = datetime(2026, 9, 5, 10, 0, 0, tzinfo=UTC)


def _make_user(
    *,
    display_name: str | None = "Arjun Sharma",
    time_zone: str = "Asia/Kolkata",
    base_currency: str = "INR",
) -> User:
    user = MagicMock(spec=User)
    user.id = _USER_ID
    user.email = "arjun@example.com"
    user.display_name = display_name
    user.time_zone = time_zone
    user.base_currency = base_currency
    user.is_email_verified = True
    user.is_admin = False
    user.created_at = _NOW
    return user


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def override_auth(http_client: AsyncClient) -> None:  # noqa: ARG001
    """Override get_current_user_id to simulate an authenticated session."""
    from tradeforge.api.v1.deps import get_current_user_id
    from tradeforge.main import app

    app.dependency_overrides[get_current_user_id] = lambda: _USER_ID
    yield
    app.dependency_overrides.pop(get_current_user_id, None)


# ---------------------------------------------------------------------------
# B-15-01: GET /v1/users/me — authenticated, returns full profile
# ---------------------------------------------------------------------------


async def test_get_profile_returns_all_fields(http_client: AsyncClient) -> None:
    """B-15-01: GET /v1/users/me returns UserProfileOut with profile fields."""
    user = _make_user()

    mock_repo = AsyncMock()
    mock_repo.find_by_id.return_value = user

    with patch("tradeforge.api.v1.users.UserRepository", return_value=mock_repo):
        response = await http_client.get("/v1/users/me")

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "arjun@example.com"
    assert body["display_name"] == "Arjun Sharma"
    assert body["time_zone"] == "Asia/Kolkata"
    assert body["base_currency"] == "INR"
    assert body["is_email_verified"] is True
    assert "id" in body
    assert "created_at" in body


# ---------------------------------------------------------------------------
# B-15-02: GET /v1/users/me — unauthenticated returns 401
# ---------------------------------------------------------------------------


async def test_get_profile_unauthenticated(http_client: AsyncClient) -> None:
    """B-15-02: GET /v1/users/me returns 401 when no session."""
    from tradeforge.api.v1.deps import get_current_user_id
    from tradeforge.main import app

    app.dependency_overrides[get_current_user_id] = lambda: (_ for _ in ()).throw(
        HTTPException(status_code=401, detail="NOT_AUTHENTICATED")
    )
    try:
        response = await http_client.get("/v1/users/me")
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_current_user_id] = lambda: _USER_ID


# ---------------------------------------------------------------------------
# B-15-03: PATCH /v1/users/me — updates display_name
# ---------------------------------------------------------------------------


async def test_patch_profile_updates_display_name(http_client: AsyncClient) -> None:
    """B-15-03: PATCH /v1/users/me with display_name updates and returns updated profile."""
    updated_user = _make_user(display_name="New Name")

    mock_repo = AsyncMock()
    mock_repo.update_profile.return_value = updated_user

    with patch("tradeforge.api.v1.users.UserRepository", return_value=mock_repo):
        response = await http_client.patch("/v1/users/me", json={"display_name": "New Name"})

    assert response.status_code == 200
    assert response.json()["display_name"] == "New Name"
    mock_repo.update_profile.assert_awaited_once()


# ---------------------------------------------------------------------------
# B-15-04: PATCH /v1/users/me — blank display_name → 422 DISPLAY_NAME_BLANK
# ---------------------------------------------------------------------------


async def test_patch_profile_blank_display_name_422(http_client: AsyncClient) -> None:
    """B-15-04: PATCH /v1/users/me with blank display_name returns 422."""
    mock_repo = AsyncMock()

    with patch("tradeforge.api.v1.users.UserRepository", return_value=mock_repo):
        response = await http_client.patch("/v1/users/me", json={"display_name": "   "})

    assert response.status_code == 422
    assert response.json()["detail"] == "DISPLAY_NAME_BLANK"
    mock_repo.update_profile.assert_not_awaited()


# ---------------------------------------------------------------------------
# B-15-05: PATCH /v1/users/me — invalid timezone → 422 INVALID_TIMEZONE
# ---------------------------------------------------------------------------


async def test_patch_profile_invalid_timezone_422(http_client: AsyncClient) -> None:
    """B-15-05: PATCH /v1/users/me with invalid time_zone returns 422."""
    mock_repo = AsyncMock()

    with patch("tradeforge.api.v1.users.UserRepository", return_value=mock_repo):
        response = await http_client.patch("/v1/users/me", json={"time_zone": "Mars/Olympus"})

    assert response.status_code == 422
    assert response.json()["detail"] == "INVALID_TIMEZONE"
    mock_repo.update_profile.assert_not_awaited()


# ---------------------------------------------------------------------------
# B-15-06: PATCH /v1/users/me — unsupported currency → 422 UNSUPPORTED_CURRENCY
# ---------------------------------------------------------------------------


async def test_patch_profile_unsupported_currency_422(http_client: AsyncClient) -> None:
    """B-15-06: PATCH /v1/users/me with base_currency USD returns 422."""
    mock_repo = AsyncMock()

    with patch("tradeforge.api.v1.users.UserRepository", return_value=mock_repo):
        response = await http_client.patch("/v1/users/me", json={"base_currency": "USD"})

    assert response.status_code == 422
    assert response.json()["detail"] == "UNSUPPORTED_CURRENCY"
    mock_repo.update_profile.assert_not_awaited()


# ---------------------------------------------------------------------------
# B-15-07: PATCH /v1/users/me — empty body is a no-op
# ---------------------------------------------------------------------------


async def test_patch_profile_empty_body_is_noop(http_client: AsyncClient) -> None:
    """B-15-07: PATCH /v1/users/me with no body fields returns unchanged profile."""
    user = _make_user()

    mock_repo = AsyncMock()
    mock_repo.update_profile.return_value = user

    with patch("tradeforge.api.v1.users.UserRepository", return_value=mock_repo):
        response = await http_client.patch("/v1/users/me", json={})

    assert response.status_code == 200
    # update_profile is still called but with no changed fields (only updated_at)
    mock_repo.update_profile.assert_awaited_once()


# ---------------------------------------------------------------------------
# B-15-08: PATCH /v1/users/me — display_name=null clears the field
# ---------------------------------------------------------------------------


async def test_patch_profile_null_display_name_clears_field(
    http_client: AsyncClient,
) -> None:
    """B-15-08: PATCH /v1/users/me with display_name=null clears it (returns null)."""
    cleared_user = _make_user(display_name=None)

    mock_repo = AsyncMock()
    mock_repo.update_profile.return_value = cleared_user

    with patch("tradeforge.api.v1.users.UserRepository", return_value=mock_repo):
        response = await http_client.patch("/v1/users/me", json={"display_name": None})

    assert response.status_code == 200
    assert response.json()["display_name"] is None
    # Verify update_profile was called with display_name=None (explicit clear)
    call_kwargs = mock_repo.update_profile.call_args.kwargs
    assert "display_name" in call_kwargs
    assert call_kwargs["display_name"] is None
