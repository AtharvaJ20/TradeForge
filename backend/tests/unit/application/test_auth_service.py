"""Unit tests for AuthService.login() — SR-AUTH-010 regression guard.

DEF-AUTH-001: clear_forced_reauth was never called after a successful login,
leaving users locked out for 24 hours after any password reset.

These tests mock all I/O dependencies so they run without DB or Redis.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tradeforge.application.auth.service import AuthService
from tradeforge.domain.auth.errors import InvalidCredentialsError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service() -> tuple[AuthService, AsyncMock]:
    """Return (service, session_repo_mock) with all dependencies mocked."""
    user_repo = AsyncMock()
    audit_repo = AsyncMock()
    verification_repo = AsyncMock()
    reset_repo = AsyncMock()
    session_repo = AsyncMock()
    email_sender = AsyncMock()

    svc = AuthService(
        user_repo=user_repo,
        audit_repo=audit_repo,
        verification_repo=verification_repo,
        reset_repo=reset_repo,
        session_repo=session_repo,
        email_sender=email_sender,
    )
    return svc, session_repo


def _make_user(user_id: uuid.UUID | None = None) -> MagicMock:
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.email = "test@example.com"
    user.is_email_verified = True
    user.is_locked = False
    user.password_hash = "hashed"
    return user


# ---------------------------------------------------------------------------
# DEF-AUTH-001 regression: clear_forced_reauth called on successful login
# ---------------------------------------------------------------------------


async def test_login_clears_forced_reauth_on_success() -> None:
    """SR-AUTH-010: login() must call clear_forced_reauth after creating a session.

    Before the DEF-AUTH-001 fix, clear_forced_reauth was never invoked — users
    were locked out for 24 hours after any password reset.
    """
    svc, session_repo = _make_service()
    user = _make_user()

    svc._users.find_by_email = AsyncMock(return_value=user)
    session_repo.get_login_failures = AsyncMock(return_value=0)
    session_repo.increment_ip_attempts = AsyncMock(return_value=1)
    session_repo.reset_login_failures = AsyncMock()
    session_repo.create_session = AsyncMock()
    session_repo.clear_forced_reauth = AsyncMock()
    svc._audit.log = AsyncMock()

    with patch("tradeforge.application.auth.service._ph") as mock_ph:
        mock_ph.verify.return_value = None  # password check passes
        mock_ph.check_needs_rehash.return_value = False

        await svc.login(
            email="test@example.com",
            password="any-password",
            ip="127.0.0.1",
            user_agent=None,
        )

    session_repo.clear_forced_reauth.assert_awaited_once_with(str(user.id))


async def test_login_clears_forced_reauth_after_create_session() -> None:
    """clear_forced_reauth must be called AFTER create_session (ordering check)."""
    svc, session_repo = _make_service()
    user = _make_user()
    call_order: list[str] = []

    async def _create_session(**kwargs: object) -> None:
        call_order.append("create_session")

    async def _clear_reauth(user_id: str) -> None:
        call_order.append("clear_forced_reauth")

    svc._users.find_by_email = AsyncMock(return_value=user)
    session_repo.get_login_failures = AsyncMock(return_value=0)
    session_repo.increment_ip_attempts = AsyncMock(return_value=1)
    session_repo.reset_login_failures = AsyncMock()
    session_repo.create_session = _create_session  # type: ignore[method-assign]
    session_repo.clear_forced_reauth = _clear_reauth  # type: ignore[method-assign]
    svc._audit.log = AsyncMock()

    with patch("tradeforge.application.auth.service._ph") as mock_ph:
        mock_ph.verify.return_value = None
        mock_ph.check_needs_rehash.return_value = False

        await svc.login(
            email="test@example.com",
            password="any-password",
            ip="127.0.0.1",
            user_agent=None,
        )

    assert call_order == ["create_session", "clear_forced_reauth"], (
        f"Expected create_session before clear_forced_reauth, got: {call_order}"
    )


async def test_login_does_not_clear_forced_reauth_on_wrong_password() -> None:
    """clear_forced_reauth must NOT be called when login fails."""
    from argon2.exceptions import VerifyMismatchError

    svc, session_repo = _make_service()
    user = _make_user()

    svc._users.find_by_email = AsyncMock(return_value=user)
    session_repo.get_login_failures = AsyncMock(return_value=0)
    session_repo.increment_ip_attempts = AsyncMock(return_value=1)
    session_repo.increment_login_failures = AsyncMock(return_value=1)
    session_repo.clear_forced_reauth = AsyncMock()
    svc._audit.log = AsyncMock()

    with patch("tradeforge.application.auth.service._ph") as mock_ph:
        mock_ph.verify.side_effect = VerifyMismatchError()

        with pytest.raises(InvalidCredentialsError):
            await svc.login(
                email="test@example.com",
                password="wrong-password",
                ip="127.0.0.1",
                user_agent=None,
            )

    session_repo.clear_forced_reauth.assert_not_awaited()
