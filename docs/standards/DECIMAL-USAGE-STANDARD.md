# Decimal Usage Standard

**Status:** Final — prerequisite for financial calculation implementation
**Required by:** ADR-001
**Owner:** Kubera
**Binding on:** Bhima (implementation), Sahadeva (validation), all agents writing financial calculation code

---

## Purpose

This standard defines the exact rules for decimal arithmetic in TradeForge. Every monetary value, every price, every charge, every ratio computed in this system must conform to these rules without exception.

ADR-001 established that Python's `Decimal` type is the mechanism. This standard defines how it must be used. A `Decimal` type used incorrectly produces wrong numbers with the appearance of precision. The rules below eliminate that failure mode.

This document does not contain implementation code. It contains the specification that Bhima implements and Sahadeva validates.

---

## Scope

This standard applies to every value that is:
- A monetary amount (P&L, charges, turnover, premium, margin)
- A price or rate (entry price, exit price, charge rate, brokerage rate)
- A ratio used in financial computation (R-multiple, lot size multiplier)
- A percentage used in charge calculation (STT rate, GST rate)
- A quantity of a financial instrument

It does not apply to:
- UI display formatting (frontend concern)
- Statistical metrics that are inherently approximate (Sharpe ratio, Sortino ratio — produced by
  Karna, may use float internally with Decimal at the boundary)
- Non-financial application state (IDs, timestamps, counts of records)

---

## Rule 1 — Initialization

**The single most common source of silent error. No exception to this rule.**

### Permitted initializations

```python
# From string — always correct
Decimal('250.00')
Decimal('0.00025')
Decimal('0')

# From integer — always correct (integers are exact in binary)
Decimal(250)
Decimal(0)

# From another Decimal — always correct
Decimal(existing_decimal_value)

# From database DECIMAL column via SQLAlchemy Numeric type — correct
# (SQLAlchemy returns Python Decimal when column is Numeric(18, 4, asdecimal=True))
```

### Prohibited initializations

```python
# From float — ALWAYS WRONG. Captures float's binary approximation.
Decimal(250.40)      # → Decimal('250.39999999999997726263245...') WRONG
Decimal(0.025)       # → Decimal('0.025000000000000001387778...') WRONG
Decimal(float_var)   # WRONG regardless of where float_var came from

# From arithmetic on floats before conversion
Decimal(quantity * price)   # if quantity or price is float → WRONG
```

### CSV and external input handling

CSV imports, broker API responses, and user-entered values arrive as strings. The conversion path is:

```
string → Decimal           CORRECT
string → float → Decimal   WRONG
```

If an external value arrives as a Python `float` (e.g., from a JSON response that did not use string
encoding), convert via its string representation:

```python
# Acceptable last resort — not preferred
Decimal(str(float_value))
```

The preferred solution is to configure JSON parsing to return strings for numeric fields and convert
to Decimal directly. Never use `float()` as an intermediate step for any value entering a financial
calculation.

---

## Rule 2 — Working Precision

Python's `decimal` module uses a configurable `Context` object governing precision (significant digits)
and rounding during arithmetic operations.

**Default Python context: 28 significant digits, `ROUND_HALF_EVEN`.**

The default precision of 28 significant digits is sufficient for all intermediate calculations in this
system. Do not reduce it.

The default rounding mode (`ROUND_HALF_EVEN`) must not be relied upon for output. Rounding mode is
applied explicitly via `quantize()` at output boundaries — see Rule 4.

**Do not set a global context rounding mode.** Charge calculations, price calculations, and ratio
calculations have different rounding requirements. A global rounding mode creates silent errors when
a value moves between contexts. Every `quantize()` call states its rounding mode explicitly.

---

## Rule 3 — Intermediate Calculation Rule

**Rounding is applied once, at the output or storage boundary. Never at intermediate steps.**

An intermediate value is any value computed during a calculation chain that is not the final output
being stored or returned. Intermediate values carry full Decimal precision throughout.

### Correct pattern

```
avg_entry = sum(qty_i × price_i) / sum(qty_i)
            ↑ full precision throughout
            ↓
quantize to 4dp only when storing or returning avg_entry
```

### Incorrect pattern

```
# Rounding at intermediate steps — WRONG
fill_1_value = (300 × Decimal('250.00')).quantize(TWO_PLACES)   ← WRONG
fill_2_value = (200 × Decimal('252.50')).quantize(TWO_PLACES)   ← WRONG
avg_entry    = (fill_1_value + fill_2_value) / 500              ← accumulated error
```

The only exception: when a rounded intermediate is what is legally defined (e.g., a regulation
explicitly states "round each component before summing"). No such regulation applies to the
calculations in this system.

---

## Rule 4 — Rounding Mode and Quantization by Output Type

`quantize()` is the only permitted method for applying final rounding to a Decimal value.
Python's built-in `round()` uses `ROUND_HALF_EVEN` and must not be used on financial values.

### Rounding mode decision

**`ROUND_HALF_UP` is the standard rounding mode for all monetary outputs in this system.**

Justification: Indian brokerage charge calculations, STT, exchange charges, and SEBI charges all
conventionally round half-up to the nearest paisa. `ROUND_HALF_EVEN` (Python's default) produces
different results on `.5` values and would cause systematic discrepancies against broker contract
notes. The difference is small per trade but compounds across high trade volumes and creates
reconciliation failures.

### Quantization reference table

| Output type               | Decimal places | Rounding mode  | `quantize()` argument |
|---------------------------|----------------|----------------|-----------------------|
| Gross P&L                 | 2              | ROUND_HALF_UP  | `Decimal('0.01')`     |
| Net P&L                   | 2              | ROUND_HALF_UP  | `Decimal('0.01')`     |
| Individual charge (stored)| 4              | ROUND_HALF_UP  | `Decimal('0.0001')`   |
| Total charges             | 2              | ROUND_HALF_UP  | `Decimal('0.01')`     |
| Average entry price       | 4              | ROUND_HALF_UP  | `Decimal('0.0001')`   |
| Average exit price        | 4              | ROUND_HALF_UP  | `Decimal('0.0001')`   |
| R-multiple                | 4              | ROUND_HALF_UP  | `Decimal('0.0001')`   |
| Turnover (intermediate)   | No rounding    | —              | Not quantized         |
| Charge rate (from config) | Stored as-is   | —              | Not rounded           |
| Percentage metrics        | 4 (stored)     | ROUND_HALF_UP  | `Decimal('0.0001')`   |
| Quantity                  | 4              | ROUND_DOWN     | `Decimal('0.0001')`   |

### Quantity rounding rule

Quantity uses `ROUND_DOWN`, not `ROUND_HALF_UP`. You may never round a quantity up — that would
imply owning more of an instrument than was actually transacted. Fractional quantities that do not
resolve to a whole number round toward zero.

### Charge component storage vs. display

Individual charge components (STT, brokerage, exchange charges, etc.) are stored at 4 decimal places.
Displayed at 2 decimal places. This distinction matters:

- **Total charges** is computed by summing the unquantized (4dp) component values, then quantizing
  the sum to 2dp.
- The sum of displayed (2dp) components may differ from the displayed total by ±₹0.01 due to display
  rounding. This is expected, documented, and must not be treated as a calculation error.
- The stored 4dp values are the authoritative record. The 2dp display is a presentation artifact.

---

## Rule 5 — Prohibited Python Constructs

These constructs must not appear in any financial calculation code. A linting rule or code review
checklist must enforce this.

| Prohibited | Reason | Replacement |
|---|---|---|
| `float()` on any financial value | Introduces binary approximation | `Decimal(str(value))` if unavoidable |
| `round(decimal_value, n)` | Uses ROUND_HALF_EVEN silently | `decimal_value.quantize(PLACES, rounding=ROUND_HALF_UP)` |
| `Decimal(float_literal)` | Captures float error at construction | `Decimal('string_literal')` |
| `Float` column type in SQLAlchemy for financial data | Loses precision at storage boundary | `Numeric(18, 4, asdecimal=True)` |
| Arithmetic mixing `Decimal` and `float` | Raises `TypeError` — must not be worked around with `float()` cast | Keep all values `Decimal` throughout |

---

## Rule 6 — Charge Rate Storage and Retrieval

All charge rates (STT, exchange charge rates, SEBI rates, brokerage rates, stamp duty rates, GST rate)
are stored in the database as `NUMERIC(10, 8)` — eight decimal places to preserve rate precision.

Example: STT rate for equity intraday sell = `0.00025000` (representing 0.025%)

Rates are retrieved as `Decimal` values via SQLAlchemy. They must never be hardcoded as float literals
in application code. Every charge calculation must reference the rate from the configuration table,
selecting the rate effective on the trade date.

The GST rate (currently 18%) is stored as `Decimal('0.18')`, not `18` or `0.18` (float).

---

## Rule 7 — Database Precision Mapping

All financial columns in PostgreSQL use `NUMERIC(18, 4)`. The SQLAlchemy column definition must
include `asdecimal=True` — this instructs SQLAlchemy to return Python `Decimal` objects, not floats.

| Data category           | PostgreSQL type   | SQLAlchemy type                       |
|-------------------------|-------------------|---------------------------------------|
| Monetary amounts        | `NUMERIC(18, 4)`  | `Numeric(18, 4, asdecimal=True)`      |
| Prices                  | `NUMERIC(18, 4)`  | `Numeric(18, 4, asdecimal=True)`      |
| Quantities              | `NUMERIC(18, 4)`  | `Numeric(18, 4, asdecimal=True)`      |
| Charge rates            | `NUMERIC(10, 8)`  | `Numeric(10, 8, asdecimal=True)`      |
| R-multiple              | `NUMERIC(10, 4)`  | `Numeric(10, 4, asdecimal=True)`      |
| Percentage metrics      | `NUMERIC(10, 4)`  | `Numeric(10, 4, asdecimal=True)`      |

No `Float` column type may be used for any financial value. A `Float` column found in a migration
file for a financial field is a defect — raise it before the migration runs.

---

## Rule 8 — Named Constants

All quantization targets and rounding modes must be defined as named constants in a single module
(`domain/decimal_config.py` or equivalent). They must not be defined inline at call sites.

The following named constants must be defined:

```
FOUR_PLACES  = Decimal('0.0001')
TWO_PLACES   = Decimal('0.01')
EIGHT_PLACES = Decimal('0.00000001')

# Quantization bundles: (places, rounding_mode)
MONETARY      = (TWO_PLACES,   ROUND_HALF_UP)   # gross/net P&L, total charges
PRICE         = (FOUR_PLACES,  ROUND_HALF_UP)   # avg entry, avg exit
CHARGE_STORED = (FOUR_PLACES,  ROUND_HALF_UP)   # individual charge components at rest
RATE          = (EIGHT_PLACES, ROUND_HALF_UP)   # charge rates from config
R_MULTIPLE    = (FOUR_PLACES,  ROUND_HALF_UP)   # R-multiples
QUANTITY      = (FOUR_PLACES,  ROUND_DOWN)       # quantities — never round up
PERCENTAGE    = (FOUR_PLACES,  ROUND_HALF_UP)   # stored percentage metrics
```

Any calculation result that does not fit a named constant must have its quantization decision reviewed
by Kubera before implementation.

---

## Rule 9 — Zero and Sign Handling

**Zero:** The canonical zero for monetary accumulators before accumulation is `Decimal('0')`. No
quantization needed for an accumulator — quantize at the end.

**Sign convention for charges:** All charge values are stored as positive numbers. Charges are
subtracted from gross P&L to produce net P&L. A charge stored as a negative number is a defect.

**Sign convention for P&L:**
- Positive = profit
- Negative = loss
- `net_pnl = gross_pnl − total_charges`
- For a losing trade, total_charges makes the loss larger (more negative).
- For a winning trade, total_charges reduces the gain.

**Sign convention for R-multiple:** Signed per net P&L sign. Positive R = profit. Negative R = loss.

---

## Rule 10 — Validation Assertions for Test Suite

These assertions verify that the standard is being followed, not that P&L logic is correct (that is
Sahadeva's domain). These are Decimal hygiene checks.

```
ASSERTION: All monetary outputs are Decimal, not float or int
ASSERTION: All monetary display/return values have scale of exactly 2
ASSERTION: All price outputs have scale of exactly 4
ASSERTION: No financial function accepts float parameters
ASSERTION: Decimal('0.1') + Decimal('0.2') == Decimal('0.3')
ASSERTION: Decimal('2.5').quantize(Decimal('1'), rounding=ROUND_HALF_UP) == Decimal('3')
ASSERTION: Decimal('2.5').quantize(Decimal('1'), rounding=ROUND_HALF_EVEN) == Decimal('2')
  — These two assertions confirm ROUND_HALF_UP and ROUND_HALF_EVEN differ on .5 values,
    and that we are deliberately choosing ROUND_HALF_UP.
ASSERTION: No charge value is negative
ASSERTION: net_pnl == gross_pnl - total_charges (to 4dp stored precision)
ASSERTION: total_charges computed from 4dp component values, not from 2dp display values
```

---

## Open Questions Passed to Ganesha

Two questions arise from this standard that fall within Ganesha's domain (trading domain rules), not
Kubera's (financial calculation rules). They must be answered before trade reconstruction and P&L
code is written.

1. **FIFO vs. average cost — per account or per instrument?** This standard assumes FIFO for cost
   basis tracking. If Ganesha determines that average cost is required for any segment (e.g.,
   delivery equity positions across multiple buy dates), the partial exit calculation will need a
   variant. Kubera will specify the variant once Ganesha's rule is defined.

2. **Intraday vs. delivery classification trigger:** STT rates, stamp duty rates, and brokerage rates
   differ materially between intraday and delivery. The rule that determines this classification must
   come from Ganesha. Kubera applies the correct rates once that classification is provided by the
   trade record.
