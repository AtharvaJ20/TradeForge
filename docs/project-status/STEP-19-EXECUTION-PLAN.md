# Step 19 — Trade List + Trade Detail Screen

**Document:** `docs/project-status/STEP-19-EXECUTION-PLAN.md`  
**Author:** Krishna (Project Manager)  
**Date:** 2026-09-09  
**Parent plan:** `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`  
**Branch:** `feat/step-19-trade-list-detail` (base: `main` at commit `af57349` — Step 17 merged)  
**Status:** APPROVED FOR IMPLEMENTATION — Mayasura architectural review applied 2026-09-09 (A-19-1 through A-19-7); Ganesha trading domain review applied 2026-09-09 (G-19-1 through G-19-7); Sahadeva QA review applied 2026-09-09 (QA-19-1 through QA-19-9)

---

## Pre-Condition: Step 18 Must Merge First

This branch was created from `main` at commit `af57349` (Step 17 merged). Step 18 (`feat/step-18-dashboard`) is in progress and is NOT yet merged.

**Before any implementation work begins:**

1. Step 18 must be accepted (Sahadeva GO → Nakula CI GREEN → Yudhishthira ACCEPT) and merged to `main`.
2. This branch must be rebased onto updated `main`:
   ```
   git checkout feat/step-19-trade-list-detail
   git rebase main
   ```
3. After rebase, `GET /v1/trades` (implemented in B-18-C) is available as the foundation for the Trade List screen. Step 19 extends it — it does not rebuild it.

Do not start B-19-A or any frontend work until this rebase is confirmed.

---

## Architectural Review Decisions (Mayasura — 2026-09-09)

| ID | Severity | Decision |
|----|----------|----------|
| A-19-1 | Blocking → Resolved | **Ownership check moved into WHERE clause.** The implementation sequence originally queried without `user_id`, then checked ownership post-query and raised 403. B-19-17 correctly required 404 for another user's trade. Fix: include `AND t.user_id = :user_id` in the initial SELECT WHERE clause. Return 404 for all non-owned/non-existent/deleted trades. 403 is never returned — it would confirm the trade ID exists and enable enumeration. Separate step-2 ownership check removed. |
| A-19-2 | Blocking → Resolved | **`instrument` ILIKE uses `startswith(autoescape=True)`.** The original plan used `func.upper(Instrument.symbol).like(instrument.upper() + '%')`. While this uses a bound parameter (preventing SQL injection), `%` and `_` characters within the user's input would still be interpreted as LIKE wildcards. Fix: use `func.upper(Instrument.symbol).startswith(instrument.upper(), autoescape=True)`. D-19-1 updated accordingly. |
| A-19-3 | Required → Resolved | **`toTradeForJournal` moved to `src/features/trades/adapters.ts`.** Functions do not belong in `types.ts`. The inline `import('../journal/types').TradeForJournal` dynamic import in a return type annotation is non-standard TypeScript. Fix: new file `adapters.ts` with a static import. `TradeDetailPage` imports from `adapters.ts`. |
| A-19-4 | Required → Resolved | **`limit` default resolved — Option A selected.** Backend default changed to 25, cap changed to 100 in B-19-A. Aligns API contract with trade list semantics. Dashboard tile passes `limit=10` explicitly — unaffected. OI-19-4 added and immediately resolved. |
| A-19-5 | Required → Resolved | **PARTIAL trade test B-19-14b added.** Tests OPEN and CLOSED only — PARTIAL trade has `pnl: null`, both ENTRY and EXIT fills, `hold_duration_seconds` non-null. Total backend tests: 21. |
| A-19-6 | Informational | **`FillItemOut` quantity/price convention: use `string`.** Consistent with `FillInput` in Step 16 (`trades/types.ts`). `FillItemOut` carries raw fill prices and quantities from `Numeric(18, 4)` — `string` avoids float precision ambiguity and matches the existing project pattern for mutable/display fill data. Updated in F-19-A. |
| A-19-7 | Informational | **Remove unused `_svc` from `list_trades`.** `TradingAccountService` dependency injected but not referenced. Bhima removes it as part of B-19-A since the handler is being modified anyway. |

---

## Trading Domain Review Decisions (Ganesha — 2026-09-09)

| ID | Severity | Decision |
|----|----------|----------|
| G-19-1 | Blocking → Resolved | **Trade type filter "CNC" omits `CNC_SAME_DAY`.** The filter bar showed "All / MIS / CNC / Futures / Options". Selecting "CNC" sends `trade_type=CNC`, which excludes CNC positions that were opened and closed on the same trading day (stored as `CNC_SAME_DAY` by the reconstruction engine). A user filtering by "CNC" would silently miss all same-day-closed delivery positions. Fix: Rename "CNC" to "CNC (Delivery)" and add "CNC (Intraday)" as a fifth option mapping to `trade_type=CNC_SAME_DAY`. Filter options are now: All / MIS / CNC (Delivery) / CNC (Intraday) / Futures / Options. The backend whitelist `{'MIS', 'CNC', 'CNC_SAME_DAY', 'NRML_FUT', 'NRML_OPT'}` already covers `CNC_SAME_DAY` — no backend change needed. Updated in F-19-C. Added test B-19-05b. |
| G-19-2 | Required → Resolved | **`hold_duration_seconds` label must be status-aware.** For PARTIAL trades `hold_duration_seconds` is non-null but represents elapsed time since first fill — not a completed hold duration. The Trade Detail header must: render label "Hold duration" for CLOSED trades; render label "Elapsed" (same value, different label) for PARTIAL trades; render the literal text "Open" for OPEN trades where the value is null. Updated in F-19-D Trade Summary. Added test F-19-13b. |
| G-19-3 | Required → Resolved | **P&L placeholder must distinguish OPEN from PARTIAL.** The original placeholder "P&L not yet available — trade is open." is factually wrong for PARTIAL trades, which have executed exits. Fix: OPEN trade → "No exits yet — P&L will be available when the trade closes." PARTIAL trade → "Partially closed — final P&L will be calculated when all positions are exited." Updated in F-19-D Section 3. Added test F-19-17b. |
| G-19-4 | Required → Resolved | **Quantity display `total_entry_quantity × total_exit_quantity` is misleading.** The `×` symbol implies multiplication, not an entry/exit relationship. Fix: render as "`{total_entry_quantity}` entered / `{total_exit_quantity}` exited". For OPEN trades where `total_exit_quantity` is 0, show "`{total_entry_quantity}` entered". Updated in F-19-D Trade Summary. |
| G-19-5 | Required → Resolved | **`exchange_segment` raw DB values must not be shown to users.** Values `NSE_EQ`, `NSE_FO`, `BSE_EQ` are internal tokens. Map to human-readable labels: `NSE_EQ` → "NSE Equity", `NSE_FO` → "NSE F&O", `BSE_EQ` → "BSE Equity". Define an `EXCHANGE_SEGMENT_LABELS` constant in `src/features/trades/constants.ts` and use it wherever `exchange_segment` is rendered. Updated in F-19-D and added F-19-A3. |
| G-19-6 | Informational | **`instrument_name` not in `TradeDetailOut`.** `Instrument.name` (e.g., "RELIANCE INDUSTRIES LTD") exists in the ORM and the detail query already JOINs `instruments`. Including it lets the Trade Detail header show the full name alongside the symbol. Add `instrument_name: str` to `TradeDetailOut`, select `i.name` in the B-19-B JOIN, and add `instrument_name: string` to the `TradeDetailOut` TypeScript interface. Updated in B-19-B and F-19-A. |
| G-19-7 | Informational | **Hold duration format must handle sub-minute scalp trades.** Format "Xh Ym" renders as "0h 0m" for trades closed within 60 seconds. Add sub-minute case: if `hold_duration_seconds < 60`, display "`{hold_duration_seconds}s`". Updated in F-19-D. |

---

## QA Review Decisions (Sahadeva — 2026-09-09)

| ID | Severity | Decision |
|----|----------|----------|
| QA-19-1 | Required → Resolved | **Wildcard injection guard (A-19-2) has no dedicated test.** The gate criteria specifies "passing `%` or `_` in the instrument param does not widen the match" — but no test ID verifies this property. B-19-10 tests a normal prefix match; it does not confirm that wildcard characters in user input are escaped. A regression from `startswith(autoescape=True)` back to `.like()` would pass B-19-10 silently. Fix: add B-19-21. |
| QA-19-2 | Required → Resolved | **Sort controls have no test coverage.** The Trade List page specifies column header cycling (ASC → DESC → default), mutual exclusion of active sorts, and an active-column arrow indicator — a non-trivial stateful interaction. No frontend test exercises any sort behavior. Fix: add F-19-23. |
| QA-19-3 | Required → Resolved | **`exchange_segment` display mapping (G-19-5) is in gate criteria but has no test.** Gate criteria requires "exchange_segment is never rendered as a raw DB value — always mapped via EXCHANGE_SEGMENT_LABELS" — but no frontend test ID verifies this. A rendering that shows "NSE_FO" instead of "NSE F&O" would pass all 24 existing tests. Fix: add F-19-24. Set `exchange_segment: 'NSE_FO'` in `TRADE_DETAIL_CLOSED` fixture to exercise the mapping. |
| QA-19-4 | Required → Resolved | **Quantity "entered / exited" format (G-19-4) is in gate criteria but has no test.** Gate criteria requires "Quantity shows 'entered / exited' format" — but no frontend test verifies the Trade Summary renders this. The old `×` format would pass all current tests. Fix: add F-19-25. |
| QA-19-5 | Required → Resolved | **`instrument_name` field (G-19-6) has no test — backend or frontend.** The field was added to `TradeDetailOut` and the TypeScript interface, but B-19-12 (which checks all `TradeDetailOut` fields) predates the G-19-6 addition. No backend test verifies `instrument_name` is populated from `instruments.name`, and no frontend test verifies it renders. Fix: add B-19-22 (backend) and F-19-26 (frontend). |
| QA-19-6 | Informational | **No multi-filter combination test.** Each filter param is tested in isolation. No test verifies that all WHERE clauses compose correctly when multiple params are active simultaneously (e.g., `direction=LONG&trade_type=MIS&from_date=2026-09-01&instrument=REL`). Interaction bugs in filter composition cannot be caught by isolated tests. Added B-19-23. |
| QA-19-7 | Informational | **"Previous" button untested.** F-19-03 and F-19-04 cover "Next" behavior (disabled state and offset increment). No test verifies "Previous" is disabled on the first page, or that it decrements offset correctly. Added F-19-27. |
| QA-19-8 | Informational | **Sub-minute hold duration format (G-19-7) not tested.** G-19-7 added `{n}s` rendering for trades under 60 seconds, but no test exercises this code branch. Added F-19-28. Add `TRADE_DETAIL_SCALP` fixture: CLOSED trade with `hold_duration_seconds: 45`. |
| QA-19-9 | Plan correction | **Bhima's Order of Work cites stale test range "B-19-01 through B-19-20".** Reviews added B-19-05b (G-19-1), B-19-14b (A-19-5), and QA-19 additions (B-19-21 through B-19-23). Range is now misleading. Updated to "all backend tests". |

---

## Goal

Let users navigate their complete trade history and inspect each trade in full detail.

Done means: `GET /v1/trades` is extended with additional filter params; `GET /v1/trades/{trade_id}` is live; Trade List screen at `/trades` renders paginated/filtered/sorted history; Trade Detail screen at `/trades/:id` renders all sections (summary, fills timeline, P&L breakdown, journal, attachments, audit history) — Sahadeva GO, Nakula CI GREEN, Yudhishthira ACCEPT.

---

## What "Done" Looks Like

A logged-in user can:

1. **Browse their trade history:** Navigate to the Trades screen and see a paginated list of all trades across all statuses, filterable by date range, direction, trade type, and instrument symbol.
2. **Sort the list:** Click column headers to sort by date (default), net P&L, or R-multiple.
3. **Click through to a trade:** Select any row and see full trade detail: instrument, direction, fill-by-fill execution timeline, P&L breakdown with all 7 charge components, their journal entry (if captured), attachments, and audit history.
4. **Journal directly from the detail page:** The full `JournalPanel` is embedded — users can capture or edit the journal entry without navigating away.

---

## What Already Exists (Do Not Rebuild)

| Concern | What exists | Location |
|---------|-------------|----------|
| **Trade list endpoint** | `GET /v1/trades` — paginated, filtered by `account_id`/`status`, sorted | `backend/src/tradeforge/api/v1/trades.py` (added in Step 18 B-18-C) |
| **`TradeListItemOut` schema** | Already defined in `trades.py` | Same file |
| **`_SORT_COLUMNS` + `_VALID_STATUSES` whitelists** | SQL injection guards already in place | `trades.py:130–137` |
| **`JournalPanel`** | Full journal + attachments + audit history in one composable component | `frontend/src/features/journal/components/JournalPanel.tsx` |
| **`TradeForJournal` type** | Interface defining the props `JournalPanel` needs | `frontend/src/features/journal/types.ts:51–61` |
| **`AttachmentGrid`, `AuditHistoryDrawer`** | Already built; rendered internally by `JournalPanel` | `frontend/src/features/journal/components/` |
| **`AnalyticsFilterBar`** | Filter panel pattern established in Step 12 | `frontend/src/features/analytics/components/AnalyticsFilterBar.tsx` |
| **`AccountContext` / `useAccount()`** | Account selection state | `frontend/src/features/accounts/context/AccountContext.tsx` |
| **`TradePnl` ORM model** | All 7 charge columns + gross/net/r_multiple | `backend/src/tradeforge/infrastructure/models/trade_pnl.py` |
| **`ExecutionFill` ORM model** | All fill fields including `fill_role`, `import_source`, `broker` | `backend/src/tradeforge/infrastructure/models/trade_domain.py:171` |

**Reuse decision:** `JournalPanel` is a self-contained composition root — it owns its own data-fetching for journal entry, attachments, and audit history. The Trade Detail screen passes a `TradeForJournal` object and nothing more. Do NOT replicate journal, attachment, or audit logic in Step 19.

---

## Backend Scope (Owner: Bhima)

### Task B-19-A — Extend `GET /v1/trades` with Filter Params

**File:** `backend/src/tradeforge/api/v1/trades.py`

Add the following optional query parameters to the existing `list_trades` route handler:

| Param | Type | Validation | WHERE clause |
|-------|------|-----------|--------------|
| `direction` | `str \| None` | Whitelist: `{'LONG', 'SHORT'}`. Invalid value → 422 `INVALID_DIRECTION` | `t.direction = :direction` |
| `trade_type` | `str \| None` | Whitelist: `{'MIS', 'CNC', 'CNC_SAME_DAY', 'NRML_FUT', 'NRML_OPT'}`. Invalid → 422 `INVALID_TRADE_TYPE` | `t.trade_type = :trade_type` |
| `from_date` | `date \| None` | FastAPI native date parsing | `t.trade_date >= :from_date` |
| `to_date` | `date \| None` | FastAPI native date parsing | `t.trade_date <= :to_date` |
| `instrument` | `str \| None` | Max 50 chars; uppercased before query | `i.symbol ILIKE :instrument%` (prefix match — use `func.upper(Instrument.symbol).like(instrument.upper() + '%')` — never string interpolation) |

> **D-19-1 (SQL injection + wildcard guard — A-19-2):** `instrument` must never be interpolated into SQL as a raw string. Use `func.upper(Instrument.symbol).startswith(instrument.upper(), autoescape=True)` — this both uses a bound parameter (preventing SQL injection) and escapes any `%` or `_` characters in the user-supplied value (preventing wildcard injection). Do NOT use `.like(instrument.upper() + '%')` — it leaves `%`/`_` in the user input unescaped.

> **D-19-2 (date range ordering):** If both `from_date` and `to_date` are provided and `from_date > to_date`, return 422 with detail `INVALID_DATE_RANGE`.

No new migration. No changes to existing query logic — only additive WHERE clauses.

**Also add `total_count` to support pagination UI:**

Extend the response to a paginated envelope. Change `response_model` from `list[TradeListItemOut]` to `TradeListPageOut`:

```python
class TradeListPageOut(BaseModel):
    items: list[TradeListItemOut]
    total: int     # total matching rows (ignoring limit/offset)
    limit: int
    offset: int
```

Implement with two queries: one `COUNT(*)` on the same filtered statement (without LIMIT/OFFSET), one for the data rows. This allows the frontend to render page counts and "showing X–Y of Z" UI.

**Default and cap (A-19-4 — Option A):** Change the existing backend default from 50 to 25, and cap from 200 to 100:
```python
limit: int = Query(default=25, ge=1, le=100)
```
This aligns the API contract with the trade list use case. The Dashboard tile passes `limit=10` explicitly — this change does not affect it.

**Remove unused dependency (A-19-7):** Remove `_svc: TradingAccountService = Depends(get_account_service)` from `list_trades`. It is injected but never referenced in the handler body.

> **Design note:** The existing `GET /v1/trades` returns `list[TradeListItemOut]`. Changing the response shape is a breaking change for the Dashboard's Recent Trades tile (which calls `GET /v1/trades?limit=10&status=CLOSED`). Arjun must update `dashboard/api.ts` and its MSW handlers to read `.items` from the response. Bhima must confirm `dashboard.py` is unaffected (it does not call this endpoint).

---

### Task B-19-B — New Endpoint: `GET /v1/trades/{trade_id}`

**File:** `backend/src/tradeforge/api/v1/trades.py` (add to existing router)

#### Response schemas

```python
class FillItemOut(BaseModel):
    id: uuid.UUID
    side: str              # BUY / SELL
    quantity: Decimal
    price: Decimal
    fill_role: str | None  # ENTRY / EXIT / None (null for orphan fills)
    fill_timestamp: datetime
    import_source: str     # MANUAL / CSV
    broker: str

class PnlBreakdownOut(BaseModel):
    gross_pnl: Decimal
    net_pnl: Decimal
    total_charges: Decimal
    brokerage: Decimal
    stt: Decimal
    exchange_charges: Decimal
    sebi_charges: Decimal
    stamp_duty: Decimal
    gst: Decimal
    ipft: Decimal
    r_multiple: Decimal | None

class TradeDetailOut(BaseModel):
    # Identity
    id: uuid.UUID
    account_id: uuid.UUID | None
    # Instrument
    symbol: str
    instrument_name: str          # i.name — full name e.g. "RELIANCE INDUSTRIES LTD" (G-19-6)
    exchange_segment: str
    instrument_type: str
    expiry_date: date | None
    strike_price: Decimal | None
    # Trade state
    direction: str
    trade_type: str
    status: str
    trade_date: date
    first_fill_at: datetime
    last_fill_at: datetime | None
    total_entry_quantity: Decimal
    total_exit_quantity: Decimal
    average_entry: Decimal | None
    average_exit: Decimal | None
    planned_stop: Decimal | None
    planned_target: Decimal | None
    planned_risk_amount: Decimal | None
    setup_name: str | None
    hold_duration_seconds: int | None   # None for OPEN trades (last_fill_at is None)
    # Sub-lists
    fills: list[FillItemOut]  # ordered ASC by fill_timestamp
    pnl: PnlBreakdownOut | None  # null for OPEN/PARTIAL trades
```

> **No journal fields in `TradeDetailOut`.** The frontend `JournalPanel` fetches `GET /v1/journal/entry/{trade_id}` independently. Adding journal fields here would duplicate that endpoint's ownership and create a synchronisation risk.

#### Route handler

```python
@router.get("/{trade_id}", response_model=TradeDetailOut)
async def get_trade_detail(
    trade_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> TradeDetailOut:
```

**Implementation sequence:**

1. Query the trade and instrument in one JOIN. Include `user_id` in the WHERE clause — ownership is enforced at query time, not post-query (A-19-1):
   ```sql
   SELECT t.*, i.symbol, i.name AS instrument_name, i.exchange_segment,
          i.instrument_type, i.expiry_date, i.strike_price
   FROM trades t
   JOIN instruments i ON i.id = t.instrument_id
   WHERE t.id = :trade_id
     AND t.user_id = :user_id
     AND t.is_deleted = false
   ```
   If no row (trade does not exist, is deleted, or belongs to another user): return `404 TRADE_NOT_FOUND`. **Do not raise 403.** Returning 403 would confirm the trade ID exists and enable enumeration across users. There is no separate post-query ownership check.
2. Query fills: `SELECT * FROM execution_fills WHERE trade_id = :trade_id ORDER BY fill_timestamp ASC`. A trade with no fills is an edge case (should not exist in production) — return an empty list; do not error.
3. Query P&L: `SELECT * FROM trade_pnl WHERE trade_id = :trade_id`. May return no row for OPEN/PARTIAL trades.
4. Compute `hold_duration_seconds`: if `trade_row.last_fill_at` is not None, compute `int((trade_row.last_fill_at - trade_row.first_fill_at).total_seconds())`. Otherwise `None`.
5. Build and return `TradeDetailOut`.

---

### Backend Tests (Bhima)

**File:** `backend/tests/api/test_trades_api.py` (extend existing file)

#### New filter param tests (B-19-A)

| Test ID | Description |
|---------|-------------|
| B-19-01 | `GET /v1/trades?account_id=<uuid>` returns `TradeListPageOut` with `items`, `total`, `limit`, `offset` fields |
| B-19-02 | `direction=LONG` filter — only LONG trades returned |
| B-19-03 | `direction=SHORT` filter — only SHORT trades returned |
| B-19-04 | `direction=invalid` → 422 `INVALID_DIRECTION` |
| B-19-05 | `trade_type=MIS` filter — only MIS trades returned |
| B-19-05b | `trade_type=CNC_SAME_DAY` filter — only same-day-closed CNC trades returned; a CNC (delivery) trade is excluded (G-19-1) |
| B-19-06 | `trade_type=invalid` → 422 `INVALID_TRADE_TYPE` |
| B-19-07 | `from_date=2026-09-01` — trades before that date excluded |
| B-19-08 | `to_date=2026-09-01` — trades after that date excluded |
| B-19-09 | `from_date > to_date` → 422 `INVALID_DATE_RANGE` |
| B-19-10 | `instrument=RELIANCE` — returns only trades whose symbol starts with `RELIANCE` (case-insensitive: `reliance` also matches) |
| B-19-11 | `total` field reflects count after all filters applied; paging with `offset=5` + `limit=5` returns rows 6–10 and `total` is unchanged |

#### Trade detail tests (B-19-B)

| Test ID | Description |
|---------|-------------|
| B-19-12 | `GET /v1/trades/{id}` → 200 with all `TradeDetailOut` fields; `fills` list non-empty and ordered ASC by `fill_timestamp` |
| B-19-13 | `fills` items include `fill_role` (ENTRY/EXIT/null), `import_source`, `broker` |
| B-19-14 | CLOSED trade: `pnl` is non-null; all 7 charge components present; `r_multiple` correct |
| B-19-14b | PARTIAL trade: `pnl` is null, `status = 'PARTIAL'`, `fills` includes both ENTRY and EXIT fill roles, `hold_duration_seconds` is non-null (A-19-5) |
| B-19-15 | OPEN trade: `pnl` is null; `hold_duration_seconds` is null |
| B-19-16 | `hold_duration_seconds` equals `(last_fill_at - first_fill_at).total_seconds()` for a CLOSED trade |
| B-19-17 | Another user's trade_id → 404 `TRADE_NOT_FOUND` (user_id filter prevents data leak — do not distinguish "not found" from "not owned" in 404 response) |
| B-19-18 | Unauthenticated → 401 |
| B-19-19 | `is_deleted = true` trade → 404 (excluded by `is_deleted = false` filter) |
| B-19-20 | `setup_name` and `planned_risk_amount` fields present in response (null acceptable for trades without these fields set) |
| B-19-21 | `instrument=REL%ANCE` (input contains `%`) — result count is 0 (no symbol literally starts with "REL%ANCE"); confirms `autoescape=True` prevents `%` from acting as a wildcard and matching all "REL*" symbols (A-19-2, QA-19-1) |
| B-19-22 | `GET /v1/trades/{id}` response includes `instrument_name` field populated from `instruments.name` (e.g., "RELIANCE INDUSTRIES LTD" for symbol "RELIANCE") — field is non-null and non-empty (G-19-6, QA-19-5) |
| B-19-23 | Combined filters: `direction=LONG&trade_type=MIS&from_date=2026-09-01&instrument=REL` — returned items satisfy all four WHERE clauses simultaneously; result count is less than results for each filter applied alone (QA-19-6) |

**Total new backend tests: 25** (B-19-14b per A-19-5; B-19-05b per G-19-1; B-19-21 through B-19-23 per QA review).

---

## Frontend Scope (Owner: Arjun)

### Task F-19-A — Types: `src/features/trades/types.ts`

Add to the existing `types.ts` (which already contains `Trade`, `CreateTradeBody`, `FillInput`, `AddFillBody` from Step 16):

```typescript
// --- Read response types (Step 19) ---

export interface TradeListPageOut {
  items: TradeListItemOut[]
  total: number
  limit: number
  offset: number
}

export interface TradeListItemOut {
  id: string
  account_id: string | null
  symbol: string
  instrument_type: string
  direction: string
  status: string
  trade_date: string
  last_fill_at: string | null
  net_pnl: number | null       // P&L displayed only; number acceptable for INR ranges
  r_multiple: number | null
}

// Decimal fields from Numeric(18,4) columns are typed as string to match the
// project convention in FillInput (Step 16) and prevent float precision loss
// on quantities and prices. (A-19-6)
export interface FillItemOut {
  id: string
  side: string
  quantity: string          // Numeric — string per project convention
  price: string             // Numeric — string per project convention
  fill_role: string | null  // ENTRY / EXIT / null
  fill_timestamp: string    // ISO 8601 datetime
  import_source: string     // MANUAL / CSV
  broker: string
}

export interface PnlBreakdownOut {
  gross_pnl: string         // Numeric — string per project convention
  net_pnl: string
  total_charges: string
  brokerage: string
  stt: string
  exchange_charges: string
  sebi_charges: string
  stamp_duty: string
  gst: string
  ipft: string
  r_multiple: string | null
}

export interface TradeDetailOut {
  id: string
  account_id: string | null
  // Instrument
  symbol: string
  instrument_name: string        // full instrument name e.g. "RELIANCE INDUSTRIES LTD" (G-19-6)
  exchange_segment: string
  instrument_type: string
  expiry_date: string | null
  strike_price: string | null   // Numeric — string
  // Trade state
  direction: string
  trade_type: string
  status: string
  trade_date: string
  first_fill_at: string
  last_fill_at: string | null
  total_entry_quantity: string  // Numeric — string
  total_exit_quantity: string
  average_entry: string | null
  average_exit: string | null
  planned_stop: string | null
  planned_target: string | null
  planned_risk_amount: string | null
  setup_name: string | null
  hold_duration_seconds: number | null
  // Sub-lists
  fills: FillItemOut[]
  pnl: PnlBreakdownOut | null
}
```

### Task F-19-A3 — Display Constants: `src/features/trades/constants.ts` *(new file)*

> **G-19-5:** Raw DB values must never be rendered to users verbatim.

```typescript
export const EXCHANGE_SEGMENT_LABELS: Record<string, string> = {
  NSE_EQ: 'NSE Equity',
  NSE_FO: 'NSE F&O',
  BSE_EQ: 'BSE Equity',
}
```

Import and use this map wherever `exchange_segment` is rendered (Trade Detail header, and any future Trade List column that shows it). Fallback for an unknown value: render the raw string prefixed with "?" for visibility during development.

---

### Task F-19-A2 — Adapter: `src/features/trades/adapters.ts` *(new file)*

> **A-19-3:** Cross-feature type conversion functions must not live in `types.ts`. This new file is the correct home for `toTradeForJournal`.

```typescript
import type { TradeForJournal, TradeType } from '../journal/types'
import type { TradeDetailOut } from './types'

/** Maps TradeDetailOut to the TradeForJournal interface required by JournalPanel. */
export function toTradeForJournal(t: TradeDetailOut): TradeForJournal {
  return {
    id: t.id,
    symbol: t.symbol,
    exchange: t.exchange_segment,
    tradeDate: t.trade_date,
    firstFillAt: t.first_fill_at,
    direction: t.direction as 'LONG' | 'SHORT',
    tradeType: t.trade_type as TradeType,
    averageEntry: t.average_entry ?? null,
    totalEntryQuantity: t.total_entry_quantity,
  }
}
```

`TradeDetailPage` imports `toTradeForJournal` from `./adapters`, not from `./types`.

---

### Task F-19-B — API Client: `src/features/trades/api.ts`

Extend the existing trades API client (if one exists from Step 16) or create:

```typescript
export const tradesApi = {
  listTrades: (params: {
    account_id?: string
    status?: string
    direction?: string
    trade_type?: string
    from_date?: string
    to_date?: string
    instrument?: string
    limit?: number
    offset?: number
    sort_by?: string
    sort_dir?: string
  }) => {
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v != null && v !== '') qs.set(k, String(v))
    })
    return apiClient.get<TradeListPageOut>(`/v1/trades?${qs}`)
  },

  getTradeDetail: (tradeId: string) =>
    apiClient.get<TradeDetailOut>(`/v1/trades/${tradeId}`),
}
```

**Update `dashboard/api.ts`:** The Dashboard Recent Trades tile calls `GET /v1/trades`. After B-19-A changes the response to `TradeListPageOut`, update `dashboardApi.listTrades` to read `.items` and update the MSW handler fixture to return the envelope shape.

---

### Task F-19-C — Trade List Page: `src/features/trades/TradeListPage.tsx`

Routed at `/trades`.

#### Layout

**Filter bar (top):**
- Account selector — driven by `AccountContext`. If no account selected, prompt user to select one.
- Status filter: All / Open / Partial / Closed (tab strip or segmented control)
- Direction filter: All / Long / Short
- Trade type filter: All / MIS / CNC (Delivery) / CNC (Intraday) / Futures / Options
  - "CNC (Delivery)" sends `trade_type=CNC`; "CNC (Intraday)" sends `trade_type=CNC_SAME_DAY` (G-19-1)
- Date range: From date / To date (date inputs)
- Instrument search: text input — debounced 300ms; sends `instrument=` param
- "Clear filters" button when any filter is active

> **Do NOT fork the full `AnalyticsFilterBar` component.** The analytics filter bar is tightly coupled to analytics state. Build a standalone `TradeFilterBar` for this page using the same visual design language.

**Table:**

| Column | Source | Notes |
|--------|--------|-------|
| Date | `trade_date` | Format: DD MMM YY |
| Symbol | `symbol` | |
| Type | `instrument_type` chip | EQ / FUT / CE / PE |
| Direction | `direction` chip | Long (green) / Short (red) |
| Status | `status` chip | Open / Partial / Closed |
| Net P&L | `net_pnl` | ₹ with sign, coloured; "—" if null |
| R-multiple | `r_multiple` | 2dp; "—" if null |

Clicking any row navigates to `/trades/<id>`.

**Sort controls:**
- Clicking "Date" column header cycles ASC → DESC → (default DESC).
- Clicking "Net P&L" and "R-multiple" headers also cycle.
- Only one active sort at a time. Active column shows an arrow icon.

**Pagination:**
- "Previous" / "Next" buttons. Show "Showing X–Y of Z trades". Page size: 25 (default).
- `total` from `TradeListPageOut` drives the "of Z" and Next button disabled state.

**Empty state:** "No trades found. Try adjusting your filters." when `items.length === 0`.  
**Loading state:** Skeleton table rows (same width as real rows).

---

### Task F-19-D — Trade Detail Page: `src/features/trades/TradeDetailPage.tsx`

Routed at `/trades/:tradeId`. Called from Trade List row clicks and from the Recent Trades tile on the Dashboard.

#### Layout (four sections — one scroll)

**Section 1 — Trade Summary header**

| Field | Source |
|-------|--------|
| Symbol + instrument type | `symbol`, `instrument_type` |
| Exchange segment | `exchange_segment` mapped via `EXCHANGE_SEGMENT_LABELS` (`NSE_EQ` → "NSE Equity", `NSE_FO` → "NSE F&O", `BSE_EQ` → "BSE Equity") — never render the raw DB value (G-19-5) |
| Direction chip | `direction` |
| Status badge | `status` |
| Trade date | `trade_date` |
| Entry / Exit averages | `average_entry`, `average_exit` (null for OPEN) |
| Quantity | `{total_entry_quantity}` entered / `{total_exit_quantity}` exited. For OPEN trades (`total_exit_quantity` = 0), show `{total_entry_quantity}` entered only (G-19-4) |
| Hold duration / Elapsed | CLOSED → label "Hold duration", format `{d}d {h}h`, `{h}h {m}m`, or `{s}s` for < 60s. PARTIAL → label "Elapsed" (same value, different label — G-19-2). OPEN → "Open" (null value — no label). Sub-minute: `{hold_duration_seconds}s` (G-19-7) |
| Setup | `setup_name` (hidden if null) |
| Planned stop / target | `planned_stop`, `planned_target` (hidden if null) |

**Section 2 — Execution Timeline**

Ordered table of fills from `fills[]` (already ASC by timestamp):

| Column | Source |
|--------|--------|
| Timestamp | `fill_timestamp` — formatted in IST (use `toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })`) |
| Side | `side` chip (BUY green, SELL red) |
| Role | `fill_role` chip (Entry / Exit / —) |
| Quantity | `quantity` |
| Price | `price` (₹) |
| Broker | `broker` |
| Source | `import_source` chip (Manual / CSV) |

Empty state (edge case): "No fill data available."

**Section 3 — P&L Breakdown**

Only rendered when `pnl` is non-null (CLOSED trades).

| Line item | Source |
|-----------|--------|
| Gross P&L | `pnl.gross_pnl` |
| Brokerage | `pnl.brokerage` |
| STT | `pnl.stt` |
| Exchange charges | `pnl.exchange_charges` |
| SEBI charges | `pnl.sebi_charges` |
| Stamp duty | `pnl.stamp_duty` |
| GST | `pnl.gst` |
| IPFT | `pnl.ipft` |
| **Total charges** | `pnl.total_charges` (bold) |
| **Net P&L** | `pnl.net_pnl` (bold, coloured) |
| R-multiple | `pnl.r_multiple` (show "—" if null) |

For OPEN trades: render a muted "No exits yet — P&L will be available when the trade closes." For PARTIAL trades: render "Partially closed — final P&L will be calculated when all positions are exited." (G-19-3 — do not use a single generic placeholder for both states.)

**Section 4 — Journal, Attachments, and Audit History**

```tsx
<JournalPanel trade={toTradeForJournal(trade)} />
```

This single line delivers the full journal entry form, attachments grid, uploader, audit prompt, and audit history drawer — all already built in Step 9. No new logic required.

---

### Task F-19-E — MSW Handlers and Fixtures

Add to `src/__tests__/msw/handlers.ts`:

| Handler | Fixtures |
|---------|---------|
| `GET /v1/trades` | Update existing `TRADES_LIST` to use `TradeListPageOut` envelope shape (`items`, `total`, `limit`, `offset`). Add `TRADES_LIST_FILTERED` (200, fewer items matching a direction/date filter). |
| `GET /v1/trades/:tradeId` | `TRADE_DETAIL_CLOSED` (200, full `TradeDetailOut` with pnl populated, 3 fills — set `exchange_segment: 'NSE_FO'` and `instrument_name: 'RELIANCE INDUSTRIES LTD'` to exercise G-19-5 and G-19-6 tests). `TRADE_DETAIL_OPEN` (200, `pnl: null`, `hold_duration_seconds: null`). `TRADE_DETAIL_PARTIAL` (200, `status: 'PARTIAL'`, `pnl: null`, `hold_duration_seconds` non-null, both ENTRY and EXIT fills — required for F-19-13b and F-19-17b). `TRADE_DETAIL_SCALP` (200, CLOSED, `hold_duration_seconds: 45` — required for F-19-28). `TRADE_DETAIL_NOT_FOUND` (404). |

Update the Dashboard MSW handler for `GET /v1/trades` to match the new envelope shape (required by the Dashboard test regression fix — see Task F-19-B).

---

### Task F-19-F — Router and Navigation Updates

**`frontend/src/app.tsx`:**

```tsx
<Route path="/trades" element={<TradeListPage />} />
<Route path="/trades/:tradeId" element={<TradeDetailPage />} />
```

**`AppShell.tsx`:** Add "Trades" as a nav link in the sidebar, pointing to `/trades`. Arjun decides icon and visual placement consistent with existing nav style (after "Dashboard", before "Journal" or wherever fits the navigation hierarchy).

---

### Frontend Tests (Arjun)

**New file:** `src/features/trades/__tests__/TradeListPage.test.tsx`

| Test ID | Description |
|---------|-------------|
| F-19-01 | Trade List renders table with items from `TRADES_LIST` fixture; each row shows symbol, direction, status, net P&L |
| F-19-02 | `total` field drives "Showing X–Y of Z trades" text |
| F-19-03 | "Next" button is disabled when all items fit on one page (`total <= limit`) |
| F-19-04 | Clicking "Next" increments offset and triggers a new fetch |
| F-19-05 | Status tab "Closed" applies `status=CLOSED` param to the API call |
| F-19-06 | Direction filter "Long" applies `direction=LONG` param |
| F-19-07 | Instrument text input (after 300ms debounce) applies `instrument=` param |
| F-19-08 | "Clear filters" button resets all filter params to their defaults |
| F-19-09 | Empty state "No trades found…" renders when `TRADES_LIST_FILTERED` returns `items: []` |
| F-19-10 | Clicking a row navigates to `/trades/<id>` |
| F-19-11 | Loading state: skeleton rows visible before fixture resolves |

**New file:** `src/features/trades/__tests__/TradeDetailPage.test.tsx`

| Test ID | Description |
|---------|-------------|
| F-19-12 | Trade Detail renders Trade Summary section with symbol, direction chip, status badge, trade date |
| F-19-13 | CLOSED trade: `hold_duration_seconds` renders as formatted duration ("2h 15m"); null (OPEN) renders as "Open" |
| F-19-13b | PARTIAL trade: `hold_duration_seconds` renders the same formatted value but with label "Elapsed" not "Hold duration" (G-19-2) |
| F-19-14 | Execution Timeline renders all fills from `TRADE_DETAIL_CLOSED.fills` in order; each row shows timestamp, side, role, quantity, price |
| F-19-15 | Fill `fill_role` null renders as "—" in the Role column |
| F-19-16 | P&L Breakdown section visible for CLOSED trade; gross P&L, all 7 charge rows, net P&L all render |
| F-19-17 | P&L Breakdown hidden for OPEN trade (`TRADE_DETAIL_OPEN`); "No exits yet — P&L will be available when the trade closes." renders (G-19-3) |
| F-19-17b | PARTIAL trade: P&L Breakdown hidden; "Partially closed — final P&L will be calculated when all positions are exited." renders (G-19-3) — use `TRADE_DETAIL_PARTIAL` fixture (status=PARTIAL, pnl=null) |
| F-19-18 | `JournalPanel` is rendered for both OPEN and CLOSED trades (journal is always available regardless of P&L status) |
| F-19-19 | Trade Detail page shows "Back to trades" link / breadcrumb navigating to `/trades` |
| F-19-20 | `TRADE_DETAIL_NOT_FOUND` fixture: page renders a "Trade not found" error state (not a crash) |
| F-19-21 | Loading state: skeleton renders while trade detail is fetching |

**Regression fix required (F-19-B note):**

| Test ID | Description |
|---------|-------------|
| F-19-22 | `DashboardPage` Recent Trades tile still renders correctly after `GET /v1/trades` response shape change to `TradeListPageOut` (reads `.items` not the root array) |
| F-19-23 | Clicking "Date" column header fires API call with `sort_by=trade_date`; clicking again cycles `sort_dir`; only one column shows an active sort indicator at a time (QA-19-2) |
| F-19-24 | Trade Detail header renders `exchange_segment` as "NSE F&O" (not raw "NSE_FO") using `TRADE_DETAIL_CLOSED` fixture with `exchange_segment: 'NSE_FO'`; no raw DB token string appears in the rendered output (G-19-5, QA-19-3) |
| F-19-25 | Trade Summary Quantity row for CLOSED trade shows "`{n}` entered / `{m}` exited"; for OPEN trade (`total_exit_quantity: '0'`) shows only "`{n}` entered" — the `×` character does not appear (G-19-4, QA-19-4) |
| F-19-26 | Trade Detail header renders `instrument_name` (e.g., "RELIANCE INDUSTRIES LTD") alongside the symbol in the Trade Summary section (G-19-6, QA-19-5) |
| F-19-27 | "Previous" button is disabled when `offset === 0` (first page); clicking "Next" then "Previous" triggers a fetch with `offset=0` and re-renders first-page rows (QA-19-7) |
| F-19-28 | Trade Detail with `hold_duration_seconds: 45` (`TRADE_DETAIL_SCALP` fixture — CLOSED, `hold_duration_seconds < 60`) renders "45s" not "0h 0m" (G-19-7, QA-19-8) |

**Total new frontend tests: 30** (F-19-13b per G-19-2; F-19-17b per G-19-3; F-19-23 through F-19-28 per QA review).

---

## Explicitly NOT in Step 19

| Deferred to | What |
|-------------|------|
| Phase 2 | Execution chart overlaid on price chart (requires market data) |
| Phase 2 | AI analysis panel on trade detail |
| Phase 2 | Market context section (trend, VIX, regime) |
| Phase 2 | Editing fills on an already-reconstructed trade |
| Phase 2 | Trade tagging infrastructure |
| Phase 2 | Global trade search (by symbol, emotion, tag) |
| Phase 2 | Export trade detail to PDF/CSV |
| Phase 2 | Comparison view (multiple trades side by side) |

---

## Open Items for Step 19

| # | Item | Owner | Status | Required by |
|---|------|-------|--------|------------|
| OI-19-1 | **Breaking change to `GET /v1/trades` response shape** — confirm Dashboard `dashboardApi.listTrades` updated to read `.items`. Bhima and Arjun must coordinate. | Bhima + Arjun | ❌ Open | Before B-19-A is implemented |
| OI-19-2 | **Navigation hierarchy**: where does "Trades" sit in the AppShell sidebar relative to Dashboard, Journal, Analytics, Risk, Import, Settings? Arjun decides — product intent is "second item after Dashboard" but Arjun may adjust for visual balance. | Arjun | ❌ Open | F-19-F |
| OI-19-3 | Confirm `JournalPanel` works when embedded in `TradeDetailPage` without a surrounding `JournalPage` context (check for any implicit context dependencies). | Arjun | ❌ Open — verify before F-19-D |
| OI-19-4 | `limit` default — resolved as Option A (backend default changed to 25, cap to 100 in B-19-A). Dashboard tile passes `limit=10` explicitly — unaffected. | Bhima | ✅ Resolved — A-19-4 |

---

## Order of Work

### Bhima (backend)

1. Extend `GET /v1/trades` with the 5 new filter params + `TradeListPageOut` envelope (B-19-A).
2. Add `GET /v1/trades/{trade_id}` with `TradeDetailOut` schema (B-19-B).
3. Write all backend tests (B-19-01 through B-19-23, including B-19-05b and B-19-14b) — 25 total.

### Arjun (frontend — can start steps 1–2 immediately while Bhima works)

1. Add read types to `src/features/trades/types.ts` (F-19-A); create `src/features/trades/adapters.ts` with `toTradeForJournal` (F-19-A2).
2. Extend API client in `src/features/trades/api.ts`; update `dashboard/api.ts` for envelope change (F-19-B).
3. Add/update MSW fixtures for both endpoints and the Dashboard regression (F-19-E).
4. Implement `TradeListPage.tsx` — filter bar, table, sort, pagination (F-19-C).
5. Implement `TradeDetailPage.tsx` — four sections, embed `JournalPanel` (F-19-D).
6. Update `app.tsx` routes and `AppShell.tsx` nav (F-19-F).
7. Write all frontend tests (F-19-01 through F-19-28, including F-19-13b and F-19-17b) — 30 total.

**Arjun's blocker:** Arjun can develop against MSW fixtures from the start. The only step requiring Bhima's backend to be live is integration/E2E testing. No blocker for unit/component tests.

---

## Gate Criteria

| Gate | Owner | Criteria |
|------|-------|---------|
| **Sahadeva QA** | Sahadeva | All 25 new backend tests pass (B-19-01 through B-19-20, B-19-05b, B-19-14b, B-19-21 through B-19-23); all 30 new frontend tests pass (F-19-01 through F-19-28 including F-19-13b, F-19-17b); no regressions in Dashboard, Import, or Manual Trade Entry tests; `instrument=REL%ANCE` returns 0 results — `%` is not treated as a wildcard (A-19-2, B-19-21); `from_date > to_date` → 422 (B-19-09); `GET /v1/trades/{id}` returns 404 (not 403) for another user's trade — never 403 (A-19-1, B-19-17); fills ordered ASC by `fill_timestamp` (B-19-12); `hold_duration_seconds` null for OPEN trades (B-19-15), non-null for PARTIAL trades (B-19-14b); PARTIAL trade `pnl` is null (B-19-14b); Dashboard `DashboardPage` tests still pass after envelope shape change (F-19-22); "Next" button disabled at last page (F-19-03); "Previous" button disabled on first page (F-19-27); `toTradeForJournal` imported from `./adapters` not `./types` (verified by `tsc --noEmit` — Nakula CI gate); trade type filter "CNC (Intraday)" sends `trade_type=CNC_SAME_DAY` (G-19-1, B-19-05b); PARTIAL trade hold duration renders with label "Elapsed" not "Hold duration" (G-19-2, F-19-13b); OPEN and PARTIAL trades show distinct P&L placeholder text (G-19-3, F-19-17, F-19-17b); `exchange_segment` rendered as "NSE Equity" / "NSE F&O" / "BSE Equity" — never as raw DB token (G-19-5, F-19-24); Quantity renders as "X entered / Y exited" — not `×` (G-19-4, F-19-25); `instrument_name` present in response and rendered in Trade Detail header (G-19-6, B-19-22, F-19-26); sub-minute hold duration renders as `{n}s` (G-19-7, F-19-28); sort cycling applies correct `sort_by`/`sort_dir` params (F-19-23) |
| **Nakula CI** | Nakula | `pytest` coverage thresholds pass; `npm run coverage` passes; `tsc --noEmit` clean; ESLint 0 warnings; `GET /v1/trades/{trade_id}` route confirmed in OpenAPI schema; `GET /v1/trades` response shape in OpenAPI schema updated to `TradeListPageOut` |
| **Yudhishthira ACCEPT** | Yudhishthira | Trades screen accessible from nav; filter bar allows filtering by direction, status, date range; pagination "Showing X–Y of Z" renders accurately; clicking a trade opens Trade Detail; Trade Detail shows fill timeline, P&L breakdown (CLOSED) or "open" placeholder; Journal section embedded and functional; switching accounts on Trade List updates the list |

---

## Effort Estimate

| Owner | Work | Estimate |
|-------|------|----------|
| Bhima | Extend `GET /v1/trades` filter params + `TradeListPageOut` | ~0.2 session |
| Bhima | `GET /v1/trades/{id}` detail endpoint | ~0.3 session |
| Bhima | Backend tests B-19-01 through B-19-20 | ~0.5 session |
| Arjun | Types + API client + MSW fixtures | ~0.2 session |
| Arjun | `TradeListPage.tsx` (filter bar + table + pagination) | ~0.5 session |
| Arjun | `TradeDetailPage.tsx` (4 sections + JournalPanel embed) | ~0.4 session |
| Arjun | Router + AppShell + Dashboard regression fix | ~0.1 session |
| Arjun | Frontend tests F-19-01 through F-19-22 | ~0.5 session |
| **Total** | | **~2.7 sessions** |

Within the Phase 1 estimate (plan allowed 1–2 sessions; backend simplicity from reuse brings it close to that range with parallel work).

---

## Pre-Conditions

- `feat/step-19-trade-list-detail` ✅ created from `main` at commit `af57349` (2026-09-09)
- Step 18 ❌ not yet merged — rebase required before implementation
- `GET /v1/trades` (list endpoint) — available after Step 18 merge (B-18-C)
- `JournalPanel` ✅ confirmed at `frontend/src/features/journal/components/JournalPanel.tsx`
- `TradeForJournal` interface ✅ confirmed at `frontend/src/features/journal/types.ts:51–61` — requires: `id`, `symbol`, `exchange`, `tradeDate`, `firstFillAt`, `direction`, `tradeType`, `averageEntry`, `totalEntryQuantity`
- `TradePnl` ORM ✅ confirmed all 7 charge columns at `backend/src/tradeforge/infrastructure/models/trade_pnl.py`
- `ExecutionFill` ORM ✅ confirmed `fill_role`, `import_source`, `broker` fields at `trade_domain.py:171`

---

*Krishna — Senior Project Manager*  
*Architectural review: Mayasura — 2026-09-09 (A-19-1 through A-19-7 applied)*  
*Trading domain review: Ganesha — 2026-09-09 (G-19-1 through G-19-7 applied)*  
*QA review: Sahadeva — 2026-09-09 (QA-19-1 through QA-19-9 applied)*  
*Source: `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`, `backend/src/tradeforge/api/v1/trades.py`, `backend/src/tradeforge/infrastructure/models/trade_pnl.py`, `backend/src/tradeforge/infrastructure/models/trade_domain.py`, `frontend/src/features/journal/components/JournalPanel.tsx`, `frontend/src/features/journal/types.ts`, `frontend/src/features/trades/api.ts`, `frontend/src/features/trades/types.ts`*
