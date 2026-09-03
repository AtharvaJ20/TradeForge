# NormalizedFill Contract — Zerodha CSV Adapter (WS-0 Decision 1)

**Status:** Accepted — WS-0 Decision 1 output, Step 11 execution plan
**Author:** Sanjaya (Broker Integration)
**Date:** 2026-09-01
**Binding on:** Bhima (Step 11 domain + infrastructure implementation), Ganesha (domain rule validation), Sahadeva (QA test design)
**Governs:** `ZerodhaAdapter.parse()` output; `ImportService` ingestion contract; `execution_fills` write path

---

## Purpose

This document resolves WS-0 Decision 1 from the Step 11 execution plan. It defines:

1. The exact Zerodha tradebook CSV column layout (EQ and F&O segments)
2. The `NormalizedFill` value object — the canonical contract between any broker adapter and the import pipeline
3. Field-by-field normalization rules, EQ/F&O differences, known edge cases, and error handling

`NormalizedFill` is a domain value object. It lives at `backend/src/tradeforge/domain/import_domain/types.py`. It carries no framework imports and no SQLAlchemy types. Bhima must not write the `ZerodhaAdapter` or the `ImportService` until this contract is reviewed by Ganesha and accepted.

---

## 1. Zerodha Tradebook CSV — Column Layout

### 1.1 Source

File obtained from: Zerodha Console → Reports → Tradebook → Download CSV.

The tradebook is a **fill-level report** — one row per individual exchange execution. It is not an order-level report. One order may produce multiple rows if it was partially filled in separate exchange matches.

### 1.2 Column Definitions

| # | Column name | Type in CSV | Required | Notes |
|---|---|---|---|---|
| 1 | `symbol` | string | yes | Broker-format symbol — see §1.4 for EQ vs F&O |
| 2 | `isin` | string | EQ only | 12-character ISIN. Blank for F&O rows. |
| 3 | `trade_date` | string `YYYY-MM-DD` | yes | IST calendar date of the fill |
| 4 | `exchange` | string | yes | `NSE` or `BSE` |
| 5 | `segment` | string | yes | `EQ`, `FO`, or `CD` (CD = currency derivatives — **out of Phase 1 scope**) |
| 6 | `series` | string | EQ only | `EQ` (standard), `BE` (trade-for-trade delivery), `N` (permitted category), etc. Blank for F&O |
| 7 | `trade_type` | string | yes | `buy` or `sell` (lowercase) |
| 8 | `auction` | string | yes | `yes` or `no` |
| 9 | `quantity` | integer string | yes | Number of shares (EQ) or contracts (F&O). Always positive. |
| 10 | `price` | decimal string | yes | Fill price per share or per unit |
| 11 | `trade_id` | string | yes | Exchange-assigned trade identifier — **deduplication key** |
| 12 | `order_id` | string | yes | Zerodha-assigned order identifier |
| 13 | `order_execution_time` | string `YYYY-MM-DD HH:MM:SS` | yes | Timestamp of fill execution, in **IST** |

**`product` column:** Zerodha tradebooks from some console versions include a `product` column (`MIS`, `CNC`, `NRML`). When present, it is the authoritative source for `product_type`. When absent, see §3.4 for the derivation rule.

### 1.3 EQ Segment — Symbol Format

```
RELIANCE      → equity
INFY          → equity
NIFTYBEES     → ETF (treat as EQ)
```

For EQ segment: `isin` is always populated. `series` is present. `segment = EQ`.

### 1.4 F&O Segment — Symbol Format

Zerodha uses a compact notation. The adapter must parse these into `(base_symbol, expiry_date, instrument_type, strike_price, option_type)`:

```
NIFTY25JANFUT          → NIFTY index future, expiry Jan 2025
RELIANCE25JANFUT       → RELIANCE equity future, expiry Jan 2025
NIFTY2510123500CE      → NIFTY option, expiry 25-Oct, strike 23500, Call
NIFTY2510123500PE      → NIFTY option, expiry 25-Oct, strike 23500, Put
BANKNIFTY25JAN52000CE  → BANKNIFTY option, expiry Jan 2025, strike 52000, Call
```

**Compact option expiry format:** `YYMDD` or `YYMMM` — weekly options use `YYMDD` (two-digit year, single-digit month as 1–9 then O, N, D for Oct–Dec, two-digit day). Monthly options use `YYMMM` (three-letter month abbreviation).

For F&O: `isin` is blank. `series` is blank. `segment = FO`.

### 1.5 `CD` Segment (Currency Derivatives)

**Out of Phase 1 scope.** Any row with `segment = CD` must be rejected with `InvalidFillError(row_index, "CD segment not supported in Phase 1")`. The import continues for the remaining rows — do not abort the entire file.

---

## 2. NormalizedFill Value Object Contract

`NormalizedFill` is the output type of `BrokerAdapterPort.parse()`. It represents one broker execution fill after normalization. All upstream broker-specific formats are resolved at this boundary — nothing downstream touches raw CSV data.

### 2.1 Field Definitions

| Field | Python type | Nullable | Source | Maps to `execution_fills` |
|---|---|---|---|---|
| `broker_trade_id` | `str` | No | CSV `trade_id` | `fill_id` |
| `broker_order_id` | `str` | No | CSV `order_id` | `order_id` |
| `broker` | `str` | No | Adapter constant `"ZERODHA"` | `broker` |
| `import_source` | `str` | No | Adapter constant `"CSV"` | `import_source` |
| `symbol_raw` | `str` | No | CSV `symbol` (normalized to uppercase) | Instrument resolution only — not stored |
| `exchange` | `str` | No | Normalized: `NSE` or `BSE` | Instrument resolution only — not stored |
| `exchange_segment` | `str` | No | Derived: `NSE_EQ`, `NSE_FO`, `BSE_EQ` | Instrument resolution only — not stored |
| `instrument_type` | `str` | No | Derived: `EQ`, `FUT`, `CE`, `PE` | Instrument resolution only — not stored |
| `expiry_date` | `date` | Yes | Parsed from F&O symbol; `None` for EQ | Instrument resolution only — not stored |
| `strike_price` | `Decimal` | Yes | Parsed from option symbol; `None` for non-option | Instrument resolution only — not stored |
| `trade_date` | `date` | No | CSV `trade_date` parsed as IST date | `trade_date` |
| `fill_timestamp` | `datetime` | No | CSV `order_execution_time` converted to UTC | `fill_timestamp` |
| `session` | `str` | No | Derived from `fill_timestamp` IST time — see §3.2 | `session` |
| `side` | `str` | No | Normalized: `BUY` or `SELL` | `side` |
| `quantity` | `Decimal` | No | CSV `quantity` — always positive | `quantity` |
| `price` | `Decimal` | No | CSV `price` | `price` |
| `product_type` | `str` | No | See §3.4 — `MIS`, `CNC`, or `NRML` | `product_type` |
| `is_auction` | `bool` | No | Derived from CSV `auction` column (`yes` → `True`) | Used to tag auction fills (logged; no dedicated `execution_fills` column in Phase 1) |
| `is_expiry_squareoff` | `bool` | No | Derived — see §3.5 | When `True`, sets `execution_fills.exit_type = 'EXPIRY_SQUAREOFF'` |

### 2.2 Fields Explicitly Out of NormalizedFill

The following are resolved by the import pipeline, not the adapter, and are therefore NOT in `NormalizedFill`:

| Field | Resolved by |
|---|---|
| `user_id` | From authenticated session |
| `account_id` | From the `account_id` parameter passed to `ImportService.import_fills()` |
| `instrument_id` | Instrument lookup: `(exchange_segment, symbol_raw, instrument_type, expiry_date, strike_price)` against `instruments` table |
| `trade_id` | NULL at import — assigned by `ReconstructionEngine` |
| `fill_role` | NULL at import — assigned by `ReconstructionEngine` |

---

## 3. Normalization Rules

### 3.1 Timestamp Normalization (Critical)

Zerodha's `order_execution_time` is in **IST (UTC+5:30)**. The adapter must convert every timestamp to UTC before populating `fill_timestamp`.

```
IST timestamp: 2025-01-15 10:32:45  →  UTC: 2025-01-15 05:02:45+00:00
```

The `trade_date` in the CSV is the IST calendar date of the fill. Store it directly — no conversion. It is the canonical date for all P&L, charge schedule lookup, and lot-size lookup.

**Timezone parsing:** Parse `order_execution_time` as a naive datetime, assume IST (UTC+5:30), then convert to UTC timezone-aware `datetime`. Never assume the CSV is already UTC.

**Off-hours timestamps:** Occasionally Zerodha records fills with timestamps outside regular market hours (e.g., 08:50 IST for a pre-open auction). Apply session derivation per §3.2 regardless. The `fill_timestamp` is stored as-is (after UTC conversion) — do not clip or round timestamps to market hours.

### 3.2 Session Derivation

Derive `session` from the IST time component of `order_execution_time`:

| IST time range | `session` |
|---|---|
| 09:00:00 – 09:14:59 | `PRE_OPEN` |
| 09:15:00 – 15:29:59 | `REGULAR` |
| 15:30:00 – 15:39:59 | `REGULAR` (closing auction — within regular session window) |
| 15:40:00 – 16:00:00 | `POST_CLOSE` |
| Outside all ranges | `REGULAR` (safest fallback — log a WARNING with the row index and raw timestamp) |

**Rationale for closing auction (15:30–15:39):** The closing price auction is conducted from 15:30–15:40. Fills in this window are part of the regular session for accounting purposes.

### 3.3 Side Normalization

CSV `trade_type` values: `buy` or `sell` (lowercase). Normalize:

```
"buy"  → "BUY"
"sell" → "SELL"
```

Any other value → `InvalidFillError(row_index, f"Unknown trade_type: {value!r}")`.

### 3.4 `product_type` Derivation — Known Limitation

**Rule 3.1 of `TRADE-DOMAIN-RULES.md` is absolute:** `product_type` must reflect the product code set at order entry time. It must not be inferred from trading behavior.

Zerodha tradebooks may or may not include a `product` column:

#### When `product` column is present in the file

Use the CSV value directly. Map:

```
"MIS"  → "MIS"
"CNC"  → "CNC"
"NRML" → "NRML"
```

Any other value → `InvalidFillError(row_index, f"Unknown product code: {value!r}")`.

#### When `product` column is absent

**Rule 3.1 of `TRADE-DOMAIN-RULES.md` is absolute** — product_type must not be inferred from behavior. Ganesha ruling G4 (2026-09-01) rejected the original FO-defaults-to-NRML rule. Apply the following derivation table **in order**:

| Condition | Derived `product_type` | Basis |
|---|---|---|
| `segment = EQ`, `series = BE` | `CNC` | Structural: MIS orders are broker-blocked on BE series (G3 confirmed) |
| `product_type_hint` provided | Use hint value for all remaining unclassified fills | User declaration — Rule 3.1 compliant |
| `segment = EQ`, `series = EQ`, no hint | **Cannot derive** — `MissingProductTypeError` | Rule 3.1 |
| `segment = FO`, no hint | **Cannot derive** — `MissingProductTypeError` | Rule 3.1 (G4 ruling) |

**`MissingProductTypeError` is raised before any rows are written** when the file lacks the `product` column AND any rows require hint-based classification AND no hint was provided. Message:

> `"This tradebook does not contain a 'product' column. Provide product_type_hint='MIS', 'CNC', or 'NRML' to classify fills. If the file contains mixed product types (e.g. both MIS and NRML F&O), perform separate imports per product type."`

**Note on G4:** F&O MIS fills belong to the `INTRADAY` product_type_family and are reconstructed in a separate unit from NRML F&O fills. Silently defaulting to NRML would group MIS-F&O fills with NRML fills into the same processing unit, producing incorrect trade reconstruction.

**This is a Phase 1 limitation.** Zerodha's API (Phase 2) provides product_type on every order, eliminating this gap entirely.

### 3.5 Expiry Square-Off Detection

Broker-initiated expiry square-off fills occur on expiry day (last Thursday of the month for monthly contracts; every Thursday for weekly index contracts). They are distinguishable from trader-initiated exits in two ways:

**Primary detection — F&O only:**
- `segment = FO`
- AND `trade_date` matches a known expiry Thursday for the parsed contract's `expiry_date`
- AND `auction = "yes"` (Zerodha tags auto-square-off fills in the auction field in some versions)
  
**Secondary detection (when `auction` is not reliable):**
- `segment = FO`
- AND `trade_date == expiry_date` of the parsed instrument
- AND IST time of `order_execution_time` is between 15:20:00 and 15:35:00 (closing window used for expiry square-offs)

When either condition is met: set `is_expiry_squareoff = True` on the `NormalizedFill`.

**Consequence in import pipeline:** When `is_expiry_squareoff = True`, the `ImportService` sets `execution_fills.exit_type = 'EXPIRY_SQUAREOFF'` on the written row.

### 3.6 AMO (After Market Order) Timestamps

AMO orders are placed after 15:30 IST and are queued for execution on the next trading day in the pre-open session (typically 9:00–9:08 IST).

**The adapter requires no special AMO handling.** In the Zerodha tradebook:
- `trade_date` is the **execution date** (the next trading day), not the order placement date.
- `order_execution_time` is the **execution timestamp** on the next trading day (9:00–9:08 IST).
- `order_id` may carry an AMO prefix (e.g., begins with `"AMO"`) but this is informational only.

From the adapter's perspective, AMO fills look like any other pre-open fill. Session derivation per §3.2 will classify them as `PRE_OPEN` correctly.

**No `is_amo` flag is needed in `NormalizedFill`** — the `session = PRE_OPEN` classification is sufficient for Phase 1.

### 3.7 Auction Fills

Some EQ fills come from the call auction (pre-open price discovery, 9:00–9:08 IST) or block deal windows. The CSV `auction` column is `"yes"` for these.

Map: `auction = "yes"` → `is_auction = True`. These fills are stored normally and processed through reconstruction. No `execution_fills` column is reserved for auction status in Phase 1 — the `session = PRE_OPEN` classification is the relevant indicator. `is_auction` is logged in the import record for audit purposes only.

### 3.8 Instrument Resolution

`NormalizedFill` carries `symbol_raw`, `exchange_segment`, `instrument_type`, `expiry_date`, and `strike_price`. The `ImportService` uses these to resolve `instrument_id` via the `instruments` table.

**This resolution is not the adapter's responsibility.** The adapter produces the raw parsed values. The import pipeline performs the lookup and raises `InstrumentNotFoundError` if no match exists.

For F&O: the adapter must parse the compact Zerodha symbol into its components before constructing `NormalizedFill`. The adapter is responsible for correct symbol parsing; the import pipeline is responsible for the database lookup.

**exchange_segment derivation:**

| CSV `exchange` | CSV `segment` | `exchange_segment` |
|---|---|---|
| `NSE` | `EQ` | `NSE_EQ` |
| `NSE` | `FO` | `NSE_FO` |
| `BSE` | `EQ` | `BSE_EQ` |
| `BSE` | `FO` | Not supported — flag as `InvalidFillError` |
| `NSE` or `BSE` | `CD` | Not supported — flag as `InvalidFillError` |
| Any other | Any | `InvalidFillError` |

### 3.9 Quantity and Price Precision

- `quantity`: parse as integer string; initialize as `Decimal(str(int_value))`. Must be `> 0` — zero or negative quantity → `InvalidFillError`.
- `price`: parse as decimal string; initialize as `Decimal(price_str)`. Must be `> 0` — zero or negative price → `InvalidFillError`.
- Never initialize Decimal from a float. Parse directly from the string representation per `DECIMAL-USAGE-STANDARD.md`.

---

## 4. Deduplication Key

**Per-fill dedup key:** `(fill_id, account_id)` on `execution_fills`.

`fill_id` maps to the CSV `trade_id` (the exchange-assigned trade identifier — see §1.2 column 11). This is the most stable identifier: exchange trade IDs are immutable once assigned.

A partial unique index must be present on `execution_fills`:
```sql
CREATE UNIQUE INDEX uq_fills_broker_trade_account
    ON execution_fills (fill_id, account_id)
    WHERE fill_id IS NOT NULL;
```

This index is referenced in the existing ORM comment: *"Partial unique index for idempotent re-import is defined in the migration."* Bhima must add this index in migration 0008 alongside the `account_id` column addition.

**Import-level dedup:** The `ImportService` also checks the `import_records` table for a matching `(file_hash, account_id)` pair before parsing. This prevents re-processing of an identical file upload. A re-upload with corrections (different bytes, different hash) is treated as a new import run — fill-level dedup handles overlap naturally via the unique index.

---

## 5. Malformed and Unknown-Row Behavior

### 5.1 Principle: Isolate, Skip, Continue

A single malformed row must not abort the entire import. The adapter collects errors and returns them alongside the valid fills. The `ImportService` records errors in the `ImportRecord` and continues writing valid fills.

### 5.2 Error Classification

| Error class | When raised | Recovery |
|---|---|---|
| `InvalidFillError(row_index, message)` | A single row fails validation — missing required column, unparseable value, unsupported segment, bad side value, price ≤ 0, quantity ≤ 0 | Skip row; continue |
| `MissingProductTypeError` | EQ-series or FO-segment rows present but no `product` column and no `product_type_hint` provided (G4 ruling) | Raised before any rows are parsed; entire import halted |
| `UnrecognizedFileError` | `detect()` returns `False` — file does not match Zerodha tradebook format | Raised by adapter; `ImportService` can try other registered adapters |
| `EmptyFileError` | CSV has headers but zero data rows | Raised; import record written with `status = EMPTY` |

### 5.3 Error Context in `InvalidFillError`

`InvalidFillError` must carry:
- `row_index` (1-based row number in the CSV, excluding header)
- `field_name` (which column caused the failure)
- `raw_value` (the raw string from the CSV)
- `message` (human-readable description)

This allows the import summary returned to the caller to include a structured error list that can be surfaced in the UI (Phase 2).

### 5.4 Rows That Cannot Be Classified

If a row has all required fields populated but cannot be classified into a supported instrument type (e.g., a warrant, a bond, an instrument type not in `['EQ', 'FUT', 'CE', 'PE']`): raise `InvalidFillError(row_index, "Unsupported instrument type")`. Do not silently drop rows.

---

## 6. `detect()` Method Contract

`ZerodhaAdapter.detect(file_content: bytes) → bool`

Returns `True` if the first non-empty CSV row contains at least these columns in the header:
`symbol`, `trade_date`, `exchange`, `segment`, `trade_type`, `quantity`, `price`, `trade_id`, `order_id`, `order_execution_time`

Returns `False` otherwise. Does not raise.

Column order is not checked — Zerodha may vary column ordering across versions. Detection is header-presence-based, not column-position-based.

---

## 7. What the Adapter Does Not Do

The adapter is responsible for **parsing and normalizing raw broker data into `NormalizedFill` objects**. The following are explicitly NOT adapter responsibilities:

| Not an adapter concern | Handled by |
|---|---|
| Instrument resolution (`instrument_id` lookup) | `ImportService` |
| Duplicate detection (DB query) | `ImportService` |
| Writing to `execution_fills` | `ImportService` |
| Trade reconstruction | `ReconstructionEngine` |
| P&L calculation | `PnlService` |
| `account_id` assignment | `ImportService` (from API call parameter) |
| `user_id` assignment | `ImportService` (from session) |
| Reconciliation against contract note totals | Phase 2 (Sanjaya) |

---

## 8. Ganesha Validation Points

The following domain rule validations must be confirmed by Ganesha before Bhima implements `ImportService`:

| Point | Domain rule reference | Question |
|---|---|---|
| **G1** — Is `is_expiry_squareoff = True` sufficient to set `exit_type = 'EXPIRY_SQUAREOFF'`? | `TRADE-DOMAIN-RULES.md` | Confirm this `exit_type` value is legal and recognized by the reconstruction engine. |
| **G2** — Are auction fills (pre-open CNC buys at 9:00–9:08) treated identically to regular fills by the reconstruction engine? | `TRADE-RECONSTRUCTION-SPEC.md` | Confirm no special handling is needed for `session = PRE_OPEN`. |
| **G3** — For EQ `series = BE` (trade-for-trade), confirming `product_type = CNC` is the correct mapping. | Rule 3.1 `TRADE-DOMAIN-RULES.md` | BE series is always delivery — confirm. |
| **G4** — For F&O fills with `product` column absent, confirming `product_type = NRML` is always correct for the FO segment. | Rule 3.1 | F&O intraday (MIS) in Zerodha is still placed under the FO segment — confirm how the tradebook distinguishes these when `product` column is absent. |

Bhima should not implement derivation rules for G1, G2, G3, G4 until Ganesha provides written confirmation.

---

## 9. Open Item: MIS vs CNC Disambiguation (Phase 1 Limitation)

**Summary:** Zerodha tradebooks that lack the `product` column cannot distinguish MIS from CNC for EQ-series equity fills without external context. This is a real Phase 1 limitation.

**Phase 1 mitigation:** The `POST /v1/accounts/{id}/import` endpoint accepts an optional query parameter `product_type_hint: 'MIS' | 'CNC'`. Callers must provide this when uploading a tradebook that lacks the `product` column and contains EQ-series fills. The import will fail with `MissingProductTypeError` if the hint is absent and the file lacks the column.

**Phase 2 resolution:** Zerodha Kite API (`GET /trades`) includes `product` on every trade response. When API integration is built in Phase 2, this derivation gap is eliminated at source.

---

*Sanjaya — Broker & Market Data Integration Engineer*
*Inputs: `docs/design/TRADE-DOMAIN-DATA-MODEL.md`, `docs/standards/TRADE-DOMAIN-RULES.md`, `docs/project-status/STEP-11-EXECUTION-PLAN.md`, `ADR-005`, Sanjaya `REFERENCE.md`*
*Ganesha validation required on items G1–G4 before implementation of §3.4 and §3.5.*
*Implementation owner: Bhima*
