"""Redis connection pool and FastAPI dependency.

The connection pool is a module-level singleton. Each request borrows a
connection via `get_redis()` and returns it to the pool on completion.
"""

import functools
from collections.abc import AsyncGenerator

from redis.asyncio import ConnectionPool, Redis


@functools.lru_cache(maxsize=1)
def _pool() -> ConnectionPool:
    from tradeforge.settings import get_settings

    settings = get_settings()
    return ConnectionPool.from_url(
        settings.redis_url,
        decode_responses=True,
        max_connections=20,
    )


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI dependency: yields a per-request Redis client backed by the shared pool."""
    client: Redis = Redis(connection_pool=_pool())
    try:
        yield client
    finally:
        await client.aclose()
