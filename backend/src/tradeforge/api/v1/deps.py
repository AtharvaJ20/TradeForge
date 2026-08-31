"""FastAPI dependencies shared across the v1 router.

Security notes:
  - get_current_user_id sources user_id from the Redis session, never from the
    request body or URL parameters (SR-AUTH-008).
  - Redis failure raises 503 so the request is never processed unauthenticated
    against a degraded session store (SR-AUTH-021 Rule D).
"""

import ipaddress
import uuid

from fastapi import Cookie, Depends, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.application.auth.email import get_email_sender
from tradeforge.application.auth.service import AuthService
from tradeforge.domain.auth.errors import RedisUnavailableError
from tradeforge.infrastructure.db import get_db
from tradeforge.infrastructure.redis_client import get_redis
from tradeforge.infrastructure.repositories.auth_repo import (
    AuditLogRepository,
    PendingResetRepository,
    PendingVerificationRepository,
)
from tradeforge.infrastructure.repositories.session_repo import SessionRepository
from tradeforge.infrastructure.repositories.user_repo import UserRepository
from tradeforge.infrastructure.models.user import User
from tradeforge.settings import get_settings

SESSION_COOKIE = "tf_session"

# ---------------------------------------------------------------------------
# Client IP extraction — trusted-proxy aware (BLOCKER-2)
# ---------------------------------------------------------------------------

_TrustedNetworks = frozenset[ipaddress.IPv4Network | ipaddress.IPv6Network]


def _parse_trusted_proxies(raw: str) -> _TrustedNetworks:
    networks: set[ipaddress.IPv4Network | ipaddress.IPv6Network] = set()
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            networks.add(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            pass  # ignore malformed entries; fail open (use direct peer)
    return frozenset(networks)


def _ip_in_trusted(ip_str: str, trusted: _TrustedNetworks) -> bool:
    if not trusted:
        return False
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(addr in net for net in trusted)


def get_client_ip(request: Request) -> str:
    """Return the real client IP, trusting X-Forwarded-For only from configured proxies.

    When TRUSTED_PROXIES is empty (default), the direct peer IP is always used,
    preventing XFF spoofing from any client. When the direct peer is a trusted
    proxy, the rightmost non-trusted IP in X-Forwarded-For is returned, which
    is the actual client regardless of how many trusted hops are in the chain.
    """
    trusted = _parse_trusted_proxies(get_settings().trusted_proxies)
    direct_peer = request.client.host if request.client else ""

    if not _ip_in_trusted(direct_peer, trusted):
        # Direct peer is not a known proxy — trust it; ignore XFF.
        return direct_peer or "127.0.0.1"

    # Direct peer is a trusted proxy — extract real client from XFF.
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if not forwarded_for:
        return direct_peer

    # Walk right-to-left: the rightmost non-trusted IP is the true client.
    for ip in reversed([p.strip() for p in forwarded_for.split(",")]):
        if ip and not _ip_in_trusted(ip, trusted):
            return ip

    # All IPs in XFF are trusted proxies (edge case) — fall back to direct peer.
    return direct_peer


async def get_auth_service(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AuthService:
    return AuthService(
        user_repo=UserRepository(db),
        audit_repo=AuditLogRepository(db),
        verification_repo=PendingVerificationRepository(db),
        reset_repo=PendingResetRepository(db),
        session_repo=SessionRepository(redis),
        email_sender=get_email_sender(),
    )


async def get_current_user_id(
    redis: Redis = Depends(get_redis),
    tf_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> uuid.UUID:
    """Resolve the session cookie to an authenticated user_id (fail-closed on Redis errors)."""
    if not tf_session:
        raise HTTPException(status_code=401, detail="NOT_AUTHENTICATED")

    session_repo = SessionRepository(redis)
    try:
        session = await session_repo.get_session(tf_session)
    except RedisUnavailableError:
        raise HTTPException(status_code=503, detail="SERVICE_UNAVAILABLE")

    if session is None:
        raise HTTPException(status_code=401, detail="SESSION_EXPIRED")

    try:
        if await session_repo.check_forced_reauth(session.user_id):
            raise HTTPException(status_code=401, detail="REAUTH_REQUIRED")
    except RedisUnavailableError:
        raise HTTPException(status_code=503, detail="SERVICE_UNAVAILABLE")

    return uuid.UUID(session.user_id)


async def get_current_user(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve user_id to a User ORM row for endpoints that need profile data."""
    from tradeforge.infrastructure.repositories.user_repo import UserRepository

    user = await UserRepository(db).find_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="USER_NOT_FOUND")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="ADMIN_REQUIRED")
    return user
