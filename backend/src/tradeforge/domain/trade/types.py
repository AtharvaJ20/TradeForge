"""Pure domain types and helpers for the trade reconstruction engine.

No I/O. No SQLAlchemy. No FastAPI. stdlib only.
All helpers are deterministic and unit-testable without a database.

Implements:
  - ProductTypeFamily enum and mapping from raw product_type
  - trade_type derivation helpers (§8 of TRADE-RECONSTRUCTION-SPEC.md)
  - fill_role derivation (§7)
  - direction derivation from first fill (§6)
  - Lightweight dataclasses used by the engine and repositories
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from tradeforge.domain.trade.errors import ReconstructionDataError

# ---------------------------------------------------------------------------
# ProductTypeFamily
# ---------------------------------------------------------------------------


class ProductTypeFamily(StrEnum):
    """Internal engine concept grouping raw broker product_type values.

    Maps: MIS → INTRADAY, CNC → DELIVERY, NRML → FO.
    Does NOT appear in the database schema.
    """

    INTRADAY = "INTRADAY"
    DELIVERY = "DELIVERY"
    FO = "FO"


_PRODUCT_TYPE_TO_FAMILY: dict[str, ProductTypeFamily] = {
    "MIS": ProductTypeFamily.INTRADAY,
    "CNC": ProductTypeFamily.DELIVERY,
    "NRML": ProductTypeFamily.FO,
}

# trade_type values that belong to each family — used in the open-trade lookup query.
TRADE_TYPES_FOR_FAMILY: dict[ProductTypeFamily, tuple[str, ...]] = {
    ProductTypeFamily.INTRADAY: ("MIS",),
    ProductTypeFamily.DELIVERY: ("CNC", "CNC_SAME_DAY"),
    ProductTypeFamily.FO: ("NRML_FUT", "NRML_OPT"),
}


def product_type_family_for(product_type: str) -> ProductTypeFamily:
    """Map a raw broker product_type to its processing unit family."""
    try:
        return _PRODUCT_TYPE_TO_FAMILY[product_type]
    except KeyError:
        raise ReconstructionDataError(f"Unknown product_type: {product_type!r}") from None


# ---------------------------------------------------------------------------
# trade_type derivation (§8)
# ---------------------------------------------------------------------------


def provisional_trade_type(family: ProductTypeFamily, instrument_type: str) -> str:
    """Return the provisional trade_type at trade open.

    For DELIVERY / CNC trades the provisional value is 'CNC'; it may be upgraded
    to 'CNC_SAME_DAY' at close if entry and exit dates match (Phase 2 of §8).
    """
    if family == ProductTypeFamily.INTRADAY:
        return "MIS"
    if family == ProductTypeFamily.DELIVERY:
        return "CNC"
    if family == ProductTypeFamily.FO:
        if instrument_type == "FUT":
            return "NRML_FUT"
        if instrument_type in ("CE", "PE"):
            return "NRML_OPT"
        raise ReconstructionDataError(
            f"Unknown instrument_type for FO family: {instrument_type!r}. "
            "Expected 'FUT', 'CE', or 'PE'."
        )
    raise ReconstructionDataError(f"Unknown ProductTypeFamily: {family!r}")  # pragma: no cover


def finalize_trade_type(provisional: str, open_date: date, close_date: date) -> str:
    """Apply Phase 2 trade_type derivation at trade close.

    Only CNC → CNC_SAME_DAY is possible; all other trade_types are unchanged.
    """
    if provisional == "CNC" and open_date == close_date:
        return "CNC_SAME_DAY"
    return provisional


# ---------------------------------------------------------------------------
# fill_role derivation (§7)
# ---------------------------------------------------------------------------


_FILL_ROLE_TABLE: dict[tuple[str, str], str] = {
    ("LONG", "BUY"): "ENTRY",
    ("LONG", "SELL"): "EXIT",
    ("SHORT", "SELL"): "ENTRY",
    ("SHORT", "BUY"): "EXIT",
}


def fill_role_for(direction: str, side: str) -> str:
    """Derive fill_role from trade direction and fill side (§7)."""
    try:
        return _FILL_ROLE_TABLE[(direction, side)]
    except KeyError:
        raise ReconstructionDataError(
            f"Invalid direction/side combination: direction={direction!r}, side={side!r}"
        ) from None


def direction_for_first_fill(side: str) -> str:
    """The direction of a new trade is determined by the side of its first fill (§6)."""
    if side == "BUY":
        return "LONG"
    if side == "SELL":
        return "SHORT"
    raise ReconstructionDataError(f"Unknown fill side: {side!r}")


# ---------------------------------------------------------------------------
# Lightweight dataclasses — engine input/output contracts
# ---------------------------------------------------------------------------


@dataclass
class FillRecord:
    """Snapshot of a single execution_fills row consumed by the engine.

    All financial values are Decimal. No ORM dependency.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    instrument_id: uuid.UUID
    trade_id: uuid.UUID | None
    fill_timestamp: datetime
    trade_date: date
    side: str
    quantity: Decimal
    price: Decimal
    product_type: str
    fill_id_str: str | None  # broker fill_id string — NOT the PK UUID; used for tie-breaking
    created_at: datetime
    import_source: str
    account_id: uuid.UUID | None = None  # NULL on pre-Step-11 fills; always set on import fills


@dataclass
class OpenTradeSnapshot:
    """Minimal view of an OPEN or PARTIAL trades row.

    The engine reads this at the start of a run and updates it in memory as
    fills are processed.
    """

    id: uuid.UUID
    direction: str
    status: str
    trade_date: date
    first_fill_at: datetime
    total_entry_quantity: Decimal
    total_exit_quantity: Decimal
    net_position: Decimal
    average_entry: Decimal
    trade_type: str


@dataclass
class ReconstructionResult:
    """Summary of a single reconstruction run for one processing unit."""

    fills_processed: int = 0
    fills_skipped_no_unprocessed: int = 0
    trades_opened: int = 0
    trades_closed: int = 0
    tax_lots_created: int = 0
    tax_lots_updated: int = 0
    halted_at_fill_id: uuid.UUID | None = None
    error_detail: str | None = None
