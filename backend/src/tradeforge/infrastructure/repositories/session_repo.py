"""Redis-backed session repository.

All session state lives in Redis. If Redis is unreachable, authenticated
endpoints fail with 503 rather than falling back to in-memory state (SR-AUTH-021 Rule D).

Key schema:
  sessions:{token}          → Hash {user_id, issued_at, expires_at, ip, ua_hash}  TTL=30d
  user_sessions:{user_id}   → Set of active session tokens
  forced_reauth:{user_id}   → "1"  TTL=24h
  login_failures:{key}      → integer counter  TTL=15min (fixed window)
  login_attempts_ip:{ip}    → integer counter  TTL=60s (fixed window) — login only
  auth_attempts_ip:{ip}     → integer counter  TTL=60s (fixed window) — register/verify-email/reset
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from redis.asyncio import Redis
from redis.exceptions import RedisError

from tradeforge.domain.auth.errors import RedisUnavailableError

SESSION_TTL = 30 * 24 * 60 * 60  # 30 days
FORCED_REAUTH_TTL = 24 * 60 * 60  # 24 hours
LOGIN_FAILURE_WINDOW = 15 * 60  # 15 minutes
LOGIN_FAILURE_THRESHOLD = 5
IP_ATTEMPT_WINDOW = 60  # 1 minute
IP_ATTEMPT_THRESHOLD = 50


@dataclass
class SessionData:
    user_id: str
    issued_at: float
    expires_at: float
    ip: str
    ua_hash: str


class SessionRepository:
    def __init__(self, redis: Redis[str]) -> None:
        self._r = redis

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def create_session(self, token: str, user_id: str, ip: str, ua_hash: str) -> None:
        now = time.time()
        expires_at = now + SESSION_TTL
        session_key = f"sessions:{token}"
        user_key = f"user_sessions:{user_id}"
        try:
            async with self._r.pipeline(transaction=False) as pipe:
                await pipe.hset(
                    session_key,
                    mapping={
                        "user_id": user_id,
                        "issued_at": str(now),
                        "expires_at": str(expires_at),
                        "ip": ip,
                        "ua_hash": ua_hash,
                    },
                )
                await pipe.expire(session_key, SESSION_TTL)
                await pipe.sadd(user_key, token)
                await pipe.execute()
        except RedisError as exc:
            raise RedisUnavailableError("Redis unavailable during session creation") from exc

    async def get_session(self, token: str) -> SessionData | None:
        """Returns None if session not found or expired. Raises RedisUnavailableError on failure."""
        try:
            data = await self._r.hgetall(f"sessions:{token}")
        except RedisError as exc:
            raise RedisUnavailableError("Redis unavailable during session lookup") from exc
        if not data:
            return None
        expires_at = float(data["expires_at"])
        if time.time() > expires_at:
            return None
        return SessionData(
            user_id=data["user_id"],
            issued_at=float(data["issued_at"]),
            expires_at=expires_at,
            ip=data["ip"],
            ua_hash=data["ua_hash"],
        )

    async def delete_session(self, token: str, user_id: str) -> None:
        try:
            async with self._r.pipeline(transaction=False) as pipe:
                await pipe.delete(f"sessions:{token}")
                await pipe.srem(f"user_sessions:{user_id}", token)
                await pipe.execute()
        except RedisError as exc:
            raise RedisUnavailableError("Redis unavailable during session deletion") from exc

    async def revoke_all_user_sessions(self, user_id: str) -> None:
        """Revoke every session for a user and set forced_reauth (SR-AUTH-010)."""
        user_key = f"user_sessions:{user_id}"
        try:
            tokens = await self._r.smembers(user_key)
            async with self._r.pipeline(transaction=False) as pipe:
                for token in tokens:
                    await pipe.delete(f"sessions:{token}")
                await pipe.delete(user_key)
                await pipe.set(f"forced_reauth:{user_id}", "1", ex=FORCED_REAUTH_TTL)
                await pipe.execute()
        except RedisError as exc:
            raise RedisUnavailableError("Redis unavailable during session revocation") from exc

    # ------------------------------------------------------------------
    # Forced re-authentication
    # ------------------------------------------------------------------

    async def set_forced_reauth(self, user_id: str) -> None:
        try:
            await self._r.set(f"forced_reauth:{user_id}", "1", ex=FORCED_REAUTH_TTL)
        except RedisError as exc:
            raise RedisUnavailableError("Redis unavailable") from exc

    async def check_forced_reauth(self, user_id: str) -> bool:
        try:
            return bool(await self._r.exists(f"forced_reauth:{user_id}"))
        except RedisError as exc:
            raise RedisUnavailableError("Redis unavailable") from exc

    async def clear_forced_reauth(self, user_id: str) -> None:
        try:
            await self._r.delete(f"forced_reauth:{user_id}")
        except RedisError as exc:
            raise RedisUnavailableError("Redis unavailable") from exc

    # ------------------------------------------------------------------
    # Rate limiting — fixed window counters
    # ------------------------------------------------------------------

    async def increment_login_failures(self, email_hash: str) -> int:
        """Increment per-account failure counter; return new count."""
        key = f"login_failures:{email_hash}"
        try:
            async with self._r.pipeline(transaction=False) as pipe:
                await pipe.incr(key)
                await pipe.expire(key, LOGIN_FAILURE_WINDOW, nx=True)
                results = await pipe.execute()
            return int(results[0])
        except RedisError as exc:
            raise RedisUnavailableError("Redis unavailable") from exc

    async def reset_login_failures(self, email_hash: str) -> None:
        try:
            await self._r.delete(f"login_failures:{email_hash}")
        except RedisError as exc:
            raise RedisUnavailableError("Redis unavailable") from exc

    async def get_login_failures(self, email_hash: str) -> int:
        try:
            val = await self._r.get(f"login_failures:{email_hash}")
            return int(val) if val else 0
        except RedisError as exc:
            raise RedisUnavailableError("Redis unavailable") from exc

    async def increment_ip_attempts(self, ip: str) -> int:
        """Increment per-IP attempt counter; return new count."""
        key = f"login_attempts_ip:{ip}"
        try:
            async with self._r.pipeline(transaction=False) as pipe:
                await pipe.incr(key)
                await pipe.expire(key, IP_ATTEMPT_WINDOW, nx=True)
                results = await pipe.execute()
            return int(results[0])
        except RedisError as exc:
            raise RedisUnavailableError("Redis unavailable") from exc

    async def get_ip_attempts(self, ip: str) -> int:
        try:
            val = await self._r.get(f"login_attempts_ip:{ip}")
            return int(val) if val else 0
        except RedisError as exc:
            raise RedisUnavailableError("Redis unavailable") from exc

    async def increment_auth_attempts_ip(self, ip: str) -> int:
        """Increment per-IP rate-limit counter for register/verify-email/reset endpoints.

        Uses a separate key from login attempts so the two windows don't bleed
        into each other. Shares the same window and threshold as login IP limiting.
        """
        key = f"auth_attempts_ip:{ip}"
        try:
            async with self._r.pipeline(transaction=False) as pipe:
                await pipe.incr(key)
                await pipe.expire(key, IP_ATTEMPT_WINDOW, nx=True)
                results = await pipe.execute()
            return int(results[0])
        except RedisError as exc:
            raise RedisUnavailableError("Redis unavailable") from exc
