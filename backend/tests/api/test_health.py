"""Smoke test — the /health endpoint responds correctly.

This verifies the application factory wires up without error and the FastAPI
app is importable. No database or Redis connection is required.
"""

from httpx import AsyncClient


async def test_health_returns_ok(http_client: AsyncClient) -> None:
    response = await http_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
