# Step 16 — Manual Trade Entry

**Document:** `docs/project-status/STEP-16-EXECUTION-PLAN.md`  
**Author:** Krishna (Project Manager)  
**Date:** 2026-09-06  
**Parent plan:** `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`  
**Branch:** `feat/step-16-manual-trade-entry` (base: `main` after Step 15 merged as PR #9)  
**Status:** READY TO IMPLEMENT — Ganesha AMB-01/02/03 + D6 rulings applied (2026-09-07); Dhanvantari BLK-1/BLK-2 applied (2026-09-06); Dhanvantari BLK-3 + REQ-5/6/7 + R-16-6 (elevated) + R-16-7 (clarified) applied (2026-09-07); PLN-01/02/03 plan corrections applied; Mayasura A-16-1 through A-16-5 applied (2026-09-07); BLK-1 data path corrected (Bhima inspection 2026-09-07); Sahadeva QA-10 (B-16-37) added; QA-11/QA-12 recorded as accepted known risks (2026-09-07); all blocking corrections incorporated

---

## Goal

Let users add trades without a CSV file. A user picks an instrument, specifies a direction, enters one or more fills (price, quantity, timestamp), and the existing reconstruction engine handles everything else — trade creation, P&L computation if closed, R-multiple if planned stop is provided.

Done means: `POST /v1/trades` and `POST /v1/trades/{id}/fills` and `DELETE /v1/trades/{id}` are live and correctly tested; the Add Trade screen is accessible from the nav and end-to-end entry works — Sahadeva GO, Nakula CI GREEN, Yudhishthira ACCEPT.

---

## What "Done" Looks Like

A logged-in user with an active trading account can:

1. **Add a trade (entry only):** Enter instrument symbol, exchange, direction, trade type, one or more entry fills (side, price, quantity, timestamp) → POST creates fills in `execution_fills`, reconstruction runs → trade appears as OPEN/PARTIAL.
2. **Add a trade (closed):** Supply both entry and exit fills → trade appears as CLOSED with computed P&L and R-multiple (if planned stop was provided).
3. **Scale into an open trade:** Via `POST /v1/trades/{id}/fills`, add a fill to an existing OPEN or PARTIAL trade → reconstruction runs again → trade positions update.
4. **Delete a manually entered trade:** `DELETE /v1/trades/{id}` — soft-deletes the trade; fills are excluded from future reconstruction; trade no longer appears in analytics.
5. **Frontend:** The `/trades/new` route (linked from sidebar or floating button) opens an Add Trade screen with instrument search, fill entry, and account selector. Client-side validation prevents bad submissions.

---

## Opening Obligations

No external specialist sign-off required before implementation starts.

Step 15 is merged to `main`. Branch `feat/step-16-manual-trade-entry` is based on that state.

**R-5 from Phase 1 risk register is relevant here:** Sanjaya should confirm the `POST /v1/trades` request shape is compatible with future import adapter use before the API is finalized. The endpoint and request schema are specified below — Sanjaya can review and flag any structural mismatch without blocking implementation.

---

## What Already Exists (Do Not Rebuild)

| Concern | What exists | Location |
|---------|-------------|----------|
| Trade ORM model | `trades` table + all columns | `backend/src/tradeforge/infrastructure/models/trade_domain.py` |
| ExecutionFill ORM model | `execution_fills` table | `backend/src/tradeforge/infrastructure/models/trade_domain.py` |
| Reconstruction engine | `ReconstructionEngine.run()` | `backend/src/tradeforge/application/trade/reconstruction.py` |
| Fill insertion | `FillRepository.insert_normalized_fill()` | `backend/src/tradeforge/infrastructure/repositories/fill_repo.py:113` |
| Instrument lookup | `InstrumentRepository.find_for_fill()` | `backend/src/tradeforge/infrastructure/repositories/instrument_repo.py:84` |
| P&L computation | `PnlService.backfill_all_closed()` | `backend/src/tradeforge/application/pnl_service.py` |
| Account lookup + auth | `TradingAccountService.get()` / `get_active()` | `backend/src/tradeforge/application/trading_account_service.py` |
| Fill exclusions | `FillExclusionRepository` | `backend/src/tradeforge/infrastructure/repositories/fill_exclusion_repo.py` |
| Trade repo | `TradeRepository` | `backend/src/tradeforge/infrastructure/repositories/trade_repo.py` |
| Product type types | `ProductTypeFamily`, `product_type_family_for()` | `backend/src/tradeforge/domain/trade/types.py` |
| Account context | `AccountContext`, `useAccount()` | `frontend/src/features/accounts/context/AccountContext.tsx` |
| App router | `/trades` route → `PlaceholderPage` | `frontend/src/app.tsx:38` |
| Sidebar nav | `/trades` link already present | `frontend/src/layout/AppShell.tsx` |

---

## Domain Rulings (Ganesha — Trading Domain Analyst, 2026-09-06)

Formal rulings resolving domain ambiguities identified during the pre-implementation review. These decisions govern implementation choices and must not be altered without a new Ganesha review.

---

### Ruling D2 — DELETE Endpoint: Restricted to Manually Entered Trades Only

**Decision:** `DELETE /v1/trades/{id}` is restricted to trades whose fills are entirely manually entered. A trade is manually entered when **all** of its fills carry `import_source = 'MANUAL'`. If any fill has `import_source = 'CSV'` (or any other non-MANUAL source), the endpoint returns 422 `TRADE_NOT_MANUAL`.

**Rationale:** The CSV import pipeline represents broker-verified, exchange-confirmed execution data. A trade created from a CSV import is the broker's record of what happened; it is not the user's assertion. Allowing users to soft-delete CSV-imported trades would permanently remove auditable broker records from analytics with no reconciliation trail — the fill exclusion entries would record the user's intent but not any broker dispute. If a user needs to dispute a specific broker-imported fill (wrong price, wrong quantity, data error), the correct path is the fill exclusion mechanism, which preserves the original fill in the database and records the dispute as an audit event. Manual trades, by contrast, are entirely user-asserted; the user is both the source and the authority, and they should be able to correct or remove their own entries freely.

**Implementation effect:** Step 2 added to the DELETE sequence, after ownership verification — see B-16-B. (Corrected by Dhanvantari: fill provenance must not be disclosed before the caller is verified as the trade owner.)

---

### Ruling D3 — `POST /v1/trades/{id}/fills`: Mixed-Provenance Trades Are Permitted

**Decision:** A user may add a manual fill to any non-CLOSED trade regardless of that trade's origin. No `import_source` restriction is placed on the receiving trade. A trade that contains both broker-CSV fills and user-MANUAL fills is a valid, permitted state.

**Rationale:** The primary legitimate use case is trade gap repair: a broker CSV export was incomplete (connectivity failure, end-of-day export missed a fill, late trade report), and the user needs to add the missing fill to a trade that is already open in the system. Blocking this forces the user to either accept a permanently PARTIAL trade (incorrect P&L, broken analytics) or delete and re-enter everything — both worse outcomes. The reconstruction engine is provenance-agnostic; it processes all non-excluded fills for the processing unit by FIFO order regardless of `import_source`. The per-fill `import_source` column provides a permanent audit trail of which fills came from the broker and which the user asserted.

**Boundary condition:** If the user adds a manual fill to a CSV-imported trade and a subsequent CSV import includes the broker's version of that fill, `fill_exists()` (checking `broker_trade_id + account_id`) will not match the user's manual fill (whose `broker_trade_id` is a generated UUID). Both fills would be present. Bhima must document this in the service code: if a user adds a manual fill as a gap-repair and then a corrected CSV import arrives, the manual fill must be excluded via fill_exclusions before re-importing, or the position will be double-counted. This is a user-workflow concern, not a data model defect.

**Phase 2 note:** Mixed-provenance trades should be visually distinguished in the trade list and detail view (Step 19). A `has_manual_fills` derived field is a query-time computation; no schema change is required now.

---

### Ruling D6 — `product_type` Source for `add_fill()` Reconstruction Path

**Decision:** In `POST /v1/trades/{id}/fills`, `product_type` is not stored on the `trades` table and is not carried in `AddFillRequest`. It must be derived server-side from `trade.trade_type` using a new pure helper `product_type_from_trade_type()` in `domain/trade/types.py`. The mapping is deterministic:

| `trade.trade_type` | Derived `product_type` |
|--------------------|------------------------|
| `MIS` | `MIS` |
| `CNC` | `CNC` |
| `CNC_SAME_DAY` | `CNC` |
| `NRML_FUT` | `NRML` |
| `NRML_OPT` | `NRML` |

**Rationale:** `ExecutionFill.product_type` stores raw broker values (`MIS`, `CNC`, `NRML`); `Trade.trade_type` stores the system's enriched encoding (`MIS`, `CNC`, `CNC_SAME_DAY`, `NRML_FUT`, `NRML_OPT`). `ReconstructionEngine.run()` requires `product_type` as a processing-unit discriminator. For `add_fill()`, the trade already exists — its `trade_type` encodes exactly the information needed to recover the original `product_type`. The mapping is the exact inverse of `provisional_trade_type()` and is consistent with `TRADE_TYPES_FOR_FAMILY`. The `Trade` ORM has no `product_type` column; computing it from `trade_type` avoids any schema change.

**Implementation effect:** Step 5 of `POST /v1/trades/{id}/fills` is extended to derive `product_type` alongside `instrument_type`. `product_type_from_trade_type()` is added to `domain/trade/types.py` — see B-16-D.

---

## Backend Scope (Owner: Bhima)

### Task B-16-A — Migration 0015: Soft-Delete and Import Source

**File:** `backend/alembic/versions/0015_manual_trade_soft_delete.py`

Two changes:

**1. Add `is_deleted` to `trades`:**

```sql
ALTER TABLE trades
  ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT false;

-- Partial index: covers only the common case (non-deleted rows).
-- A standard composite index on (user_id, boolean) has poor selectivity
-- because is_deleted = false represents ~100% of rows; the planner
-- would ignore it. A partial index is smaller and always used.
CREATE INDEX idx_trades_user_active ON trades (user_id) WHERE is_deleted = false;
```

- `is_deleted = true` is the soft-delete flag. **The trade's `status` column is NOT changed by the delete operation** — a soft-deleted OPEN trade remains `status = 'OPEN'` in the database. The `is_deleted` flag is the sole deletion signal. All queries that surface trades to users must add `trades.is_deleted = false` to their WHERE clauses. See B-16-C for the mandatory audit list.
- `DEFAULT false` ensures existing rows are unaffected.

**2. Extend `import_source` check constraint on `execution_fills` to include `'MANUAL'`:**

The existing check constraint on `execution_fills.import_source` accepts `'CSV'` only. Verify:

```sql
-- Check current constraint name in 0002_trade_domain_tables.py
-- then update it:
ALTER TABLE execution_fills DROP CONSTRAINT ck_fills_import_source;
ALTER TABLE execution_fills ADD CONSTRAINT ck_fills_import_source
  CHECK (import_source IN ('CSV', 'MANUAL'));
```

If the constraint does not exist (column is unconstrained), skip this step and add a note.

> **Note on `broker = 'MANUAL'`:** The existing `ck_fills_broker` constraint on `execution_fills` already includes `'MANUAL'` — `"broker IN ('ZERODHA', 'UPSTOX', 'ANGEL_ONE', 'MANUAL')"`. No migration change is needed for the broker column.

**Downgrade:** reverse the `is_deleted` column addition and restore the prior check constraint.

**Grant:**

```sql
GRANT UPDATE (is_deleted) ON trades TO tradeforge_app;
```

---

### Task B-16-B — New Router: `POST /v1/trades`, `POST /v1/trades/{id}/fills`, `DELETE /v1/trades/{id}`

**File (new):** `backend/src/tradeforge/api/v1/trades.py`

Register under `prefix="/trades"`, tag `"trades"`. Wire into `main.py` alongside existing routers.

---

#### API Types

**`FillInput`** — shared input type for a single fill:

```python
class FillInput(BaseModel):
    model_config = {"extra": "forbid"}

    side: Literal["BUY", "SELL"]
    quantity: Decimal = Field(..., gt=0)
    price: Decimal = Field(..., gt=0)
    fill_timestamp: datetime  # must be timezone-aware (UTC-offset accepted; stored as UTC)
```

**`InstrumentInput`** — identifies the instrument. Used by both POST endpoints:

```python
class InstrumentInput(BaseModel):
    model_config = {"extra": "forbid"}

    symbol: str = Field(..., min_length=1, max_length=50, description="Uppercase NSE/BSE symbol")
    exchange_segment: Literal["NSE_EQ", "NSE_FO", "BSE_EQ"]
    instrument_type: Literal["EQ", "FUT", "CE", "PE"]
    expiry_date: date | None = None          # required for FUT, CE, PE
    strike_price: Decimal | None = None      # required for CE, PE; gt=0
```

**`CreateTradeRequest`** — request body for `POST /v1/trades`:

```python
class CreateTradeRequest(BaseModel):
    model_config = {"extra": "forbid"}

    account_id: uuid.UUID
    instrument: InstrumentInput
    product_type: Literal["MIS", "CNC", "NRML"]
    fills: list[FillInput] = Field(..., min_length=1, max_length=20)
    planned_stop: Decimal | None = Field(default=None, gt=0)
    planned_target: Decimal | None = Field(default=None, gt=0)
```

Validation rules (applied in the endpoint before calling any service):
- All `fill_timestamp` values must be timezone-aware — return 422 `FILL_TIMESTAMP_NOT_TZ_AWARE` if any is naive.
- Fills must be in strictly ascending timestamp order — return 422 `FILLS_NOT_CHRONOLOGICAL` if any fill is ≤ the prior fill's timestamp.
- For `instrument_type` of `FUT`, `CE`, `PE`: `expiry_date` must be provided — return 422 `EXPIRY_DATE_REQUIRED`.
- For `instrument_type` of `CE`, `PE`: `strike_price` must be provided — return 422 `STRIKE_PRICE_REQUIRED`.
- `product_type` must be valid for `instrument.instrument_type` per Indian exchange domain rules (D1 — Ganesha). Equities use MIS/CNC only; F&O uses MIS/NRML only. CNC is not a valid product type on derivative instruments; NRML is not a valid product type for equity:
  - `instrument_type = EQ` → `product_type` must be `MIS` or `CNC` — return 422 `INVALID_PRODUCT_TYPE_FOR_INSTRUMENT` if `NRML`
  - `instrument_type = FUT` → `product_type` must be `MIS` or `NRML` — return 422 `INVALID_PRODUCT_TYPE_FOR_INSTRUMENT` if `CNC`
  - `instrument_type = CE` or `PE` → `product_type` must be `MIS` or `NRML` — return 422 `INVALID_PRODUCT_TYPE_FOR_INSTRUMENT` if `CNC`

**`AddFillRequest`** — request body for `POST /v1/trades/{id}/fills`:

```python
class AddFillRequest(BaseModel):
    model_config = {"extra": "forbid"}

    fill: FillInput
```

**`TradeOut`** — response from both POST endpoints and delete:

```python
class TradeOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    account_id: uuid.UUID | None  # nullable: mirrors ORM nullable=True; Step 16 endpoints always return non-None (AMB-03 — Ganesha)
    instrument_id: uuid.UUID
    trade_type: str
    direction: str
    status: str
    trade_date: date
    first_fill_at: datetime
    last_fill_at: datetime | None
    total_entry_quantity: Decimal
    total_exit_quantity: Decimal
    net_position: Decimal
    average_entry: Decimal | None
    average_exit: Decimal | None
    planned_stop: Decimal | None
    planned_target: Decimal | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
```

---

#### `POST /v1/trades`

Creates a new trade from manual fills.

**Implementation sequence:**

1. Validate the request body (timestamp ordering, expiry/strike presence for F&O).
2. Resolve `account_id` — verify the account exists, is ACTIVE, and belongs to the authenticated user (use `TradingAccountService.get()`). Return 404 `ACCOUNT_NOT_FOUND` if not.
3. Resolve `instrument_id` via `InstrumentRepository.find_for_fill()`. Return 422 `INSTRUMENT_NOT_FOUND` with `{symbol, exchange_segment, instrument_type}` detail if not found.
4. For each fill in `request.fills`: construct a `NormalizedFill` and call `FillRepository.insert_normalized_fill()`. For manual fills, set fields as follows (D5 — Ganesha):
   - `broker_trade_id = str(uuid.uuid4())` — a freshly generated UUID string per fill. Manual fills have no broker fill ID; a UUID satisfies the `NormalizedFill.broker_trade_id: str` type contract (non-optional) and guarantees uniqueness without conflicting with the partial unique index `uq_fills_broker_trade_account`. The `broker='MANUAL'` + `import_source='MANUAL'` markers on each fill row permanently identify it as a manual entry.
   - `broker_order_id = str(uuid.uuid4())` — same rationale; one UUID per fill, independent of `broker_trade_id`.
   - `import_source = "MANUAL"`
   - `broker = "MANUAL"`
   - `is_expiry_squareoff = False`
   - `is_auction = False`
   - Do **not** call `fill_exists()` before inserting manual fills. That method deduplicates on `broker_trade_id + account_id`, which is meaningful only for broker-sourced fills where the broker assigns a stable fill ID. For manual fills the UUID is generated at call time — it is always unique. Every `POST /v1/trades` call always creates new fills; deduplication at the manual entry level is the user's responsibility.
   - Derive `session` from `fill_timestamp` converted to `Asia/Kolkata` local time. The `execution_fills.session` column has a DB check constraint permitting only three values: `'PRE_OPEN'`, `'REGULAR'`, `'POST_CLOSE'`. Map as follows:
     - `'PRE_OPEN'` — IST time before 09:15
     - `'REGULAR'` — IST time 09:15 to 15:30 (inclusive)
     - `'POST_CLOSE'` — IST time after 15:30
   - **Do not use the six N-2 analytics bands** (Open Volatility, Mid-Morning, etc.) here. Those are computed at query time from `fill_timestamp AT TIME ZONE 'Asia/Kolkata'` by the analytics layer and are never stored in the `session` column.
   - Derive `trade_date` as `.date()` of `fill_timestamp` localised to `Asia/Kolkata`.
5. Flush (not commit) after all fills are inserted, so they are visible to the reconstruction query within the same transaction.
6. Run `ReconstructionEngine.run(session, user_id, account_id, instrument_id, product_type, instrument_type)`. Pass `instrument_type` from `request.instrument.instrument_type` — the engine requires it to disambiguate `NRML_FUT` from `NRML_OPT` at trade-open time. On `ReconstructionError` — rollback and return 422 `RECONSTRUCTION_FAILED` with the error detail.
   > **Implementation verification point (Dhanvantari REQ-7):** `ReconstructionEngine.run()` must call `await session.flush()` after creating or updating any `Trade` row, before returning `ReconstructionResult`. This ensures the `average_entry`, `total_entry_quantity`, `status`, and `direction` fields written by the engine are visible to the subsequent query in step 8a. Bhima must verify this is the case in the existing engine implementation before implementing `TradeService`.
7. The `run()` call returns a `ReconstructionResult`. Obtain the trade ID from `result.affected_trade_id` (see B-16-D — `ReconstructionResult` must be extended with this field). This is the trade that was created or last modified by the run.
8. If `planned_stop` or `planned_target` was provided:
   a. Query the `Trade` ORM row by `result.affected_trade_id` for `average_entry`, `total_entry_quantity`, and `direction` — the reconstruction engine (step 6) has written all three (see REQ-7 above). This query is within the same transaction (no commit yet); the values are correct.
   b. If `planned_stop` was provided, validate stop placement against trade direction before computing risk:
      - If `trade.direction == "LONG"` and `planned_stop >= trade.average_entry`: return 422 `PLANNED_STOP_WRONG_SIDE` — "Planned stop for a LONG trade must be below the average entry price."
      - If `trade.direction == "SHORT"` and `planned_stop <= trade.average_entry`: return 422 `PLANNED_STOP_WRONG_SIDE` — "Planned stop for a SHORT trade must be above the average entry price."
      > **Why validate here (Dhanvantari REQ-5):** This validation cannot be done at request time (step 1) because trade direction is unknown until reconstruction runs. The `abs()` in the formula silently accepts a stop placed on the wrong side of entry — a LONG with stop above entry produces a positive `planned_risk_amount` but models an impossible trade (stop triggers on a gain). R-multiples computed from such a `planned_risk_amount` are structurally meaningless. Validation after reconstruction, when direction is known, catches this without requiring direction in the request body.
   c. Compute `planned_risk_amount = abs(trade.average_entry - planned_stop) * trade.total_entry_quantity`. Only compute if `planned_stop` passes direction validation in step 8b.
   d. Call `TradeRepository.update_trade()` for `result.affected_trade_id` with: `planned_stop` (if provided and validated), `planned_target` (if provided), and `planned_risk_amount` (if computed in step c). Flush immediately (not commit). The reconstruction engine does not set any of these three fields.
   > **Ordering constraint (Dhanvantari BLK-1 — rationale corrected, Bhima inspection 2026-09-07):** This step must execute BEFORE step 9. `PnlService.backfill_all_closed()` → `PnlRepository.get_planned_risk()` reads **`trades.planned_risk_amount`** (via an extended fallback path — see B-16-D) to compute `r_multiple` for Step 16 trades that have no journal entry. If `trades.planned_risk_amount` is written after the backfill runs, `get_planned_risk()` returns NULL and a NULL R-multiple is persisted permanently with no subsequent recalculation path. Flush after `update_trade()`, then proceed to step 9.
   > **Correction to prior BLK-1 rationale:** The earlier version stated that `PnlService.backfill_all_closed()` reads `trades.planned_stop`. This is incorrect. Bhima inspection confirmed that `PnlRepository.get_planned_risk()` reads `journal_entries.planned_risk_amount` — which is NULL for all Step 16 trades that have no journal entry — and currently returns NULL unconditionally in that case. Writing `trades.planned_stop` alone has no effect on R-multiple computation. The fix is two-part: (1) populate `trades.planned_risk_amount` here from `planned_stop` as specified above; (2) extend `get_planned_risk()` to fall back to `trades.planned_risk_amount` when no journal entry exists — see B-16-D. Without both parts, B-16-28 will always produce a NULL R-multiple regardless of `planned_stop` being provided.
9. If any trades were closed by the reconstruction (`result.trades_closed > 0`), run `PnlService.backfill_all_closed()`. `planned_stop` is now present in the database within this transaction, so R-multiple is computed correctly for any manually entered closed trade that provided a planned stop.
10. Commit.
11. Query the `Trade` ORM row by `result.affected_trade_id` and return `TradeOut`.

**Response:** `201 Created` with `TradeOut`.

> **Multi-cycle behavior (D4 — Ganesha):** If the submitted fills span a complete position cycle and then reopen — e.g., BUY 100 → SELL 100 → BUY 50 for the same instrument + product_type — the reconstruction engine creates more than one trade via FIFO boundary detection. The `201 Created` response returns only the trade identified by `result.affected_trade_id`, which is the trade affected by the final fill. Earlier trades created within the same call (e.g., a fully closed trade from the first BUY→SELL cycle) are persisted and will appear in the trade list (Step 19), but are not returned in this response. This is expected and correct behavior: trade boundaries are determined by the reconstruction engine at position-zero crossings, not by the API caller. Test B-16-27 covers this case.

---

#### `POST /v1/trades/{trade_id}/fills`

Adds a fill to an existing trade in OPEN or PARTIAL status.

> **Domain ruling (D3 — Ganesha):** This endpoint permits adding manual fills to trades of any origin — including CSV-imported trades. Mixed-provenance trades (some fills from broker CSV, some from manual entry) are a valid state and support the gap-repair use case. If a user adds a manual fill as gap-repair and a corrected CSV import later arrives containing the broker's version of that fill, the manual fill must be excluded via fill_exclusions before re-importing to prevent double-counting. Document this in the `TradeService.add_fill()` code.

**Implementation sequence:**

1. Look up the trade by `trade_id`. Return 404 `TRADE_NOT_FOUND` if not found or `is_deleted = true`.
2. Verify the trade's `account_id` belongs to the authenticated user using an **ownership-only query**: `SELECT id FROM trading_accounts WHERE id = trade.account_id AND user_id = authenticated_user_id`. Return 403 `TRADE_NOT_OWNED` if no row is returned.
   > **Implementation constraint (Dhanvantari REQ-6):** Do NOT use `TradingAccountService.get()` or `TradingAccountService.get_active()` here. Both methods check `ACTIVE` account status, which would incorrectly block adding fills to trades that belong to a now-deactivated account. A user with an OPEN position on an account subsequently deactivated — the primary R-16-7 scenario — would be unable to add corrective fills via this endpoint. The fill is being added to a trade that already exists; the account's current administrative status is irrelevant to ownership. Status checks belong only at trade creation (where the account must be ACTIVE to accept new positions, per `create_trade()` step 2).
3. If the trade status is `CLOSED`, return 422 `TRADE_ALREADY_CLOSED` — exits on a closed trade are not supported via this endpoint in Phase 1.
4. Validate the `fill.fill_timestamp` is timezone-aware and is **at or after** (`>=`) the trade's `first_fill_at`. Return 422 `FILL_TIMESTAMP_BEFORE_TRADE_OPEN` if the fill timestamp precedes the trade's opening fill. A fill with the same timestamp as `first_fill_at` is valid — simultaneous partial fills from the same broker order share a timestamp, and the reconstruction engine resolves ordering deterministically via `fill_id ASC, created_at ASC`. (AMB-01 — Ganesha)
5. Derive both server-side arguments required by `ReconstructionEngine.run()`:
   - **`instrument_type`:** query the `instruments` table via `InstrumentRepository` using `trade.instrument_id`. Not carried on the `Trade` ORM model; must be fetched.
   - **`product_type`:** call `product_type_from_trade_type(trade.trade_type)` from `domain/trade/types.py` (D6 — Ganesha, 2026-09-07). Applies the deterministic reverse mapping: `MIS→MIS`, `CNC/CNC_SAME_DAY→CNC`, `NRML_FUT/NRML_OPT→NRML`. The `Trade` ORM has no `product_type` column; `trade.trade_type` encodes all information needed to recover it. `AddFillRequest` carries neither field — both are derived server-side.
6. Insert the fill using `FillRepository.insert_normalized_fill()` as above (apply the same `session` derivation: PRE_OPEN / REGULAR / POST_CLOSE against `fill_timestamp` IST).
7. Flush, then run `ReconstructionEngine.run(session, user_id, account_id, instrument_id, product_type, instrument_type)` using `product_type` and `instrument_type` both derived in step 5.
   > **Implementation verification point (Dhanvantari REQ-7):** `ReconstructionEngine.run()` must call `await session.flush()` after creating or updating any `Trade` row, before returning `ReconstructionResult`. This ensures the updated `average_entry`, `total_entry_quantity`, `direction`, and `status` fields are visible to the subsequent query in step 7b. Bhima must verify this is the case in the existing engine implementation before implementing `TradeService`.
7b. If `trade.planned_stop IS NOT NULL` (meaning a stop was recorded at create time), recompute `planned_risk_amount` from the updated position:
    a. Query the `Trade` ORM row by `trade_id` for updated `average_entry`, `total_entry_quantity`, and `direction` — the reconstruction engine (step 7) has flushed all three.
    b. Validate stop placement against trade direction: if `trade.direction == "LONG"` and `trade.planned_stop >= trade.average_entry`, return 422 `PLANNED_STOP_WRONG_SIDE`. If `trade.direction == "SHORT"` and `trade.planned_stop <= trade.average_entry`, return 422 `PLANNED_STOP_WRONG_SIDE`. This is a consistency guard — the stop was valid at create time, but if scale-ins have moved `average_entry` past the stop, the planned risk is structurally invalid.
    c. Compute `planned_risk_amount = abs(trade.average_entry - trade.planned_stop) * trade.total_entry_quantity`.
    d. Call `TradeRepository.update_trade()` for `trade_id` with the new `planned_risk_amount`. Flush immediately.
    > **Ordering constraint (Dhanvantari BLK-3):** This flush must precede step 8. `PnlService.backfill_all_closed()` → `PnlRepository.get_planned_risk()` reads `trades.planned_risk_amount` via the fallback path (B-16-D). If the stale create-time value is not replaced before backfill runs, the closed-trade R-multiple is computed from the original position size, not the current scaled position — producing permanently wrong analytics.
    > **Why recompute (Dhanvantari BLK-3):** `planned_risk_amount` was computed at `create_trade()` step 8c using the initial `average_entry` and `total_entry_quantity`. After `add_fill()`, both values change. Example: create BUY 100 @ ₹250, planned_stop=₹240 → `planned_risk_amount = ₹1,000`. add_fill() BUY 100 @ ₹260 → average_entry=₹255, total_qty=200 → correct `planned_risk_amount = ₹3,000` but stored value is still ₹1,000 (67% understatement). R-multiple and at-risk calculations would be fabricated. `trade.planned_stop` is already on the trades row from `create_trade()` — no additional request parameter is needed.
8. Run `PnlService.backfill_all_closed()` if the reconstruction closed the trade (`result.trades_closed > 0`).
9. Commit. Query and return the updated `Trade` ORM row by `trade_id` as `TradeOut`.

**Response:** `200 OK` with `TradeOut`.

---

#### `DELETE /v1/trades/{trade_id}`

Soft-deletes a manually entered trade.

**Implementation sequence:**

0. Look up the trade by `trade_id`. Return 404 `TRADE_NOT_FOUND` if not found or already `is_deleted = true`.
1. Verify the trade's `account_id` belongs to the authenticated user using an **ownership-only query**: `SELECT id FROM trading_accounts WHERE id = trade.account_id AND user_id = authenticated_user_id`. Return 403 `TRADE_NOT_OWNED` if no row is returned.
   > **Implementation constraint (Mayasura A-16-4):** Do NOT use `TradingAccountService.get()` or `TradingAccountService.get_active()` here. Both methods check `ACTIVE` account status, which would incorrectly block deletion of trades that belong to a now-deactivated trading account. A trade's account being deactivated does not revoke the user's right to delete their own manually entered trade. The ownership check must be a direct query against `trading_accounts` filtering only on `id` and `user_id`, with no status condition.
   > **Auth boundary (Dhanvantari BLK-2):** Steps 0–1 establish identity before any fill data is accessed. Without this ordering, an unauthenticated caller can probe fill provenance (CSV vs. MANUAL) on any trade UUID in the system by observing whether the response is 422 `TRADE_NOT_MANUAL` vs. 403/404 — an information-disclosure vulnerability. No fill data is fetched until ownership is confirmed.
2. Fetch all `execution_fills` where `trade_id = trade_id`. If any fill has `import_source ≠ 'MANUAL'`, return 422 `TRADE_NOT_MANUAL` — "This trade contains broker-imported fills and cannot be deleted via this endpoint. Use the fill exclusion mechanism to dispute specific fills." See Domain Ruling D2.
3. Call `FillExclusionRepository.get_excluded_fill_ids_for_trade(trade_id)` — **one batch query** that returns the set of all already-excluded fill UUIDs for this trade. Compute `fills_to_exclude = [f for f in fills if f.id not in excluded_fill_ids]`. If `fills_to_exclude` is empty (all fills were already individually excluded), proceed directly to step 5 — the DELETE still succeeds and sets `is_deleted = true`. This is correct and expected: a user who excluded all fills one by one via the fill-exclusion mechanism should still be able to soft-delete the resulting empty trade shell. The two operations (fill exclusion and trade soft-delete) are independent. (AMB-02 — Ganesha)
   > **Implementation constraint (Mayasura A-16-5):** `get_excluded_fill_ids_for_trade(trade_id)` must be added to `FillExclusionRepository` as part of B-16-B if it does not already exist. It issues a single `SELECT fill_id FROM fill_exclusions WHERE fill_id IN (SELECT id FROM execution_fills WHERE trade_id = :trade_id)` (or an equivalent join) and returns a `set[uuid.UUID]`. This replaces the per-fill `exists_by_fill_id()` pattern, which would issue N queries for a trade with N fills — an O(N) query amplification that causes unnecessary DB round-trips.
4. For each fill in `fills_to_exclude`: call `FillExclusionRepository.create_exclusion()` with:
   - `fill_id = fill.id`
   - `reason = "USER_DELETED_TRADE"`
   - `replacement_fill_ids = []` (no replacement fills for user-initiated deletion)
   - `excluded_by = user_id` (authenticated user)
   Do NOT call `exists_by_fill_id()` here — the batch query in step 3 already resolved which fills need exclusion records. Calling it again per fill reintroduces the N+1 pattern.
5. Set `trades.is_deleted = true` for this trade via `TradeRepository.update_trade()`. **Do not change `trades.status`** — the status (OPEN, PARTIAL, or CLOSED) is left as-is. The `is_deleted` flag is the authoritative deletion signal; `status` remains accurate for audit purposes.
6. Commit.
7. Return `204 No Content`.

**Critical invariant:** Because `is_deleted = true` trades retain their original `status`, `TradeRepository.get_open_trade_with_lock()` — which queries `status IN ('OPEN', 'PARTIAL')` — **must** also filter `is_deleted = false`. Without this, a soft-deleted OPEN trade would be picked up as the "existing open trade" by a future reconstruction run for the same instrument/account/product_type, causing silent data corruption. This filter is mandatory and is listed in B-16-C.

**Note on `fill_exclusions` as an audit log:** `fill_exclusions` is a permanent append-only table — `UPDATE` and `DELETE` are blocked by DB triggers. Using it here is deliberate: the fills are genuinely excluded from future reconstruction, and the exclusion record serves as a permanent audit trail of the user's deletion action. `replacement_fill_ids = []` is valid — the array column has a server default of `ARRAY[]::uuid[]`.

---

### Task B-16-C — Audit Existing Queries for `is_deleted`

After migration 0015 lands, Bhima must add `is_deleted = false` predicates to every query that surfaces trade rows to users. This is not optional — a soft-deleted trade appearing in analytics or risk metrics is a data correctness bug, not a cosmetic one.

**Specific callsites that must be updated (verified by Mayasura against the source):**

| File | Callsite | Fix |
|------|----------|-----|
| `analytics_repo.py` | `AnalyticsRepository._base_where()` — shared predicate builder used by all 9 analytics metrics | Add `Trade.is_deleted.is_(False)` to the `clauses` list. **One line fixes all 9 metrics.** |
| `risk_service.py` | `_AT_RISK_BY_ACCOUNT` raw SQL template — queries `FROM trades WHERE status IN ('OPEN', 'PARTIAL')` | Add `AND is_deleted = false` to the WHERE clause |
| `risk_service.py` | `_DAILY_LOSS_BY_ACCOUNT` raw SQL template — queries `FROM trades t JOIN trade_pnl` | Add `AND t.is_deleted = false` to the WHERE clause |
| `risk_service.py` | `_AT_RISK_BY_USER` raw SQL template (and any other raw SQL templates in the file) | Add `AND is_deleted = false` / `AND t.is_deleted = false` as appropriate |
| `trade_repo.py` | `TradeRepository.get_open_trade_with_lock()` — queries `status IN ('OPEN', 'PARTIAL')` without `is_deleted` filter | Add `Trade.is_deleted.is_(False)` to the WHERE clause. **This is the highest-priority fix**: without it, a soft-deleted OPEN trade is found as the "existing open trade" by a future reconstruction run, corrupting the next import or manual entry for the same processing unit. |
| `pnl_repo.py` | Any query joining or selecting from `trades` | Add `Trade.is_deleted.is_(False)` or `AND is_deleted = false` |
| `journal_repo.py` | Any query joining or selecting from `trades` | Add `Trade.is_deleted.is_(False)` if trades are queried directly |
| `risk_service.py` | All `_AT_RISK_BY_ACCOUNT` and `_AT_RISK_BY_USER` raw SQL templates — verify no join to `trading_accounts` on status (Dhanvantari R-16-7) | If any join to `trading_accounts` exists in these templates, confirm it does NOT filter `status = 'ACTIVE'`. Orphaned open positions from INACTIVE accounts represent real capital at risk; their omission corrupts daily loss limit enforcement (Layers 2–3 of the risk stack). Document the verification result in the code as a comment. |

**Priority order:** Fix `trade_repo.py → get_open_trade_with_lock()` first (prevents reconstruction corruption), then `analytics_repo.py → _base_where()` (one-line fix for all analytics), then `risk_service.py` raw SQL templates.

---

### Task B-16-D — New Service: `TradeService` + `ReconstructionResult` Extension

**File (new):** `backend/src/tradeforge/application/trade_service.py`

Extract the orchestration logic for `POST /v1/trades` and `POST /v1/trades/{id}/fills` into a `TradeService` class, keeping the router thin. The router handles HTTP concerns (auth, request parsing, response shaping); the service handles domain orchestration.

`TradeService.__init__` dependencies: `TradingAccountService`, `InstrumentRepository`, `FillRepository`, `FillExclusionRepository`, `TradeRepository`, `ReconstructionEngine`, `PnlService`.

Methods:
- `async create_trade(session, user_id, request) -> Trade`
- `async add_fill(session, user_id, trade_id, fill_input) -> Trade`
- `async soft_delete_trade(session, user_id, trade_id) -> None`

**Required change to `ReconstructionResult`:**

**File:** `backend/src/tradeforge/domain/trade/types.py`

Add `affected_trade_id: uuid.UUID | None = None` to the `ReconstructionResult` dataclass:

```python
@dataclass
class ReconstructionResult:
    fills_processed: int = 0
    fills_skipped_no_unprocessed: int = 0
    trades_opened: int = 0
    trades_closed: int = 0
    tax_lots_created: int = 0
    tax_lots_updated: int = 0
    halted_at_fill_id: uuid.UUID | None = None
    error_detail: str | None = None
    affected_trade_id: uuid.UUID | None = None  # ← NEW: trade created or operated on
```

The reconstruction engine must set `result.affected_trade_id` to the trade it opened or continued processing fills against. Specifically:
- When the engine opens a new trade: set `result.affected_trade_id = trade_id` at the point where `result.trades_opened += 1`.
- When the engine resumes an existing OPEN/PARTIAL trade (i.e., `open_trade is not None` at step 4 of `run()`): set `result.affected_trade_id = open_trade.id` before the fill loop begins.
- **`affected_trade_id` is always overwritten at every `trades_opened += 1` event — not only on the first open.** For the D4 multi-cycle case (BUY→SELL→BUY: first trade closes, second trade opens in the same run), the second `trades_opened += 1` must overwrite the field so the 201 response returns the last OPEN trade, not the closed first trade. After `run()` returns, `result.affected_trade_id` always identifies the trade created or last operated on — the one whose ORM row `TradeService` must query and return as `TradeOut`.

This field is used by `TradeService.create_trade()` to identify which `Trade` ORM row to query and return as `TradeOut`. Without it, the service has no reference to the affected trade ID after `run()` returns.

---

**Required addition to `domain/trade/types.py` — `product_type_from_trade_type()` (D6 — Ganesha, 2026-09-07):**

Add alongside `provisional_trade_type()` and `finalize_trade_type()`. Implements the deterministic reverse mapping from stored `trade_type` back to raw broker `product_type`, used by `TradeService.add_fill()` to supply the `product_type` argument to `ReconstructionEngine.run()`:

```python
def product_type_from_trade_type(trade_type: str) -> str:
    """Reverse-map a stored trade_type to the raw broker product_type.

    Used by add_fill() when trade.trade_type must be converted back to the
    product_type expected by ReconstructionEngine.run().
    """
    if trade_type == "MIS":
        return "MIS"
    if trade_type in ("CNC", "CNC_SAME_DAY"):
        return "CNC"
    if trade_type in ("NRML_FUT", "NRML_OPT"):
        return "NRML"
    raise ReconstructionDataError(f"Unknown trade_type: {trade_type!r}")
```

This function is pure and has zero I/O dependencies — it belongs in the domain layer alongside the other type helpers and is independently unit-testable.

---

**Required extension to `PnlRepository.get_planned_risk()` — `trades.planned_risk_amount` fallback (BLK-1 corrected, Bhima inspection 2026-09-07):**

**File:** `backend/src/tradeforge/infrastructure/repositories/pnl_repo.py`

`get_planned_risk()` currently reads only `journal_entries.planned_risk_amount`. For Step 16 manually entered trades, no journal entry exists at the time `backfill_all_closed()` runs, so the method returns NULL and R-multiple is never computed. The method must fall back to `trades.planned_risk_amount` (column already present at `trade_domain.py:122`):

```python
async def get_planned_risk(self, trade_id: uuid.UUID) -> Decimal | None:
    # Primary: journal entry (user's explicit pre-trade risk annotation)
    stmt = select(JournalEntry.planned_risk_amount).where(
        JournalEntry.trade_id == trade_id,
        JournalEntry.deleted_at.is_(None),
    )
    result = await self._db.execute(stmt)
    value = result.scalar_one_or_none()
    if value is not None:
        return Decimal(str(value))
    # Fallback: trades.planned_risk_amount — populated at create_trade time
    # from planned_stop when no journal entry exists (Step 16 manual trades)
    stmt2 = select(Trade.planned_risk_amount).where(Trade.id == trade_id)
    result2 = await self._db.execute(stmt2)
    value2 = result2.scalar_one_or_none()
    return Decimal(str(value2)) if value2 is not None else None
```

This change is additive: existing behavior (journal entry takes priority) is unchanged. Trades with a journal entry continue to use `journal_entries.planned_risk_amount`. Only trades without a journal entry — all Step 16 manually entered trades — fall through to `trades.planned_risk_amount`.

**Session contract — `PnlService` per-request DI (Mayasura A-16-1, confirmed by Bhima inspection 2026-09-07):**

`PnlService.backfill_all_closed()` uses `self._pnl_repo._db` — the `AsyncSession` injected at `PnlRepository` construction time. This means `PnlService` must be constructed with the **same** per-request `AsyncSession` instance as `TradeRepository`, `FillRepository`, and `FillExclusionRepository`. When all services share one session, `trades.planned_risk_amount` flushed in `create_trade()` step 8c is visible to `get_planned_risk()` in step 9 without a separate transaction or commit. Do not construct `PnlService` with a different session or a session from a separate request context.

`TradeService.__init__` must therefore accept a single `AsyncSession` parameter and pass it to all repository constructors, rather than accepting pre-constructed repositories with potentially different sessions.

---

### Backend Tests (Bhima)

All tests follow the existing `AsyncClient` + pytest-asyncio + conftest pattern.

**New file:** `backend/tests/api/test_trades_api.py`

| Test ID | Description |
|---------|-------------|
| B-16-01 | `POST /v1/trades` with valid EQ entry fill creates OPEN trade — returns 201 with `TradeOut`; assert `account_id` is non-None and equals the request `account_id` (AMB-03) |
| B-16-02 | `POST /v1/trades` with entry + exit fills for same day CNC creates CLOSED trade with P&L; assert `account_id` is non-None (AMB-03) |
| B-16-03 | `POST /v1/trades` with entry + exit fills for MIS creates CLOSED trade with P&L; assert `account_id` is non-None (AMB-03) |
| B-16-04 | `POST /v1/trades` with unknown instrument returns 422 `INSTRUMENT_NOT_FOUND` |
| B-16-05 | `POST /v1/trades` with inactive account returns 404 `ACCOUNT_NOT_FOUND` |
| B-16-06 | `POST /v1/trades` with another user's account returns 404 `ACCOUNT_NOT_FOUND` |
| B-16-07 | `POST /v1/trades` with fills in non-chronological order returns 422 `FILLS_NOT_CHRONOLOGICAL` |
| B-16-08 | `POST /v1/trades` with naive (non-tz-aware) `fill_timestamp` returns 422 `FILL_TIMESTAMP_NOT_TZ_AWARE` |
| B-16-09 | `POST /v1/trades` with `instrument_type=FUT` and no `expiry_date` returns 422 `EXPIRY_DATE_REQUIRED` |
| B-16-10 | `POST /v1/trades` with `instrument_type=CE` and no `strike_price` returns 422 `STRIKE_PRICE_REQUIRED` |
| B-16-11 | `POST /v1/trades` with `planned_stop` persists value in returned `TradeOut` |
| B-16-12 | `POST /v1/trades` unauthenticated returns 401 |
| B-16-13 | `POST /v1/trades/{id}/fills` on OPEN trade adds fill and returns updated `TradeOut` |
| B-16-14 | `POST /v1/trades/{id}/fills` on CLOSED trade returns 422 `TRADE_ALREADY_CLOSED` |
| B-16-15 | `POST /v1/trades/{id}/fills` on another user's trade returns 403 `TRADE_NOT_OWNED` |
| B-16-16 | `POST /v1/trades/{id}/fills` with fill timestamp **strictly before** `first_fill_at` returns 422 `FILL_TIMESTAMP_BEFORE_TRADE_OPEN` (AMB-01) |
| B-16-16b | `POST /v1/trades/{id}/fills` with fill timestamp **equal to** `first_fill_at` is accepted — returns 200 with updated `TradeOut` (AMB-01 boundary: simultaneous fills are valid) |
| B-16-17 | `DELETE /v1/trades/{id}` sets `is_deleted = true` — verify via direct DB assertion that `trades.is_deleted = true` for the deleted row, and that `TradeRepository.get_open_trade_with_lock()` returns `None` for that processing unit (no GET endpoint in Step 16; QA-06) |
| B-16-18 | `DELETE /v1/trades/{id}` on already-deleted trade returns 404 |
| B-16-19 | `DELETE /v1/trades/{id}` on another user's trade returns 403 `TRADE_NOT_OWNED` |
| B-16-20 | Soft-deleted trade fills are present in `fill_exclusions` after `DELETE` |
| B-16-21 | `is_deleted` trades do not appear in `GET /v1/analytics/summary` — integration guard |

_(B-16-24 through B-16-34 are in the same file — added by Dhanvantari and Sahadeva reviews. B-16-22 and B-16-23 are unit tests in `test_trade_service.py`, shown separately below. — PLN-01)_

| Test ID | Description |
|---------|-------------|
| B-16-24 | `POST /v1/trades` with `instrument_type=EQ` and `product_type=NRML` returns 422 `INVALID_PRODUCT_TYPE_FOR_INSTRUMENT` (D1) |
| B-16-25 | `POST /v1/trades` with `instrument_type=FUT` and `product_type=CNC` returns 422 `INVALID_PRODUCT_TYPE_FOR_INSTRUMENT` (D1) |
| B-16-26 | `DELETE /v1/trades/{id}` on a CSV-imported trade returns 422 `TRADE_NOT_MANUAL` (D2) |
| B-16-27 | `POST /v1/trades` with fills spanning a close-and-reopen cycle (BUY→SELL→BUY) returns 201 with the second (OPEN) trade; first (CLOSED) trade is persisted in the database with correct P&L (D4) |
| B-16-28 | `POST /v1/trades` with entry + exit fills and `planned_stop` returns 201 where the corresponding `trade_pnl` record has a non-NULL `r_multiple` computed from `planned_stop` — verifies that `planned_stop` is written before `PnlService.backfill_all_closed()` runs (Dhanvantari BLK-1) |
| B-16-34 | `POST /v1/trades` with `instrument_type=CE` and `product_type=CNC` returns 422 `INVALID_PRODUCT_TYPE_FOR_INSTRUMENT` (D1 — Sahadeva QA-08) |
| B-16-35 | `POST /v1/trades/{id}/fills` on an OPEN trade that has `planned_stop` set — after adding a second entry fill at a different price, assert that `trades.planned_risk_amount` in the database reflects `abs(new_average_entry - planned_stop) × new_total_entry_quantity`, not the original value from create time (Dhanvantari BLK-3) |
| B-16-36 | `POST /v1/trades` with a LONG entry fill (BUY side) and `planned_stop` greater than or equal to the fill price returns 422 `PLANNED_STOP_WRONG_SIDE`; mirror case: SHORT entry (SELL side) with `planned_stop` less than or equal to the fill price returns 422 `PLANNED_STOP_WRONG_SIDE` (Dhanvantari REQ-5) |
| B-16-37 | `POST /v1/trades/{id}/fills` on a trade whose account has been set to INACTIVE (direct DB status update in the test fixture after trade creation) — authenticated as the trade owner — returns 200 with updated `TradeOut`, not 403. Verifies that the ownership-only query in `add_fill()` step 2 does not filter on account status, per Dhanvantari REQ-6. (Sahadeva QA-10) |

**New file:** `backend/tests/unit/application/test_trade_service.py`

| Test ID | Description |
|---------|-------------|
| B-16-22 | `TradeService.create_trade()` resolves instrument, inserts fills, calls reconstruction engine, returns Trade |
| B-16-23 | `TradeService.soft_delete_trade()` excludes fills and sets `is_deleted` |

---

## Frontend Scope (Owner: Arjun)

### Task F-16-A — API Client: `src/features/trades/api.ts`

New file. Follows the existing `accountsApi` / `authApi` pattern.

```typescript
export const tradesApi = {
  create: (body: CreateTradeBody) =>
    apiClient.post<Trade>('/v1/trades', body),
  addFill: (tradeId: string, body: AddFillBody) =>
    apiClient.post<Trade>(`/v1/trades/${tradeId}/fills`, body),
  delete: (tradeId: string) =>
    apiClient.delete<void>(`/v1/trades/${tradeId}`),
}
```

**Types:** `src/features/trades/types.ts`

```typescript
export interface FillInput {
  side: 'BUY' | 'SELL'
  quantity: string          // Decimal as string — matches backend Numeric
  price: string
  fill_timestamp: string    // ISO 8601 with offset e.g. "2026-09-06T10:15:00+05:30"
}

export interface InstrumentInput {
  symbol: string
  exchange_segment: 'NSE_EQ' | 'NSE_FO' | 'BSE_EQ'
  instrument_type: 'EQ' | 'FUT' | 'CE' | 'PE'
  expiry_date?: string      // "YYYY-MM-DD"
  strike_price?: string
}

export interface CreateTradeBody {
  account_id: string
  instrument: InstrumentInput
  product_type: 'MIS' | 'CNC' | 'NRML'
  fills: FillInput[]
  planned_stop?: string
  planned_target?: string
}

export interface AddFillBody {
  fill: FillInput
}

export interface Trade {
  id: string
  account_id: string | null
  instrument_id: string
  trade_type: string
  direction: string
  status: 'OPEN' | 'PARTIAL' | 'CLOSED'
  trade_date: string
  first_fill_at: string
  last_fill_at: string | null
  total_entry_quantity: string
  total_exit_quantity: string
  net_position: string
  average_entry: string | null
  average_exit: string | null
  planned_stop: string | null
  planned_target: string | null
  is_deleted: boolean
  created_at: string
  updated_at: string
}
```

---

### Task F-16-B — Add Trade Screen: `src/features/trades/AddTradePage.tsx`

Routed at `/trades/new`. This is a new page, not a modal — the form is complex enough to warrant a dedicated route.

#### Layout

Three sections in a single-column form (or two-column on wider viewports — Arjun's call):

**Section 1 — Instrument**

| Field | Type | Notes |
|-------|------|-------|
| Account | select / account picker | Populated from `useAccount()`. Shows active accounts only. Defaults to `selectedAccount`. |
| Symbol | text input | Uppercase-forced on change. Placeholder: "RELIANCE", "NIFTY24OCTFUT". |
| Exchange Segment | select | NSE\_EQ, NSE\_FO, BSE\_EQ |
| Instrument Type | select | EQ, FUT, CE, PE |
| Expiry Date | date input | Shown only when instrument type is FUT, CE, or PE |
| Strike Price | number input | Shown only when instrument type is CE or PE |
| Product Type | select | MIS (Intraday), CNC (Delivery), NRML (F&O) |

**Section 2 — Fills**

A repeating fill row list. Each fill row contains:

| Field | Type | Notes |
|-------|------|-------|
| Side | select / toggle | BUY or SELL |
| Quantity | number input | Positive integers only for EQ. Decimals for F&O. |
| Price | number input | > 0 |
| Date | date input | Defaults to today in `Asia/Kolkata` |
| Time | time input | HH:MM in `Asia/Kolkata` local time. Combined with date to produce `fill_timestamp` as ISO 8601 with +05:30 offset. |

"Add fill" button appends a new row (up to 20). First row cannot be removed; subsequent rows have a remove button.

Fill rows are ordered by (date, time). The frontend enforces no duplicate timestamps — show an inline warning if two fills share the same timestamp (don't block submission, the backend validates).

**Section 3 — Plan (optional)**

| Field | Type | Notes |
|-------|------|-------|
| Planned Stop | number input | Optional. > 0. |
| Planned Target | number input | Optional. > 0. |

**Submit button:** "Add Trade". Disabled while submission is in-flight.

---

#### Client-Side Validation (before submission)

- Symbol: required, at least 1 char.
- Exchange Segment: required.
- Instrument Type: required.
- For FUT/CE/PE: expiry date required.
- For CE/PE: strike price required.
- Product Type: required.
- At least 1 fill.
- Each fill: side, quantity (> 0), price (> 0), date, and time are all required.
- Fills must be in chronological order (date+time ascending) — show inline error on the offending row.
- `product_type` must be valid for the selected `instrument_type` (enforced inline on `instrument_type` change, not after submission — D1 — Ganesha):
  - `instrument_type = EQ` → disable the `NRML` option in the Product Type select. Show helper text below the select: "NRML is not valid for equity instruments — use MIS (intraday) or CNC (delivery)."
  - `instrument_type = FUT`, `CE`, or `PE` → disable the `CNC` option in the Product Type select. Show helper text: "CNC is not valid for F&O instruments — use MIS (intraday) or NRML (overnight)."
  - Preferred implementation: disable the invalid option (not hide it) so the user can see it exists but is unavailable for the selected instrument type. If the user's current `product_type` selection becomes invalid when `instrument_type` changes, reset the `product_type` field to force an explicit new selection rather than silently submitting an invalid combination.

**On success:** Navigate to `/trades` (the Trade List page — implemented in Step 19). For Step 16, since that page is still a placeholder, show a success toast and navigate to `/trades`. The toast should read "Trade added successfully."

**On error:** Show the API error detail inline below the form (not a toast — the user needs to see it without the form disappearing).

---

### Task F-16-C — Router Update

**File:** `frontend/src/app.tsx`

Replace the `/trades` placeholder with the new AddTradePage route, and add the `/trades/new` route:

```tsx
<Route path="/trades" element={<PlaceholderPage title="Trades" />} />
<Route path="/trades/new" element={<AddTradePage />} />
```

The `/trades` route stays as a placeholder — Step 19 will implement the trade list. The new `/trades/new` route is the Add Trade form.

**Update the AppShell sidebar:** Add an "Add Trade" action — either a button/CTA in the sidebar or a "+" icon next to the "Trades" nav link — that routes to `/trades/new`. Arjun decides the exact placement.

---

### Frontend Tests (Arjun)

All tests follow the existing MSW + Vitest + Testing Library pattern.

**Add MSW handlers to `src/__tests__/msw/handlers.ts`:**

| Handler | Fixture |
|---------|---------|
| `POST /v1/trades` | `CREATE_TRADE_SUCCESS` (returns `TRADE_OPEN_FIXTURE`), `CREATE_TRADE_INSTRUMENT_NOT_FOUND` (422), `CREATE_TRADE_FILLS_NOT_CHRONOLOGICAL` (422) |
| `POST /v1/trades/:id/fills` | `ADD_FILL_SUCCESS` |
| `DELETE /v1/trades/:id` | `DELETE_TRADE_SUCCESS` (204) |

**AddTradePage tests (`src/features/trades/__tests__/AddTradePage.test.tsx`):**

| Test ID | Description |
|---------|-------------|
| F-16-01 | Renders account selector populated from `AccountContext` |
| F-16-02 | Expiry date field is hidden when instrument type is EQ, shown when FUT |
| F-16-03 | Strike price field is hidden when instrument type is EQ, shown when CE |
| F-16-04 | "Add fill" button appends a second fill row |
| F-16-05 | Submit with all valid fields calls `POST /v1/trades` with correct body |
| F-16-06 | Symbol is forced to uppercase on input |
| F-16-07 | Submit with missing symbol shows validation error, no API call |
| F-16-08 | Submit with fills out of chronological order shows inline error |
| F-16-09 | Submit with quantity ≤ 0 shows validation error |
| F-16-10 | Submit button is disabled while request is in flight |
| F-16-11 | On `INSTRUMENT_NOT_FOUND` response, shows inline error message |
| F-16-12 | On success, shows success toast |
| F-16-13 | When instrument type changes to FUT, the CNC option in the Product Type select is disabled and cannot be selected; when instrument type changes to EQ, the NRML option is disabled (D1 — Dhanvantari REQ-1) |

---

## Explicitly NOT in Step 16

| Deferred to | What |
|-------------|------|
| Step 19 | Trade List screen (`/trades`) — the placeholder remains for now |
| Step 17 | CSV import UI |
| Phase 2 | Bulk manual entry |
| Phase 2 | Options leg builder (multi-leg strategy entry as one logical position) |
| Phase 2 | Editing fills on an already-reconstructed trade |
| Phase 2 | Slippage field (`intended_price` — not in schema today) |
| Phase 2 | Instrument search/autocomplete from a symbol master (Phase 1 requires exact symbol+segment entry) |

---

## Order of Work

### Bhima (backend — can start immediately)

1. Check the `execution_fills.import_source` check constraint in `0002_trade_domain_tables.py` — note whether it exists and what it accepts.
2. Write migration `0015_manual_trade_soft_delete.py` — run `alembic upgrade head` locally, verify clean.
3. Audit `analytics_repo.py`, `risk_service.py`, `trade_repo.py`, `pnl_repo.py`, `journal_repo.py` for trade queries — add `is_deleted = false` predicate to each.

   > **Gate — B-16-C must be verified before proceeding to step 4 (Dhanvantari REQ-4):** Before implementing `TradeService`, manually verify that `TradeRepository.get_open_trade_with_lock()` correctly excludes soft-deleted trades: (a) create a trade, (b) set `is_deleted = true` directly in the DB, (c) assert that `get_open_trade_with_lock()` returns `None` for that instrument/account/product_type unit. Do not proceed to `TradeService` or the router until this assertion passes. The DELETE endpoint creates soft-deleted OPEN trades — if this filter is missing, the next reconstruction run for the same processing unit silently treats the deleted trade as an active open position and corrupts the trade history.

4. Create `backend/src/tradeforge/application/trade_service.py` — `TradeService` with `create_trade`, `add_fill`, `soft_delete_trade`.
5. Create `backend/src/tradeforge/api/v1/trades.py` — three routes, thin router calling `TradeService`.
6. Wire `trades` router into `main.py`.
7. Write backend tests B-16-01 through B-16-23.

### Arjun (frontend — steps 1–2 can start in parallel with Bhima)

1. Create `src/features/trades/types.ts` and `src/features/trades/api.ts`.
2. Add MSW fixtures and handlers for trades endpoints.
3. Create `src/features/trades/__tests__/AddTradePage.test.tsx` (write tests first — TDD approach works well for form validation logic).
4. Implement `src/features/trades/AddTradePage.tsx` with all three sections and validation.
5. Update `frontend/src/app.tsx` to add the `/trades/new` route.
6. Update `AppShell.tsx` to add the "Add Trade" navigation action.
7. Write frontend tests F-16-01 through F-16-13. (PLN-02)

**Arjun dependency on Bhima:** All frontend work can be developed against MSW fixtures. No blocker. Integration against the real backend happens once Bhima's routes are live on the branch.

---

## Risk Register (Step 16)

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|-----------|
| R-16-1 | Existing queries on `trades` table (analytics, risk) don't filter `is_deleted` — soft-deleted trades silently appear in analytics | High | Medium | B-16-C is a mandatory audit task. B-16-21 is an integration test that catches this regression specifically. |
| R-16-2 | Reconstruction engine processes manual fills and opens a trade that interferes with an existing import-sourced open trade for the same instrument+account+product_type combo | Medium | High | The reconstruction engine is designed to handle this correctly — it processes ALL unprocessed fills for the processing unit together. Manual fills with `import_source='MANUAL'` are indistinguishable to the engine. The risk is only if the user creates a second trade in the same processing unit when one is already open. The engine will correctly merge the fills into the existing open trade — this is correct behavior (adding a fill to an open trade). The endpoint should document this clearly. |
| R-16-3 | `fill_timestamp` timezone handling — user enters local IST time, frontend sends UTC offset incorrectly | Medium | Medium | Frontend must produce ISO 8601 with explicit +05:30 offset (not UTC `Z`). Backend stores as UTC after converting. Test B-16-01 must verify `first_fill_at` timezone round-trips correctly. |
| R-16-4 | `DELETE /v1/trades/{id}` on a trade that has a journal entry — journal orphaned | Low | Low | Journal entries reference `trade_id` via FK. After soft-delete, `is_deleted = true` but the trade row still exists (soft-delete, not hard delete), so the FK remains valid. The journal entry becomes orphaned in UX terms (no trade to navigate to) but there is no data integrity problem. Step 19 will handle journal visibility filtering. Acceptable for Phase 1 — document in code. |
| R-16-5 | Phase 1 has no instrument symbol master — user must know exact symbol and segment | Accepted | Low | Accepted for Phase 1. Phase 2 will add symbol search/autocomplete from NSE master. Document on the Add Trade screen with a placeholder-text hint (e.g. "RELIANCE", "NIFTY24OCTFUT"). |
| R-16-6 | Manual gap-repair fill (D3) inflates at-risk calculation during the window between adding the manual fill and receiving a corrected CSV. If the corrected CSV arrives without first excluding the manual fill, both fills persist — position is double-counted and at-risk is permanently overstated until the user manually excludes the fill. Phase 1 has no fill-exclusion UI and no user-executable correction path — this is a known shipped limitation. | **Medium** | Medium | Document this limitation explicitly in `TradeService.add_fill()` code. Add a warning tooltip on the Add Fill action: "Added fills cannot be removed from this screen. If you add a fill in error and later receive a corrected broker import, contact support before importing." Flag as Phase 2 blocker: build fill-exclusion UI before enabling automated CSV re-import. Do not enable automated CSV re-import (Step 17 or later) while Phase 1 has no user-facing fill-exclusion path. (Dhanvantari REQ-2 / R-16-6 elevated 2026-09-07) |
| R-16-7 | CSV-imported OPEN trades on INACTIVE accounts have no Phase 1 clearing path — `DELETE` is blocked (D2: not MANUAL), CSV import is blocked (`get_active()`), and the at-risk calculation persists indefinitely with no normal user-facing correction flow. | Low | Medium | Document at `TradingAccountService.get_active()` call sites. During the B-16-C audit, Bhima must explicitly verify that `_AT_RISK_BY_ACCOUNT` and `_AT_RISK_BY_USER` in `risk_service.py` do not join to `trading_accounts` or filter on `trading_accounts.status` — if they do, that filter must be removed (see B-16-C audit table). Orphaned open positions from INACTIVE accounts represent real capital at risk; their omission corrupts daily loss limit enforcement. Phase 2 must include: (a) a fill exclusion UI for individual fills, or (b) a closing-fill workflow that bypasses the account-active check for existing OPEN positions on INACTIVE accounts. Account administrative status does not mean positions were closed. (Dhanvantari REQ-3 / R-16-7 clarified 2026-09-07) |

---

## Gate Criteria

| Gate | Owner | Criteria |
|------|-------|---------|
| Sahadeva QA | Sahadeva | All 46 new tests pass (B-16-01 through B-16-28 + B-16-16b + B-16-34 through B-16-37, F-16-01 through F-16-13); no regressions in Steps 12–15 tests; `is_deleted` predicate verified in analytics integration guard (B-16-21); D1/D2 validation confirmed by B-16-24 through B-16-26 and B-16-34 (PLN-03); D4 multi-cycle behavior confirmed by B-16-27; R-multiple correctness with `planned_stop` confirmed by B-16-28; AMB-01 boundary behaviour confirmed by B-16-16 and B-16-16b; D1 frontend select disabling confirmed by F-16-13; `planned_risk_amount` recomputation on scale-in confirmed by B-16-35 (BLK-3); stop-side direction validation confirmed by B-16-36 (REQ-5); REQ-6 ownership-only auth (deactivated account) confirmed by B-16-37 (QA-10) |
| Nakula CI | Nakula | `pytest` coverage thresholds pass; `npm run coverage` passes thresholds; `tsc --noEmit` clean; ESLint 0 warnings; `alembic upgrade head` applies cleanly from 0014 head |
| Yudhishthira accept | Yudhishthira | Add Trade screen accessible from nav; OPEN trade created from entry fill; CLOSED trade with P&L created from entry+exit fills; soft-delete removes trade from analytics view |

---

## Accepted Known Testing Risks (Sahadeva QA, 2026-09-07)

The following gaps were identified by Sahadeva's final QA review and **explicitly accepted** before implementation begins. They are not implementation blockers. Both must be addressed — by adding the proposed tests — before Step 16 ships to production.

| # | Finding | Description | Decision |
|---|---------|-------------|----------|
| QA-11 | `add_fill()` stop-side consistency guard untested | `add_fill()` step 7b.b validates that `planned_stop` remains on the correct side of `average_entry` after a scale-in moves `average_entry` past the stop. B-16-36 tests this path only in `create_trade()`. The `add_fill()` consistency guard path — where a scale-in drives `average_entry` past the recorded `planned_stop` — has no test. Proposed B-16-38: LONG trade with a BUY scale-in that moves `average_entry` below `planned_stop` → assert 422 `PLANNED_STOP_WRONG_SIDE`. | **Accepted** — scenario requires an extreme scale-in below the stop price; unlikely in normal use. The implementation path is straightforward from the spec. Add B-16-38 before production release. |
| QA-12 | DELETE with all fills pre-excluded untested | AMB-02 specifies that `DELETE /v1/trades/{id}` succeeds (sets `is_deleted = true`) even when `fills_to_exclude` is empty because all fills were already individually excluded. Step 3 of the DELETE sequence handles this case explicitly. No test covers it. Proposed B-16-39: create a trade, individually exclude all fills via fill_exclusions, then `DELETE /v1/trades/{id}` → assert 204 and `is_deleted = true` in the database. | **Accepted** — simple code path, explicitly specified in AMB-02 and documented in the implementation sequence. Add B-16-39 before production release. |

---

## Effort Estimate

| Owner | Work | Estimate |
|-------|------|----------|
| Bhima | Migration 0015 + constraint audit | ~0.15 session |
| Bhima | `is_deleted` audit across existing queries | ~0.15 session |
| Bhima | `TradeService` (create, add_fill, soft_delete) | ~0.3 session |
| Bhima | `trades.py` router — 3 routes | ~0.2 session |
| Bhima | Backend tests B-16-01 through B-16-23 | ~0.4 session |
| Arjun | Types + API client + MSW fixtures | ~0.15 session |
| Arjun | `AddTradePage.tsx` — 3 sections, validation, error states | ~0.5 session |
| Arjun | Router + AppShell updates | ~0.1 session |
| Arjun | Frontend tests F-16-01 through F-16-13 | ~0.3 session |
| **Total** | | **~2.25 sessions** |

This is within the Phase 1 plan estimate of 1–2 sessions, at the high end due to the multi-fill UX complexity and the `is_deleted` audit across existing query code. No scope is at risk.

---

*Krishna — Senior Project Manager*  
*Domain review: Ganesha (Trading Domain Analyst) — 2026-09-06 — D1 through D5 rulings; AMB-01/02/03 rulings applied 2026-09-07; D6 (`product_type_from_trade_type()`) ruling applied 2026-09-07*  
*Risk review: Dhanvantari (Risk Management Engineer) — 2026-09-06 — BLK-1, BLK-2, REQ-1 through REQ-4 applied; BLK-1 data path corrected 2026-09-07 (Bhima inspection); second review 2026-09-07 — BLK-3 (`planned_risk_amount` recomputation in `add_fill()`), REQ-5 (stop-side direction validation), REQ-6 (`add_fill()` ownership-only auth), REQ-7 (engine flush dependency), R-16-6 (likelihood elevated to Medium), R-16-7 (B-16-C audit requirement added) applied*  
*Architecture review: Mayasura (Senior Software Architect) — 2026-09-07 — A-16-1 through A-16-5 applied; A-16-1 session contract confirmed by Bhima inspection*  
*Backend inspection: Bhima (Senior Backend Engineer) — 2026-09-07 — confirmed `PnlRepository.get_planned_risk()` reads `journal_entries.planned_risk_amount`, NOT `trades.planned_stop`; confirmed `backfill_all_closed()` uses per-request DI session; identified `trades.planned_risk_amount` as required fallback path*  
*QA review: Sahadeva — 2026-09-07 — PLN-01/02/03 corrections and B-16-34 applied; QA-01 through QA-07, QA-09 deferred (separate task); final QA review 2026-09-07 — QA-10 (B-16-37, REQ-6 regression guard) added as required test (46 total); QA-11 (add_fill() stop-side guard) and QA-12 (DELETE pre-excluded fills) recorded as accepted known risks*  
*Source: `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`, `backend/src/tradeforge/infrastructure/models/trade_domain.py`, `backend/src/tradeforge/infrastructure/repositories/fill_repo.py`, `backend/src/tradeforge/infrastructure/repositories/pnl_repo.py`, `backend/src/tradeforge/application/pnl_service.py`, `backend/src/tradeforge/application/trade/reconstruction.py`, `backend/src/tradeforge/domain/trade/types.py`, `frontend/src/app.tsx`, `frontend/src/features/accounts/context/AccountContext.tsx`*
