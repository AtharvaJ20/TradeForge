"""Unit tests for ImportService."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from tradeforge.application.import_service import ImportService, ImportSummary
from tradeforge.domain.import_domain.errors import (
    AccountInactiveError,
    DuplicateImportError,
    InvalidFillError,
    UnrecognizedFileError,
)
from tradeforge.domain.import_domain.types import (
    AdapterParseResult,
    NormalizedFill,
    TradingAccount,
)
from tradeforge.domain.trade.types import ReconstructionResult

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

_NOW = datetime.now(UTC)
_TODAY = date.today()


def _account(status: str = "ACTIVE") -> TradingAccount:
    return TradingAccount(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        broker="ZERODHA",
        display_name="Test",
        account_type="INDIVIDUAL",
        base_currency="INR",
        status=status,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _fill(
    broker_trade_id: str = "T001",
    instrument_type: str = "EQ",
    product_type: str = "CNC",
) -> NormalizedFill:
    return NormalizedFill(
        broker_trade_id=broker_trade_id,
        broker_order_id="O001",
        broker="ZERODHA",
        import_source="CSV",
        symbol_raw="RELIANCE",
        exchange="NSE",
        exchange_segment="NSE_EQ",
        instrument_type=instrument_type,
        expiry_date=None,
        strike_price=None,
        trade_date=_TODAY,
        fill_timestamp=_NOW,
        session="REGULAR",
        side="BUY",
        quantity=Decimal("10"),
        price=Decimal("2500.00"),
        product_type=product_type,
        is_auction=False,
        is_expiry_squareoff=False,
    )


def _make_service(
    account: TradingAccount | None = None,
    *,
    file_already_imported: bool = False,
    instrument_id: uuid.UUID | None = None,
    fill_already_exists: bool = False,
    parse_result: AdapterParseResult | None = None,
    reconstruction_result: ReconstructionResult | None = None,
    pnl_result: tuple[int, int] = (0, 0),
    adapter_detects: bool = True,
) -> ImportService:
    acct = account or _account()
    instr_id = instrument_id or uuid.uuid4()

    account_svc = MagicMock()
    account_svc.get_active = AsyncMock(return_value=acct)

    import_record_repo = MagicMock()
    import_record_repo.exists = AsyncMock(return_value=file_already_imported)
    import_record_repo.create = AsyncMock(return_value=uuid.uuid4())

    instrument_repo = MagicMock()
    instrument_repo.find_for_fill = AsyncMock(return_value=instr_id)

    fill_repo = MagicMock()
    fill_repo.fill_exists = AsyncMock(return_value=fill_already_exists)
    fill_repo.insert_normalized_fill = AsyncMock(return_value=uuid.uuid4())

    engine = MagicMock()
    engine.run = AsyncMock(
        return_value=reconstruction_result or ReconstructionResult(trades_opened=1, trades_closed=1)
    )

    pnl_svc = MagicMock()
    pnl_svc.backfill_all_closed = AsyncMock(return_value=pnl_result)

    adapter = MagicMock()
    adapter.detect = MagicMock(return_value=adapter_detects)
    adapter.parse = MagicMock(return_value=parse_result or AdapterParseResult(fills=[_fill()]))

    return ImportService(
        account_service=account_svc,
        import_record_repo=import_record_repo,
        instrument_repo=instrument_repo,
        fill_repo=fill_repo,
        reconstruction_engine=engine,
        pnl_service=pnl_svc,
        adapters=[adapter],
    )


_FILE = b"header\nrow1"
_USER_ID = uuid.uuid4()
_ACCOUNT_ID = uuid.uuid4()


# ──────────────────────────────────────────────────────────────────────────────
# Account validation
# ──────────────────────────────────────────────────────────────────────────────


class TestAccountValidation:
    @pytest.mark.asyncio
    async def test_inactive_account_raises(self):
        acct = _account(status="INACTIVE")
        svc = _make_service(acct)
        svc._accounts.get_active = AsyncMock(side_effect=AccountInactiveError(_ACCOUNT_ID))
        with pytest.raises(AccountInactiveError):
            await svc.import_fills(AsyncMock(), _USER_ID, _ACCOUNT_ID, _FILE)


# ──────────────────────────────────────────────────────────────────────────────
# File-level dedup
# ──────────────────────────────────────────────────────────────────────────────


class TestFileLevelDedup:
    @pytest.mark.asyncio
    async def test_duplicate_file_raises(self):
        svc = _make_service(file_already_imported=True)
        with pytest.raises(DuplicateImportError):
            await svc.import_fills(AsyncMock(), _USER_ID, _ACCOUNT_ID, _FILE)

    @pytest.mark.asyncio
    async def test_dedup_uses_sha256_of_file_content(self):
        svc = _make_service()
        session = AsyncMock()
        session.flush = AsyncMock()
        await svc.import_fills(session, _USER_ID, _ACCOUNT_ID, _FILE)
        expected_hash = hashlib.sha256(_FILE).hexdigest()
        call_args = svc._import_records.exists.call_args
        assert call_args.args[1] == expected_hash


# ──────────────────────────────────────────────────────────────────────────────
# Adapter selection
# ──────────────────────────────────────────────────────────────────────────────


class TestAdapterSelection:
    @pytest.mark.asyncio
    async def test_unrecognized_file_raises(self):
        svc = _make_service(adapter_detects=False)
        with pytest.raises(UnrecognizedFileError):
            await svc.import_fills(AsyncMock(), _USER_ID, _ACCOUNT_ID, _FILE)

    @pytest.mark.asyncio
    async def test_first_matching_adapter_is_used(self):
        svc = _make_service()
        session = AsyncMock()
        session.flush = AsyncMock()
        await svc.import_fills(session, _USER_ID, _ACCOUNT_ID, _FILE)
        svc._adapters[0].parse.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# Happy path
# ──────────────────────────────────────────────────────────────────────────────


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_complete_status_on_clean_import(self):
        svc = _make_service(
            parse_result=AdapterParseResult(fills=[_fill()]),
            reconstruction_result=ReconstructionResult(trades_opened=1, trades_closed=1),
            pnl_result=(1, 0),
        )
        session = AsyncMock()
        session.flush = AsyncMock()
        summary = await svc.import_fills(session, _USER_ID, _ACCOUNT_ID, _FILE)

        assert isinstance(summary, ImportSummary)
        assert summary.fills_ingested == 1
        assert summary.fills_skipped == 0
        assert summary.row_errors == 0
        assert summary.trades_created == 1
        assert summary.trades_closed == 1
        assert summary.pnl_succeeded == 1
        assert summary.pnl_failed == 0

    @pytest.mark.asyncio
    async def test_import_record_written_with_complete_status(self):
        svc = _make_service()
        session = AsyncMock()
        session.flush = AsyncMock()
        await svc.import_fills(session, _USER_ID, _ACCOUNT_ID, _FILE)
        create_call = svc._import_records.create.call_args.kwargs
        assert create_call["status"] == "COMPLETE"

    @pytest.mark.asyncio
    async def test_product_type_hint_forwarded_to_adapter(self):
        svc = _make_service()
        session = AsyncMock()
        session.flush = AsyncMock()
        await svc.import_fills(session, _USER_ID, _ACCOUNT_ID, _FILE, product_type_hint="NRML")
        svc._adapters[0].parse.assert_called_once_with(_FILE, product_type_hint="NRML")

    @pytest.mark.asyncio
    async def test_file_name_forwarded_to_import_record(self):
        svc = _make_service()
        session = AsyncMock()
        session.flush = AsyncMock()
        await svc.import_fills(session, _USER_ID, _ACCOUNT_ID, _FILE, file_name="trades.csv")
        create_kwargs = svc._import_records.create.call_args.kwargs
        assert create_kwargs["file_name"] == "trades.csv"


# ──────────────────────────────────────────────────────────────────────────────
# Fill-level dedup
# ──────────────────────────────────────────────────────────────────────────────


class TestFillLevelDedup:
    @pytest.mark.asyncio
    async def test_skips_duplicate_fills(self):
        svc = _make_service(
            parse_result=AdapterParseResult(fills=[_fill()]),
            fill_already_exists=True,
        )
        session = AsyncMock()
        session.flush = AsyncMock()
        summary = await svc.import_fills(session, _USER_ID, _ACCOUNT_ID, _FILE)
        assert summary.fills_ingested == 0
        assert summary.fills_skipped == 1
        svc._fills.insert_normalized_fill.assert_not_awaited()


# ──────────────────────────────────────────────────────────────────────────────
# Instrument resolution
# ──────────────────────────────────────────────────────────────────────────────


class TestInstrumentResolution:
    @pytest.mark.asyncio
    async def test_instrument_not_found_increments_row_errors(self):
        svc = _make_service(parse_result=AdapterParseResult(fills=[_fill()]))
        svc._instruments.find_for_fill = AsyncMock(return_value=None)
        session = AsyncMock()
        session.flush = AsyncMock()
        summary = await svc.import_fills(session, _USER_ID, _ACCOUNT_ID, _FILE)
        assert summary.fills_ingested == 0
        assert summary.row_errors == 1

    @pytest.mark.asyncio
    async def test_instrument_not_found_does_not_abort_other_fills(self):
        f1 = _fill("T001")
        f2 = _fill("T002")
        svc = _make_service(parse_result=AdapterParseResult(fills=[f1, f2]))
        instr_id = uuid.uuid4()
        # f1 fails, f2 succeeds
        svc._instruments.find_for_fill = AsyncMock(side_effect=[None, instr_id])
        session = AsyncMock()
        session.flush = AsyncMock()
        summary = await svc.import_fills(session, _USER_ID, _ACCOUNT_ID, _FILE)
        assert summary.fills_ingested == 1
        assert summary.row_errors == 1


# ──────────────────────────────────────────────────────────────────────────────
# Status logic
# ──────────────────────────────────────────────────────────────────────────────


class TestStatusLogic:
    @pytest.mark.asyncio
    async def _run(self, svc: ImportService) -> ImportSummary:
        session = AsyncMock()
        session.flush = AsyncMock()
        return await svc.import_fills(session, _USER_ID, _ACCOUNT_ID, _FILE)

    @pytest.mark.asyncio
    async def test_empty_status_when_no_fills_and_no_errors(self):
        svc = _make_service(parse_result=AdapterParseResult(fills=[], errors=[]))
        summary = await self._run(svc)
        create_kwargs = svc._import_records.create.call_args.kwargs
        assert create_kwargs["status"] == "EMPTY"
        assert summary.fills_ingested == 0

    @pytest.mark.asyncio
    async def test_failed_status_when_only_row_errors(self):
        err = InvalidFillError(0, "side", "X", "invalid side")
        svc = _make_service(parse_result=AdapterParseResult(fills=[], errors=[err]))
        summary = await self._run(svc)
        create_kwargs = svc._import_records.create.call_args.kwargs
        assert create_kwargs["status"] == "FAILED"
        assert summary.row_errors == 1

    @pytest.mark.asyncio
    async def test_partial_status_when_mix_of_fills_and_errors(self):
        err = InvalidFillError(0, "side", "X", "invalid side")
        svc = _make_service(parse_result=AdapterParseResult(fills=[_fill()], errors=[err]))
        summary = await self._run(svc)
        create_kwargs = svc._import_records.create.call_args.kwargs
        assert create_kwargs["status"] == "PARTIAL"
        assert summary.fills_ingested == 1
        assert summary.row_errors == 1

    @pytest.mark.asyncio
    async def test_complete_status_when_all_fills_skipped_no_errors(self):
        # All fills deduped (skipped), no parse errors → COMPLETE
        # (skipped fills are not errors; the file was processed successfully)
        svc = _make_service(
            parse_result=AdapterParseResult(fills=[_fill()]),
            fill_already_exists=True,
        )
        summary = await self._run(svc)
        create_kwargs = svc._import_records.create.call_args.kwargs
        # fills_ingested=0, fills_skipped=1, row_errors=0 → not FAILED or EMPTY → COMPLETE
        assert create_kwargs["status"] == "COMPLETE"
        assert summary.fills_skipped == 1


# ──────────────────────────────────────────────────────────────────────────────
# Reconstruction + P&L invocation
# ──────────────────────────────────────────────────────────────────────────────


class TestReconstructionAndPnl:
    @pytest.mark.asyncio
    async def test_reconstruction_run_once_per_unique_instrument_product_pair(self):
        instr_a = uuid.uuid4()
        instr_b = uuid.uuid4()
        f1 = _fill("T001")
        f2 = _fill("T002")

        svc = _make_service(parse_result=AdapterParseResult(fills=[f1, f2]))
        # Both fills map to different instruments
        svc._instruments.find_for_fill = AsyncMock(side_effect=[instr_a, instr_b])
        session = AsyncMock()
        session.flush = AsyncMock()
        await svc.import_fills(session, _USER_ID, _ACCOUNT_ID, _FILE)
        assert svc._engine.run.await_count == 2

    @pytest.mark.asyncio
    async def test_reconstruction_run_once_for_same_instrument_product_pair(self):
        instr_id = uuid.uuid4()
        f1 = _fill("T001")
        f2 = _fill("T002")

        svc = _make_service(parse_result=AdapterParseResult(fills=[f1, f2]))
        svc._instruments.find_for_fill = AsyncMock(return_value=instr_id)
        session = AsyncMock()
        session.flush = AsyncMock()
        await svc.import_fills(session, _USER_ID, _ACCOUNT_ID, _FILE)
        # Same (instrument_id, product_type) → run only once
        assert svc._engine.run.await_count == 1

    @pytest.mark.asyncio
    async def test_pnl_backfill_always_called(self):
        svc = _make_service()
        session = AsyncMock()
        session.flush = AsyncMock()
        await svc.import_fills(session, _USER_ID, _ACCOUNT_ID, _FILE)
        svc._pnl.backfill_all_closed.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pnl_not_called_when_no_fills_ingested(self):
        # Even with no fills ingested, backfill_all_closed is called
        # (existing trades may already need backfilling)
        svc = _make_service(parse_result=AdapterParseResult(fills=[]))
        session = AsyncMock()
        session.flush = AsyncMock()
        await svc.import_fills(session, _USER_ID, _ACCOUNT_ID, _FILE)
        svc._pnl.backfill_all_closed.assert_awaited_once()
