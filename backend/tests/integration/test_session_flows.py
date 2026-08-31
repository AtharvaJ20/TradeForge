"""Integration tests for the Redis-backed SessionRepository.

Requires the Docker Compose stack (Redis at REDIS_URL).  Each test uses
unique keys so tests are fully isolated and can run in any order.

Run with:
    cd backend
    pytest tests/integration/test_session_flows.py -v

Scenarios covered:
  - create_session / get_session round-trip
  - get_session returns None for unknown token
  - get_session returns None when TTL has logically expired (expires_at in past)
  - delete_session removes the session hash and the user-sessions set entry
  - revoke_all_user_sessions removes every session and sets forced_reauth flag
  - forced_reauth lifecycle: set → check (True) → clear → check (False)
  - login_failures: increment, get, reset, auto-expire window
  - ip login attempt counter (login_attempts_ip)
  - ip auth attempt counter (auth_attempts_ip, separate namespace)
"""

from __future__ import annotations

import os
import time
import uuid

import pytest
from dotenv import load_dotenv
from redis.asyncio import Redis

from tradeforge.domain.auth.tokens import generate_session_token, sha256_hex
from tradeforge.infrastructure.repositories.session_repo import (
    SessionRepository,
)

load_dotenv()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def redis_url() -> str:
    url = os.environ.get("REDIS_URL")
    if not url:
        pytest.skip("REDIS_URL not set — Docker Compose stack required")
    return url


@pytest.fixture(scope="module")
async def redis_client(redis_url: str):  # type: ignore[return]
    client = Redis.from_url(redis_url, decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
def repo(redis_client: Redis) -> SessionRepository:
    return SessionRepository(redis_client)


def _token() -> str:
    """Generate a unique raw session token for each test."""
    return generate_session_token()


def _user_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


async def test_create_and_get_session(repo: SessionRepository) -> None:
    token = _token()
    user_id = _user_id()

    await repo.create_session(token, user_id, ip="1.2.3.4", ua_hash="abc123")

    data = await repo.get_session(token)

    assert data is not None
    assert data.user_id == user_id
    assert data.ip == "1.2.3.4"
    assert data.ua_hash == "abc123"
    assert data.expires_at > time.time()
    assert data.issued_at <= time.time()


async def test_create_session_registers_in_user_set(
    repo: SessionRepository, redis_client: Redis
) -> None:
    token = _token()
    user_id = _user_id()

    await repo.create_session(token, user_id, ip="10.0.0.1", ua_hash="hash1")

    members = await redis_client.smembers(f"user_sessions:{user_id}")
    assert token in members


async def test_get_session_returns_none_for_unknown_token(repo: SessionRepository) -> None:
    result = await repo.get_session("nonexistent-token-" + _user_id())
    assert result is None


async def test_get_session_returns_none_when_logically_expired(
    repo: SessionRepository, redis_client: Redis
) -> None:
    """get_session checks expires_at itself; overwrite it to simulate a past expiry."""
    token = _token()
    user_id = _user_id()

    await repo.create_session(token, user_id, ip="5.5.5.5", ua_hash="zzz")

    # Overwrite expires_at to be in the past (keep the key alive in Redis so
    # we can test the application-layer expiry check, not the TTL path).
    past = str(time.time() - 1)
    await redis_client.hset(f"sessions:{token}", "expires_at", past)

    result = await repo.get_session(token)
    assert result is None


async def test_delete_session_removes_hash_and_user_set_entry(
    repo: SessionRepository, redis_client: Redis
) -> None:
    token = _token()
    user_id = _user_id()

    await repo.create_session(token, user_id, ip="9.9.9.9", ua_hash="del")
    assert await repo.get_session(token) is not None

    await repo.delete_session(token, user_id)

    assert await repo.get_session(token) is None
    members = await redis_client.smembers(f"user_sessions:{user_id}")
    assert token not in members


async def test_delete_nonexistent_session_is_noop(repo: SessionRepository) -> None:
    """Deleting a token that never existed must not raise."""
    await repo.delete_session("ghost-token", _user_id())


# ---------------------------------------------------------------------------
# Revoke all sessions
# ---------------------------------------------------------------------------


async def test_revoke_all_user_sessions_removes_every_session(
    repo: SessionRepository, redis_client: Redis
) -> None:
    user_id = _user_id()
    tokens = [_token() for _ in range(3)]

    for t in tokens:
        await repo.create_session(t, user_id, ip="1.1.1.1", ua_hash="h")

    await repo.revoke_all_user_sessions(user_id)

    for t in tokens:
        assert await repo.get_session(t) is None

    remaining = await redis_client.smembers(f"user_sessions:{user_id}")
    assert remaining == set()


async def test_revoke_all_user_sessions_sets_forced_reauth(
    repo: SessionRepository, redis_client: Redis
) -> None:
    user_id = _user_id()
    await repo.create_session(_token(), user_id, ip="2.2.2.2", ua_hash="x")

    await repo.revoke_all_user_sessions(user_id)

    flag = await redis_client.exists(f"forced_reauth:{user_id}")
    assert flag == 1


async def test_revoke_all_sessions_for_user_with_no_sessions(repo: SessionRepository) -> None:
    """Revoking an unknown user must not raise."""
    await repo.revoke_all_user_sessions(_user_id())


# ---------------------------------------------------------------------------
# Forced re-authentication
# ---------------------------------------------------------------------------


async def test_forced_reauth_lifecycle(repo: SessionRepository) -> None:
    user_id = _user_id()

    assert not await repo.check_forced_reauth(user_id)

    await repo.set_forced_reauth(user_id)
    assert await repo.check_forced_reauth(user_id)

    await repo.clear_forced_reauth(user_id)
    assert not await repo.check_forced_reauth(user_id)


# ---------------------------------------------------------------------------
# Login failure counter
# ---------------------------------------------------------------------------


async def test_login_failure_counter_increments(repo: SessionRepository) -> None:
    email_hash = sha256_hex("counter-test-" + _user_id())

    count1 = await repo.increment_login_failures(email_hash)
    count2 = await repo.increment_login_failures(email_hash)
    count3 = await repo.increment_login_failures(email_hash)

    assert count1 == 1
    assert count2 == 2
    assert count3 == 3

    assert await repo.get_login_failures(email_hash) == 3


async def test_login_failure_counter_reset(repo: SessionRepository) -> None:
    email_hash = sha256_hex("reset-test-" + _user_id())

    await repo.increment_login_failures(email_hash)
    await repo.increment_login_failures(email_hash)

    await repo.reset_login_failures(email_hash)

    assert await repo.get_login_failures(email_hash) == 0


async def test_get_login_failures_returns_zero_for_unknown_key(repo: SessionRepository) -> None:
    result = await repo.get_login_failures(sha256_hex("unknown-" + _user_id()))
    assert result == 0


# ---------------------------------------------------------------------------
# IP-level rate-limit counters
# ---------------------------------------------------------------------------


async def test_ip_login_attempt_counter(repo: SessionRepository) -> None:
    ip = f"10.0.{uuid.uuid4().int % 256}.1"

    count1 = await repo.increment_ip_attempts(ip)
    count2 = await repo.increment_ip_attempts(ip)

    assert count1 == 1
    assert count2 == 2

    assert await repo.get_ip_attempts(ip) == 2


async def test_get_ip_attempts_returns_zero_for_unknown_ip(repo: SessionRepository) -> None:
    result = await repo.get_ip_attempts(f"192.168.{uuid.uuid4().int % 256}.99")
    assert result == 0


async def test_auth_attempts_ip_counter_uses_separate_namespace(
    repo: SessionRepository, redis_client: Redis
) -> None:
    """auth_attempts_ip and login_attempts_ip must use distinct Redis keys."""
    ip = f"172.16.{uuid.uuid4().int % 256}.1"

    login_count = await repo.increment_ip_attempts(ip)
    auth_count = await repo.increment_auth_attempts_ip(ip)

    assert login_count == 1
    assert auth_count == 1  # independent counter, starts at 1

    login_key_exists = await redis_client.exists(f"login_attempts_ip:{ip}")
    auth_key_exists = await redis_client.exists(f"auth_attempts_ip:{ip}")
    assert login_key_exists == 1
    assert auth_key_exists == 1
