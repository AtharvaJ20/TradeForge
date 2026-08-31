# Trade Reconstruction Specification

**Status:** Authoritative — binding on Bhima (implementation), Sanjaya (import pipeline), Kubera (P&L inputs), Karna (analytics inputs), Sahadeva (QA)
**Author:** Ganesha (Trading Domain Analyst)
**Date:** 2026-08-23
**Depends on:** `TRADE-DOMAIN-RULES.md` · `TRADE-DOMAIN-DATA-MODEL.md` · `DECIMAL-USAGE-STANDARD.md`

---

## Purpose

This document specifies the deterministic algorithm by which the TradeForge reconstruction engine converts immutable `execution_fills` rows into `trades`, `execution_fills.fill_role` assignments, and `tax_lots`. It is the single source of truth for every decision the engine makes: when a new trade starts, how direction is determined, how entry and exit fills are classified, how the average entry price is maintained, how trade_type is derived, and how CNC delivery lot tracking interacts with the reconstruction process.

Bhima must not implement the reconstruction engine without satisfying every rule in this document and in `TRADE-DOMAIN-RULES.md`. Any gap between this specification and implementation is a defect.

---

## Contents

1. [Definitions](#1-definitions)
2. [Reconstruction Inputs and Outputs](#2-reconstruction-inputs-and-outputs)
3. [Processing Unit and Fill Ordering](#3-processing-unit-and-fill-ordering)
4. [Position State Machine](#4-position-state-machine)
5. [Trade Boundary Conditions](#5-trade-boundary-conditions)
6. [LONG/SHORT Direction Determination](#6-longshort-direction-determination)
7. [Entry/Exit Classification](#7-entryexit-classification)
8. [trade_type Derivation](#8-trade_type-derivation)
9. [Trade Field Maintenance](#9-trade-field-maintenance)
10. [Tax Lot Interaction](#10-tax-lot-interaction)
11. [Idempotency and Re-import Safety](#11-idempotency-and-re-import-safety)
12. [Error Conditions](#12-error-conditions)
13. [Out of Scope — Unresolved Domain Areas](#13-out-of-scope--unresolved-domain-areas)

---

## 1. Definitions

**Reconstruction engine:** the component (owned by Bhima) that processes newly imported execution fills and produces or updates trade records, assigns `trade_id` and `fill_role` on fills, and creates or updates tax lots. It is the only system component permitted to write `trade_id` and `fill_role` on an `execution_fill`.

**Fill stream:** the ordered sequence of `execution_fills` for a given processing unit (see §3), sorted by `fill_timestamp ASC`. The stream may contain fills that have already been processed (assigned a `trade_id`) alongside newly imported fills. Only unprocessed fills (where `trade_id IS NULL`) are candidate inputs to the engine on a given run.

**Running position:** the algebraic sum of all fill quantities for a given processing unit processed so far, where BUY quantities are positive and SELL quantities are negative. `running_position > 0` means the current trade is LONG; `running_position < 0` means the current trade is SHORT; `running_position = 0` means the position is flat (no open trade).

**Trade boundary:** the event that closes one trade and optionally opens the next. The boundary occurs when the running position transitions to exactly zero.

**Processing unit:** the scope within which the engine tracks a single running position. Defined in §3.

**Unprocessed fill:** an `execution_fill` row where `trade_id IS NULL`. These are the direct input to the reconstruction engine.

**Assigned fill:** an `execution_fill` row where `trade_id IS NOT NULL` and `fill_role IS NOT NULL`. These are immutable — the engine does not re-process or re-assign them.

**product_type_family:** an internal engine concept that groups the three raw broker `product_type` values (`MIS`, `CNC`, `NRML`) into three mutually exclusive families (`INTRADAY`, `DELIVERY`, `FO`). `product_type_family` does not appear in the database schema — it is derived by the engine from the `product_type` field on each fill and used to define the processing unit scope (§3). The mapping is fixed and non-configurable: `MIS → INTRADAY`, `CNC → DELIVERY`, `NRML → FO`. See §3 for the complete mapping table and rationale.

**Prior open position (POP):** a broker position that was opened by fills that pre-date the user's TradeForge import window. The reconstruction engine has no knowledge of a POP until the user explicitly represents it. See §3.4.

**Excluded fill:** an `execution_fill` row that has a corresponding row in the `fill_exclusions` side-table. The reconstruction engine permanently skips excluded fills — they are never processed regardless of their `trade_id` status. The `execution_fills` row is never modified; immutability is preserved. The exclusion record, reason, and references to replacement fills are stored in `fill_exclusions` for audit. See §12 (E1) for the full mechanism.

---

## 2. Reconstruction Inputs and Outputs

### Inputs

| Input | Source | Notes |
|---|---|---|
| Unprocessed fills | `execution_fills WHERE trade_id IS NULL AND id NOT IN (SELECT fill_id FROM fill_exclusions)` | Ordered by `fill_timestamp ASC` within processing unit |
| Existing open trade | `trades WHERE status IN ('OPEN', 'PARTIAL')` | May exist for the processing unit; engine continues building it |
| Existing open tax lots | `tax_lots WHERE status != 'CLOSED'` | For CNC processing units; queried in FIFO order |
| Instrument record | `instruments` | Required for `instrument_type` (needed for `NRML_FUT` vs `NRML_OPT` distinction) |

### Outputs

| Output | Target | Notes |
|---|---|---|
| New `trades` row | `trades` INSERT | When a new trade opens (first fill for a flat position) |
| Updated `trades` row | `trades` UPDATE | On every subsequent fill: running totals, status, average price, timestamps |
| `fill_role` and `trade_id` assigned | `execution_fills` UPDATE | Via `FillRepository.assign_trade(fill_id, trade_id, fill_role)` — the only permitted mutation |
| New `tax_lots` row | `tax_lots` INSERT | When a new CNC trade opens |
| Updated `tax_lots` row | `tax_lots` UPDATE | When CNC exit fills are processed (FIFO lot decrement) |

### What the engine does NOT produce

- P&L figures — owned by Kubera
- Charge amounts — owned by Kubera
- R-multiple — computed by Karna
- Management events — entered by the user, not synthesized from fills

---

## 3. Processing Unit and Fill Ordering

### Processing unit definition

The engine tracks one independent running position per **processing unit**. A processing unit is the 3-tuple:

```
(user_id, instrument_id, product_type_family)
```

where `product_type_family` maps the raw broker `product_type` to one of three buckets:

| Raw `product_type` on fill | `product_type_family` |
|---|---|
| `MIS` | `INTRADAY` |
| `CNC` | `DELIVERY` |
| `NRML` | `FO` |

**Rationale:** in Indian markets, a trader may hold simultaneous positions in the same underlying instrument across product types — for example, 100 RELIANCE CNC (delivery, long-term hold) and 50 RELIANCE MIS (intraday) on the same day. These are not the same position. The broker tracks them separately with independent margin requirements and auto-square rules. The reconstruction engine must track them separately.

`CNC` and `MIS` fills for the same instrument never belong to the same trade. `NRML` fills for a futures contract and a different options contract are on different instruments (different `instrument_id`) and are therefore separate processing units by definition.

### Fill ordering guarantee

Within a processing unit, fills **must** be processed in ascending `fill_timestamp` order. This is the deterministic ordering guarantee. The reconstruction output must be identical regardless of the order in which fills arrive at the import stage, as long as the engine processes them sorted by `fill_timestamp ASC`.

**Tie-breaking:** if two fills share the same `fill_timestamp`, order by `fill_id ASC` (broker's fill ID, lexicographic). If `fill_id` is NULL on both (manual entries), order by `created_at ASC` (import timestamp). If still tied, raise a `ReconstructionAmbiguityError` — two fills with identical timestamps and no distinguishing ID cannot be deterministically ordered; manual resolution is required.

### What triggers a reconstruction run

The engine is triggered per processing unit. Triggers:

1. **Import event:** Sanjaya completes a fill import batch for a user. The engine runs for every processing unit that received at least one new fill.
2. **Manual fill entry:** a user manually enters a fill. The engine runs for the affected processing unit.
3. **Replay:** an operator re-runs reconstruction for a processing unit (e.g., after correcting an import error). All fills are reprocessed from the earliest unprocessed fill (assigned fills are skipped).

### Prior open positions

A **prior open position (POP)** exists when a trader has a position at the broker that was opened by fills that predate the TradeForge import window. The reconstruction engine starts the processing unit in the FLAT state — it has no fills in its database representing how that position was built.

**The problem:** if the first fill the engine encounters for this processing unit is an EXIT fill (e.g., a SELL against a pre-existing long), the state machine in §4 treats it as the opening fill of a SHORT trade. This produces an incorrect trade record: the direction is wrong, the average entry cost is the exit price, and the gross P&L will be inverted.

**The resolution — mandatory manual entry fill:** the user must create a manual `execution_fill` row (via the TradeForge manual entry interface) representing the opening of the prior position, using `import_source = 'MANUAL'`. This fill must:

- Carry a `fill_timestamp` that is strictly earlier than any real broker fill for this processing unit.
- Carry the correct `side` that opens the position (BUY for a prior long, SELL for a prior short).
- Carry a `quantity` equal to the open position size at the time of import.
- Carry a `price` that is the trader's best estimate of their average cost basis for the prior position. This price becomes `average_entry` on the resulting trade and is the cost basis Kubera will use for P&L — an inaccurate price produces an inaccurate P&L.
- Carry the same `product_type` and `broker` values as the fills that will follow.

The engine processes this manual fill as if it were a real fill. The trade it creates will have `import_source = 'MANUAL'` on its opening fill, which is visible in the journal and can serve as a marker that the trade's cost basis is user-declared rather than broker-sourced.

**What the engine does NOT do:**
- It does not detect that a processing unit has a POP problem automatically. A SELL arriving into a FLAT state is reconstructed as a SHORT trade, silently. There is no warning.
- It does not query the broker API to discover the current open position — that is Sanjaya's concern and is out of scope for Phase 1.

**Operator guidance for a new user onboarding with existing positions:** before importing any real broker fills, use the manual fill entry to create one opening fill per processing unit that has an existing position. Import the opening fills with timestamps set to a date before the earliest real fill in the import batch. Then import the real fills normally.

**Sanjaya integration note:** a future Sanjaya enhancement could query the broker's open position API at import time and automatically generate the manual opening fill when a POP is detected. This is not defined here — it is a future Sanjaya responsibility.

---

## 4. Position State Machine

The reconstruction engine maintains a `running_position` (signed Decimal, 4 decimal places) for each processing unit. The engine processes fills one at a time in the ordering defined in §3.

### Signed contribution of each fill

| Fill `side` | Signed contribution to `running_position` |
|---|---|
| `BUY` | `+fill.quantity` |
| `SELL` | `−fill.quantity` |

### State transitions

At each fill, after computing the signed contribution, the engine determines the transition:

```
previous_position = running_position (before this fill)
signed_delta      = +quantity (BUY) or −quantity (SELL)
new_position      = previous_position + signed_delta
```

| Previous state | Fill | New state | Engine action |
|---|---|---|---|
| `= 0` (FLAT) | BUY | `> 0` (LONG) | Open new LONG trade. Fill role = ENTRY. |
| `= 0` (FLAT) | SELL | `< 0` (SHORT) | Open new SHORT trade. Fill role = ENTRY. |
| `> 0` (LONG) | BUY | `> 0` (LONG, larger) | Scale-in. Add to existing trade. Fill role = ENTRY. |
| `> 0` (LONG) | SELL | `> 0` (LONG, smaller) | Partial exit. Fill role = EXIT. |
| `> 0` (LONG) | SELL | `= 0` (FLAT) | Full exit. Fill role = EXIT. Trade closes. |
| `< 0` (SHORT) | SELL | `< 0` (SHORT, larger) | Scale-in. Add to existing trade. Fill role = ENTRY. |
| `< 0` (SHORT) | BUY | `< 0` (SHORT, smaller) | Partial exit. Fill role = EXIT. |
| `< 0` (SHORT) | BUY | `= 0` (FLAT) | Full exit. Fill role = EXIT. Trade closes. |
| `> 0` (LONG) | SELL | `< 0` (SHORT) | **POSITION CROSSING ZERO — error. See §12.** |
| `< 0` (SHORT) | BUY | `> 0` (LONG) | **POSITION CROSSING ZERO — error. See §12.** |

### State machine invariants

These invariants must hold after processing every fill. The engine must assert them before committing each step:

1. `running_position >= 0` for LONG trades and `<= 0` for SHORT trades at all times. `running_position` never crosses zero as part of a single fill — a crossing is an error.
2. `trades.net_position` always equals `|running_position|`.
3. `trades.total_exit_quantity <= trades.total_entry_quantity` at all times.
4. Every fill assigned to a trade has a `fill_role` consistent with the direction × side table in §7.

---

## 5. Trade Boundary Conditions

### Opening a new trade

A new trade is opened when:

- The processing unit is in the FLAT state (`running_position = 0`), AND
- A new fill arrives

The engine creates a new `trades` row. The `id` (trade_id) is generated at this moment and is stable for the lifetime of the trade.

**CRITICAL — trade_id is generated once and never regenerated.** Even if reconstruction is replayed, the same fill must produce the same trade. This is achieved by storing the trade_id on the first assigned fill: if the first fill of a processing unit already has a `trade_id`, the engine resumes the existing trade. It does not create a new one.

### Closing a trade

A trade closes when `new_position = 0` after processing an exit fill. At closure:

1. `trades.status` → `'CLOSED'`
2. `trades.last_fill_at` → `fill.fill_timestamp` of the closing fill
3. `trades.average_exit` is computed (see §9)
4. `trades.net_position` → `0`
5. For CNC trades: affected tax lots are updated (see §10)

### Re-entry after closure: new trade, new trade_id

After a trade closes, the processing unit returns to the FLAT state. The next fill for this processing unit opens a **new trade** with a **new trade_id**, even if:

- The new trade is in the same instrument
- The new trade is in the same direction
- The new trade occurs on the same calendar date (same session)
- The new trade has the same `product_type`

**Rule 1.2 is absolute:** position returning to zero is the only trade boundary condition. There is no minimum hold time, no session boundary, and no calendar date rule that creates a new trade independently of the position returning to zero.

**Example — same-instrument re-entry:**
```
09:31:00  BUY  100 RELIANCE MIS → opens Trade A (LONG, running_position = +100)
09:45:00  SELL 100 RELIANCE MIS → closes Trade A (running_position = 0)
10:02:00  BUY   50 RELIANCE MIS → opens Trade B (LONG, new trade_id, running_position = +50)
```

Trade B is a new trade. It cannot inherit Trade A's `trade_id`.

### Same-session partial exit and re-entry

```
09:31:00  BUY  100 RELIANCE MIS → Trade A opens, ENTRY, position = +100
10:15:00  SELL  50 RELIANCE MIS → Trade A partial exit, EXIT, position = +50
10:45:00  SELL  50 RELIANCE MIS → Trade A closes, EXIT, position = 0
11:00:00  BUY   75 RELIANCE MIS → Trade B opens, ENTRY, position = +75
```

The SELL at 10:45:00 brings the position to zero and closes Trade A. The BUY at 11:00:00 opens Trade B with a new trade_id.

---

## 6. LONG/SHORT Direction Determination

The direction of a trade is determined by the **first fill** processed for that trade (i.e., the fill that opens the trade from a FLAT state).

| First fill `side` | `trades.direction` |
|---|---|
| `BUY` | `LONG` |
| `SELL` | `SHORT` |

**Direction is set once and never changed.** No subsequent fill — scale-in, partial exit, or full exit — may alter `trades.direction`. If a fill's side is inconsistent with the established direction in a way that does not produce a valid transition in §4, the engine raises an error (see §12).

**Direction is not user-supplied during import.** It is a derived field, computed by the engine from the first fill. A user may later annotate a trade's direction for journaling purposes (e.g., correcting an error trade), but the reconstruction engine derives it mechanically.

**SHORT trades in the Indian market context:**

SHORT trades are valid only in specific contexts:

- `MIS` product type on equity: intraday short selling is permitted on NSE-listed securities with SLB availability. The reconstruction engine does not validate whether the short was permitted — it reconstructs what happened.
- `NRML` product type on futures: short futures positions are standard.
- `NRML` product type on options sell-to-open: selling options short (collecting premium) is standard. These are SHORT trades on the options instrument.
- `CNC` short selling: CNC short selling (short delivery) is permitted by some brokers for select securities. The engine reconstructs it identically to any other SHORT trade.

---

## 7. Entry/Exit Classification

The `fill_role` on each fill is derived deterministically from the fill's `side` and the parent trade's `direction`. There are no exceptions.

| Trade `direction` | Fill `side` | `fill_role` |
|---|---|---|
| `LONG` | `BUY` | `ENTRY` |
| `LONG` | `SELL` | `EXIT` |
| `SHORT` | `SELL` | `ENTRY` |
| `SHORT` | `BUY` | `EXIT` |

**Reading the table:**

- A LONG trade is built by buying (ENTRY) and exited by selling (EXIT). Every BUY fill in a LONG trade adds to the position; every SELL fill reduces it.
- A SHORT trade is built by selling (ENTRY) and exited by buying (EXIT). Every SELL fill in a SHORT trade adds to the short; every BUY fill covers (reduces) it.

**Partial exit classification:**

A fill that reduces but does not eliminate the position is still classified as `EXIT`. There is no separate `PARTIAL_EXIT` fill_role. The partial nature of the exit is conveyed by the updated `trades.net_position` and `trades.status = 'PARTIAL'`, not by the fill_role value.

**Scale-in classification:**

A fill that adds to an already-open position (BUY when LONG, SELL when SHORT) is classified as `ENTRY`. There is no separate `SCALE_IN` fill_role. Scale-ins are reflected in the increasing `trades.total_entry_quantity` and recomputed `trades.average_entry`.

**Assignment atomicity:**

`trade_id` and `fill_role` are assigned together in a single atomic write via `FillRepository.assign_trade(fill_id, trade_id, fill_role)`. It is never valid for a fill to have `trade_id IS NOT NULL` and `fill_role IS NULL` or vice versa (the database trigger enforces `(trade_id IS NOT NULL OR fill_role IS NULL)`; the engine guarantees they are set together).

---

## 8. trade_type Derivation

`trade_type` is a derived field set on the `trades` row. It is not entered by the user and is not preserved from the broker record. The engine computes it deterministically.

### Input to derivation

| Input | Source |
|---|---|
| `product_type` from fills | `execution_fills.product_type` — immutable, broker-sourced (Rule 3.1) |
| `instrument_type` from instrument | `instruments.instrument_type` — `EQ`, `FUT`, `CE`, `PE` |
| `trade_date` of first entry fill | `execution_fills.trade_date` |
| `trade_date` of last exit fill | `execution_fills.trade_date` at close |

### Mixed product_type within a trade

The `product_type` on fills within the same trade must all belong to the same `product_type_family` (§3), because the processing unit is scoped by family. Fills from different families cannot share a trade. If a trader converted a MIS position to CNC intraday (a broker-level conversion), the broker will report both fills with their respective product_types; in that case, the engine sees a MIS fill and a CNC fill for the same instrument on the same day. These belong to **different processing units** and therefore produce **different trades** — one MIS trade and one CNC trade.

**When all fills in a trade carry the same raw product_type:** this is the normal case. Use the derivation table below directly.

**When fills within the same product_type_family have different raw product_types:** this cannot occur by construction (MIS and CNC are in different families). Within the `FO` family, all fills carry `product_type = NRML`. No variation is possible within a family.

### Derivation table

| `product_type_family` | Instrument `instrument_type` | Condition | `trade_type` |
|---|---|---|---|
| `INTRADAY` | `EQ` | — | `MIS` |
| `DELIVERY` | `EQ` | First entry fill `trade_date` ≠ last exit fill `trade_date` | `CNC` |
| `DELIVERY` | `EQ` | First entry fill `trade_date` = last exit fill `trade_date` | `CNC_SAME_DAY` |
| `FO` | `FUT` | — | `NRML_FUT` |
| `FO` | `CE` or `PE` | — | `NRML_OPT` |

### trade_type is set in two phases

**Phase 1 — at trade open:**
Set `trade_type` to the provisional value using only information available at open:

| `product_type_family` | Instrument type | Provisional `trade_type` |
|---|---|---|
| `INTRADAY` | `EQ` | `MIS` |
| `DELIVERY` | `EQ` | `CNC` (provisional — may become `CNC_SAME_DAY` at close) |
| `FO` | `FUT` | `NRML_FUT` |
| `FO` | `CE` or `PE` | `NRML_OPT` |

**Phase 2 — at trade close:**
If provisional `trade_type = CNC` and `trades.trade_date = last_exit_fill.trade_date` (same-day close), update `trade_type → CNC_SAME_DAY`.

For all other `trade_type` values, Phase 2 produces no change.

**`CNC_SAME_DAY` is never set at open — it can only be determined at close.** A CNC trade opened at 10:00 that is partially exited at 14:00 on the same day but not yet fully closed remains `CNC` until the final exit fill arrives. At final close, if the open and close dates match, it becomes `CNC_SAME_DAY`.

### Why instrument_type, not instrument class

`NRML_FUT` and `NRML_OPT` are disambiguated by `instruments.instrument_type` (`FUT` vs `CE`/`PE`), not by the fill's `product_type` (both are `NRML`). The instrument record is the authoritative source for this classification. Bhima must look up the instrument record during reconstruction — it cannot be derived from the fill alone.

---

## 9. Trade Field Maintenance

This section specifies how each field on the `trades` row is maintained as fills are processed. All calculations follow `DECIMAL-USAGE-STANDARD.md`.

### Fields set at trade open (first ENTRY fill)

| Field | Value at open |
|---|---|
| `id` | Newly generated UUID |
| `user_id` | `fill.user_id` |
| `instrument_id` | `fill.instrument_id` |
| `trade_type` | Provisional (see §8) |
| `direction` | From §6 |
| `status` | `'OPEN'` |
| `trade_date` | `fill.trade_date` |
| `first_fill_at` | `fill.fill_timestamp` |
| `last_fill_at` | `NULL` |
| `total_entry_quantity` | `fill.quantity` |
| `total_exit_quantity` | `0` |
| `net_position` | `fill.quantity` |
| `average_entry` | `fill.price` (quantized to 4 dp) |
| `average_exit` | `NULL` |

### average_entry — maintained incrementally on each ENTRY fill

After each new ENTRY fill is assigned to a trade, recompute `average_entry` using all ENTRY fills assigned to that trade:

```
average_entry = Σ(fill.quantity × fill.price for all ENTRY fills on this trade)
                ÷ Σ(fill.quantity for all ENTRY fills on this trade)
```

Quantized to 4 decimal places per Rule 7 of `DECIMAL-USAGE-STANDARD.md`. Intermediate calculation uses full Decimal precision; quantization is applied to the final result only.

`average_entry` **does not change** on EXIT fills. A partial exit does not alter the average entry cost.

### average_exit — computed at trade close

`average_exit` is computed **once, at trade close**, from all EXIT fills assigned to that trade:

```
average_exit = Σ(fill.quantity × fill.price for all EXIT fills on this trade)
               ÷ Σ(fill.quantity for all EXIT fills on this trade)
```

Quantized to 4 decimal places. `average_exit` is `NULL` until the trade closes.

**Note:** for partial exits, the per-partial-exit P&L is computed by Kubera using the per-fill price and `average_entry` at the time of exit. The reconstruction engine does not compute P&L — it provides the fill records and the trade-level averages, which are the inputs Kubera requires. See Rule 2.2.

### Running totals maintained per fill

| Field | On ENTRY fill | On EXIT fill |
|---|---|---|
| `total_entry_quantity` | `+= fill.quantity` | no change |
| `total_exit_quantity` | no change | `+= fill.quantity` |
| `net_position` | `+= fill.quantity` | `−= fill.quantity` |
| `average_entry` | recomputed | no change |
| `average_exit` | no change | `NULL` (until closed) |
| `status` | `'OPEN'` or `'PARTIAL'`* | `'PARTIAL'` or `'CLOSED'`** |
| `last_fill_at` | no change | `fill.fill_timestamp` |

\* Status transitions to `'PARTIAL'` if this is a scale-in fill AND the trade already had at least one EXIT fill (net_position < total_entry_quantity). For a pure scale-in with no exits yet, status stays `'OPEN'`. In practice: `status = 'OPEN'` if `total_exit_quantity = 0`, `'PARTIAL'` if `0 < total_exit_quantity < total_entry_quantity`, `'CLOSED'` if `total_exit_quantity = total_entry_quantity`.

\*\* Status transitions to `'CLOSED'` when `net_position = 0` after this EXIT fill.

### Fields updated at trade close

| Field | Value at close |
|---|---|
| `status` | `'CLOSED'` |
| `last_fill_at` | `fill.fill_timestamp` of the final EXIT fill |
| `average_exit` | computed from all EXIT fills |
| `net_position` | `0` |
| `trade_type` | Updated to `CNC_SAME_DAY` if applicable (see §8) |

---

## 10. Tax Lot Interaction

Tax lot interaction applies **only to the `DELIVERY` processing unit** (fills with `product_type = CNC`). For `INTRADAY` and `FO` processing units, the engine never touches the `tax_lots` table. See Rule 4.2.

### When a new CNC trade opens

At the moment the first ENTRY fill is processed for a CNC trade, the engine **creates a new `tax_lots` row**:

| Field | Value |
|---|---|
| `id` | Newly generated UUID |
| `trade_id` | The new trade's `id` |
| `user_id` | `fill.user_id` |
| `instrument_id` | `fill.instrument_id` |
| `purchase_date` | `fill.trade_date` (equals `trades.trade_date`) |
| `quantity_original` | `fill.quantity` |
| `quantity_remaining` | `fill.quantity` |
| `cost_per_share` | `fill.price` (provisional — updated on scale-in) |
| `status` | `'OPEN'` |

The tax lot is created atomically with the new trade row in a single database transaction.

### When a CNC trade receives a scale-in (additional ENTRY fill)

The existing tax lot for this trade is updated to reflect the new total position and new average cost:

```
new_quantity_original = Σ(fill.quantity for all ENTRY fills on this trade)
new_cost_per_share    = trades.average_entry (after recomputing per §9)
```

Updated fields:
- `tax_lots.quantity_original` → `new_quantity_original`
- `tax_lots.quantity_remaining` → `new_quantity_original` (scale-in adds to the open lot; no exits have consumed from this lot yet if this is a pure scale-in — in the partial-exit case, see below)
- `tax_lots.cost_per_share` → `trades.average_entry` (recomputed)

**Scale-in after partial exit:** if a partial exit has already decremented `quantity_remaining`, then on a subsequent scale-in:
```
quantity_remaining = quantity_original_before_scale_in
                   - quantity_already_exited
                   + scale_in_fill.quantity
```
Where `quantity_already_exited = quantity_original_before_scale_in − quantity_remaining_before_scale_in`.

And `quantity_original` also grows by the scale-in amount.

The `cost_per_share` is updated to the new `average_entry` after the scale-in.

### Phase 1 tax lot model: aggregated trade lot

**Phase 1 uses the aggregated trade lot model.** This means each CNC trade produces exactly one `tax_lots` row, regardless of how many ENTRY fills built the position. The lot's `cost_per_share` equals `trades.average_entry` — the weighted average price across all ENTRY fills for that trade, not the individual acquisition price of each fill.

This is distinct from the acquisition lot model (one lot per fill or one lot per acquisition date), which is how some tax systems model CNC holdings for LTCG/STCG purposes. The acquisition lot model is not implemented in Phase 1 and is not defined by these domain rules.

| Model | Lot count per trade | `cost_per_share` |
|---|---|---|
| **Aggregated trade lot (Phase 1)** | 1 lot per trade | `trades.average_entry` |
| Acquisition lot (out of scope) | 1 lot per ENTRY fill | `fill.price` |

**Rationale:** the acquisition lot model requires storing per-fill acquisition dates and prices in `tax_lots`, which the current data model does not support (there is no `tax_lot_acquisitions` child table). Phase 1 uses the aggregated model as the simplest correct implementation.

### Phase 1 scope: single open CNC trade per instrument

Under the reconstruction algorithm in this specification, a new CNC trade can only open when the processing unit is in the FLAT state (running_position = 0). **At most one CNC trade per instrument is open at any given time** in Phase 1. This means:

- FIFO across simultaneously open CNC trades does not apply in Phase 1 reconstruction.
- The `idx_taxlots_fifo` index exists in the schema for future use, but the Phase 1 reconstruction engine does not execute a FIFO query across multiple open lots.
- A CNC EXIT fill is allocated entirely against the single open tax lot for this (user, instrument) pair.

This is not a domain rule — it is a Phase 1 implementation scope boundary. The multi-lot case (separate tax lots from separate CNC trades that are simultaneously open) is blocked by Unresolved 4 (see §13).

### Reconciliation with Rule 4.1 (FIFO)

Rule 4.1 states that CNC EXIT fills are allocated against open lots in FIFO order (earliest `purchase_date` first). This may appear to conflict with the aggregated trade lot model — if there is only one lot per trade, what does FIFO mean?

The reconciliation is as follows:

- **Rule 4.1's FIFO rule applies across simultaneously open trades**, not across fills within a single trade. It governs which of several open trades absorbs an exit fill first, when multiple CNC trades on the same instrument are open at the same time.
- **In Phase 1, only one CNC trade per instrument is open at any given time.** The engine enforces this via the "position must return to zero before a new trade opens" boundary rule (§5). There is never more than one open lot to choose from.
- **FIFO is therefore trivially satisfied in Phase 1**: every exit fill goes to the only open lot. No FIFO query is needed.

The `idx_taxlots_fifo` index (`user_id, instrument_id, status, purchase_date`) exists to support a future implementation where multiple CNC trades on the same instrument are simultaneously open and FIFO allocation across them is exercised. That case is blocked by Unresolved 4 (§13) and is not implemented in Phase 1.

### When a CNC trade receives EXIT fills

When an EXIT fill is processed for a CNC trade:

1. Find the single open tax lot for this (user_id, instrument_id) pair:
   ```sql
   SELECT * FROM tax_lots
   WHERE user_id = $user_id
     AND instrument_id = $instrument_id
     AND status != 'CLOSED'
   ORDER BY purchase_date ASC
   LIMIT 1
   ```
   Under Phase 1 scope, this returns exactly one row (or zero if no open lot — which is an error, see §12).

2. Decrement `quantity_remaining` by `fill.quantity`.

3. Update `status`:
   - If `quantity_remaining > 0` → `'PARTIALLY_CLOSED'`
   - If `quantity_remaining = 0` → `'CLOSED'`

### When a CNC trade closes

The tax lot's `status` should already be `'CLOSED'` (set in the final exit fill step above). At trade close, assert that `tax_lots.quantity_remaining = 0` and `tax_lots.status = 'CLOSED'` for this trade. If the assertion fails, raise a `ReconstructionConsistencyError`.

---

## 11. Idempotency and Re-import Safety

The reconstruction engine must be safe to run multiple times on the same fill data. The following guarantees this:

### Assigned fills are skipped

The engine queries unprocessed fills (`trade_id IS NULL`) only. Fills with `trade_id IS NOT NULL` are never re-processed. The immutability trigger on `execution_fills` guarantees that once `trade_id` is assigned, it cannot be changed.

### Duplicate fill detection

Duplicate fill imports are caught by the partial unique index `UNIQUE (broker, fill_id) WHERE fill_id IS NOT NULL`. The import pipeline (Sanjaya) should detect this at insert time. If a duplicate reaches the reconstruction engine (e.g., `fill_id IS NULL` manual entry), the engine has no mechanism to detect duplication — prevention is Sanjaya's responsibility at import time.

### Open trade resumption

If the processing unit has an existing open trade (`status IN ('OPEN', 'PARTIAL')`), new fills are added to that trade rather than creating a new one. The engine determines whether an open trade exists by querying:

```sql
SELECT * FROM trades
WHERE user_id = $user_id
  AND instrument_id = $instrument_id
  AND status IN ('OPEN', 'PARTIAL')
  AND trade_type IN ($types_for_product_type_family)
```

If a row is found, the engine resumes it. If no row is found, the processing unit is FLAT and the next fill opens a new trade.

**The engine must hold a row-level lock on the open trade row for the duration of a reconstruction run** to prevent concurrent reconstruction runs on the same processing unit from producing inconsistent state. Two concurrent imports for the same user and instrument must be serialized.

---

## 12. Error Conditions

The following conditions represent domain errors. The engine raises a typed exception and halts reconstruction for the affected processing unit. The unprocessed fill is left with `trade_id = NULL`. No partial state is committed — each fill processing step is a single atomic transaction.

### E1 — Position crossing zero

A fill would cause `running_position` to cross zero (a LONG position becoming SHORT or vice versa in a single fill).

**Example:** running_position = +100, incoming SELL quantity = 150 → new_position would be −50.

**Domain meaning:** this fill simultaneously closes an existing trade AND opens a new trade in the opposite direction. A single `execution_fill` row cannot be assigned to two different `trades` rows and cannot hold two different `fill_role` values.

**What the engine does when E1 is detected:**

1. The crossing-zero fill is **quarantined** — left with `trade_id = NULL` and `fill_role = NULL`. No state changes from processing this fill are committed; the fill processing step is a single atomic transaction that is rolled back.
2. The engine **halts reconstruction for the entire processing unit**. All fills that follow the quarantined fill in the sorted order are also left unprocessed (`trade_id = NULL`).
3. The engine raises a `PositionCrossingZeroError` with the fill ID of the offending fill.

**Why halting is required:** subsequent fills were sequenced into the processing unit assuming the position state that the crossing-zero fill would have produced. Processing them against the pre-E1 position state (e.g., still LONG +100 instead of SHORT −50) would assign wrong directions, wrong fill_roles, and produce incorrect trade records. The only safe action is to leave all post-E1 fills unprocessed until the E1 condition is resolved.

**Resolution path:** the crossing-zero fill must be split into two synthetic fills:
- Fill A: a closing fill (quantity = 100, role = EXIT, closing the long trade)
- Fill B: an opening fill (quantity = 50, role = ENTRY, opening a new short trade)

Both replacement fills must be created with `import_source = 'MANUAL'` and `fill_timestamp` values that preserve the correct ordering relative to adjacent fills. The operator creates these via the manual fill entry interface. Once the replacement fills are in place, reconstruction can be re-triggered for the processing unit.

**Permanent exclusion via `fill_exclusions`:** the original crossing-zero fill cannot be modified — the `execution_fills` immutability trigger forbids UPDATE, and this guarantee must not be weakened. The authoritative mechanism for permanently excluding the fill from future reconstruction runs is the **`fill_exclusions` side-table**.

The `fill_exclusions` table records fills that must be skipped on every future reconstruction run. It contains:

| Column | Type | Description |
|---|---|---|
| `fill_id` | UUID (FK → `execution_fills.id`) | The fill being excluded |
| `reason` | TEXT | Human-readable explanation (e.g., "E1 crossing-zero — replaced by MANUAL fills abc and def") |
| `replacement_fill_ids` | UUID[] | IDs of the `import_source = 'MANUAL'` fills that replace this one |
| `excluded_by` | UUID (FK → `users.id`) or operator identifier | Who created the exclusion record |
| `excluded_at` | TIMESTAMPTZ | When the exclusion was recorded |

The `fill_exclusions` table is append-only. Once a row is inserted, it is never deleted or updated — the exclusion is permanent and the record is audit evidence.

**The engine's unprocessed-fill query always filters out excluded fills** (see §2). The engine never encounters an excluded fill. No state machine transition, no E1 detection, no halt — the fill does not exist from the engine's perspective.

**The `execution_fills` row is never modified.** It remains with `trade_id = NULL` and `import_source` intact. It is visible in the raw audit log as evidence that the original broker fill existed and what it contained. The `fill_exclusions` row alongside it explains why it was not reconstructed.

**Complete operator workflow after E1 is detected:**

1. The engine raises `PositionCrossingZeroError` and halts the processing unit. The offending fill ID is recorded in the error.
2. The operator reviews the crossing-zero fill to determine the correct split: what quantity closes the existing trade and what quantity opens the new one.
3. The operator creates Fill A (closing fill) and Fill B (opening fill) via the manual fill entry interface, with `import_source = 'MANUAL'` and `fill_timestamp` values that place them immediately before the original fill in the sorted order.
4. The operator creates a row in `fill_exclusions` referencing the original fill ID, the reason, and the IDs of Fill A and Fill B as `replacement_fill_ids`.
5. The operator re-triggers reconstruction for the processing unit. The engine skips the excluded fill, processes Fill A and Fill B in order, and reconstruction proceeds correctly.

**Invariant:** the total quantity represented by Fill A and Fill B must equal the quantity of the excluded fill. If the original fill was SELL 150 against a LONG 100 position: Fill A is SELL 100 (closes the long), Fill B is SELL 50 (opens the short). 100 + 50 = 150. The operator is responsible for verifying this invariant — the engine does not validate it.

**This is expected to be extremely rare in Indian markets.** Most Indian brokers do not permit a single order to cross zero — you must close the long before opening a short. If this error occurs, it most likely indicates a broker data anomaly or an instrument with unusual margin rules.

### E2 — Mixed product_type within a trade (should not occur by construction)

A fill's `product_type_family` (§3) does not match the processing unit being run. The engine should detect this before processing, but if it does encounter this state (e.g., due to a data migration error), it raises `ReconstructionDataError` and halts.

### E3 — Inconsistent direction

A fill's `side` combined with the trade's `direction` does not produce a valid entry in the direction × side table (§7), and the state machine transition (§4) would require crossing zero (which would be caught by E1 first) or some other undefined state.

In practice, E3 is subsumed by E1. All direction-side combinations produce valid transitions or cross zero.

### E4 — No open tax lot on CNC EXIT

An EXIT fill arrives for a CNC trade, but no open tax lot exists for this (user_id, instrument_id). This indicates a reconstruction consistency failure — a trade closed to zero previously without correctly updating the tax lot, or the tax lot was manually deleted.

Engine raises `ReconstructionConsistencyError`. Manual operator intervention required to reconcile the tax lot state.

### E5 — Ambiguous fill ordering (timestamp tie with no tiebreaker)

Two fills in the same processing unit share identical `fill_timestamp` and both have NULL `fill_id`, making deterministic ordering impossible.

Engine raises `ReconstructionAmbiguityError`. Operator must provide an explicit ordering by setting `fill_id` or adjusting `fill_timestamp` by one second.

### E6 — Open trade exists for an NRML instrument with a resolved expiry

(Future: when Unresolved 1 is resolved.) A NRML trade is open past the instrument's `expiry_date`. Currently: the engine does not detect this condition — expiry handling is out of scope (see §13).

---

## 13. Out of Scope — Unresolved Domain Areas

The five unresolved domain areas from `TRADE-DOMAIN-RULES.md` Part 6 each have specific blocking effects on the reconstruction algorithm. Bhima must not implement any logic that depends on these areas until Ganesha formally resolves them and publishes updated rules.

---

### Unresolved 1 — F&O Expiry Handling

**What is blocked in reconstruction:**

- An open `NRML_FUT` or `NRML_OPT` trade that reaches its instrument's `expiry_date` without an explicit exit fill has no closing event in the current model. The reconstruction engine has no rule for synthesizing an expiry fill or closing the trade at a settlement price.
- The `exit_type = EXPIRY_WORTHLESS` value that would be needed for a worthless options expiry does not exist in the current schema.
- The source of the final settlement price (broker fill vs. NSE settlement publication) is not defined.

**Current engine behavior:** leaves the trade as `OPEN` past expiry. No synthetic close is generated. Karna and Kubera will see stale open trades for expired instruments.

**Resolution needed from Ganesha:** define whether expiry produces a synthetic fill (synthesized by the engine from NSE settlement price data) or a real fill imported from the broker. Define `exit_type` values for expiry and settlement. Bhima and Sanjaya unblocked upon resolution.

---

### Unresolved 2 — Options Exercise and Assignment

**What is blocked in reconstruction:**

- When a long ITM option is exercised, the trade closes on the options instrument AND a new trade opens on the underlying equity. The reconstruction engine has no mechanism to link these two trades or to compute the cost basis of the resulting equity position from the options premium paid.
- When a short option is assigned, the same bidirectional transition occurs.
- There is no `exercise_event` or `assignment_event` table — the current data model has no structure for this transition.

**Current engine behavior:** if the broker sends a closing fill on the options instrument (which some brokers do on exercise), the reconstruction engine will close the options trade normally. The resulting equity position (if any) will be processed as a new, independent CNC trade when the equity fills arrive — without knowledge that it originated from an options exercise. This produces incorrect cost basis.

**Resolution needed from Ganesha:** define the data model for the options → equity transition. Specify cost basis treatment for the resulting equity position. Bhima unblocked upon resolution.

---

### Unresolved 3 — Corporate Actions on Delivery Holdings

**What is blocked in reconstruction:**

- When a stock split, bonus issue, or reverse split occurs while a CNC trade is open, the `quantity_remaining` and `cost_per_share` on the active tax lot need adjustment.
- Historical fills (ENTRY fills before the corporate action) have prices and quantities that are no longer directly comparable to post-action fills.
- The reconstruction engine has no corporate action event table and no adjustment algorithm.

**Current engine behavior:** reconstruction proceeds with unadjusted historical fill data. Post-corporate-action fills are processed as new fills with no adjustment. `average_entry` will be computed from a mix of pre- and post-action prices, producing an incorrect result.

**Resolution needed from Ganesha:** define the corporate action event model, the retroactive adjustment algorithm for tax lots and historical fills, and whether adjustment is applied to the fill records or stored as a separate transformation layer.

---

### Unresolved 4 — Multi-Day Partial Exits for Delivery Trades (Multiple Open CNC Lots)

**What is blocked in reconstruction:**

This is the most significant reconstruction blocker for the delivery segment.

Under the Phase 1 reconstruction algorithm (§5, §10), at most one CNC trade is open per instrument at any time (the "position to zero" boundary rule from Rule 1.2 applies). FIFO across simultaneously open CNC trades is therefore not exercised in Phase 1.

If the domain rules are later extended to allow a trader's second CNC purchase (different date) to open a second parallel CNC trade while the first is still open — enabling true FIFO allocation across lots — the following reconstruction problems arise:

1. **A single exit fill spanning multiple trades:** a SELL 150 fill that closes Trade A (100 shares) and partially closes Trade B (50 shares) cannot be assigned to two `trade_id` values. The `execution_fills` data model has one `trade_id` column — a single fill cannot reference two trades.

2. **Fill splitting mechanics:** closing 100 shares from Trade A and 50 shares from Trade B requires either splitting the original fill into two synthetic fills or defining a separate allocation table that maps a single fill to multiple (trade_id, quantity) allocations without changing the fill record itself.

3. **fill_role assignment:** the same fill cannot be both EXIT for Trade A and EXIT for Trade B — though both are EXIT, the assignment is to one trade only.

**Current Phase 1 scope:** the single-lot CNC model avoids these problems entirely. Unresolved 4 must be resolved before multi-lot CNC reconstruction can be implemented.

**Resolution needed from Ganesha:** define whether each CNC purchase date creates a separate parallel trade, or whether all CNC purchases in the same instrument accumulate into one trade until position reaches zero. If parallel trades are intended, define the fill allocation model for fills that span multiple trades. Bhima and Sanjaya unblocked upon resolution.

---

### Unresolved 5 — F&O Tax Lot Accounting (Incremental NRML Position Builds)

**What is blocked in reconstruction:**

- For `NRML_FUT` trades, a trader may add to a futures position incrementally over multiple days (buying additional lots of the same futures contract on different dates). Under the current reconstruction algorithm, these scale-in fills are all added to the same `NRML_FUT` trade (the "position to zero" boundary applies), and the average_entry is recomputed with each ENTRY fill. This is consistent with §4 and §9.
- The unresolved question is whether FIFO should apply to such incremental NRML builds — i.e., should each day's addition to a futures position be treated as a separately tracked "lot" with its own cost basis for tax purposes, analogous to CNC delivery lots?
- If FIFO applies to `NRML_FUT` incremental builds, the same multi-lot reconstruction problem from Unresolved 4 applies.

**Current engine behavior:** the reconstruction engine treats all NRML position builds as additions to a single trade, using average cost (Rule 2.1). No FIFO allocation is applied across dates. This is the correct behavior until Ganesha resolves whether FIFO applies to F&O.

**Resolution needed from Ganesha:** clarify whether FIFO applies to incremental NRML_FUT position builds. If yes, define the lot tracking model for F&O (analogous to `tax_lots` for CNC). Bhima unblocked upon resolution.

---

## Summary: What Is Fully Specified vs. Blocked

| Scenario | Phase 1 status |
|---|---|
| MIS intraday reconstruction (single or scaled entry, partial exits, re-entry) | ✅ **Fully specified** |
| CNC delivery reconstruction — single trade per instrument (position to zero boundary) | ✅ **Fully specified** |
| CNC tax lot creation and per-trade FIFO decrement (single open lot) | ✅ **Fully specified** |
| NRML_FUT reconstruction (single trade, average cost, position to zero) | ✅ **Fully specified** |
| NRML_OPT reconstruction (single trade, average cost, position to zero) | ✅ **Fully specified** |
| trade_type derivation: MIS, CNC, CNC_SAME_DAY, NRML_FUT, NRML_OPT | ✅ **Fully specified** |
| LONG/SHORT direction from first fill | ✅ **Fully specified** |
| Entry/Exit classification (direction × side table) | ✅ **Fully specified** |
| Position crossing zero error handling | ✅ **Fully specified** (error, quarantine, manual split) |
| F&O expiry (worthless expiry, settlement price) | 🚫 **Blocked — Unresolved 1** |
| Options exercise / assignment → equity transition | 🚫 **Blocked — Unresolved 2** |
| Corporate action adjustment to open tax lots | 🚫 **Blocked — Unresolved 3** |
| Multi-lot CNC: FIFO across simultaneously open delivery trades | 🚫 **Blocked — Unresolved 4** |
| NRML_FUT incremental lot tracking with FIFO | 🚫 **Blocked — Unresolved 5** |

---

*Ganesha — Trading Domain Analyst*
*This specification is authoritative and binding on all implementing roles. Unresolved areas are explicitly identified and must not be implemented speculatively. When a resolution is published by Ganesha, this document will be updated before implementation proceeds.*
