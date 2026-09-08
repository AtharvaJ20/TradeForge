"""Backend API tests for Step 17 — Import Trades Screen.

Tests B-17-01 through B-17-16:
  B-17-01 to B-17-07: POST /v1/accounts/{account_id}/import — status field + error codes
  B-17-08:            POST unauthenticated → 401
  B-17-09 to B-17-13: GET /v1/imports — import history list
  B-17-14:            POST file > 10 MB → 413 FILE_TOO_LARGE
  B-17-15:            POST CSV with mix of valid+invalid rows → 201 status=PARTIAL
  B-17-16:            POST CSV with all malformed rows → 201 status=FAILED

All service and repository dependencies are replaced with AsyncMock via
FastAPI dependency_overrides so no DB or Redis connection is required.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from httpx import AsyncClient

from tradeforge.application.import_service import ImportService, ImportSummary
from tradeforge.application.trading_account_service import TradingAccountService
from tradeforge.domain.import_domain.errors import (
    AccountInactiveError,
    AccountNotFoundError,
    DuplicateImportError,
    EmptyFileError,
    MissingProductTypeError,
    UnrecognizedFileError,
)
from tradeforge.infrastructure.models.import_record import ImportRecord
from tradeforge.infrastructure.repositories.import_record_repo import ImportRecordRepository

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_USER_ID = uuid.uuid4()
_ACCOUNT_ID = uuid.uuid4()
_ACCOUNT2_ID = uuid.uuid4()
_NOW = datetime(2026, 9, 8, 10, 0, 0, tzinfo=UTC)
_RECORD_ID = uuid.uuid4()

_CSV_BYTES = b"symbol,trade_date\nRELIANCE,2024-10-15\n"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_summary(
    *,
    status: str = "COMPLETE",
    fills_ingested: int = 5,
    fills_skipped: int = 0,
    row_errors: int = 0,
    trades_created: int = 3,
    trades_closed: int = 1,
    pnl_succeeded: int = 1,
    pnl_failed: int = 0,
) -> ImportSummary:
    return ImportSummary(
        import_record_id=_RECORD_ID,
        fills_ingested=fills_ingested,
        fills_skipped=fills_skipped,
        row_errors=row_errors,
        trades_created=trades_created,
        trades_closed=trades_closed,
        pnl_succeeded=pnl_succeeded,
        pnl_failed=pnl_failed,
        status=status,
    )


def _make_import_record(
    *,
    record_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
    broker: str = "ZERODHA",
    file_name: str | None = "trades.csv",
    row_count: int = 50,
    error_count: int = 0,
    status: str = "COMPLETE",
) -> ImportRecord:
    return ImportRecord(
        id=record_id or uuid.uuid4(),
        account_id=account_id or _ACCOUNT_ID,
        broker=broker,
        file_hash="a" * 64,
        file_name=file_name,
        row_count=row_count,
        error_count=error_count,
        status=status,
        imported_at=_NOW,
        created_at=_NOW,
    )


async def _raise_401() -> uuid.UUID:
    raise HTTPException(status_code=401, detail="NOT_AUTHENTICATED")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_import_svc() -> AsyncMock:
    return AsyncMock(spec=ImportService)


@pytest.fixture
def mock_account_svc() -> AsyncMock:
    return AsyncMock(spec=TradingAccountService)


@pytest.fixture
def mock_import_record_repo() -> AsyncMock:
    return AsyncMock(spec=ImportRecordRepository)


# ===========================================================================
# POST /v1/accounts/{account_id}/import — authenticated tests
# ===========================================================================


class TestPostImport:
    @pytest.fixture(autouse=True)
    def _override_deps(self, mock_import_svc: AsyncMock) -> None:
        from tradeforge.api.v1.accounts import get_import_service
        from tradeforge.api.v1.deps import get_current_user_id
        from tradeforge.main import app

        app.dependency_overrides[get_current_user_id] = lambda: _USER_ID
        app.dependency_overrides[get_import_service] = lambda: mock_import_svc
        yield
        app.dependency_overrides.pop(get_current_user_id, None)
        app.dependency_overrides.pop(get_import_service, None)

    # -----------------------------------------------------------------------
    # B-17-01: valid Zerodha CSV → 201, status=COMPLETE
    # -----------------------------------------------------------------------

    async def test_valid_csv_returns_201_with_complete_status(
        self, http_client: AsyncClient, mock_import_svc: AsyncMock
    ) -> None:
        """B-17-01: valid CSV → 201; status="COMPLETE"; import_record_id is valid UUID."""
        mock_import_svc.import_fills.return_value = _make_summary(
            status="COMPLETE", fills_ingested=10
        )

        response = await http_client.post(
            f"/v1/accounts/{_ACCOUNT_ID}/import",
            files={"file": ("trades.csv", _CSV_BYTES, "text/csv")},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "COMPLETE"
        assert body["fills_ingested"] == 10
        assert uuid.UUID(body["import_record_id"]) == _RECORD_ID

    # -----------------------------------------------------------------------
    # B-17-02: duplicate file for same account → 409 DUPLICATE_IMPORT
    # -----------------------------------------------------------------------

    async def test_duplicate_file_returns_409(
        self, http_client: AsyncClient, mock_import_svc: AsyncMock
    ) -> None:
        """B-17-02: same file for same account → 409 DUPLICATE_IMPORT."""
        mock_import_svc.import_fills.side_effect = DuplicateImportError("abc", _ACCOUNT_ID)

        response = await http_client.post(
            f"/v1/accounts/{_ACCOUNT_ID}/import",
            files={"file": ("trades.csv", _CSV_BYTES, "text/csv")},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "DUPLICATE_IMPORT"

    # -----------------------------------------------------------------------
    # B-17-03: same file, different account (same user) → 201
    # -----------------------------------------------------------------------

    async def test_same_file_different_account_returns_201(
        self, http_client: AsyncClient, mock_import_svc: AsyncMock
    ) -> None:
        """B-17-03: same file content for a different account → 201.

        (file_hash, account_id) uniqueness is per-account; different account_id
        means no duplicate constraint applies.
        """
        mock_import_svc.import_fills.return_value = _make_summary(status="COMPLETE")

        response = await http_client.post(
            f"/v1/accounts/{_ACCOUNT2_ID}/import",
            files={"file": ("trades.csv", _CSV_BYTES, "text/csv")},
        )

        assert response.status_code == 201
        assert response.json()["status"] == "COMPLETE"

    # -----------------------------------------------------------------------
    # B-17-04: non-CSV file → 422 UNRECOGNIZED_FILE_FORMAT
    # -----------------------------------------------------------------------

    async def test_non_csv_file_returns_422_unrecognized(
        self, http_client: AsyncClient, mock_import_svc: AsyncMock
    ) -> None:
        """B-17-04: non-CSV file → 422 UNRECOGNIZED_FILE_FORMAT."""
        mock_import_svc.import_fills.side_effect = UnrecognizedFileError()

        response = await http_client.post(
            f"/v1/accounts/{_ACCOUNT_ID}/import",
            files={"file": ("report.pdf", b"%PDF-1.4", "application/pdf")},
        )

        assert response.status_code == 422
        assert response.json()["detail"] == "UNRECOGNIZED_FILE_FORMAT"

    # -----------------------------------------------------------------------
    # B-17-05: header-only CSV → 422 EMPTY_FILE (G-17-1)
    # -----------------------------------------------------------------------

    async def test_header_only_csv_returns_422_empty_file(
        self, http_client: AsyncClient, mock_import_svc: AsyncMock
    ) -> None:
        """B-17-05: header-only CSV → 422 EMPTY_FILE.

        ZerodhaAdapter raises EmptyFileError for zero-data-row CSVs, which
        the route handler maps to 422 EMPTY_FILE before ImportService computes
        any status. The status="EMPTY" success-path is unreachable via Zerodha.
        """
        mock_import_svc.import_fills.side_effect = EmptyFileError()

        response = await http_client.post(
            f"/v1/accounts/{_ACCOUNT_ID}/import",
            files={"file": ("trades.csv", b"symbol,trade_date\n", "text/csv")},
        )

        assert response.status_code == 422
        assert response.json()["detail"] == "EMPTY_FILE"

    # -----------------------------------------------------------------------
    # B-17-06: another user's account_id → 404 ACCOUNT_NOT_FOUND
    # -----------------------------------------------------------------------

    async def test_other_users_account_returns_404(
        self, http_client: AsyncClient, mock_import_svc: AsyncMock
    ) -> None:
        """B-17-06: account_id not owned by authenticated user → 404."""
        mock_import_svc.import_fills.side_effect = AccountNotFoundError(uuid.uuid4())

        response = await http_client.post(
            f"/v1/accounts/{uuid.uuid4()}/import",
            files={"file": ("trades.csv", _CSV_BYTES, "text/csv")},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "ACCOUNT_NOT_FOUND"

    # -----------------------------------------------------------------------
    # B-17-07: INACTIVE account → 422 ACCOUNT_INACTIVE (A-17-3)
    # -----------------------------------------------------------------------

    async def test_inactive_account_returns_422(
        self, http_client: AsyncClient, mock_import_svc: AsyncMock
    ) -> None:
        """B-17-07: INACTIVE account → 422 ACCOUNT_INACTIVE (not 404)."""
        mock_import_svc.import_fills.side_effect = AccountInactiveError(_ACCOUNT_ID)

        response = await http_client.post(
            f"/v1/accounts/{_ACCOUNT_ID}/import",
            files={"file": ("trades.csv", _CSV_BYTES, "text/csv")},
        )

        assert response.status_code == 422
        assert response.json()["detail"] == "ACCOUNT_INACTIVE"

    # -----------------------------------------------------------------------
    # B-17-14: file > 10 MB → 413 FILE_TOO_LARGE (D-17-1)
    # -----------------------------------------------------------------------

    async def test_file_over_10mb_returns_413(
        self, http_client: AsyncClient, mock_import_svc: AsyncMock
    ) -> None:
        """B-17-14: file content > 10 MB → 413 FILE_TOO_LARGE.

        The size check fires in the route handler before import_fills() is called.
        """
        large_content = b"x" * (10 * 1024 * 1024 + 1)

        response = await http_client.post(
            f"/v1/accounts/{_ACCOUNT_ID}/import",
            files={"file": ("huge.csv", large_content, "text/csv")},
        )

        assert response.status_code == 413
        assert response.json()["detail"] == "FILE_TOO_LARGE"
        mock_import_svc.import_fills.assert_not_awaited()

    # -----------------------------------------------------------------------
    # B-17-15: CSV with mix of valid and invalid rows → 201 status=PARTIAL (QA-17-1)
    # -----------------------------------------------------------------------

    async def test_partial_import_returns_201_with_partial_status(
        self, http_client: AsyncClient, mock_import_svc: AsyncMock
    ) -> None:
        """B-17-15: CSV with valid EQ rows + rows the adapter rejects → 201, status=PARTIAL.

        Represents a file where some rows succeed (fills_ingested > 0) and some
        produce parse errors (row_errors > 0). Exercises the PARTIAL status code path.
        """
        mock_import_svc.import_fills.return_value = _make_summary(
            status="PARTIAL",
            fills_ingested=45,
            fills_skipped=0,
            row_errors=5,
        )

        response = await http_client.post(
            f"/v1/accounts/{_ACCOUNT_ID}/import",
            files={"file": ("trades.csv", _CSV_BYTES, "text/csv")},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "PARTIAL"
        assert body["fills_ingested"] == 45
        assert body["row_errors"] == 5

    # -----------------------------------------------------------------------
    # B-17-16: all-malformed CSV → 201 status=FAILED (QA-17-1)
    # -----------------------------------------------------------------------

    async def test_all_malformed_rows_returns_201_with_failed_status(
        self, http_client: AsyncClient, mock_import_svc: AsyncMock
    ) -> None:
        """B-17-16: CSV where every data row is malformed → 201, status=FAILED.

        Represents a file where all rows raise InvalidFillError; fills_ingested == 0
        and fills_skipped == 0 with row_errors > 0, triggering status=FAILED.
        """
        mock_import_svc.import_fills.return_value = _make_summary(
            status="FAILED",
            fills_ingested=0,
            fills_skipped=0,
            row_errors=10,
        )

        response = await http_client.post(
            f"/v1/accounts/{_ACCOUNT_ID}/import",
            files={"file": ("trades.csv", _CSV_BYTES, "text/csv")},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "FAILED"
        assert body["fills_ingested"] == 0
        assert body["fills_skipped"] == 0
        assert body["row_errors"] == 10

    # -----------------------------------------------------------------------
    # Additional: 422 MISSING_PRODUCT_TYPE
    # -----------------------------------------------------------------------

    async def test_missing_product_type_returns_422(
        self, http_client: AsyncClient, mock_import_svc: AsyncMock
    ) -> None:
        """POST with F&O CSV lacking product column and no hint → 422 MISSING_PRODUCT_TYPE."""
        mock_import_svc.import_fills.side_effect = MissingProductTypeError()

        response = await http_client.post(
            f"/v1/accounts/{_ACCOUNT_ID}/import",
            files={"file": ("trades.csv", _CSV_BYTES, "text/csv")},
        )

        assert response.status_code == 422
        assert response.json()["detail"] == "MISSING_PRODUCT_TYPE"


# ===========================================================================
# POST /v1/accounts/{account_id}/import — unauthenticated
# ===========================================================================


class TestPostImportUnauthenticated:
    @pytest.fixture(autouse=True)
    def _override_deps(self, mock_import_svc: AsyncMock) -> None:
        from tradeforge.api.v1.accounts import get_import_service
        from tradeforge.api.v1.deps import get_current_user_id
        from tradeforge.main import app

        app.dependency_overrides[get_current_user_id] = _raise_401
        app.dependency_overrides[get_import_service] = lambda: mock_import_svc
        yield
        app.dependency_overrides.pop(get_current_user_id, None)
        app.dependency_overrides.pop(get_import_service, None)

    async def test_post_unauthenticated_returns_401(
        self, http_client: AsyncClient, mock_import_svc: AsyncMock
    ) -> None:
        """B-17-08: POST /v1/accounts/{account_id}/import unauthenticated → 401."""
        response = await http_client.post(
            f"/v1/accounts/{_ACCOUNT_ID}/import",
            files={"file": ("trades.csv", _CSV_BYTES, "text/csv")},
        )

        assert response.status_code == 401
        mock_import_svc.import_fills.assert_not_awaited()


# ===========================================================================
# GET /v1/imports — authenticated tests
# ===========================================================================


class TestGetImports:
    @pytest.fixture(autouse=True)
    def _override_deps(
        self,
        mock_account_svc: AsyncMock,
        mock_import_record_repo: AsyncMock,
    ) -> None:
        from tradeforge.api.v1.deps import get_current_user_id
        from tradeforge.api.v1.imports import get_account_service, get_import_record_repo
        from tradeforge.main import app

        app.dependency_overrides[get_current_user_id] = lambda: _USER_ID
        app.dependency_overrides[get_account_service] = lambda: mock_account_svc
        app.dependency_overrides[get_import_record_repo] = lambda: mock_import_record_repo
        yield
        app.dependency_overrides.pop(get_current_user_id, None)
        app.dependency_overrides.pop(get_account_service, None)
        app.dependency_overrides.pop(get_import_record_repo, None)

    # -----------------------------------------------------------------------
    # B-17-09: GET returns list for owned account
    # -----------------------------------------------------------------------

    async def test_get_imports_returns_list_for_owned_account(
        self,
        http_client: AsyncClient,
        mock_account_svc: AsyncMock,
        mock_import_record_repo: AsyncMock,
    ) -> None:
        """B-17-09: GET /v1/imports?account_id=<uuid> returns list; asserts status and broker."""
        from tradeforge.domain.import_domain.types import TradingAccount

        mock_account_svc.get.return_value = TradingAccount(
            id=_ACCOUNT_ID,
            user_id=_USER_ID,
            broker="ZERODHA",
            display_name="Main",
            account_type="INDIVIDUAL",
            base_currency="INR",
            status="ACTIVE",
            created_at=_NOW,
            updated_at=_NOW,
        )
        mock_import_record_repo.list_by_account.return_value = [
            _make_import_record(status="COMPLETE", broker="ZERODHA"),
        ]

        response = await http_client.get(f"/v1/imports?account_id={_ACCOUNT_ID}")

        assert response.status_code == 200
        body = response.json()
        assert len(body) >= 1
        assert body[0]["status"] == "COMPLETE"
        assert body[0]["broker"] == "ZERODHA"

    # -----------------------------------------------------------------------
    # B-17-10: GET for another user's account → 404
    # -----------------------------------------------------------------------

    async def test_get_imports_other_users_account_returns_404(
        self,
        http_client: AsyncClient,
        mock_account_svc: AsyncMock,
        mock_import_record_repo: AsyncMock,
    ) -> None:
        """B-17-10: GET /v1/imports?account_id=<uuid> for another user's account → 404."""
        mock_account_svc.get.side_effect = AccountNotFoundError(uuid.uuid4())

        response = await http_client.get(f"/v1/imports?account_id={uuid.uuid4()}")

        assert response.status_code == 404
        assert response.json()["detail"] == "ACCOUNT_NOT_FOUND"
        mock_import_record_repo.list_by_account.assert_not_awaited()

    # -----------------------------------------------------------------------
    # B-17-12: GET for deactivated account → 200 (ownership-only check)
    # -----------------------------------------------------------------------

    async def test_get_imports_deactivated_account_returns_200(
        self,
        http_client: AsyncClient,
        mock_account_svc: AsyncMock,
        mock_import_record_repo: AsyncMock,
    ) -> None:
        """B-17-12: GET for user-owned INACTIVE account → 200.

        list_imports uses TradingAccountService.get() which checks ownership only,
        not ACTIVE status. Import history is accessible for deactivated accounts.
        """
        from tradeforge.domain.import_domain.types import TradingAccount

        mock_account_svc.get.return_value = TradingAccount(
            id=_ACCOUNT_ID,
            user_id=_USER_ID,
            broker="ZERODHA",
            display_name="Old Account",
            account_type="INDIVIDUAL",
            base_currency="INR",
            status="INACTIVE",
            created_at=_NOW,
            updated_at=_NOW,
        )
        mock_import_record_repo.list_by_account.return_value = [
            _make_import_record(status="COMPLETE"),
        ]

        response = await http_client.get(f"/v1/imports?account_id={_ACCOUNT_ID}")

        assert response.status_code == 200
        assert len(response.json()) == 1

    # -----------------------------------------------------------------------
    # B-17-13: GET returns empty list for account with no history
    # -----------------------------------------------------------------------

    async def test_get_imports_no_history_returns_empty_list(
        self,
        http_client: AsyncClient,
        mock_account_svc: AsyncMock,
        mock_import_record_repo: AsyncMock,
    ) -> None:
        """B-17-13: GET /v1/imports?account_id=<uuid> → empty list when no imports exist."""
        from tradeforge.domain.import_domain.types import TradingAccount

        mock_account_svc.get.return_value = TradingAccount(
            id=_ACCOUNT_ID,
            user_id=_USER_ID,
            broker="ZERODHA",
            display_name="Main",
            account_type="INDIVIDUAL",
            base_currency="INR",
            status="ACTIVE",
            created_at=_NOW,
            updated_at=_NOW,
        )
        mock_import_record_repo.list_by_account.return_value = []

        response = await http_client.get(f"/v1/imports?account_id={_ACCOUNT_ID}")

        assert response.status_code == 200
        assert response.json() == []


# ===========================================================================
# GET /v1/imports — unauthenticated
# ===========================================================================


class TestGetImportsUnauthenticated:
    @pytest.fixture(autouse=True)
    def _override_deps(
        self,
        mock_account_svc: AsyncMock,
        mock_import_record_repo: AsyncMock,
    ) -> None:
        from tradeforge.api.v1.deps import get_current_user_id
        from tradeforge.api.v1.imports import get_account_service, get_import_record_repo
        from tradeforge.main import app

        app.dependency_overrides[get_current_user_id] = _raise_401
        app.dependency_overrides[get_account_service] = lambda: mock_account_svc
        app.dependency_overrides[get_import_record_repo] = lambda: mock_import_record_repo
        yield
        app.dependency_overrides.pop(get_current_user_id, None)
        app.dependency_overrides.pop(get_account_service, None)
        app.dependency_overrides.pop(get_import_record_repo, None)

    async def test_get_imports_unauthenticated_returns_401(
        self,
        http_client: AsyncClient,
        mock_import_record_repo: AsyncMock,
    ) -> None:
        """B-17-11: GET /v1/imports unauthenticated → 401."""
        response = await http_client.get(f"/v1/imports?account_id={_ACCOUNT_ID}")

        assert response.status_code == 401
        mock_import_record_repo.list_by_account.assert_not_awaited()
