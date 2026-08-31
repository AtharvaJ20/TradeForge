"""Decimal quantization constants — authoritative source for all financial arithmetic.

Defined here per DECIMAL-USAGE-STANDARD.md Rule 8. Every quantize() call in the
codebase must use a constant from this module, never an inline literal.

Domain layer: stdlib only. No framework imports.
"""

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

# ---------------------------------------------------------------------------
# Quantization targets
# ---------------------------------------------------------------------------
TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")
SIX_PLACES = Decimal("0.000001")
EIGHT_PLACES = Decimal("0.00000001")

# ---------------------------------------------------------------------------
# Named quantization bundles: (places, rounding_mode)
# Usage: value.quantize(*MONETARY)
# ---------------------------------------------------------------------------

# Gross P&L, net P&L, total charges displayed to user
MONETARY = (TWO_PLACES, ROUND_HALF_UP)

# Average entry price, average exit price stored in DB
PRICE = (FOUR_PLACES, ROUND_HALF_UP)

# Individual charge components (STT, brokerage, exchange charge) stored in DB
CHARGE_STORED = (FOUR_PLACES, ROUND_HALF_UP)

# Charge rates fetched from configuration table (STT rate, GST rate, etc.)
RATE = (EIGHT_PLACES, ROUND_HALF_UP)

# R-multiples
R_MULTIPLE = (SIX_PLACES, ROUND_HALF_UP)

# Quantities — ROUND_DOWN: never round a quantity up (DECIMAL-USAGE-STANDARD Rule 4)
QUANTITY = (FOUR_PLACES, ROUND_DOWN)

# Percentage metrics stored in DB (win rate, etc.)
PERCENTAGE = (FOUR_PLACES, ROUND_HALF_UP)

# ---------------------------------------------------------------------------
# Canonical zero for monetary accumulators
# ---------------------------------------------------------------------------
ZERO = Decimal("0")
