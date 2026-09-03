# Ganesha Domain Ruling — G1–G4 Confirmations for NORMALIZED-FILL-CONTRACT.md

**Status:** Accepted — formal domain ruling
**Author:** Ganesha (Trading Domain Analyst)
**Date:** 2026-09-01
**Requested by:** Sanjaya (WS-0 Decision 1, Step 11)
**Binding on:** Bhima (import pipeline implementation), Sanjaya (adapter spec updates), Sahadeva (QA)
**Reference document:** `docs/design/NORMALIZED-FILL-CONTRACT.md` §8

---

## G1 — `exit_type = 'EXPIRY_SQUAREOFF'` for broker-initiated F&O expiry close

**Ruling: CONFIRMED — with clarification.**

A broker-initiated expiry square-off is a real exchange fill. When Zerodha auto-closes an open NRML F&O position at or before expiry (e.g., because the contract expires while a position is still open), the broker submits a market order on the trader's behalf. This produces a fill row in the tradebook with all standard fill fields populated. It is a legitimate `EXIT` fill.

Setting `exit_type = 'EXPIRY_SQUAREOFF'` on that fill row is correct and is consistent with the existing `exit_type = 'FORCED'` designation in Rule 5.3 (MIS auto-squareoff). Both represent broker-initiated closes — `FORCED` is mid-session, `EXPIRY_SQUAREOFF` is at or before contract expiry.

**Formal addition to the accepted `exit_type` vocabulary:**

| `exit_type` value | Meaning | Domain rule |
|---|---|---|
| `NULL` | Exit type not specified (manual entry or standard close) | Default |
| `FORCED` | MIS position auto-squared by broker at session cutoff (15:10–15:20 IST) | Rule 5.3 |
| `EXPIRY_SQUAREOFF` | NRML F&O position closed by broker because the contract is expiring | **Added by this ruling** |

`EXPIRY_SQUAREOFF` is **not** the same as an option expiring worthless (Unresolved 1 in `TRADE-DOMAIN-RULES.md`). An `EXPIRY_SQUAREOFF` fill exists in the tradebook — the broker executed a real closing transaction. An expired-worthless option produces no fill — the position simply ceases to exist at zero value. Unresolved 1 (how to handle a zero-value option expiry) remains open and is outside the scope of this ruling.

**Constraint:** `exit_type = 'EXPIRY_SQUAREOFF'` may only be set when `fill_role = 'EXIT'`. The existing ORM CHECK constraint `(exit_type IS NULL OR fill_role = 'EXIT' OR fill_role IS NULL)` already enforces this. No migration change required.

---

## G2 — Pre-open session fills (`session = PRE_OPEN`) treated identically by reconstruction engine

**Ruling: CONFIRMED — no special handling required.**

The reconstruction engine's position state machine (TRADE-RECONSTRUCTION-SPEC.md §4) processes fills ordered by `fill_timestamp ASC`. The `session` field is stored on the fill for audit and analytics purposes, but the engine's state transitions are driven exclusively by:

- `fill.side` (BUY/SELL)
- `fill.quantity`
- `fill.fill_timestamp` (ordering)
- `fill.trade_date` (for CNC_SAME_DAY detection at close)
- `fill.product_type` (processing unit scoping)

Session value does not alter any state machine transition. A `PRE_OPEN` BUY fill opens a trade identically to a `REGULAR` BUY fill. The reconstruction engine must not branch on `session`.

**CNC_SAME_DAY note:** A CNC trade opened in the pre-open session (09:00–09:15) and closed during the same regular session carries `trade_date` equal to the execution date for both open and close fills. The `CNC_SAME_DAY` detection in §8 of the reconstruction spec compares `first_entry_fill.trade_date == last_exit_fill.trade_date` — this comparison is date-only and is unaffected by the session value. A pre-open CNC buy closed the same day is correctly classified as `CNC_SAME_DAY`. No special handling needed.

**AMO corollary (confirmed):** AMO fills that execute in the pre-open session the following day carry that following day's `trade_date` and a `fill_timestamp` in the 09:00–09:08 IST window. They are classified as `session = PRE_OPEN` by Sanjaya's adapter and processed identically to any other pre-open fill. The engine has no concept of "the order was placed yesterday." Confirmed — no special AMO handling needed in the reconstruction engine.

---

## G3 — `series = BE` (trade-for-trade) maps to `product_type = CNC`

**Ruling: CONFIRMED.**

BE series (sometimes called "Trade-for-Trade" or "T2T" series) stocks are securities placed by NSE/BSE in a special settlement category that requires compulsory physical delivery. Key characteristics:

1. **MIS orders are structurally prohibited** on BE series stocks. Zerodha (and all compliant brokers) block intraday (MIS) order placement for BE series instruments at the order entry stage. An MIS fill in the BE series cannot exist in a legitimate Zerodha tradebook.

2. BE series stocks settle T+1 compulsorily. The settlement mechanism is delivery — consistent with CNC semantics.

3. The distinction between `series = BE` and `series = EQ` at Zerodha is a function of exchange classification, not a trader choice. A stock in BE series always requires CNC product behaviour.

**Therefore:** `series = BE` → `product_type = CNC` is not an inference from behaviour — it is a structural constraint of how the instrument is classified. This derivation is Rule 3.1 compliant.

**Bhima implementation note:** The instrument record for BE series stocks must store `exchange_segment = NSE_EQ`. The series information (`BE`) is not stored in the `instruments` table and does not need to be — it is only used at adapter time to derive `product_type`, which is stored on the `execution_fill`.

---

## G4 — F&O segment without `product` column: `product_type = NRML` default

**Ruling: PARTIAL REJECTION — Sanjaya must update the spec.**

### The problem

Rule 3.1 is absolute: *"The classification of a trade as intraday or delivery (or F&O) is determined by the `product_type` field on the order at the time of order entry. It is not inferred from trading behavior after the fact."*

Traders who use **F&O intraday margin (MIS product type)** will have FO segment fills with `product_type = MIS` in their tradebook when the `product` column is present. These fills:
- Belong to the `INTRADAY` product_type_family (MIS → INTRADAY per the processing unit table)
- Are NOT in the same processing unit as NRML F&O fills on the same instrument
- May carry different charge schedule considerations (though at Zerodha, F&O brokerage is flat ₹20/trade regardless of MIS or NRML)

Assuming all FO segment fills are `NRML` when the `product` column is absent would silently misclassify any MIS-F&O fills as NRML. Even if the charge impact at Zerodha specifically is negligible, the processing unit scoping is wrong — MIS F&O fills would be grouped with NRML F&O fills into a single processing unit and potentially reconstructed into the same trade. This is incorrect reconstruction behaviour.

### The correct approach

The `product_type_hint` mechanism Sanjaya already defined for EQ segment applies equally to FO segment. When the `product` column is absent:

- **If the user provides `product_type_hint`:** apply it to all EQ-series fills AND all FO segment fills where `product_type` cannot be derived from file content.
- **If the user does not provide `product_type_hint`:** raise `MissingProductTypeError` before parsing any rows. The message should say: *"This tradebook does not contain a 'product' column. Provide product_type_hint='MIS', 'CNC', or 'NRML' to classify fills. If the file contains mixed product types, separate the fills into separate imports."*

**Practical note for Sanjaya:** In reality, the vast majority of retail traders using Zerodha either (a) only trade F&O positionally (all NRML) or (b) only trade F&O intraday (all MIS). A mixed MIS+NRML account is uncommon. The `product_type_hint` mechanism handles both cases correctly. The important thing is that the user makes an explicit declaration rather than the system guessing.

### Correction to NORMALIZED-FILL-CONTRACT.md §3.4

The F&O derivation rule in §3.4 currently reads:
> "F&O segment: always `NRML`"

This must be updated to:
> "F&O segment: if `product` column is present, use it directly (`MIS` or `NRML`). If `product` column is absent, apply `product_type_hint` if provided. If neither is available, raise `MissingProductTypeError`."

### The derivation table in §3.4, corrected

| Condition | Derived `product_type` | Basis |
|---|---|---|
| `product` column present in file | Use CSV value directly (`MIS`, `CNC`, `NRML`) | Authoritative per Rule 3.1 |
| `product` column absent, `segment = EQ`, `series = BE` | `CNC` | Structural (G3 ruling) |
| `product` column absent, `product_type_hint` provided | Use hint value | User declaration — acceptable under Rule 3.1 |
| `product` column absent, no hint, `segment = EQ`, `series = EQ` | `MissingProductTypeError` | Cannot derive |
| `product` column absent, no hint, `segment = FO` | `MissingProductTypeError` | Cannot derive |

---

## Summary of Required Changes to NORMALIZED-FILL-CONTRACT.md

| Change | Section | Owner |
|---|---|---|
| Add `EXPIRY_SQUAREOFF` to the accepted `exit_type` vocabulary | §3.5 and new table | Sanjaya (update spec) |
| Add G2 confirmation that session has no effect on reconstruction | §3.2 (already correct — no change needed; this is a confirmation) | — |
| Add G3 confirmation that `series = BE` → `CNC` is a structural rule | §3.4 (already correct — no change needed) | — |
| Remove the claim that FO segment without `product` defaults to NRML | §3.4 — must be revised per G4 ruling above | Sanjaya (update spec) |
| Update `MissingProductTypeError` description to cover FO segment | §5.2 | Sanjaya (update spec) |

---

## What Bhima May Now Implement

With G1–G4 resolved:

- **G1 confirmed:** Bhima may implement `exit_type = 'EXPIRY_SQUAREOFF'` in the import pipeline when `is_expiry_squareoff = True` on the `NormalizedFill`.
- **G2 confirmed:** Bhima may implement the reconstruction engine without any session-based branching. `PRE_OPEN` fills enter the state machine identically to `REGULAR` fills.
- **G3 confirmed:** Bhima may implement `series = BE` → `product_type = CNC` in the `ZerodhaAdapter`.
- **G4 partially rejected:** Bhima must NOT implement `product_type = NRML` as the default for FO segment fills when `product` column is absent. Sanjaya must first update NORMALIZED-FILL-CONTRACT.md §3.4, then Bhima implements per the corrected spec.

---

*Ganesha — Trading Domain Analyst*
*Inputs: `TRADE-DOMAIN-RULES.md` (Rules 3.1, 3.2, 5.3), `TRADE-RECONSTRUCTION-SPEC.md` (§3, §4, §7, §8), `NORMALIZED-FILL-CONTRACT.md` §8*
*Effective immediately. Bhima and Sanjaya must not proceed past the blocked items until §3.4 is corrected.*
