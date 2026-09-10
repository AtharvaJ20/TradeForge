"""Unit tests for S20-1 rate-limit additions to SessionRepository.

Verifies:
- IP_AUTH_THRESHOLD is 5 (register/verify-email)
- IP_RESET_THRESHOLD is 3 (request_password_reset / confirm_password_reset)
- increment_reset_attempts_ip uses the reset_attempts_ip:{ip} key
- reset and auth attempt keys are distinct (counter isolation)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from tradeforge.infrastructure.repositories.session_repo import (
    IP_AUTH_THRESHOLD,
    IP_RESET_THRESHOLD,
    SessionRepository,
)


def _make_repo(pipeline_results: list[object] | None = None):
    """Return (repo, pipeline_mock) with a mock Redis client."""
    mock_redis = MagicMock()
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.incr = AsyncMock(return_value=None)
    pipe.expire = AsyncMock(return_value=None)
    pipe.execute = AsyncMock(return_value=pipeline_results or [1, 1])
    mock_redis.pipeline.return_value = pipe
    return SessionRepository(mock_redis), pipe


# ---------------------------------------------------------------------------
# Threshold values
# ---------------------------------------------------------------------------


class TestRateLimitConstants:
    def test_ip_auth_threshold_is_5(self):
        assert IP_AUTH_THRESHOLD == 5

    def test_ip_reset_threshold_is_3(self):
        assert IP_RESET_THRESHOLD == 3

    def test_reset_threshold_is_tighter_than_auth(self):
        assert IP_RESET_THRESHOLD < IP_AUTH_THRESHOLD


# ---------------------------------------------------------------------------
# increment_reset_attempts_ip — key and return value
# ---------------------------------------------------------------------------


class TestIncrementResetAttemptsIp:
    async def test_returns_count_from_pipeline(self):
        repo, pipe = _make_repo(pipeline_results=[4, 1])

        count = await repo.increment_reset_attempts_ip("1.2.3.4")

        assert count == 4

    async def test_uses_reset_attempts_ip_key(self):
        repo, pipe = _make_repo()

        await repo.increment_reset_attempts_ip("10.0.0.1")

        pipe.incr.assert_called_once_with("reset_attempts_ip:10.0.0.1")

    async def test_reset_and_auth_keys_are_distinct(self):
        """reset_attempts_ip and auth_attempts_ip must be independent Redis keys."""
        repo, pipe = _make_repo()

        await repo.increment_auth_attempts_ip("1.2.3.4")
        auth_key = pipe.incr.call_args[0][0]

        pipe.incr.reset_mock()
        await repo.increment_reset_attempts_ip("1.2.3.4")
        reset_key = pipe.incr.call_args[0][0]

        assert auth_key != reset_key
        assert "auth_attempts_ip" in auth_key
        assert "reset_attempts_ip" in reset_key

    async def test_reset_and_login_keys_are_distinct(self):
        """reset_attempts_ip and login_attempts_ip must be independent Redis keys."""
        repo, pipe = _make_repo()

        await repo.increment_ip_attempts("1.2.3.4")
        login_key = pipe.incr.call_args[0][0]

        pipe.incr.reset_mock()
        await repo.increment_reset_attempts_ip("1.2.3.4")
        reset_key = pipe.incr.call_args[0][0]

        assert login_key != reset_key
        assert "login_attempts_ip" in login_key
        assert "reset_attempts_ip" in reset_key
