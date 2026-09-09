# Step 19 — Trade List + Trade Detail Screen

**Document:** `docs/project-status/STEP-19-EXECUTION-PLAN.md`  
**Author:** Krishna (Project Manager)  
**Date:** 2026-09-09  
**Parent plan:** `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`  
**Branch:** `feat/step-19-trade-list-detail` (base: `main` at commit `af57349` — Step 17 merged)  
**Status:** READY FOR SPECIALIST REVIEW — awaiting Mayasura architectural review and Ganesha trading domain review before implementation begins

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

> **D-19-1 (SQL injection guard):** `instrument` must never be interpolated into SQL as a raw string. Use SQLAlchemy's `func.upper(Instrument.symbol).like(...)` with a bound parameter. Apply the same principle as the existing `sort_dir` / `sort_by` whitelist pattern.

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

1. Query the trade and instrument in one JOIN:
   ```sql
   SELECT t.*, i.symbol, i.exchange_segment, i.instrument_type,
          i.expiry_date, i.strike_price
   FROM trades t
   JOIN instruments i ON i.id = t.instrument_id
   WHERE t.id = :trade_id AND t.is_deleted = false
   ```
   If no row: return `404 TRADE_NOT_FOUND`.
2. Ownership check: `if trade_row.user_id != user_id: raise 403 TRADE_NOT_OWNED`. Do NOT use `TradingAccountService` — ownership is on `trades.user_id`, not account.
3. Query fills: `SELECT * FROM execution_fills WHERE trade_id = :trade_id ORDER BY fill_timestamp ASC`. A trade with no fills is an edge case (should not exist in production) — return an empty list; do not error.
4. Query P&L: `SELECT * FROM trade_pnl WHERE trade_id = :trade_id`. May return no row for OPEN/PARTIAL trades.
5. Compute `hold_duration_seconds`: if `trade_row.last_fill_at` is not None, compute `int((trade_row.last_fill_at - trade_row.first_fill_at).total_seconds())`. Otherwise `None`.
6. Build and return `TradeDetailOut`.

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
| B-19-15 | OPEN trade: `pnl` is null; `hold_duration_seconds` is null |
| B-19-16 | `hold_duration_seconds` equals `(last_fill_at - first_fill_at).total_seconds()` for a CLOSED trade |
| B-19-17 | Another user's trade_id → 404 `TRADE_NOT_FOUND` (user_id filter prevents data leak — do not distinguish "not found" from "not owned" in 404 response) |
| B-19-18 | Unauthenticated → 401 |
| B-19-19 | `is_deleted = true` trade → 404 (excluded by `is_deleted = false` filter) |
| B-19-20 | `setup_name` and `planned_risk_amount` fields present in response (null acceptable for trades without these fields set) |

**Total new backend tests: 20.**

---

## Frontend Scope (Owner: Arjun)

### Task F-19-A — Types: `src/features/trades/types.ts`

```typescript
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
  net_pnl: number | null
  r_multiple: number | null
}

export interface FillItemOut {
  id: string
  side: string
  quantity: number
  price: number
  fill_role: string | null
  fill_timestamp: string
  import_source: string
  broker: string
}

export interface PnlBreakdownOut {
  gross_pnl: number
  net_pnl: number
  total_charges: number
  brokerage: number
  stt: number
  exchange_charges: number
  sebi_charges: number
  stamp_duty: number
  gst: number
  ipft: number
  r_multiple: number | null
}

export interface TradeDetailOut {
  id: string
  account_id: string | null
  symbol: string
  exchange_segment: string
  instrument_type: string
  expiry_date: string | null
  strike_price: number | null
  direction: string
  trade_type: string
  status: string
  trade_date: string
  first_fill_at: string
  last_fill_at: string | null
  total_entry_quantity: number
  total_exit_quantity: number
  average_entry: number | null
  average_exit: number | null
  planned_stop: number | null
  planned_target: number | null
  planned_risk_amount: number | null
  setup_name: string | null
  hold_duration_seconds: number | null
  fills: FillItemOut[]
  pnl: PnlBreakdownOut | null
}

/** Maps TradeDetailOut to the TradeForJournal interface required by JournalPanel. */
export function toTradeForJournal(t: TradeDetailOut): import('../journal/types').TradeForJournal {
  return {
    id: t.id,
    symbol: t.symbol,
    exchange: t.exchange_segment,
    tradeDate: t.trade_date,
    firstFillAt: t.first_fill_at,
    direction: t.direction as 'LONG' | 'SHORT',
    tradeType: t.trade_type as import('../journal/types').TradeType,
    averageEntry: t.average_entry != null ? String(t.average_entry) : null,
    totalEntryQuantity: String(t.total_entry_quantity),
  }
}
```

> **`toTradeForJournal` adapter:** `JournalPanel` expects `TradeForJournal` (camelCase, string quantities, `exchange` not `exchange_segment`). The adapter function isolates the mapping in one place — the Trade Detail page calls it once and passes the result directly to `<JournalPanel trade={...} />`.

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
- Trade type filter: All / MIS / CNC / Futures / Options
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
| Exchange segment | `exchange_segment` |
| Direction chip | `direction` |
| Status badge | `status` |
| Trade date | `trade_date` |
| Entry / Exit averages | `average_entry`, `average_exit` (null for OPEN) |
| Quantity | `total_entry_quantity` × `total_exit_quantity` |
| Hold duration | Derived from `hold_duration_seconds` — format as "Xh Ym" or "Xd Yh" — show "Open" if null |
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

For OPEN/PARTIAL trades: render a muted "P&L not yet available — trade is open." placeholder where Section 3 would be.

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
| `GET /v1/trades/:tradeId` | `TRADE_DETAIL_CLOSED` (200, full `TradeDetailOut` with pnl populated, 3 fills). `TRADE_DETAIL_OPEN` (200, `pnl: null`, `hold_duration_seconds: null`). `TRADE_DETAIL_NOT_FOUND` (404). |

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
| F-19-13 | `hold_duration_seconds` renders as formatted duration ("2h 15m"); null renders as "Open" |
| F-19-14 | Execution Timeline renders all fills from `TRADE_DETAIL_CLOSED.fills` in order; each row shows timestamp, side, role, quantity, price |
| F-19-15 | Fill `fill_role` null renders as "—" in the Role column |
| F-19-16 | P&L Breakdown section visible for CLOSED trade; gross P&L, all 7 charge rows, net P&L all render |
| F-19-17 | P&L Breakdown hidden for OPEN trade (`TRADE_DETAIL_OPEN`); placeholder "P&L not yet available…" renders |
| F-19-18 | `JournalPanel` is rendered for both OPEN and CLOSED trades (journal is always available regardless of P&L status) |
| F-19-19 | Trade Detail page shows "Back to trades" link / breadcrumb navigating to `/trades` |
| F-19-20 | `TRADE_DETAIL_NOT_FOUND` fixture: page renders a "Trade not found" error state (not a crash) |
| F-19-21 | Loading state: skeleton renders while trade detail is fetching |

**Regression fix required (F-19-B note):**

| Test ID | Description |
|---------|-------------|
| F-19-22 | `DashboardPage` Recent Trades tile still renders correctly after `GET /v1/trades` response shape change to `TradeListPageOut` (reads `.items` not the root array) |

**Total new frontend tests: 22.**

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

---

## Order of Work

### Bhima (backend)

1. Extend `GET /v1/trades` with the 5 new filter params + `TradeListPageOut` envelope (B-19-A).
2. Add `GET /v1/trades/{trade_id}` with `TradeDetailOut` schema (B-19-B).
3. Write backend tests B-19-01 through B-19-20.

### Arjun (frontend — can start steps 1–2 immediately while Bhima works)

1. Define types in `src/features/trades/types.ts` including `toTradeForJournal` adapter (F-19-A).
2. Extend API client in `src/features/trades/api.ts`; update `dashboard/api.ts` for envelope change (F-19-B).
3. Add/update MSW fixtures for both endpoints and the Dashboard regression (F-19-E).
4. Implement `TradeListPage.tsx` — filter bar, table, sort, pagination (F-19-C).
5. Implement `TradeDetailPage.tsx` — four sections, embed `JournalPanel` (F-19-D).
6. Update `app.tsx` routes and `AppShell.tsx` nav (F-19-F).
7. Write frontend tests F-19-01 through F-19-22.

**Arjun's blocker:** Arjun can develop against MSW fixtures from the start. The only step requiring Bhima's backend to be live is integration/E2E testing. No blocker for unit/component tests.

---

## Gate Criteria

| Gate | Owner | Criteria |
|------|-------|---------|
| **Sahadeva QA** | Sahadeva | All new backend tests B-19-01 through B-19-20 pass; all new frontend tests F-19-01 through F-19-22 pass; no regressions in Dashboard, Import, or Manual Trade Entry tests; `instrument` filter uses ILIKE not exact match (B-19-10); `from_date > to_date` → 422 (B-19-09); `GET /v1/trades/{id}` returns 404 (not 403) for another user's trade (B-19-17); fills ordered ASC by `fill_timestamp` (B-19-12); `hold_duration_seconds` null for OPEN trades (B-19-15); Dashboard `DashboardPage` tests still pass after envelope shape change (F-19-22); "Next" button disabled at last page (F-19-03) |
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
*Specialist reviews required: Mayasura (architecture) · Ganesha (trading domain)*  
*Source: `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`, `backend/src/tradeforge/api/v1/trades.py`, `backend/src/tradeforge/infrastructure/models/trade_pnl.py`, `backend/src/tradeforge/infrastructure/models/trade_domain.py`, `frontend/src/features/journal/components/JournalPanel.tsx`, `frontend/src/features/journal/types.ts`*
