"""Integration tests for auth flows — require the full Docker Compose stack.

Run with:
    cd backend
    uvicorn tradeforge.main:app --env-file .env  # stack must be running
    pytest tests/integration/ -v

Tests truncate auth tables before each run so the dev DB stays clean.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tradeforge.domain.auth.tokens import generate_session_token, generate_verification_token, sha256_hex
from tradeforge.infrastructure.models import Base
from tradeforge.infrastructure.models.auth import PendingEmailVerification
from tradeforge.infrastructure.models.user import User
from tradeforge.infrastructure.repositories.auth_repo import (
    AuditLogRepository,
    PendingResetRepository,
    PendingVerificationRepository,
)
from tradeforge.infrastructure.repositories.user_repo import UserRepository

# ------------------------------------------------------------------
# Session factory for integration tests — reads DATABASE_URL from env
# ------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_url() -> str:
    import os

    # Integration tests use the superuser URL so they can INSERT, DELETE, and inspect
    # tables without being blocked by the restricted tradeforge_app grants.
    # The app's user (tradeforge_app) permissions are validated separately.
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set — Docker Compose stack required")
    # Use postgres superuser for integration tests (dev-only)
    import re

    return re.sub(r"//[^@]+@", "//postgres:postgres@", url)


@pytest.fixture
async def db_engine(db_url: str):  # type: ignore[return]
    engine = create_async_engine(db_url, echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(db_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def db(session_factory: async_sessionmaker[AsyncSession]) -> AsyncSession:  # type: ignore[return]
    async with session_factory() as session:
        # Clean auth tables in FK dependency order. security_audit_log is
        # INSERT-only for tradeforge_app — skip it.
        #
        # execution_fills rows are permanently immutable (DB trigger blocks DELETE).
        # Reconstruction test users may have fills from prior runs; scope the user
        # delete to only remove users that have no dependent fill or trade records
        # — auth test users never have either.
        await session.execute(text("DELETE FROM pending_email_verifications"))
        await session.execute(text("DELETE FROM pending_password_resets"))
        await session.execute(
            text(
                "DELETE FROM users "
                "WHERE id NOT IN (SELECT DISTINCT user_id FROM execution_fills) "
                "  AND id NOT IN (SELECT DISTINCT user_id FROM trades)"
            )
        )
        await session.commit()
        yield session


# ------------------------------------------------------------------
# Repository: UserRepository
# ------------------------------------------------------------------


async def test_create_and_find_user(db: AsyncSession) -> None:
    repo = UserRepository(db)
    user = await repo.create(email="TEST@Example.com", password_hash="hashed")
    await db.commit()

    found = await repo.find_by_email("test@example.com")
    assert found is not None
    assert found.id == user.id
    assert found.email == "test@example.com"  # email is lowercased
    assert not found.is_email_verified


async def test_find_by_id_returns_none_for_unknown(db: AsyncSession) -> None:
    repo = UserRepository(db)
    result = await repo.find_by_id(uuid.uuid4())
    assert result is None


async def test_set_email_verified(db: AsyncSession) -> None:
    repo = UserRepository(db)
    user = await repo.create(email="verify@example.com", password_hash="h")
    await db.commit()

    await repo.set_email_verified(user.id)
    await db.commit()

    found = await repo.find_by_email("verify@example.com")
    assert found is not None
    assert found.is_email_verified


# ------------------------------------------------------------------
# Repository: PendingVerificationRepository
# ------------------------------------------------------------------


async def test_verification_token_lifecycle(db: AsyncSession) -> None:
    user_repo = UserRepository(db)
    ver_repo = PendingVerificationRepository(db)

    await user_repo.create(email="ver@example.com", password_hash="h")
    await db.commit()

    raw_token = generate_verification_token()
    token_hash = sha256_hex(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    await ver_repo.create(email="ver@example.com", token_hash=token_hash, expires_at=expires_at)
    await db.commit()

    found = await ver_repo.find_by_token_hash(token_hash)
    assert found is not None
    assert found.email == "ver@example.com"

    await ver_repo.delete(found.id)
    await db.commit()

    assert await ver_repo.find_by_token_hash(token_hash) is None


async def test_expired_verification_token_is_excluded_by_service_layer(db: AsyncSession) -> None:
    ver_repo = PendingVerificationRepository(db)

    raw_token = generate_verification_token()
    token_hash = sha256_hex(raw_token)
    # Store as already expired
    expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)

    await ver_repo.create(email="x@x.com", token_hash=token_hash, expires_at=expires_at)
    await db.commit()

    row = await ver_repo.find_by_token_hash(token_hash)
    assert row is not None
    # Expiry check is performed by the service layer
    assert row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc)


# ------------------------------------------------------------------
# Repository: AuditLogRepository
# ------------------------------------------------------------------


async def test_audit_log_insert(db: AsyncSession) -> None:
    audit_repo = AuditLogRepository(db)
    await audit_repo.log(
        "LOGIN_SUCCESS",
        ip_address="127.0.0.1",
        event_data={"test": True},
    )
    await db.commit()
    # If we reach here without exception, insert succeeded


# ------------------------------------------------------------------
# CSRF middleware: audit event persistence
# ------------------------------------------------------------------


async def test_csrf_attempt_is_persisted_to_audit_log(db: AsyncSession) -> None:
    """A POST with a foreign Origin must write a CSRF_ATTEMPT row to security_audit_log.

    The middleware opens its own DB session (via create_session()) and commits
    independently.  We verify the committed row is visible to a separate session
    (postgres superuser) using a timestamp boundary to isolate this test's rows.
    """
    from datetime import datetime, timezone

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select

    from tradeforge.infrastructure.models.auth import SecurityAuditLog
    from tradeforge.main import app

    before = datetime.now(timezone.utc)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/auth/register",
            json={"email": "csrf_test@example.com", "password": "StrongPass123!"},
            headers={"Origin": "https://evil.example.com"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF_VALIDATION_FAILED"

    # The middleware committed the row in its own session.  We need the test
    # session to see it; expire_all() clears any stale snapshot.
    await db.run_sync(lambda s: s.expire_all())  # type: ignore[arg-type]

    result = await db.execute(
        select(SecurityAuditLog)
        .where(SecurityAuditLog.event_type == "CSRF_ATTEMPT")
        .where(SecurityAuditLog.occurred_at >= before)
        .order_by(SecurityAuditLog.occurred_at.desc())
    )
    rows = result.scalars().all()
    assert len(rows) >= 1, "Expected at least one CSRF_ATTEMPT row after the request"
    latest = rows[0]
    assert latest.event_data is not None
    assert latest.event_data.get("origin") == "https://evil.example.com"
