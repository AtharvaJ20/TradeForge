"""API-layer tests for PATCH and DELETE /v1/accounts/* — B-15-09 through B-15-14.

TradingAccountService is injected via Depends(get_account_service) so the clean
override pattern (FastAPI dependency_overrides) is used throughout, matching the
auth test approach.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from tradeforge.application.trading_account_service import TradingAccountService
from tradeforge.domain.import_domain.errors import AccountNotFoundError
from tradeforge.domain.import_domain.types import TradingAccount

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_ID = uuid.uuid4()
_ACCOUNT_ID = uuid.uuid4()
_NOW = datetime(2026, 9, 5, 10, 0, 0, tzinfo=UTC)


def _make_account(
    *,
    display_name: str = "Main Account",
    account_type: str = "INDIVIDUAL",
    status: str = "ACTIVE",
) -> TradingAccount:
    return TradingAccount(
        id=_ACCOUNT_ID,
        user_id=_USER_ID,
        broker="ZERODHA",
        display_name=display_name,
        account_type=account_type,
        base_currency="INR",
        status=status,
        created_at=_NOW,
        updated_at=_NOW,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_account_svc() -> AsyncMock:
    return AsyncMock(spec=TradingAccountService)


@pytest.fixture(autouse=True)
def override_deps(mock_account_svc: AsyncMock) -> None:
    from tradeforge.api.v1.accounts import get_account_service
    from tradeforge.api.v1.deps import get_current_user_id
    from tradeforge.main import app

    app.dependency_overrides[get_current_user_id] = lambda: _USER_ID
    app.dependency_overrides[get_account_service] = lambda: mock_account_svc
    yield
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(get_account_service, None)


# ---------------------------------------------------------------------------
# B-15-09: PATCH /v1/accounts/{id} — updates display_name
# ---------------------------------------------------------------------------


async def test_patch_account_updates_display_name(
    http_client: AsyncClient, mock_account_svc: AsyncMock
) -> None:
    """B-15-09: PATCH /v1/accounts/{id} updates display_name and returns AccountOut."""
    updated = _make_account(display_name="Renamed Account")
    mock_account_svc.update.return_value = updated

    response = await http_client.patch(
        f"/v1/accounts/{_ACCOUNT_ID}",
        json={"display_name": "Renamed Account"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Renamed Account"
    assert body["status"] == "ACTIVE"
    mock_account_svc.update.assert_awaited_once()


# ---------------------------------------------------------------------------
# B-15-10: PATCH /v1/accounts/{id} — invalid account_type → 422
# ---------------------------------------------------------------------------


async def test_patch_account_invalid_account_type_422(
    http_client: AsyncClient, mock_account_svc: AsyncMock
) -> None:
    """B-15-10: PATCH /v1/accounts/{id} with invalid account_type returns 422."""
    mock_account_svc.update.side_effect = ValueError("Unsupported account_type")

    response = await http_client.patch(
        f"/v1/accounts/{_ACCOUNT_ID}",
        json={"account_type": "PROP"},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# B-15-11: PATCH /v1/accounts/{id} — another user's account → 404
# ---------------------------------------------------------------------------


async def test_patch_account_not_owned_returns_404(
    http_client: AsyncClient, mock_account_svc: AsyncMock
) -> None:
    """B-15-11: PATCH /v1/accounts/{id} for another user's account returns 404."""
    mock_account_svc.update.side_effect = AccountNotFoundError(uuid.uuid4())

    response = await http_client.patch(
        f"/v1/accounts/{uuid.uuid4()}",
        json={"display_name": "Hijack Attempt"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "ACCOUNT_NOT_FOUND"


# ---------------------------------------------------------------------------
# B-15-12: DELETE /v1/accounts/{id} — soft-deletes, subsequent status is INACTIVE
# ---------------------------------------------------------------------------


async def test_delete_account_soft_deletes(
    http_client: AsyncClient, mock_account_svc: AsyncMock
) -> None:
    """B-15-12: DELETE /v1/accounts/{id} sets status INACTIVE — returns 204."""
    mock_account_svc.deactivate.return_value = True

    response = await http_client.delete(f"/v1/accounts/{_ACCOUNT_ID}")

    assert response.status_code == 204
    mock_account_svc.deactivate.assert_awaited_once()
    call_kwargs = mock_account_svc.deactivate.call_args.kwargs
    assert call_kwargs["account_id"] == _ACCOUNT_ID
    assert call_kwargs["user_id"] == _USER_ID


# ---------------------------------------------------------------------------
# B-15-13: DELETE /v1/accounts/{id} — idempotent, second DELETE returns 204
# ---------------------------------------------------------------------------


async def test_delete_account_idempotent_second_call_returns_204(
    http_client: AsyncClient, mock_account_svc: AsyncMock
) -> None:
    """B-15-13: DELETE /v1/accounts/{id} is idempotent — already-INACTIVE account returns 204.

    The repo's UPDATE always sets updated_at=now(), so rowcount=1 for any owned
    account regardless of current status.  Service therefore returns True, and the
    API returns 204 on a repeated DELETE.
    """
    mock_account_svc.deactivate.return_value = True

    response = await http_client.delete(f"/v1/accounts/{_ACCOUNT_ID}")

    assert response.status_code == 204
    mock_account_svc.deactivate.assert_awaited_once()


# ---------------------------------------------------------------------------
# B-15-14: DELETE /v1/accounts/{id} — another user's account → 404
# ---------------------------------------------------------------------------


async def test_delete_account_not_owned_returns_404(
    http_client: AsyncClient, mock_account_svc: AsyncMock
) -> None:
    """B-15-14: DELETE /v1/accounts/{id} for another user's account returns 404."""
    mock_account_svc.deactivate.return_value = False

    response = await http_client.delete(f"/v1/accounts/{uuid.uuid4()}")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# B-18-27: POST /v1/accounts — starting_capital accepted and returned
# ---------------------------------------------------------------------------


async def test_create_account_with_starting_capital(
    http_client: AsyncClient, mock_account_svc: AsyncMock
) -> None:
    """B-18-27: POST /v1/accounts accepts starting_capital and returns it in AccountOut."""
    from decimal import Decimal

    account = TradingAccount(
        id=_ACCOUNT_ID,
        user_id=_USER_ID,
        broker="ZERODHA",
        display_name="Capital Account",
        account_type="INDIVIDUAL",
        base_currency="INR",
        status="ACTIVE",
        created_at=_NOW,
        updated_at=_NOW,
        starting_capital=Decimal("500000.00"),
    )
    mock_account_svc.create.return_value = account

    response = await http_client.post(
        "/v1/accounts",
        json={
            "broker": "ZERODHA",
            "display_name": "Capital Account",
            "account_type": "INDIVIDUAL",
            "starting_capital": "500000.00",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["starting_capital"] == "500000.00"
    call_kwargs = mock_account_svc.create.call_args.kwargs
    assert call_kwargs["starting_capital"] == Decimal("500000.00")


# ---------------------------------------------------------------------------
# B-18-28: PATCH /v1/accounts/{id} — starting_capital updated
# ---------------------------------------------------------------------------


async def test_patch_account_updates_starting_capital(
    http_client: AsyncClient, mock_account_svc: AsyncMock
) -> None:
    """B-18-28: PATCH /v1/accounts/{id} with starting_capital updates and returns it."""
    from decimal import Decimal

    updated = TradingAccount(
        id=_ACCOUNT_ID,
        user_id=_USER_ID,
        broker="ZERODHA",
        display_name="Main Account",
        account_type="INDIVIDUAL",
        base_currency="INR",
        status="ACTIVE",
        created_at=_NOW,
        updated_at=_NOW,
        starting_capital=Decimal("750000.00"),
    )
    mock_account_svc.update.return_value = updated

    response = await http_client.patch(
        f"/v1/accounts/{_ACCOUNT_ID}",
        json={"starting_capital": "750000.00"},
    )

    assert response.status_code == 200
    assert response.json()["starting_capital"] == "750000.00"
    call_kwargs = mock_account_svc.update.call_args.kwargs
    assert call_kwargs["starting_capital"] == Decimal("750000.00")


# ---------------------------------------------------------------------------
# B-18-29: POST /v1/accounts — starting_capital=0 or negative → 422
# ---------------------------------------------------------------------------


async def test_create_account_zero_starting_capital_returns_422(
    http_client: AsyncClient, mock_account_svc: AsyncMock
) -> None:
    """B-18-29: starting_capital must be > 0; zero and negative values return 422."""
    response_zero = await http_client.post(
        "/v1/accounts",
        json={
            "broker": "ZERODHA",
            "display_name": "Bad Capital",
            "account_type": "INDIVIDUAL",
            "starting_capital": "0",
        },
    )
    assert response_zero.status_code == 422

    response_neg = await http_client.post(
        "/v1/accounts",
        json={
            "broker": "ZERODHA",
            "display_name": "Bad Capital",
            "account_type": "INDIVIDUAL",
            "starting_capital": "-100",
        },
    )
    assert response_neg.status_code == 422
