"""Async SQLAlchemy engine and session factory.

The engine is a module-level singleton — one pool per process. FastAPI
dependency injection makes `get_db` per-request. `create_session` is an
async context manager for callers outside the DI system (e.g. middleware).
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engine: AsyncEngine | None = None
_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        from tradeforge.settings import get_settings

        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True, echo=False)
    return _engine


def _get_factory() -> async_sessionmaker[AsyncSession]:
    global _factory
    if _factory is None:
        _factory = async_sessionmaker(_get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a per-request async database session."""
    async with _get_factory()() as session:
        yield session


@asynccontextmanager
async def create_session() -> AsyncGenerator[AsyncSession, None]:
    """Standalone async session for use outside FastAPI DI (e.g. middleware)."""
    async with _get_factory()() as session:
        yield session
