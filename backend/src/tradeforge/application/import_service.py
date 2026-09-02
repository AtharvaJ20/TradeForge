"""ImportService — orchestrates the broker CSV import pipeline.

Execution sequence per import_fills():
  1. Verify the target account exists and is ACTIVE, owned by the caller.
  2. Hash the file; reject if this (file_hash, account_id) was already imported.
  3. Select the adapter for the account's broker.
  4. Parse the file via the adapter → AdapterParseResult (fills + per-row errors).
  5. For each NormalizedFill: resolve instrument, check fill-level dedup, insert.
  6. Run ReconstructionEngine for each new (instrument_id, product_type) unit.
  7. Run PnlService.backfill_all_closed() to cover any trades closed by new fills.
  8. Write ImportRecord.
  9. Return ImportSummary.

Idempotency:
  - File level: (file_hash, account_id) unique constraint → DuplicateImportError.
  - Fill level: broker_trade_id + account_id checked before each insert.

Error handling:
  - Adapter-level parse errors: collected in AdapterParseResult.errors; import continues.
  - Instrument not found: collected as InvalidFillError; fill is skipped.
  - Import does NOT abort on fill-level errors — it proceeds and reports in the summary.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.application.pnl_service import PnlService
from tradeforge.application.trade.reconstruction import ReconstructionEngine
from tradeforge.application.trading_account_service import TradingAccountService
from tradeforge.domain.import_domain.errors import (
    DuplicateImportError,
    InstrumentNotFoundError,
)
from tradeforge.domain.import_domain.types import AdapterParseResult, NormalizedFill
from tradeforge.infrastructure.adapters.broker_adapter_port import BrokerAdapterPort
from tradeforge.infrastructure.repositories.fill_repo import FillRepository
from tradeforge.infrastructure.repositories.import_record_repo import ImportRecordRepository
from tradeforge.infrastructure.repositories.instrument_repo import InstrumentRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImportSummary:
    """Outcome of a single import_fills() call."""

    import_record_id: uuid.UUID
    fills_ingested: int
    fills_skipped: int  # fill-level dedup skips
    row_errors: int  # per-row adapter parse errors + instrument-not-found
    trades_created: int
    trades_closed: int
    pnl_succeeded: int
    pnl_failed: int


# maps broker string to the instrument_type that the ReconstructionEngine expects
_ADAPTER_REGISTRY: dict[str, type[BrokerAdapterPort]] = {}


def register_adapter(broker: str, cls: type[BrokerAdapterPort]) -> None:
    """Register a BrokerAdapterPort implementation for a broker string."""
    _ADAPTER_REGISTRY[broker] = cls


class ImportService:
    def __init__(
        self,
        account_service: TradingAccountService,
        import_record_repo: ImportRecordRepository,
        instrument_repo: InstrumentRepository,
        fill_repo: FillRepository,
        reconstruction_engine: ReconstructionEngine,
        pnl_service: PnlService,
        adapters: list[BrokerAdapterPort] | None = None,
    ) -> None:
        self._accounts = account_service
        self._import_records = import_record_repo
        self._instruments = instrument_repo
        self._fills = fill_repo
        self._engine = reconstruction_engine
        self._pnl = pnl_service
        # Adapter list for detect()-based dispatch (WS-4 upload endpoint).
        # For Phase 1, adapters can also be passed per-call via product_type_hint logic.
        self._adapters: list[BrokerAdapterPort] = adapters or []

    async def import_fills(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        file_content: bytes,
        product_type_hint: str | None = None,
        file_name: str | None = None,
    ) -> ImportSummary:
        """Run the full import pipeline for one broker CSV file.

        Args:
            session: Active AsyncSession — caller owns commit/rollback.
            user_id: Authenticated user (from session token, never from request body).
            account_id: Target trading account (must be owned by user_id).
            file_content: Raw bytes of the uploaded CSV file.
            product_type_hint: Optional product type override ('MIS', 'CNC', 'NRML').
                Required when the CSV lacks a 'product' column for rows that cannot
                be classified structurally (e.g. FO fills in older Zerodha exports).
            file_name: Optional original filename for ImportRecord.file_name.

        Returns:
            ImportSummary with counts of ingested fills, skips, errors, and trades.

        Raises:
            AccountNotFoundError: account_id is not found or not owned by user_id.
            AccountInactiveError: account is INACTIVE.
            DuplicateImportError: this file was already imported into this account.
            UnrecognizedFileError: no adapter recognises the file.
            EmptyFileError: the CSV has a header but zero data rows.
            MissingProductTypeError: product column absent, no hint, FO rows present.
        """
        # --- Step 1: verify account ---
        account = await self._accounts.get_active(session, user_id, account_id)

        # --- Step 2: file-level dedup ---
        file_hash = hashlib.sha256(file_content).hexdigest()
        if await self._import_records.exists(session, file_hash, account_id):
            raise DuplicateImportError(file_hash, account_id)

        # --- Step 3: select adapter ---
        adapter = self._select_adapter(account.broker, file_content)

        # --- Step 4: parse ---
        parse_result: AdapterParseResult = adapter.parse(
            file_content, product_type_hint=product_type_hint
        )

        # --- Steps 5: resolve instruments, check fill dedup, insert fills ---
        fills_ingested = 0
        fills_skipped = 0
        row_errors = len(parse_result.errors)
        # (instrument_id, product_type, instrument_type) triples for reconstruction
        processing_units: list[tuple[uuid.UUID, str, str]] = []
        seen_units: set[tuple[uuid.UUID, str]] = set()

        for fill in parse_result.fills:
            try:
                instrument_id = await self._resolve_instrument(session, fill)
            except InstrumentNotFoundError as exc:
                logger.warning(
                    "Import: instrument not found for fill %r — %s",
                    fill.broker_trade_id,
                    exc,
                )
                row_errors += 1
                continue

            # Fill-level dedup
            if await self._fills.fill_exists(session, fill.broker_trade_id, account_id):
                fills_skipped += 1
                continue

            await self._fills.insert_normalized_fill(
                session,
                user_id=user_id,
                account_id=account_id,
                instrument_id=instrument_id,
                fill=fill,
            )
            fills_ingested += 1

            unit_key = (instrument_id, fill.product_type)
            if unit_key not in seen_units:
                seen_units.add(unit_key)
                processing_units.append((instrument_id, fill.product_type, fill.instrument_type))

        await session.flush()

        # --- Step 6: reconstruct trades ---
        trades_created = 0
        trades_closed = 0
        for instrument_id, product_type, instrument_type in processing_units:
            result = await self._engine.run(
                session, user_id, account.id, instrument_id, product_type, instrument_type
            )
            trades_created += result.trades_opened
            trades_closed += result.trades_closed

        # --- Step 7: P&L backfill ---
        pnl_succeeded, pnl_failed = await self._pnl.backfill_all_closed(user_id)

        # --- Step 8: write ImportRecord ---
        total_rows = parse_result.total_rows
        status: str
        if fills_ingested == 0 and fills_skipped == 0:
            status = "FAILED" if row_errors > 0 else "EMPTY"
        elif row_errors > 0:
            status = "PARTIAL"
        else:
            status = "COMPLETE"

        try:
            import_record_id = await self._import_records.create(
                session,
                account_id=account_id,
                broker=account.broker,
                file_hash=file_hash,
                file_name=file_name,
                row_count=total_rows,
                error_count=row_errors,
                status=status,
            )
        except IntegrityError:
            raise DuplicateImportError(file_hash, account_id)

        logger.info(
            "Import complete: account=%s broker=%s fills=%d skipped=%d errors=%d "
            "trades_created=%d trades_closed=%d status=%s",
            account_id,
            account.broker,
            fills_ingested,
            fills_skipped,
            row_errors,
            trades_created,
            trades_closed,
            status,
        )

        return ImportSummary(
            import_record_id=import_record_id,
            fills_ingested=fills_ingested,
            fills_skipped=fills_skipped,
            row_errors=row_errors,
            trades_created=trades_created,
            trades_closed=trades_closed,
            pnl_succeeded=pnl_succeeded,
            pnl_failed=pnl_failed,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _select_adapter(self, broker: str, file_content: bytes) -> BrokerAdapterPort:
        """Pick the adapter for this broker string from the registered list.

        Raises:
            UnrecognizedFileError: no adapter's detect() returns True.
        """
        from tradeforge.domain.import_domain.errors import UnrecognizedFileError

        for adapter in self._adapters:
            if adapter.detect(file_content):
                return adapter
        raise UnrecognizedFileError()

    async def _resolve_instrument(
        self,
        session: AsyncSession,
        fill: NormalizedFill,
    ) -> uuid.UUID:
        """Resolve a NormalizedFill to an instruments.id.

        Raises:
            InstrumentNotFoundError: no matching instrument found.
        """
        instrument_id = await self._instruments.find_for_fill(
            session,
            symbol=fill.symbol_raw,
            exchange_segment=fill.exchange_segment,
            instrument_type=fill.instrument_type,
            expiry_date=fill.expiry_date,
            strike_price=fill.strike_price,
        )
        if instrument_id is None:
            raise InstrumentNotFoundError(
                fill.symbol_raw, fill.exchange_segment, fill.instrument_type
            )
        return instrument_id
