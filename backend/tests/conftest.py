"""Root conftest — fixtures shared across all test tiers.

Test tiers (per ADR-001 testing architecture):
  tests/unit/        — pure domain logic; no DB, no network, no app startup
  tests/integration/ — real DB + Redis via Docker Compose; no mocked drivers
  tests/api/         — FastAPI test client; real or in-memory DB

Environment for tests:
  Set TEST_DATABASE_URL (for integration/api tests) in the CI environment or
  a local .env.test file. Unit tests need no environment variables.
"""

import os

import pytest
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient

# Load .env for local development runs. CI injects env vars directly.
# This is a no-op if .env does not exist.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))


@pytest.fixture
async def http_client() -> AsyncClient:
    """Async HTTP client wired to the FastAPI app via ASGI transport.

    No real network connection is made. Suitable for api-layer tests.
    Requires the application's backing services (DB, Redis) to be available
    if routes perform real I/O — use the Docker Compose stack for integration
    scenarios and mock dependencies for unit-level api tests.
    """
    from tradeforge.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
