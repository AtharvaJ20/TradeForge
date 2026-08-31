# Journal / P&L Integration Specification — Option A

**Status:** Authoritative — binding on Bhima (backend), Arjun (frontend), Karna (analytics), Sahadeva (QA)
**Author:** Kubera (Financial Calculation & P&L Specialist)
**Domain authority:** Ganesha (JOURNAL-DOMAIN-RULES.md — G1), Mayasura (ADR-003)
**Security authority:** Hanuman (JOURNAL-SECURITY-REQUIREMENTS.md — G4)
**Date:** 2026-08-23
**Scope:** G3 — defines the `trade_pnl` table, Step 10 engine responsibilities, nullable field semantics, and back-fill/update rules

---

## 1. Overview

This document specifies how TradeForge's Step 10 P&L engine integrates with the journal annotation layer. It defines:

- The `trade_pnl` table schema and all its fields
- Ownership of every field in that table
- Precisely when Step 10 populates the table
- How the journal reads from `trade_pnl` without writing to it
- Back-fill rules for trades that existed before Step 10 ran
- Recalculation rules for when a `trade_pnl` row becomes stale

**What this document does NOT define:** the P&L formulas themselves, charge rate tables, or the Karna analytics layer. Those are governed by the Kubera skill document (formulas) and a future Karna specification (analytics). This document governs the integration boundary between Step 10 and the journal.

---

## 2. Option A — Separate `trade_pnl` Table

**Option A** is the architectural decision to store all P&L results in a dedicated `trade_pnl` table that is separate from `trades`, rather than adding P&L columns to `trades` directly.

**Rationale for Option A:**

1. **Domain ownership is clean.** `trades` is owned by the reconstruction engine. P&L is owned by the calculation engine (Step 10/Kubera). Two different owners writing to the same table creates a write coupling that has caused production incidents in similar systems — a reconstruction update and a P&L update racing on the same row.

2. **Migration risk is lower.** P&L columns require a `charge_schedules` table that does not exist yet. Adding columns that cannot be populated to `trades` creates NOT NULL constraints that cannot be honoured at migration time. A separate table allows the Step 10 migration to be applied independently of the trade domain migration.

3. **The table is optional per trade.** `trade_pnl` has zero rows for open trades. Under Option A, absence of a row is a valid state (`PnlStatus = PENDING_CALCULATION`). Under inline columns, every `trades` row would need nullable P&L columns that are NULL until the trade closes — semantically equivalent but harder to enforce at the schema level.

4. **The journal reads this table for existence only.** The journal's contact with P&L data is narrow: one EXISTS check for `PnlStatus`, and four summary fields for display. A separate table makes this contract explicit in code — `JournalRepository` imports `TradePnl` for SELECT only, with zero capability of accidental write.

**What was ruled out:** Option B (inline P&L columns in `trades`) and Option C (a separate P&L microservice) were not formally evaluated for Phase 1. Option B is the primary alternative. Option A was chosen per ADR-003 Decision 1.

---

## 3. `trade_pnl` Table Schema

One row per closed trade. A row is absent until Step 10 runs for that trade. The table has a `UNIQUE(trade_id)` constraint — there is exactly one P&L record per trade at any point in time.

**Alembic migration:** `trade_pnl` was created as a stub in migration `0004` (`d7b3e1f5c2a4`). The full column set defined below requires Bhima to expand migration `0004` or add migration `0005` before Step 10 is implemented. The stub columns (`gross_pnl`, `net_pnl`, `total_charges`, `r_multiple`) are already present.

### 3.1 — Identity and Ownership Columns

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `UUID` | NOT NULL PK | Server-generated via `uuid.uuid4()`. |
| `trade_id` | `UUID` | NOT NULL FK → `trades.id` | `UNIQUE`. One P&L record per trade. |
| `user_id` | `UUID` | NOT NULL FK → `users.id` | Denormalized from `trades.user_id`. Required in all RLS WHERE clauses on this table. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Set when the row is first inserted by Step 10. Never updated. |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | Updated on every Step 10 recalculation of this trade. |
| `calculated_at` | `TIMESTAMPTZ` | NOT NULL | Timestamp when Step 10 last ran the P&L calculation for this trade. Distinct from `updated_at`: if a correction updates only `r_multiple` (because a planned stop was added retroactively), `calculated_at` records when the engine last ran in full. |
| `engine_version` | `VARCHAR(20)` | NOT NULL | The version string of the Step 10 engine that produced this row (e.g., `"1.0.0"`). Used to identify rows that must be recalculated after an engine change. |

### 3.2 — Summary P&L Columns

These four columns are the **only** columns the journal service is permitted to read from `trade_pnl`. All other columns are Step 10's private state.

| Column | Type | Null | Notes |
|---|---|---|---|
| `gross_pnl` | `NUMERIC(18,4)` | NOT NULL | Gross realised P&L in INR. `(average_exit − average_entry) × total_entry_quantity` for long equity, per Kubera formulas. Negative for a losing trade. Always set when the row exists. |
| `net_pnl` | `NUMERIC(18,4)` | NOT NULL | Net realised P&L after all charges. `gross_pnl − total_charges`. Always set when the row exists. |
| `total_charges` | `NUMERIC(18,4)` | NOT NULL | Sum of all seven charge components. Always ≥ 0. Always set when the row exists. |
| `r_multiple` | `NUMERIC(18,6)` | NULL | `net_pnl / journal_entries.planned_risk_amount`. NULL when `planned_risk_amount` is NULL (no planned stop set) or zero (degenerate case). 6 decimal places to preserve sign and precision for small R values (e.g., `+0.024R`). |

**Why `gross_pnl`, `net_pnl`, and `total_charges` are NOT NULL:** A `trade_pnl` row only exists when Step 10 has completed a successful calculation. If the calculation cannot be completed (missing fills, incomplete reconstruction), Step 10 does not insert the row. Absence of the row is the signal that P&L is unavailable — there is no "partial" P&L state. A row with a NULL `net_pnl` would be uninterpretable.

**Why `r_multiple` IS nullable:** `r_multiple` depends on `journal_entries.planned_risk_amount`, which requires the user to have set `planned_stop` in their journal entry. The journal and the P&L engine are decoupled — Step 10 runs when the trade closes, regardless of whether the user has populated their journal. If the user sets a planned stop after Step 10 has run, `r_multiple` must be recalculated. The NULL state means "planned stop not yet available."

### 3.3 — Charge Breakdown Columns

These columns record each charge component individually, enabling per-charge analytics by Karna and verification by Sahadeva. They are NOT read by the journal service — the journal reads only `total_charges` from the summary columns.

| Column | Type | Null | Notes |
|---|---|---|---|
| `brokerage` | `NUMERIC(18,4)` | NOT NULL | Total brokerage (entry + exit sides). Zero for zero-brokerage plans. |
| `stt` | `NUMERIC(18,4)` | NOT NULL | Securities Transaction Tax. Applied per Kubera's charge schedule for the `trade_type`. Zero for the buy side of intraday trades. |
| `exchange_charges` | `NUMERIC(18,4)` | NOT NULL | NSE/BSE transaction charges (entry + exit sides). |
| `sebi_charges` | `NUMERIC(18,4)` | NOT NULL | SEBI charges at `₹10 per crore` of turnover. |
| `stamp_duty` | `NUMERIC(18,4)` | NOT NULL | Applied on buy-side turnover only. Rate varies by `trade_type`. |
| `gst` | `NUMERIC(18,4)` | NOT NULL | 18% on `brokerage + exchange_charges + sebi_charges`. STT and stamp duty excluded. |
| `ipft` | `NUMERIC(18,4)` | NOT NULL | Investor Protection Fund Trust fee. Typically a fraction of a rupee but must be recorded. |

**Derivation constraint:**
```
total_charges = brokerage + stt + exchange_charges + sebi_charges + stamp_duty + gst + ipft
```

This identity must hold to the last paisa. Any `trade_pnl` row where this equation does not hold is a calculation error.

### 3.4 — Charge Rate Provenance Columns

These columns record which charge rate configuration was used. They allow Bhima to regenerate an identical result and allow Sahadeva to verify that the correct rate version was applied.

| Column | Type | Null | Notes |
|---|---|---|---|
| `charge_schedule_version` | `VARCHAR(50)` | NOT NULL | Identifier of the charge rate row from `charge_schedules` that was used (e.g., `"ZERODHA_MIS_NSE_20240723"`). References the rate effective on `trades.trade_date`. |
| `broker` | `VARCHAR(20)` | NOT NULL | Broker used for this trade. Copied from `execution_fills.broker` at calculation time. Used to select the correct brokerage schedule. |

### 3.5 — Full `trade_pnl` DDL Summary

```sql
CREATE TABLE trade_pnl (
    id                      UUID            NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    trade_id                UUID            NOT NULL REFERENCES trades(id),
    user_id                 UUID            NOT NULL REFERENCES users(id),
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),
    calculated_at           TIMESTAMPTZ     NOT NULL,
    engine_version          VARCHAR(20)     NOT NULL,

    -- Summary columns (journal-readable)
    gross_pnl               NUMERIC(18,4)   NOT NULL,
    net_pnl                 NUMERIC(18,4)   NOT NULL,
    total_charges           NUMERIC(18,4)   NOT NULL,
    r_multiple              NUMERIC(18,6)   NULL,

    -- Charge breakdown columns (Step 10 private)
    brokerage               NUMERIC(18,4)   NOT NULL,
    stt                     NUMERIC(18,4)   NOT NULL,
    exchange_charges        NUMERIC(18,4)   NOT NULL,
    sebi_charges            NUMERIC(18,4)   NOT NULL,
    stamp_duty              NUMERIC(18,4)   NOT NULL,
    gst                     NUMERIC(18,4)   NOT NULL,
    ipft                    NUMERIC(18,4)   NOT NULL,

    -- Rate provenance
    charge_schedule_version VARCHAR(50)     NOT NULL,
    broker                  VARCHAR(20)     NOT NULL,

    CONSTRAINT uq_trade_pnl_trade_id UNIQUE (trade_id),
    CONSTRAINT chk_trade_pnl_total_charges CHECK (
        total_charges = brokerage + stt + exchange_charges + sebi_charges
                      + stamp_duty + gst + ipft
    ),
    CONSTRAINT chk_trade_pnl_non_negative_charges CHECK (
        brokerage >= 0 AND stt >= 0 AND exchange_charges >= 0
        AND sebi_charges >= 0 AND stamp_duty >= 0 AND gst >= 0 AND ipft >= 0
    )
);

CREATE INDEX idx_trade_pnl_user_id ON trade_pnl (user_id);
CREATE INDEX idx_trade_pnl_trade_id ON trade_pnl (trade_id);
```

---

## 4. Field Ownership Summary

| Table | Field set | Written by | Read by |
|---|---|---|---|
| `trades` | `average_entry`, `average_exit`, `total_entry_quantity`, `trade_type`, `direction`, `trade_date` | Reconstruction engine (Steps 1–8) | Step 10 (P&L input) |
| `journal_entries` | `planned_stop`, `planned_risk_amount` | Journal service (JournalService.upsert_entry) | Step 10 (`r_multiple` input) |
| `trade_pnl` | All columns | Step 10 P&L engine only | Journal service (summary columns only), Karna (all columns) |
| `lot_size_history` | `lot_size`, `effective_from` | Nakula / data maintenance | Step 10 (futures and options sizing) |
| `charge_schedules` | All rate columns | Nakula / data maintenance | Step 10 (charge calculation) |

**The journal service's read contract against `trade_pnl` is exactly four columns:** `gross_pnl`, `net_pnl`, `total_charges`, `r_multiple`. `JournalRepository.has_pnl_row()` additionally selects `TradePnl.id` as an existence check. No other `trade_pnl` column may appear in any `JournalRepository` SELECT. This boundary is enforced at code review.

---

## 5. When Step 10 Runs

### 5.1 — Trigger Condition

Step 10 runs when and only when a trade's `status` transitions to `CLOSED`.

```
trades.status transitions to CLOSED → Step 10 runs for that trade_id
```

Step 10 does NOT run for:
- `OPEN` trades — no exit fills, no realised P&L
- `PARTIAL` trades — partial exits have realised some P&L, but the position is not yet fully closed. Step 10 defers until the full close. (Phase 1 only. Future phases may introduce intermediate P&L rows for partial exits.)

**Status change ownership:** `trades.status` is set by the reconstruction engine (Sanjaya). When the reconstruction engine sets `status = CLOSED`, it must emit a trigger or a notification that Step 10 can act on. In Phase 1 (FastAPI with BackgroundTasks per ADR-001), this is implemented as a FastAPI `BackgroundTask` queued immediately after the reconstruction engine closes the trade. In Phase 2 (Celery), this becomes a Celery task.

### 5.2 — Preconditions That Must Hold Before Step 10 Runs

Step 10 must verify these preconditions before inserting or updating `trade_pnl`. If any precondition fails, Step 10 logs the failure and does not insert/update the row.

| Precondition | Check | Failure action |
|---|---|---|
| Trade is CLOSED | `trades.status = 'CLOSED'` | Skip and log |
| Average entry is non-null | `trades.average_entry IS NOT NULL` | Skip and log |
| Average exit is non-null | `trades.average_exit IS NOT NULL` | Skip and log |
| Total entry quantity > 0 | `trades.total_entry_quantity > 0` | Skip and log |
| Charge schedule exists for this broker + trade_type + trade_date | `SELECT FROM charge_schedules WHERE ...` | Skip and log |
| Lot size exists for this instrument on this trade_date | For `trade_type IN ('NRML_FUT', 'NRML_OPT')` only | Skip and log |

### 5.3 — Execution Sequence

When all preconditions are satisfied, Step 10 executes in this order:

1. Load trade snapshot: `trades` row (direction, trade_type, average_entry, average_exit, total_entry_quantity, trade_date, instrument_id, broker).
2. Load lot size: `lot_size_history` row effective on `trade_date` (derivatives only).
3. Load charge schedule: `charge_schedules` row effective on `trade_date` for this broker and `trade_type`.
4. Load `journal_entries.planned_risk_amount` for this `trade_id` (nullable — may not exist yet).
5. Compute `gross_pnl` using the Kubera formula for this instrument type and direction.
6. Compute each charge component individually (brokerage, STT, exchange charges, SEBI, stamp duty).
7. Compute `gst = 0.18 × (brokerage + exchange_charges + sebi_charges)`.
8. Compute `ipft` for the applicable segment.
9. Compute `total_charges = sum of all seven components`.
10. Compute `net_pnl = gross_pnl − total_charges`.
11. Compute `r_multiple = net_pnl / planned_risk_amount` if `planned_risk_amount IS NOT NULL AND planned_risk_amount != 0`. Otherwise `r_multiple = NULL`.
12. Upsert `trade_pnl`: INSERT on first run, UPDATE on recalculation. Use ON CONFLICT (trade_id) DO UPDATE.

**No intermediate rounding.** All seven charge components are computed at full Decimal precision and summed exactly. Only the final stored values are quantized to 4 decimal places. This is mandatory per DECIMAL-USAGE-STANDARD.md.

---

## 6. Journal Integration — What the Journal Reads

### 6.1 — Existence Check (`has_pnl_row`)

```python
async def has_pnl_row(self, trade_id: uuid.UUID) -> bool:
    result = await self._db.execute(
        select(TradePnl.id).where(TradePnl.trade_id == trade_id).limit(1)
    )
    return result.scalar_one_or_none() is not None
```

This is the only query the journal service uses to determine `PnlStatus = AVAILABLE` vs. `PENDING_CALCULATION`. The journal never inspects any field of `TradePnl` in this check — only existence.

### 6.2 — Summary Field Read (when status is AVAILABLE)

When `has_pnl_row` returns True, the journal service fetches the four summary fields:

```python
async def get_pnl_snapshot(self, trade_id: uuid.UUID) -> PnlSnapshot | None:
    result = await self._db.execute(
        select(
            TradePnl.gross_pnl,
            TradePnl.net_pnl,
            TradePnl.total_charges,
            TradePnl.r_multiple,
        ).where(TradePnl.trade_id == trade_id)
    )
    row = result.one_or_none()
    if row is None:
        return None
    return PnlSnapshot(
        status=PnlStatus.AVAILABLE,
        gross_pnl=row.gross_pnl,
        net_pnl=row.net_pnl,
        total_charges=row.total_charges,
        r_multiple=row.r_multiple,
    )
```

**Critical boundary:** This SELECT touches exactly four columns. No charge breakdown column, no `engine_version`, no `charge_schedule_version`. If Bhima adds a query in `JournalRepository` that reads a charge breakdown column, that is a violation of the integration contract and must be reverted.

### 6.3 — The `PnlSnapshot` Response and Nullable Fields

The `PnlSnapshot` datatype (`domain/journal/types.py`) is the object the journal returns in `JournalEntryView.pnl`. Its fields are:

| Field | Type | Nullable in response | When non-null |
|---|---|---|---|
| `status` | `PnlStatus` | No — always present | Always |
| `gross_pnl` | `Decimal` | Yes | Only when `status = AVAILABLE` |
| `net_pnl` | `Decimal` | Yes | Only when `status = AVAILABLE` |
| `total_charges` | `Decimal` | Yes | Only when `status = AVAILABLE` |
| `r_multiple` | `Decimal` | Yes | Only when `status = AVAILABLE` AND `planned_risk_amount IS NOT NULL AND != 0` |

**Nullability contract to Arjun:** When `status = AVAILABLE`, `gross_pnl`, `net_pnl`, and `total_charges` are guaranteed non-null. `r_multiple` may still be null even when `status = AVAILABLE`. The UI must handle all four cases independently: `PENDING_STOP`, `PENDING_CALCULATION`, `AVAILABLE` with `r_multiple`, `AVAILABLE` without `r_multiple`.

**Underlying source of nulls:** `gross_pnl`, `net_pnl`, and `total_charges` are NULL in the `PnlSnapshot` response when `status != AVAILABLE` — their absence reflects the absence of a `trade_pnl` row, not NULL values in the `trade_pnl` table. When the row exists, these three columns are always NOT NULL at the database level. `r_multiple` is the only column that can be NULL inside a `trade_pnl` row.

---

## 7. `r_multiple` — Nullable Field Rules

`r_multiple` is the most analytically significant derived field and the only nullable column in the `trade_pnl` table. Its nullability rules deserve explicit treatment.

### 7.1 — Computation Formula

```
r_multiple = net_pnl / journal_entries.planned_risk_amount
```

Where:
```
journal_entries.planned_risk_amount = abs(trades.average_entry − journal_entries.planned_stop)
                                       × trades.total_entry_quantity
```

`planned_risk_amount` is computed and stored by the journal service (JOURNAL-DOMAIN-RULES.md Rule 2.4). Step 10 reads it from `journal_entries` directly — it does not recompute it.

### 7.2 — Null Conditions

`r_multiple` is stored as NULL when any of these conditions hold at the time Step 10 runs:

| Condition | Why `r_multiple` is NULL |
|---|---|
| No `journal_entries` row exists for this trade | User has not created a journal entry yet. No planned stop defined. |
| `journal_entries.planned_stop IS NULL` | User has not set a planned stop. 1R is undefined. |
| `journal_entries.planned_risk_amount IS NULL` | planned_stop is set but `trades.average_entry` was NULL at the time the journal service last computed it. Rare edge case. |
| `journal_entries.planned_risk_amount = 0` | Degenerate case: planned_stop equals average_entry. Division by zero is prevented; `r_multiple` is stored NULL. |

### 7.3 — Retroactive `r_multiple` Population

The user may set `planned_stop` in their journal entry after Step 10 has already run and inserted a `trade_pnl` row. When this happens:

1. The journal service's `upsert_entry` recomputes `planned_risk_amount` and stores it in `journal_entries`.
2. The journal service **does not** update `trade_pnl.r_multiple` — it never writes to `trade_pnl`.
3. Step 10's **retroactive recalculation trigger** (see Section 8.3) must fire to update `r_multiple`.

**Consequence:** There is a window between the user setting `planned_stop` and Step 10 running the retroactive update during which `trade_pnl.r_multiple` is NULL even though the data needed to compute it exists. The journal returns `PnlStatus = AVAILABLE` with `r_multiple = null` during this window. The UI must handle this state — a tooltip like "R-multiple calculating…" is appropriate.

---

## 8. Back-fill Rules

Back-fill refers to the process of populating `trade_pnl` for trades that were closed before Step 10 was deployed, or for trades that were closed before the charge schedule table was populated with the applicable rates.

### 8.1 — Back-fill Eligibility

A trade is eligible for back-fill if:
- `trades.status = 'CLOSED'`
- No row exists in `trade_pnl` for that `trade_id`
- All Step 10 preconditions (Section 5.2) are satisfied

### 8.2 — Back-fill Execution Model

Back-fill is executed as a **batch operation**, not a per-request operation. The journal service never triggers back-fill. The API never triggers back-fill. Back-fill is a Nakula-owned operational task.

**Back-fill query (Nakula / Step 10 engine operator):**

```sql
SELECT t.id AS trade_id
FROM trades t
LEFT JOIN trade_pnl p ON p.trade_id = t.id
WHERE t.status = 'CLOSED'
  AND p.id IS NULL
ORDER BY t.trade_date ASC;
```

For each `trade_id` returned, Step 10 runs the full calculation sequence (Section 5.3) and INSERTs the row.

### 8.3 — Back-fill Is Idempotent

If Step 10 is run twice for the same trade (due to a retry or a double trigger), the ON CONFLICT DO UPDATE clause ensures the row is updated in place rather than a duplicate being inserted. The UNIQUE constraint on `trade_id` prevents duplicate rows.

```sql
INSERT INTO trade_pnl (trade_id, user_id, gross_pnl, ...)
VALUES ($1, $2, $3, ...)
ON CONFLICT (trade_id) DO UPDATE SET
    gross_pnl = EXCLUDED.gross_pnl,
    net_pnl   = EXCLUDED.net_pnl,
    ...
    updated_at = now(),
    calculated_at = now();
```

### 8.4 — Phase 1 Back-fill Expectation

In Phase 1 of TradeForge, trade data is imported from broker CSV files (Sanjaya). The typical user workflow is:
1. Import fills from CSV → reconstruction engine runs → trades are created in `CLOSED` status.
2. Step 10 runs immediately after each reconstruction completes (BackgroundTask).

If Step 10's BackgroundTask fails (Redis unavailable, charge schedule missing), the trade's `trade_pnl` row is not created. These orphaned closed trades must be detected and back-filled before the analytics layer (Karna) is operational. Nakula must run the back-fill query as part of every Step 10 deployment.

---

## 9. Recalculation Rules

A `trade_pnl` row becomes stale when inputs change after Step 10 has already run. Stale rows must be recalculated.

### 9.1 — Events That Trigger Recalculation

| Event | Inputs affected | Recalculation required |
|---|---|---|
| A fill exclusion (`fill_exclusions` INSERT) changes `trades.average_entry` or `trades.average_exit` | `gross_pnl`, all charges (turnover-based), `r_multiple` | Yes — full recalculation |
| A MANUAL fill is added and reconstruction re-runs, changing `average_entry` or `average_exit` | Same as above | Yes — full recalculation |
| The user sets or changes `planned_stop` via the journal service | `journal_entries.planned_risk_amount` changes | Yes — `r_multiple` only (lightweight recalculation) |
| A charge schedule correction is applied (rate error in `charge_schedules`) | All charge components | Yes — full recalculation |
| A SEBI rate change takes effect (not retroactive to past trades) | Not applicable — rates are pinned to `trade_date` | No |
| The Step 10 engine is upgraded to a new version | `engine_version` mismatch with stored row | Yes — full recalculation for affected rows (Nakula batch operation) |

### 9.2 — Full Recalculation

Full recalculation reruns Steps 1–12 from Section 5.3 and updates all columns in `trade_pnl` via ON CONFLICT DO UPDATE. `engine_version` and `calculated_at` are refreshed.

### 9.3 — Lightweight `r_multiple` Recalculation

When only `journal_entries.planned_risk_amount` changes (user updates planned_stop after trade is closed), a lightweight recalculation updates `r_multiple` only:

```sql
UPDATE trade_pnl
SET r_multiple    = $new_r_multiple,
    updated_at    = now(),
    calculated_at = now()
WHERE trade_id = $trade_id;
```

This recalculation is triggered by the journal service emitting a notification after `upsert_entry` completes and `planned_risk_amount` changes. In Phase 1, this is a BackgroundTask. The journal service itself does NOT execute the UPDATE — it emits the trigger event.

**Implementation note for Bhima:** the lightweight trigger is an application-level event, not a PostgreSQL trigger. After `JournalService.upsert_entry` writes a new `planned_risk_amount`, it queues a BackgroundTask (in Phase 1) or a Celery task (in Phase 2) that calls the Step 10 engine's `recalculate_r_multiple(trade_id)` method. The Step 10 engine reads `journal_entries.planned_risk_amount` and writes `trade_pnl.r_multiple`. Journal service does not call the Step 10 service directly in a synchronous path.

### 9.4 — No Automatic Recalculation on Open→CLOSED Transition

When a trade re-opens (hypothetical future case where a CLOSED trade is re-assigned a fill) and then re-closes, recalculation is mandatory. In Phase 1, this scenario cannot occur: trades transition OPEN → PARTIAL → CLOSED and do not reverse. This rule is noted for future protection.

---

## 10. Step 10 Data Dependencies

Step 10 requires the following data sources to be available before it can run:

| Data source | Table / Source | Accessed via | Phase 1 availability |
|---|---|---|---|
| Trade aggregate | `trades` | `TradeRepository.get_by_id` | Available — Bhima's trade domain |
| Entry fills | `execution_fills` WHERE `fill_role = 'ENTRY'` | `FillRepository.list_for_trade` | Available — Bhima's trade domain |
| Exit fills | `execution_fills` WHERE `fill_role = 'EXIT'` | `FillRepository.list_for_trade` | Available — Bhima's trade domain |
| Lot size at trade_date | `lot_size_history` | `LotSizeRepository.get_for_date` | Available — Bhima's trade domain |
| Planned risk amount | `journal_entries.planned_risk_amount` | `JournalRepository.get_planned_risk(trade_id)` — READ ONLY | Available — journal layer |
| Charge rates | `charge_schedules` | `ChargeScheduleRepository.get_for_date(broker, trade_type, trade_date)` | **NOT YET AVAILABLE** — Kubera migration (Step 10) |
| Broker identity | `execution_fills.broker` | Read from fills | Available — trade domain |

**Blocking dependency:** The `charge_schedules` table does not exist yet. Step 10 cannot run until Bhima adds this table (Kubera's migration). The migration and initial seed data for Zerodha rates must be present before Step 10 can compute any charges.

---

## 11. Integration Boundary Contract

The following rules constitute the hard integration boundary between Step 10 and the journal layer. Violations are architecture errors and must be caught at code review.

### 11.1 — Journal → `trade_pnl` (READ ONLY)

| Permitted | Prohibited |
|---|---|
| `SELECT gross_pnl, net_pnl, total_charges, r_multiple FROM trade_pnl WHERE trade_id = $1` | Any INSERT, UPDATE, or DELETE on `trade_pnl` from `JournalService` or `JournalRepository` |
| `SELECT id FROM trade_pnl WHERE trade_id = $1 LIMIT 1` (existence check) | Reading `brokerage`, `stt`, `exchange_charges`, `sebi_charges`, `stamp_duty`, `gst`, `ipft`, `engine_version`, `charge_schedule_version` |
| — | Joining `trade_pnl` with charge breakdown columns for journal display |

### 11.2 — Step 10 → Journal (READ ONLY)

| Permitted | Prohibited |
|---|---|
| `SELECT planned_risk_amount FROM journal_entries WHERE trade_id = $1` | Any INSERT, UPDATE, or DELETE on `journal_entries`, `journal_attachments`, or `journal_audit_log` |
| — | Reading attachment data or audit history |

### 11.3 — Step 10 → Trade Domain (READ ONLY)

Step 10 reads `trades`, `execution_fills`, and `lot_size_history`. It never writes to any trade domain table. `trades.status = CLOSED` is the trigger but Step 10 does not set that status — the reconstruction engine does.

### 11.4 — Neither Layer Uses the Other's Errors as Control Flow

If Step 10 fails (missing charge schedule, Decimal overflow, etc.), it does not raise an error to the journal service. It logs the failure internally. The `trade_pnl` row remains absent; `PnlStatus` returns `PENDING_CALCULATION` from the journal layer. The user sees the same state as before Step 10 ran, not an error state.

If the journal service fails to write `planned_risk_amount` (e.g., `planned_stop` is rejected with a validation error), Step 10 is not notified and does not retry. Step 10's next scheduled run for this trade will find `planned_risk_amount = NULL` and set `r_multiple = NULL`.

---

## 12. Migration Instructions for Bhima

The current migration `0004` (`d7b3e1f5c2a4`) creates `trade_pnl` with only the summary columns and identity columns. The charge breakdown columns and rate provenance columns must be added. Two options:

**Option 1 (preferred if migration has not been applied to any environment):** Edit migration `0004` to add all columns from Section 3 in the initial CREATE TABLE.

**Option 2 (required if migration `0004` is already applied):** Add migration `0005` that ALTERs `trade_pnl` to add:
- `calculated_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `engine_version VARCHAR(20) NOT NULL DEFAULT '0.0.0'`
- `brokerage NUMERIC(18,4) NOT NULL DEFAULT 0`
- `stt NUMERIC(18,4) NOT NULL DEFAULT 0`
- `exchange_charges NUMERIC(18,4) NOT NULL DEFAULT 0`
- `sebi_charges NUMERIC(18,4) NOT NULL DEFAULT 0`
- `stamp_duty NUMERIC(18,4) NOT NULL DEFAULT 0`
- `gst NUMERIC(18,4) NOT NULL DEFAULT 0`
- `ipft NUMERIC(18,4) NOT NULL DEFAULT 0`
- `charge_schedule_version VARCHAR(50) NOT NULL DEFAULT 'UNSET'`
- `broker VARCHAR(20) NOT NULL DEFAULT 'MANUAL'`
- CHECK constraint: `total_charges = brokerage + stt + exchange_charges + sebi_charges + stamp_duty + gst + ipft`
- CHECK constraint: all charge components `>= 0`

The defaults are temporary scaffolding for the migration; Step 10 will overwrite them when it runs for each closed trade.

---

## 13. Validation Test Cases

These test cases must be implemented by Sahadeva and must pass before Step 10 is declared production-ready.

### TC-G3-001 — New closed trade, no journal entry

**Input:**
- Trade: LONG MIS Equity, `average_entry = ₹250`, `average_exit = ₹255`, `total_entry_quantity = 500`
- No `journal_entries` row for this trade
- Charge schedule: Zerodha MIS NSE rates

**Expected:**
- `trade_pnl` row is inserted
- `gross_pnl = (255 − 250) × 500 = ₹2,500.0000`
- `net_pnl = ₹2,500 − total_charges`
- `r_multiple IS NULL` (no journal entry, no planned_risk_amount)
- `total_charges = brokerage + stt + exchange_charges + sebi_charges + stamp_duty + gst + ipft`

**Journal side:**
- `has_pnl_row(trade_id)` returns `True`
- `PnlStatus = AVAILABLE`
- `pnl.r_multiple = null`

---

### TC-G3-002 — Closed trade, journal entry with planned_stop set

**Input:**
- Trade: same as TC-G3-001
- Journal entry: `planned_stop = ₹242`, `planned_risk_amount = abs(250 − 242) × 500 = ₹4,000.0000`

**Expected:**
- `r_multiple = net_pnl / 4000.0000`
- If `net_pnl = ₹2,407.26`, then `r_multiple = 2407.26 / 4000 = 0.601815`

---

### TC-G3-003 — `total_charges` identity check

**Input:** Any closed trade

**Expected:**
- `total_charges = brokerage + stt + exchange_charges + sebi_charges + stamp_duty + gst + ipft`
- Verified to 4 decimal places
- Check constraint prevents row from being inserted if this identity does not hold

---

### TC-G3-004 — Planned stop set after trade_pnl row exists

**Sequence:**
1. Trade closes → Step 10 runs → `trade_pnl` row inserted with `r_multiple = NULL` (no planned_stop)
2. User calls `PUT /v1/journal/trades/{trade_id}` with `planned_stop = ₹242`
3. Journal service computes `planned_risk_amount = ₹4,000` and stores it
4. Lightweight recalculation BackgroundTask runs
5. Step 10 updates `trade_pnl.r_multiple = net_pnl / 4000`

**Expected journal response after step 5:**
- `pnl.status = "AVAILABLE"`
- `pnl.r_multiple = <non-null>`

**Expected journal response between steps 3 and 5:**
- `pnl.status = "AVAILABLE"`
- `pnl.r_multiple = null` (row exists but r_multiple not yet updated)

---

### TC-G3-005 — `r_multiple` with planned_risk_amount = 0

**Input:**
- `planned_stop = trades.average_entry` (exactly equal, not a realistic plan but a boundary test)
- `planned_risk_amount = 0`

**Expected:**
- Step 10 sets `r_multiple = NULL` (division by zero prevention)
- No exception raised

---

### TC-G3-006 — Idempotency: Step 10 runs twice for same trade

**Sequence:**
1. Step 10 inserts `trade_pnl` row
2. Step 10 is triggered again for the same trade (retry scenario)

**Expected:**
- Second run executes ON CONFLICT DO UPDATE
- Final row values reflect the second calculation (idempotent — same inputs → same outputs)
- No duplicate row; UNIQUE constraint on `trade_id` is not violated
- `updated_at` is refreshed; `created_at` is unchanged

---

### TC-G3-007 — Step 10 skips open trade

**Input:** `trades.status = 'OPEN'`

**Expected:**
- No `trade_pnl` row inserted
- `has_pnl_row(trade_id)` returns `False`
- `PnlStatus = PENDING_STOP` (if no planned_stop) or `PENDING_CALCULATION` (if planned_stop set)

---

### TC-G3-008 — Back-fill batch query correctness

**Precondition:** 5 closed trades exist, 3 of which have `trade_pnl` rows, 2 do not.

**Expected:**
- Back-fill query returns exactly 2 trade_ids
- Step 10 inserts rows for those 2 trades
- After back-fill, all 5 closed trades have `trade_pnl` rows

---

### TC-G3-009 — Charge identity violated: Step 10 internal error

**Scenario:** A bug in Step 10 computes `brokerage + stt + exchange_charges + sebi_charges + stamp_duty + gst + ipft ≠ total_charges`

**Expected:**
- PostgreSQL CHECK constraint `chk_trade_pnl_total_charges` rejects the INSERT
- Step 10 catches the constraint violation, logs the error, and does NOT insert the row
- `trade_pnl` row remains absent; journal returns `PnlStatus = PENDING_CALCULATION`

---

## 14. Open Items and Deferred Scope

| Item | Status | Owner |
|---|---|---|
| `charge_schedules` table definition (rate storage, effective dates, broker configuration) | Not yet written | Kubera — separate document |
| Partial trade P&L (P&L for PARTIAL status trades before full close) | Deferred to Phase 2 | Kubera |
| Futures daily MTM breakdown (per-day settlement attribution) | Deferred to Phase 2 | Kubera |
| Options exercise / assignment P&L handling | Deferred — see Unresolved 2 in JOURNAL-DOMAIN-RULES.md | Ganesha, Kubera |
| Corporate action retroactive P&L adjustment | Deferred — see Unresolved 3 in TRADE-DOMAIN-DATA-MODEL.md | Kubera |
| Multi-day partial exit attribution (CNC delivery trades) | Deferred — Unresolved 4 in TRADE-DOMAIN-DATA-MODEL.md | Kubera |
| Karna analytics queries on `trade_pnl` | Not yet specified — Karna spec TBD | Karna |

---

*Kubera — Financial Calculation & P&L Specialist*
*Domain inputs: Ganesha (JOURNAL-DOMAIN-RULES.md Rule 2.4, Rule 3.1, Rule 3.2), Mayasura (ADR-003 Decision 1)*
*Implementation owners: Bhima (trade_pnl migration, charge_schedules), Nakula (back-fill operations, charge rate seeding), Sahadeva (TC-G3-001 through TC-G3-009)*
