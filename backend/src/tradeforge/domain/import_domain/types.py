"""Pure domain types for the broker import pipeline.

No I/O.  No SQLAlchemy.  No FastAPI.  stdlib only.

Covers:
  - TradingAccount  — domain entity (mirrors trading_accounts table)
  - NormalizedFill  — canonical value object produced by any BrokerAdapter
  - ImportRecord    — import metadata value object written to import_records
  - AdapterParseResult — return type of BrokerAdapterPort.parse()
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from tradeforge.domain.import_domain.errors import InvalidFillError


@dataclass(frozen=True)
class TradingAccount:
    """Domain entity for a user's brokerage trading account.

    Mirrors the trading_accounts table.  Instantiated by TradingAccountService
    from ORM rows; never constructed with direct DB types.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    broker: str
    display_name: str
    account_type: str
    base_currency: str
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class NormalizedFill:
    """Canonical value object produced by BrokerAdapterPort.parse().

    Represents one exchange execution fill after adapter normalization.
    All upstream broker-specific formats are resolved at the adapter boundary;
    nothing downstream touches raw CSV data.

    Field semantics follow NORMALIZED-FILL-CONTRACT.md §2.
    Fields not present here (user_id, account_id, instrument_id, trade_id,
    fill_role) are resolved by ImportService, not the adapter.
    """

    # Identity
    broker_trade_id: str  # CSV trade_id — maps to execution_fills.fill_id
    broker_order_id: str  # CSV order_id — maps to execution_fills.order_id
    broker: str  # adapter constant e.g. "ZERODHA"
    import_source: str  # adapter constant e.g. "CSV"

    # Instrument resolution fields (not stored on execution_fills directly)
    symbol_raw: str  # normalised to uppercase
    exchange: str  # "NSE" or "BSE"
    exchange_segment: str  # "NSE_EQ", "NSE_FO", "BSE_EQ"
    instrument_type: str  # "EQ", "FUT", "CE", "PE"
    expiry_date: date | None  # None for EQ
    strike_price: Decimal | None  # None for non-option

    # Fill data (map directly to execution_fills columns)
    trade_date: date
    fill_timestamp: datetime  # UTC-aware
    session: str  # "PRE_OPEN", "REGULAR", "POST_CLOSE"
    side: str  # "BUY" or "SELL"
    quantity: Decimal  # always > 0
    price: Decimal  # always > 0
    product_type: str  # "MIS", "CNC", or "NRML"

    # Flags
    is_auction: bool  # CSV auction = "yes"
    is_expiry_squareoff: bool  # detected per §3.5; sets exit_type = 'EXPIRY_SQUAREOFF'


@dataclass(frozen=True)
class ImportRecord:
    """Value object recording metadata for one import run.

    Written to the import_records table by ImportService after a successful
    (or partially successful) import.
    """

    import_id: uuid.UUID
    account_id: uuid.UUID
    broker: str
    file_hash: str  # SHA-256 hex digest of the raw file bytes
    row_count: int  # total data rows in the CSV (including rejected rows)
    error_count: int  # rows that produced InvalidFillError
    status: str  # "COMPLETE", "PARTIAL", "EMPTY", "FAILED"
    imported_at: datetime


@dataclass
class AdapterParseResult:
    """Return type of BrokerAdapterPort.parse().

    Carries both valid fills and per-row errors so the import pipeline can
    write valid fills and report errors without aborting on the first bad row.
    """

    fills: list[NormalizedFill] = field(default_factory=list)
    errors: list[InvalidFillError] = field(default_factory=list)

    @property
    def total_rows(self) -> int:
        return len(self.fills) + len(self.errors)
