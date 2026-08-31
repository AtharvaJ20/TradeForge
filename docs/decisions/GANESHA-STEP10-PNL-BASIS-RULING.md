# Ganesha Domain Ruling — P&L Cost Basis and FIFO for Step 10

**Status:** Authoritative
**Author:** Ganesha (Trading Domain Analyst)
**Date:** 2026-08-24
**Binding on:** Bhima (Step 10 implementation), Kubera (charge and P&L formulas), Sahadeva (QA test cases)
**Requested by:** Krishna (Step 10 execution plan — Decision 1 pre-decision)
**Depends on:** `TRADE-DOMAIN-RULES.md` · `TRADE-RECONSTRUCTION-SPEC.md` · `JOURNAL-PNL-INTEGRATION.md`

---

## Purpose

This ruling resolves Decision 1 from the Step 10 execution plan: which FIFO rules apply to the Step 10 P&L engine, and what cost basis inputs Step 10 may treat as authoritative. It is the written pre-decision Bhima needs before implementing `PnlCalculator`.

---

## Ruling

**Step 10 does not perform lot attribution. Step 10 does not re-solve FIFO.**

The reconstruction engine (Bhima, Steps 7–9) is the sole owner of lot attribution. It writes `trades.average_entry`, `trades.average_exit`, and `trades.total_entry_quantity` onto every closed trade. These values are the post-attribution, post-FIFO result. Step 10 reads them as authoritative inputs and computes gross P&L directly from them.

This boundary is absolute:
- **Reconstruction engine** owns: which fills belong to which lot, which lot is closed by a sell fill (FIFO), what the resulting average entry is.
- **Step 10 P&L engine** owns: gross P&L formula, charge calculation, net P&L, R-multiple.

If reconstruction produces a wrong `average_entry` (e.g., a FIFO attribution error), the P&L will be arithmetically correct but economically wrong. Correctness of `average_entry` is Bhima's responsibility, not Kubera's.

---

## P&L Basis by Instrument Type

### MIS — Intraday Equity

**Lot attribution:** none required. A MIS position is opened and closed within the same session. No overnight hold, no multi-lot accumulation.

**FIFO:** not applicable (Trade Domain Rule 4.2).

**Cost basis for Step 10:**
```
average_entry  = weighted average of all ENTRY fills within this trade
average_exit   = weighted average of all EXIT fills within this trade
total_quantity = total_entry_quantity on the trades row
```

**Gross P&L formula (LONG):**
```
gross_pnl = (average_exit − average_entry) × total_entry_quantity
```

**Gross P&L formula (SHORT):**
```
gross_pnl = (average_entry − average_exit) × total_entry_quantity
```

Both values (`average_entry`, `average_exit`) are computed and stored by the reconstruction engine before Step 10 runs. Step 10 reads them directly.

---

### CNC — Delivery Equity (Overnight Hold)

**Lot attribution:** FIFO applies when multiple open lots exist for the same instrument (Trade Domain Rule 4.1). The reconstruction engine processes sells against open tax lots in `purchase_date ASC` order, decrements `tax_lots.quantity_remaining`, and records the cost basis for each lot portion closed.

**Phase 1 constraint:** the reconstruction spec enforces at most one open CNC trade (one open lot) per instrument per user in Phase 1. With only one open lot, FIFO is trivially satisfied — the single lot is always the one closed. Reconstruction still goes through the FIFO path for consistency, but the result is identical to simple average cost in Phase 1.

**Cost basis for Step 10:** `trades.average_entry` is the `cost_per_share` of the tax lot closed. For a single-lot Phase 1 trade, this equals the weighted average of the entry fills.

**Gross P&L formula (LONG CNC):**
```
gross_pnl = (average_exit − average_entry) × total_entry_quantity
```

**Step 10 reads `average_entry` from `trades` — it does not inspect `tax_lots` directly.**

**Future multi-lot note:** when Unresolved 4 (multi-day partial exits across multiple lots) is resolved, the reconstruction engine will update `trades.average_entry` to reflect the FIFO-attributed cost basis for the quantity actually closed. Step 10 code requires no change — the formula is the same; only the value of `average_entry` changes.

---

### CNC_SAME_DAY — CNC Opened and Closed Same Day

**Lot attribution:** one trade, opened and closed within one session. No multi-lot concern.

**FIFO:** not applicable within a single trade.

**Cost basis for Step 10:** identical to MIS. `average_entry` and `average_exit` are weighted averages of entry and exit fills.

**Gross P&L formula:** same as MIS (LONG/SHORT formula above).

**Note on charges:** `CNC_SAME_DAY` uses delivery STT rates (both legs, 0.1%) not intraday rates. This is a charge calculation distinction, not a P&L basis distinction. The gross P&L formula is unchanged.

---

### NRML_FUT — Futures (Positional)

**Lot attribution:** none in Phase 1. F&O tax lot FIFO (Unresolved 5) is not resolved and is out of scope for Step 10.

**Cost basis for Step 10:** `trades.average_entry` is the weighted average of all ENTRY fills within this trade. If the position was built incrementally across multiple sessions (scale-in), reconstruction computes the running weighted average and stores the final value.

**Gross P&L formula (LONG NRML_FUT):**
```
gross_pnl = (average_exit − average_entry) × total_entry_quantity
```

Where `total_entry_quantity` is expressed in **shares/units** (not lots). `total_entry_quantity = number_of_lots × lot_size`. Step 10 reads `total_entry_quantity` from `trades` — it does not re-multiply by lot size.

**Gross P&L formula (SHORT NRML_FUT):**
```
gross_pnl = (average_entry − average_exit) × total_entry_quantity
```

---

### NRML_OPT — Options (Positional)

**Lot attribution:** none in Phase 1. Same rationale as NRML_FUT.

**Cost basis for Step 10:** `average_entry` = weighted average premium paid per unit across all entry fills. `average_exit` = weighted average premium received/paid per unit across all exit fills.

**Gross P&L formula (LONG NRML_OPT — bought premium):**
```
gross_pnl = (average_exit − average_entry) × total_entry_quantity
```

**Gross P&L formula (SHORT NRML_OPT — sold premium):**
```
gross_pnl = (average_entry − average_exit) × total_entry_quantity
```

Where `total_entry_quantity` is expressed in units (lots × lot_size), already computed by reconstruction.

---

## Step 10 Input Contract

Step 10 reads the following columns from `trades` for every closed trade. These are the only P&L inputs it requires:

| Column | Source | Notes |
|---|---|---|
| `trade_id` | `trades.id` | Key for writing `trade_pnl` |
| `user_id` | `trades.user_id` | Required on `trade_pnl` for RLS |
| `trade_type` | `trades.trade_type` | Selects charge schedule: MIS / CNC / CNC_SAME_DAY / NRML_FUT / NRML_OPT |
| `direction` | `trades.direction` | LONG or SHORT — selects gross P&L formula sign |
| `average_entry` | `trades.average_entry` | Authoritative entry cost basis. NUMERIC(18,4). |
| `average_exit` | `trades.average_exit` | Authoritative exit price. NUMERIC(18,4). |
| `total_entry_quantity` | `trades.total_entry_quantity` | Quantity in units (not lots). NUMERIC(18,4). |
| `trade_date` | `trades.trade_date` | Selects the effective charge schedule row by date. |
| `broker` | `execution_fills.broker` | Selects broker's charge schedule. Read from fills, not from `trades`. |

Step 10 does **not** read `tax_lots`. Step 10 does **not** read individual `execution_fills` except to obtain `broker`.

---

## Scale-In and Scale-Out

### Scale-In (Multiple Entry Fills)

A position built through multiple entry fills (e.g., BUY 100 @ ₹251.20, then BUY 100 @ ₹252.00) produces a single weighted average entry:

```
average_entry = (100 × 251.20 + 100 × 252.00) / 200 = ₹251.6000
```

The reconstruction engine computes this and stores it in `trades.average_entry`. Step 10 reads the stored value. Step 10 does not re-derive it from fills.

**Gross P&L is computed on the fully averaged cost basis — not per-fill.** There is no "per-fill P&L" concept in Step 10.

### Scale-Out (Multiple Exit Fills)

A position closed through multiple exit fills (e.g., SELL 100 @ ₹255.00, then SELL 100 @ ₹257.00) produces a single weighted average exit:

```
average_exit = (100 × 255.00 + 100 × 257.00) / 200 = ₹256.0000
```

The reconstruction engine computes this and stores it in `trades.average_exit`. Step 10 reads the stored value.

**Partial exits during an open trade are not a Step 10 concern.** Partial exits are management events recorded by the user. Step 10 only runs after the trade is fully closed (`trades.status = CLOSED`).

---

## Partial Fills

A partial fill is a broker execution where a single order is filled in parts (e.g., a limit order for 200 shares fills as 50 + 150 across two broker events). These arrive as multiple `execution_fills` rows. The reconstruction engine treats them as multiple fills within the same trade and computes the weighted average normally. By the time Step 10 runs, the result is identical to a single fill — `average_entry` holds the weighted value. Step 10 is not aware that partial fills occurred.

---

## Remaining Quantities (Partial Trade Close)

Step 10 only runs for fully closed trades (`trades.status = CLOSED`, `trades.net_position = 0`). It does not run for open or partially-closed trades. Remaining open quantity has no P&L record until the trade closes.

A `trade_pnl` row is created once, when the trade closes. It is not created incrementally as exit fills arrive.

---

## Edge Cases — Scope and Handling

### Edge case 1 — Zero-quantity trade

**Scenario:** `total_entry_quantity = 0` (data anomaly — no fills assigned to trade).
**Step 10 handling:** do not run. Absence of fills means `average_entry` and `average_exit` are undefined. Step 10 must not insert a `trade_pnl` row. The trade remains in `PENDING_CALCULATION` state.

### Edge case 2 — `average_entry = average_exit` (breakeven)

**Scenario:** exit price exactly equals entry price.
**Step 10 handling:** `gross_pnl = 0.0000`. Valid. Charges still apply. `net_pnl` will be negative (losing trade after charges).

### Edge case 3 — SHORT trade where `average_exit > average_entry` (losing short)

**Scenario:** trader sold short at ₹1,000 and covered at ₹1,050.
**Step 10 handling:** `gross_pnl = (1000 − 1050) × quantity = −50 × quantity`. Negative gross P&L. Normal case. The SHORT formula explicitly handles this.

### Edge case 4 — CNC trade with `average_entry = 0`

**Scenario:** reconstruction anomaly — entry fills missing or unprocessed.
**Step 10 handling:** same as Edge case 1 — do not run. `average_entry = 0` on a CNC trade is an invalid state; it means reconstruction did not complete. The P&L engine must guard against this and leave the row absent.

### Edge case 5 — Charge schedule not found for `(broker, trade_type, trade_date)`

**Scenario:** no `charge_schedules` row matches the trade's broker, trade_type, and a rate effective on or before `trade_date`.
**Step 10 handling:** raise `ChargeScheduleNotFoundError`. Do not insert a partial `trade_pnl` row. Log the error for operator review. The trade remains in `PENDING_CALCULATION` state. This is a configuration gap, not a domain error.

### Edge case 6 — `r_multiple` when `planned_risk_amount` is NULL or zero

**Scenario:** user has not set a planned stop in the journal, or planned stop equals entry (zero risk amount).
**Step 10 handling:** `r_multiple = NULL`. This is a valid state. Do not error. The `trade_pnl` row is inserted with all other columns populated and `r_multiple = NULL`.

---

## Acceptance Examples

All examples use LONG direction unless stated. All values in INR. Calculations use Python `Decimal` at full precision; final stored values are `NUMERIC(18,4)`.

---

### Example 1 — MIS Trade, Single Entry Fill, Single Exit Fill

```
Instrument:      RELIANCE EQ, NSE
Direction:       LONG
trade_type:      MIS
total_quantity:  100 shares

Entry fill:      BUY 100 @ ₹2,450.0000
average_entry:   ₹2,450.0000

Exit fill:       SELL 100 @ ₹2,480.0000
average_exit:    ₹2,480.0000

gross_pnl:       (2,480.0000 − 2,450.0000) × 100 = ₹3,000.0000
```

Step 10 reads `average_entry = 2450.0000`, `average_exit = 2480.0000`, `total_entry_quantity = 100`.

---

### Example 2 — MIS Trade, Scale-In Entry (2 fills), Scale-Out Exit (2 fills)

```
Instrument:      INFY EQ, NSE
Direction:       LONG
trade_type:      MIS

Entry fill 1:    BUY 100 @ ₹1,800.0000
Entry fill 2:    BUY 100 @ ₹1,810.0000

average_entry (computed by reconstruction):
  = (100 × 1800 + 100 × 1810) / 200
  = 361,000 / 200
  = ₹1,805.0000

Exit fill 1:     SELL 100 @ ₹1,830.0000
Exit fill 2:     SELL 100 @ ₹1,825.0000

average_exit (computed by reconstruction):
  = (100 × 1830 + 100 × 1825) / 200
  = 365,500 / 200
  = ₹1,827.5000

total_entry_quantity: 200

gross_pnl = (1,827.5000 − 1,805.0000) × 200 = ₹4,500.0000
```

Step 10 reads the stored averages — it does not re-derive them from fills.

---

### Example 3 — CNC Trade, Phase 1 (Single Lot), Overnight Swing

```
Instrument:      RELIANCE EQ, NSE
Direction:       LONG
trade_type:      CNC

Entry fill:      BUY 50 @ ₹2,400.0000  (2026-01-15)
                 BUY 50 @ ₹2,420.0000  (2026-01-16, scale-in next day)

average_entry (reconstruction):
  = (50 × 2400 + 50 × 2420) / 100
  = 241,000 / 100
  = ₹2,410.0000

Tax lot created by reconstruction:
  quantity_remaining: 100
  cost_per_share:     ₹2,410.0000

Exit fill:       SELL 100 @ ₹2,500.0000  (2026-01-22)
FIFO attribution: one open lot — 100% of the sell closes this lot
average_exit:    ₹2,500.0000

gross_pnl = (2,500.0000 − 2,410.0000) × 100 = ₹9,000.0000
```

Step 10 reads `average_entry = 2410.0000` from `trades`. The FIFO check happened in reconstruction and was trivial (one lot).

---

### Example 4 — NRML_FUT Trade (Short), Single Lot

```
Instrument:      NIFTY JAN FUT, NSE_FO
Direction:       SHORT
trade_type:      NRML_FUT
Lot size:        50 (stored on instrument; already factored into total_entry_quantity by reconstruction)

Entry fill:      SELL 1 lot (50 units) @ ₹24,000.0000
average_entry:   ₹24,000.0000

Exit fill:       BUY 1 lot (50 units) @ ₹23,800.0000
average_exit:    ₹23,800.0000

total_entry_quantity: 50 (units, not lots)

gross_pnl = (24,000.0000 − 23,800.0000) × 50 = ₹10,000.0000
```

Step 10 uses `total_entry_quantity = 50` (units) directly from `trades`. It does not multiply by lot_size again.

---

### Example 5 — NRML_OPT Trade (Long Call, Losing Trade)

```
Instrument:      NIFTY 24000 JAN CE, NSE_FO
Direction:       LONG
trade_type:      NRML_OPT
Lot size:        50 units

Entry fill:      BUY 1 lot (50 units) @ ₹200.0000 premium per unit
average_entry:   ₹200.0000

Exit fill:       SELL 1 lot (50 units) @ ₹120.0000 premium per unit
average_exit:    ₹120.0000

total_entry_quantity: 50

gross_pnl = (120.0000 − 200.0000) × 50 = −₹4,000.0000
```

Negative gross P&L — losing trade. Options premium received on exit is less than premium paid at entry. Charges still apply; `net_pnl` will be more negative.

---

### Example 6 — R-Multiple Calculation

```
gross_pnl:            ₹3,000.0000  (from Example 1)
total_charges:        ₹87.2500     (illustrative — computed by Kubera charge formulas)
net_pnl:              ₹3,000.0000 − ₹87.2500 = ₹2,912.7500

planned_risk_amount:  ₹1,000.0000  (user set planned_stop in journal entry)

r_multiple = 2,912.7500 / 1,000.0000 = 2.912750 (stored as NUMERIC(18,6))
```

If `planned_risk_amount` is NULL (no planned stop set), `r_multiple = NULL`.

---

## What FIFO Unresolveds Mean for Step 10

The following domain questions remain unresolved (from `TRADE-DOMAIN-RULES.md` Part 6):

| Unresolved | What it affects | Step 10 impact |
|---|---|---|
| Unresolved 4 — Multi-day partial exits for CNC (FIFO across exits) | Reconstruction: which lot is closed on which date | **None.** When resolved, reconstruction updates `average_entry`. Step 10 formula is unchanged. |
| Unresolved 5 — F&O tax lot FIFO (incremental position builds) | Reconstruction: average cost computation for multi-session NRML builds | **None.** When resolved, reconstruction updates `average_entry`. Step 10 formula is unchanged. |
| Unresolved 1 — F&O expiry handling | Reconstruction: how expiry fills are recorded | **None for Step 10.** Expiry creates a closing fill. Reconstruction closes the trade normally. Step 10 runs when status = CLOSED. |
| Unresolved 2 — Options exercise/assignment | Reconstruction: cost basis of resulting equity position | **None for Step 10 of the options trade itself.** The options trade closes at exercise; `average_exit = exercise settlement price`. Step 10 runs on that. |
| Unresolved 3 — Corporate actions on delivery holdings | Reconstruction: retroactive cost basis adjustment | **None.** When reconstruction adjusts `average_entry` for a corporate action, a Step 10 recalculation is triggered (engine_version bump or calculated_at staleness rule). Step 10 formula is unchanged. |

**Summary:** none of the five unresolveds block Step 10 implementation. All five are reconstruction-level concerns. Step 10 is insulated from them by the `trades.average_entry` / `trades.average_exit` abstraction boundary.

---

## Summary of Ruling

| Instrument type | FIFO applies to Step 10? | Step 10 reads | Gross P&L basis |
|---|---|---|---|
| MIS | No | `average_entry`, `average_exit`, `total_entry_quantity` | Weighted average of all fills |
| CNC | No (lot attribution done by reconstruction) | `average_entry`, `average_exit`, `total_entry_quantity` | FIFO-attributed cost from reconstruction |
| CNC_SAME_DAY | No | `average_entry`, `average_exit`, `total_entry_quantity` | Weighted average of all fills |
| NRML_FUT | No | `average_entry`, `average_exit`, `total_entry_quantity` | Weighted average of all fills |
| NRML_OPT | No | `average_entry`, `average_exit`, `total_entry_quantity` | Weighted average of all fills |

**Step 10 is not blocked by any unresolved FIFO question.**

Bhima may proceed with `PnlCalculator` implementation using `trades.average_entry`, `trades.average_exit`, and `trades.total_entry_quantity` as authoritative P&L inputs for all five trade types.

---

*Ganesha — Trading Domain Analyst*
*This ruling is binding on Bhima's Step 10 implementation. It does not modify `TRADE-DOMAIN-RULES.md` — it applies the existing rules to the specific P&L engine scope.*
