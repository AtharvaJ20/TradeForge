# Step 18 — Dashboard

**Document:** `docs/project-status/STEP-18-EXECUTION-PLAN.md`  
**Author:** Krishna (Project Manager)  
**Date:** 2026-09-08  
**Parent plan:** `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`  
**Branch:** `feat/step-18-dashboard` (base: `main` after Steps 16 + 17 merged)  
**Status:** APPROVED FOR IMPLEMENTATION — Mayasura architectural review applied 2026-09-08; Ganesha trading domain review applied 2026-09-08; Dhanvantari risk review applied 2026-09-08

---

## Architectural Review Decisions (Mayasura — 2026-09-08)

| ID | Severity | Decision |
|----|----------|----------|
| A-18-1 | Ruling | **Option A approved.** Add `starting_capital NUMERIC(14,2) DEFAULT NULL` to `trading_accounts`. Additive migration; nullable; existing accounts unaffected. |
| A-18-2 | Blocking → Resolved | **`emotion` field removed from `RecentJournalItemOut`.** `journal_entries` has no `emotion` column. Replaced with `emotion_before`, `emotion_during`, `emotion_after` (`str | None`). SQL updated accordingly. |
| A-18-3 | Blocking → Resolved | **`capture_moment` field removed from `RecentJournalItemOut`.** `capture_moment` lives on `journal_attachments`, not `journal_entries`. Field removed entirely from the schema and SQL. |
| A-18-4 | Blocking → Resolved | **MTD/WTD SQL rewritten to use `trade_date` (Date column) instead of `last_fill_at` (timestamptz).** `trade_date` is timezone-free and safe for IST calendar filtering. Eliminates the type comparison bug. See G-18-1 below for the follow-on IST anchor fix. |
| A-18-5 | Blocking → Resolved | **`from __future__ import annotations` explicitly prohibited in `dashboard.py`.** |
| A-18-6 | Blocking → Resolved | **B-18-13 corrected.** `status=OPEN` returns only OPEN trades. PARTIAL trades require `status=PARTIAL` explicitly. |
| A-18-7 | Required → Resolved | **All five `starting_capital` wiring locations enumerated in Task B-18-A.** |

---

## Trading Domain Review Decisions (Ganesha — 2026-09-08)

| ID | Severity | Decision |
|----|----------|----------|
| G-18-1 | Blocking → Resolved | **MTD/WTD boundaries and `as_of_date` now use IST calendar date.** A-18-4 fixed the type comparison bug but left `CURRENT_DATE` (UTC server date) as the boundary anchor. Between midnight IST and 05:30 IST, the UTC date lags the IST date by one day — causing WTD to span into the prior week and MTD to span into the prior month on boundary mornings. Fix: replace `CURRENT_DATE` with `(NOW() AT TIME ZONE 'Asia/Kolkata')::date` in all three SQL expressions and in `as_of_date` computation. |
| G-18-2 | Required → Resolved | **`current_equity` renamed to `realized_equity` throughout.** The formula `starting_capital + all_time_net_pnl (CLOSED trades only)` excludes unrealized P&L from OPEN/PARTIAL positions. "Current equity" implies the live account value including open positions; "realized equity" is accurate. Unrealized P&L in equity display is deferred to Phase 2. |
| G-18-3 | Required → Resolved | **Recent Journal `ORDER BY` changed from `je.updated_at DESC` to `t.trade_date DESC, t.last_fill_at DESC, t.id DESC`.** `updated_at` ordering surfaced recently-edited old entries at the top, not the most recent trades with journal entries. Chronological trade ordering matches "last 5 trades with a journal entry" acceptance criterion. B-18-23 test updated. |

---

## Risk Review Decisions (Dhanvantari — 2026-09-08)

| ID | Severity | Decision |
|----|----------|----------|
| D-18-1 | Blocking → Resolved | **`sort_dir` whitelist and implementation note added to B-18-C step 4.** The plan specified a whitelist for `sort_by` but applied no equivalent control to `sort_dir`. A naive implementation would interpolate `sort_dir` as a raw string into the ORDER BY clause — a SQL injection vector. Fix: validate `sort_dir` against `{'asc', 'desc'}`; unknown values default silently to `'desc'`. Apply using SQLAlchemy's `.asc()`/`.desc()` column methods — never string interpolation. Sahadeva gate criterion added. |
| D-18-2 | Required → Resolved | **`status` parameter validation changed from silent filter to 422 `INVALID_STATUS`.** An unrecognised `status` value (e.g. `'closed'` in lowercase, `'DELETED'`) would silently execute a WHERE clause that matches zero rows, returning `200 []` — indistinguishable from a valid empty result. Fix: validate `status` against `{'OPEN', 'PARTIAL', 'CLOSED'}` (case-sensitive); return `422 UNPROCESSABLE_ENTITY` with detail `INVALID_STATUS` for any other value. Test B-18-13b added. |

---

## Goal

Give users a home screen that summarizes their trading state at a glance. A logged-in user opens the app, sees their P&L across periods, performance metrics, streaks, their 10 most recent closed trades, and their 5 most recently journaled trades — all scoped to their active trading account.

Done means: `GET /v1/dashboard/summary`, `GET /v1/trades`, and `GET /v1/journal/recent` are live; the Dashboard screen at `/dashboard` renders all five tiles correctly; switching accounts refreshes all tiles; the default route (`/`) redirects to `/dashboard` — Sahadeva GO, Nakula CI GREEN, Yudhishthira ACCEPT.

---

## What "Done" Looks Like

A logged-in user with a trading account that has trades can:

1. **See account P&L in three time windows:** All-time net P&L, month-to-date (MTD), and week-to-date (WTD — Mon through today) at a glance in the Account Overview tile.
2. **See performance metrics:** Win rate, expectancy (R), and profit factor from the existing analytics summary.
3. **See their current streak:** Current win streak or current loss streak from the existing streaks endpoint.
4. **Scan recent trades:** Last 10 closed trades with symbol, direction, net P&L, R-multiple, and date. Clicking a row navigates to trade detail (Step 19 will build that screen — link is wired now, destination is a stub).
5. **Scan recent journal entries:** Last 5 trades with a journal entry, showing discipline score and emotion fields, ordered by most recent trade date.
6. **Switch accounts:** The account selector (from `AccountContext`) drives all tiles. Selecting a different account refetches everything.

---

## What Already Exists (Do Not Rebuild)

| Concern | What exists | Location |
|---------|-------------|----------|
| **Analytics summary** (win rate, expectancy, profit factor, drawdown, net P&L) | `GET /v1/analytics/summary` with `account_ids` filter | `backend/src/tradeforge/api/v1/analytics.py` |
| **Streaks** (current win/loss streak) | `GET /v1/analytics/streaks` with `account_ids` filter — returns `StreakStatsResponse` with `current_win_streak`, `current_loss_streak` | `analytics.py:450` |
| **Account context** | `AccountContext`, `useAccount()` — selected account in frontend state | `frontend/src/features/accounts/context/AccountContext.tsx` |
| **Analytics card components** | `DrawdownCard`, `ExpectancyCard`, `ProfitFactorCard`, `StreaksCard` — all already built for AnalyticsPage | `frontend/src/features/analytics/components/` |
| **trade_pnl schema** | `net_pnl` and `r_multiple` columns confirmed in ORM | `backend/src/tradeforge/infrastructure/models/trade_pnl.py:35,37` |
| **Journal entry schema** | `discipline_score`, `emotion_before`, `emotion_during`, `emotion_after` fields in `journal_entries` (confirmed via ORM). `capture_moment` is on `journal_attachments`, not `journal_entries`. | `backend/src/tradeforge/infrastructure/models/journal.py` |
| **AppShell nav sidebar** | Navigation sidebar — add Dashboard link | `frontend/src/features/settings/` — see Step 17 AppShell update pattern |

**Reuse decision for Performance tile and Streaks tile:** These tiles call the existing `GET /v1/analytics/summary` and `GET /v1/analytics/streaks` endpoints directly — no new backend needed for them. Arjun reuses or adapts the existing analytics card components. Do not build duplicate endpoints.

---

## Backend Scope (Owner: Bhima)

### Task B-18-A — Migration: Add `starting_capital` to `trading_accounts`

**New Alembic migration** (next in sequence after Step 17's most recent migration):

```python
# Column: starting_capital NUMERIC(14, 2) DEFAULT NULL
op.add_column(
    "trading_accounts",
    sa.Column("starting_capital", sa.Numeric(14, 2), nullable=True),
)
```

No data backfill — existing accounts get `NULL`. No NOT NULL constraint — the field is optional at account creation.

**All five wiring locations must be updated:**

1. **Alembic migration** — `op.add_column` as shown above (new migration file, next in sequence after Step 17).
2. **`TradingAccount` ORM model** (`infrastructure/models/trading_account.py`) — add `starting_capital: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)`.
3. **`TradingAccountRepository.update()`** (`infrastructure/repositories/trading_account_repo.py`) — add `starting_capital: Decimal | None = None` parameter; apply update when provided.
4. **`TradingAccountService.update()`** (`application/trading_account_service.py`) — add `starting_capital: Decimal | None = None` parameter; pass through to repository.
5. **`accounts.py` route handler** — update `UpdateAccountRequest` to add `starting_capital: Decimal | None = Field(default=None, gt=0)`; pass to `svc.update()`. Update `AccountOut` to add `starting_capital: Decimal | None`. Update `CreateAccountRequest` to add `starting_capital: Decimal | None = Field(default=None, gt=0)`.

---

### Task B-18-B — New Router: `GET /v1/dashboard/summary`

**New file:** `backend/src/tradeforge/api/v1/dashboard.py`

> **CRITICAL:** Do NOT add `from __future__ import annotations` to `dashboard.py`. This import breaks FastAPI dependency injection in this project. All other `v1/` routers follow this rule — `analytics.py` and `risk.py` both carry an explicit comment to this effect.

Register under `prefix="/dashboard"`, tag `"dashboard"`. Wire into `main.py`.

#### `DashboardSummaryResponse`

```python
class DashboardSummaryResponse(BaseModel):
    account_id: UUID
    as_of_date: str           # ISO date string in IST, e.g. "2026-09-08"

    # P&L time windows (all computed from trade_pnl.net_pnl, CLOSED trades only)
    all_time_net_pnl: Decimal
    mtd_net_pnl: Decimal      # First calendar day of current IST month → today
    wtd_net_pnl: Decimal      # Most recent Monday (IST) → today

    # Account equity (null if starting_capital is null)
    starting_capital: Decimal | None
    # starting_capital + net P&L from CLOSED trades; excludes unrealized P&L from open/partial positions
    realized_equity: Decimal | None

    # Activity counts
    total_closed_trades: int
    open_trade_count: int
```

#### `GET /v1/dashboard/summary`

**Query params:** `account_id: UUID` (required).

**Implementation sequence:**

1. Verify account ownership: call `TradingAccountService.get(session, user_id, account_id)`. Return `404 ACCOUNT_NOT_FOUND` if the account does not exist or is not owned by the authenticated user. No ACTIVE check — history is always viewable for owned accounts.
2. Compute the IST "today" date once and reuse it for all boundaries:
   ```sql
   -- IST calendar date (avoids CURRENT_DATE UTC lag between midnight IST and 05:30 IST)
   SELECT (NOW() AT TIME ZONE 'Asia/Kolkata')::date AS ist_today
   ```
   Or equivalently in Python: `datetime.datetime.now(tz=pytz.timezone('Asia/Kolkata')).date()` passed as a bind parameter.
3. Compute P&L windows via SQL using `trade_date` (timezone-free `Date` column) and the IST date as the period anchor:
   - `all_time_net_pnl` — `SELECT COALESCE(SUM(tp.net_pnl), 0) FROM trade_pnl tp JOIN trades t ON t.id = tp.trade_id WHERE t.account_id = :account_id AND t.is_deleted = false AND t.status = 'CLOSED'`
   - `mtd_net_pnl` — same base query + `AND t.trade_date >= date_trunc('month', (NOW() AT TIME ZONE 'Asia/Kolkata')::date)::date`
   - `wtd_net_pnl` — same base query + `AND t.trade_date >= date_trunc('week', (NOW() AT TIME ZONE 'Asia/Kolkata')::date)::date` (PostgreSQL `date_trunc('week', ...)` anchors to Monday)
   - `total_closed_trades` — `COUNT(t.id)` with `status = 'CLOSED'`, `is_deleted = false`
   - `open_trade_count` — `COUNT(t.id)` with `status IN ('OPEN', 'PARTIAL')`, `is_deleted = false`
4. Set `as_of_date` to `(NOW() AT TIME ZONE 'Asia/Kolkata')::date` formatted as ISO string (e.g. `"2026-09-08"`). Do not use `CURRENT_DATE` or Python's `datetime.date.today()` — both return the UTC date on Railway.
5. Fetch `starting_capital` from the `trading_accounts` row already loaded in step 1. Compute `realized_equity = starting_capital + all_time_net_pnl` if `starting_capital` is not null; else null.
6. Return `200 DashboardSummaryResponse`.

> **Why `trade_date` with IST anchor:** `trade_date` is a timezone-free `Date` column reflecting the IST trading session date as recorded by the broker. Two independent fixes are applied here: (1) A-18-4 switched from `last_fill_at` (timestamptz) to `trade_date` (Date) to eliminate the type comparison bug; (2) G-18-1 switched the boundary anchor from `CURRENT_DATE` (UTC on Railway) to `(NOW() AT TIME ZONE 'Asia/Kolkata')::date` so the period boundary is the correct IST calendar date. Between midnight IST and 05:30 IST, these two values differ by one day — using the UTC date produces a boundary one full week or month behind the IST boundary.

**Wire into `main.py`:**
```python
from tradeforge.api.v1 import dashboard as dashboard_router
app.include_router(dashboard_router.router, prefix="/v1")
```

---

### Task B-18-C — New Endpoint: `GET /v1/trades` (Paginated Trade List)

**File:** `backend/src/tradeforge/api/v1/trades.py` (add to existing router)

This endpoint is the foundation for both the Recent Trades tile (Step 18, limit=10) and the full Trade List screen (Step 19, full pagination and filtering). Implement the full capability here so Step 19 is frontend-only.

#### `TradeListItemOut`

```python
class TradeListItemOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    symbol: str               # from instruments.symbol
    instrument_type: str      # from instruments.instrument_type
    direction: str
    status: str
    trade_date: date
    last_fill_at: datetime | None
    net_pnl: Decimal | None   # from trade_pnl.net_pnl; null for OPEN trades
    r_multiple: Decimal | None  # from trade_pnl.r_multiple; null if not computed
```

#### `GET /v1/trades`

**Query params:**
- `account_id: UUID` — required. Ownership verified.
- `status: str | None = None` — optional filter: `OPEN`, `PARTIAL`, `CLOSED`. If omitted, all non-deleted trades are returned.
- `limit: int = Query(default=10, ge=1, le=100)` — page size.
- `offset: int = Query(default=0, ge=0)` — pagination offset.
- `sort_by: str = Query(default="last_fill_at")` — accepted values: `last_fill_at`, `trade_date`, `net_pnl`, `r_multiple`. Unknown values default silently to `last_fill_at`.
- `sort_dir: str = Query(default="desc")` — `asc` or `desc`.

**Response:** `200 OK` with `list[TradeListItemOut]` (may be empty).

**Implementation:**

```python
@router.get("", response_model=list[TradeListItemOut])
async def list_trades(
    account_id: UUID = Query(...),
    status: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="last_fill_at"),
    sort_dir: str = Query(default="desc"),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[TradeListItemOut]:
```

1. Verify account ownership (same pattern as B-18-B step 1 — `TradingAccountService.get()`). Return `404 ACCOUNT_NOT_FOUND` if not owned.
2. Build query: `SELECT t.*, i.symbol, i.instrument_type, tp.net_pnl, tp.r_multiple FROM trades t JOIN instruments i ON i.id = t.instrument_id LEFT JOIN trade_pnl tp ON tp.trade_id = t.id WHERE t.account_id = :account_id AND t.is_deleted = false`.
3. Apply `status` filter if provided. `status=OPEN` returns only rows where `t.status = 'OPEN'`; `status=PARTIAL` returns only `'PARTIAL'`; `status=CLOSED` returns only `'CLOSED'`. Each value is an exact, case-sensitive match. If an unrecognised `status` value is supplied (including lowercase variants such as `'closed'`), return `422 UNPROCESSABLE_ENTITY` with detail `INVALID_STATUS` — do not silently execute the filter against the database, as a non-matching status would return an empty list indistinguishable from a valid empty result.
4. Apply sort: whitelist `sort_by` to `{last_fill_at, trade_date, net_pnl, r_multiple}`; unknown values default silently to `last_fill_at`. Validate `sort_dir` against `{'asc', 'desc'}`; unknown values default silently to `'desc'`. Apply direction using SQLAlchemy's `column.asc()` / `column.desc()` methods — never by string interpolation into SQL (injectable). For `net_pnl` and `r_multiple`, sort on `tp.net_pnl` / `tp.r_multiple` (NULLs last in desc, first in asc — default PostgreSQL behaviour for NULLs is acceptable for Phase 1).
5. Apply `LIMIT limit OFFSET offset`.
6. Map rows to `TradeListItemOut`.

> **No separate TradeService method needed.** This is a read-only query — implement the SQL directly in the route handler via the `db` session, consistent with the pattern used in `AnalyticsRepository`. Do not add a new service layer just for this list query.

---

### Task B-18-D — New Endpoint: `GET /v1/journal/recent`

**File:** `backend/src/tradeforge/api/v1/journal.py` (add to existing router)

#### `RecentJournalItemOut`

```python
class RecentJournalItemOut(BaseModel):
    trade_id: UUID
    symbol: str
    instrument_type: str
    trade_date: date
    last_fill_at: datetime | None
    discipline_score: int | None
    emotion_before: str | None
    emotion_during: str | None
    emotion_after: str | None
```

> **Schema rationale (A-18-2, A-18-3):** `journal_entries` has three emotion columns (`emotion_before`, `emotion_during`, `emotion_after`) — not a single `emotion` column. `capture_moment` is on `journal_attachments`, not `journal_entries` — excluded entirely.

#### `GET /v1/journal/recent`

**Query params:**
- `account_id: UUID` — required.
- `limit: int = Query(default=5, ge=1, le=20)` — max 20.

**Implementation:**

1. Verify account ownership (`TradingAccountService.get()`). Return `404 ACCOUNT_NOT_FOUND` if not owned.
2. Query:
   ```sql
   SELECT t.id, i.symbol, i.instrument_type, t.trade_date, t.last_fill_at,
          je.discipline_score, je.emotion_before, je.emotion_during, je.emotion_after
   FROM journal_entries je
   JOIN trades t ON t.id = je.trade_id
   JOIN instruments i ON i.id = t.instrument_id
   WHERE t.account_id = :account_id
     AND t.is_deleted = false
   ORDER BY t.trade_date DESC, t.last_fill_at DESC, t.id DESC
   LIMIT :limit
   ```
3. Return `list[RecentJournalItemOut]` (empty list if no journal entries).

> **Ordering rationale (G-18-3):** Results are ordered by trade chronology (`t.trade_date DESC, t.last_fill_at DESC, t.id DESC`) so the tile always shows the 5 most recently closed trades that have a journal entry. `je.updated_at` ordering was rejected because editing an old journal entry would move it to the top, which contradicts the "last 5 trades with a journal entry" acceptance criterion.

> This endpoint returns only trades that **have a journal entry**. Trades without a journal entry are excluded. The `journal_entries` table has one row per trade (upsert pattern — established in Step 9).

---

### Backend Tests (Bhima)

**New file:** `backend/tests/api/test_dashboard_api.py`

Tests cover `GET /v1/dashboard/summary`, `GET /v1/trades`, and `GET /v1/journal/recent`. Use the existing fixture pattern (authenticated test client, fixture trading accounts and trades).

#### Dashboard Summary (`GET /v1/dashboard/summary`)

| Test ID | Description |
|---------|-------------|
| B-18-01 | `GET /v1/dashboard/summary?account_id=<uuid>` → 200 with `all_time_net_pnl`, `mtd_net_pnl`, `wtd_net_pnl`, `total_closed_trades`, `open_trade_count`, `as_of_date` fields present |
| B-18-02 | Account with trades in prior month: `mtd_net_pnl` excludes them; `all_time_net_pnl` includes them |
| B-18-03 | Account with trades before Monday of current week: `wtd_net_pnl` excludes them; `all_time_net_pnl` includes them |
| B-18-04 | Another user's `account_id` → 404 `ACCOUNT_NOT_FOUND` |
| B-18-05 | Unauthenticated → 401 |
| B-18-06 | Deactivated account owned by user → 200 (ownership-only check; ACTIVE status not required for dashboard) |
| B-18-07 | Account with no trades → 200; `all_time_net_pnl = 0`, `mtd_net_pnl = 0`, `wtd_net_pnl = 0`, `total_closed_trades = 0`, `open_trade_count = 0` |
| B-18-08 | Account with `starting_capital` set → `realized_equity = starting_capital + all_time_net_pnl`; both fields non-null |
| B-18-09 | Account with `starting_capital = NULL` → `starting_capital = null`, `realized_equity = null` |

#### Trade List (`GET /v1/trades`)

| Test ID | Description |
|---------|-------------|
| B-18-10 | `GET /v1/trades?account_id=<uuid>` → 200; returns `TradeListItemOut` list; each item has `id`, `symbol`, `direction`, `status`, `net_pnl` (null for OPEN), `r_multiple` |
| B-18-11 | Default `limit=10` — account with 15 trades returns 10 rows |
| B-18-12 | `status=CLOSED` filter — only CLOSED trades returned |
| B-18-13 | `status=OPEN` filter — only OPEN trades returned (PARTIAL trades are not returned unless `status=PARTIAL` is passed explicitly); `net_pnl = null` for all returned rows |
| B-18-13b | `status=invalid` → 422 `INVALID_STATUS`; `status=closed` (lowercase) → 422 `INVALID_STATUS` |
| B-18-14 | `offset=10` paginates correctly — skips first 10, returns next batch |
| B-18-15 | Default sort is `last_fill_at DESC` — most recent trade is first |
| B-18-16 | Another user's `account_id` → 404 |
| B-18-17 | Unauthenticated → 401 |
| B-18-18 | Account with no trades → 200 empty list |
| B-18-19 | `is_deleted = true` trades are excluded from the list |

#### Recent Journal (`GET /v1/journal/recent`)

| Test ID | Description |
|---------|-------------|
| B-18-20 | `GET /v1/journal/recent?account_id=<uuid>&limit=5` → 200; returns list of `RecentJournalItemOut`; each has `trade_id`, `symbol`, `discipline_score`, `emotion_before`, `emotion_during`, `emotion_after` |
| B-18-21 | Trade without a journal entry is excluded from the result |
| B-18-22 | Limit is respected — account with 10 journaled trades returns ≤ 5 rows at default limit |
| B-18-23 | Results are ordered by `t.trade_date DESC, t.last_fill_at DESC` — the trade with the most recent trade date (not the most recently edited journal entry) appears first |
| B-18-24 | Another user's `account_id` → 404 |
| B-18-25 | Unauthenticated → 401 |
| B-18-26 | Account with no journal entries → 200 empty list |

#### `starting_capital` Account Field Tests (add to `test_accounts_api.py`)

| Test ID | Description |
|---------|-------------|
| B-18-27 | `POST /v1/accounts` with `starting_capital: 500000` → 201; `AccountOut.starting_capital = 500000` |
| B-18-28 | `POST /v1/accounts` without `starting_capital` → 201; `AccountOut.starting_capital = null` |
| B-18-29 | `PATCH /v1/accounts/{id}` with `starting_capital: 750000` → 200; `AccountOut.starting_capital = 750000` |

**Total new backend tests:** 27.

---

## Frontend Scope (Owner: Arjun)

### Task F-18-A — Types: `src/features/dashboard/types.ts`

```typescript
export interface DashboardSummaryOut {
  account_id: string
  as_of_date: string           // IST date, e.g. "2026-09-08"
  all_time_net_pnl: number
  mtd_net_pnl: number
  wtd_net_pnl: number
  starting_capital: number | null
  realized_equity: number | null  // starting_capital + closed-trade net P&L; excludes unrealized P&L
  total_closed_trades: number
  open_trade_count: number
}

export interface TradeListItemOut {
  id: string
  symbol: string
  instrument_type: string
  direction: string
  status: string
  trade_date: string
  last_fill_at: string | null
  net_pnl: number | null
  r_multiple: number | null
}

export interface RecentJournalItemOut {
  trade_id: string
  symbol: string
  instrument_type: string
  trade_date: string
  last_fill_at: string | null
  discipline_score: number | null
  emotion_before: string | null
  emotion_during: string | null
  emotion_after: string | null
}
```

> **G-18-2:** `current_equity` renamed to `realized_equity`. The field comment makes the exclusion of unrealized P&L explicit.

---

### Task F-18-B — API Client: `src/features/dashboard/api.ts`

```typescript
export const dashboardApi = {
  getSummary: (accountId: string) =>
    apiClient.get<DashboardSummaryOut>(`/v1/dashboard/summary?account_id=${accountId}`),

  listTrades: (accountId: string, params?: {
    status?: string; limit?: number; offset?: number; sort_by?: string; sort_dir?: string
  }) => {
    const qs = new URLSearchParams({ account_id: accountId, limit: String(params?.limit ?? 10) })
    if (params?.status) qs.set('status', params.status)
    if (params?.offset) qs.set('offset', String(params.offset))
    if (params?.sort_by) qs.set('sort_by', params.sort_by)
    if (params?.sort_dir) qs.set('sort_dir', params.sort_dir)
    return apiClient.get<TradeListItemOut[]>(`/v1/trades?${qs}`)
  },

  getRecentJournal: (accountId: string, limit = 5) =>
    apiClient.get<RecentJournalItemOut[]>(`/v1/journal/recent?account_id=${accountId}&limit=${limit}`),
}
```

**Analytics and streaks calls** (for the Performance and Streaks tiles) use the **existing analytics API client** — do not duplicate those calls in `dashboard/api.ts`.

---

### Task F-18-C — Dashboard Page: `src/features/dashboard/DashboardPage.tsx`

Routed at `/dashboard`. The default route after login — see Task F-18-E.

#### Layout (five sections)

**Section 1 — Account Overview tile**

| Field | Data source |
|-------|-------------|
| All-time net P&L | `DashboardSummaryOut.all_time_net_pnl` |
| MTD net P&L | `DashboardSummaryOut.mtd_net_pnl` |
| WTD net P&L | `DashboardSummaryOut.wtd_net_pnl` |
| Starting capital | `DashboardSummaryOut.starting_capital` (hidden if null) |
| Realized equity | `DashboardSummaryOut.realized_equity` (hidden if null; display label: "Realized Equity") |
| Open positions | `DashboardSummaryOut.open_trade_count` |

P&L values are formatted with sign (+ / −) and ₹ currency. Green for positive, red for negative, neutral for zero.

**Section 2 — Performance tile**

| Field | Data source |
|-------|-------------|
| Win rate | `GET /v1/analytics/summary?account_ids=<id>` → `outcome.win_rate` |
| Expectancy (R) | Same response → `expectancy.expectancy_r` (show "N/A" if `insufficient_sample`) |
| Profit factor | Same response → `profit_factor.profit_factor` (show "N/A" if null) |

Reuse `ExpectancyCard`, `ProfitFactorCard` layout patterns or compose inline — Arjun decides. Do not copy-paste the analytics page layout verbatim; the dashboard version is a summary strip, not the full analytics panel.

**Section 3 — Streaks tile**

| Field | Data source |
|-------|-------------|
| Current win streak | `GET /v1/analytics/streaks?account_ids=<id>` → `StreakStatsResponse.current_win_streak` |
| Current loss streak | Same → `current_loss_streak` |

Show only the active streak (whichever is non-zero; if both zero, show "No active streak").

**Section 4 — Recent Trades list**

Source: `GET /v1/trades?account_id=<id>&status=CLOSED&limit=10&sort_by=last_fill_at&sort_dir=desc`

Columns: Date (`last_fill_at`), Symbol, Direction chip, Net P&L (₹, coloured), R-multiple ("—" if null).

Clicking a row navigates to `/trades/<trade_id>` (the Trade Detail route — Step 19 will build that screen; for Phase 1 the link can render a placeholder or simply navigate — Arjun decides, but the href must be wired).

Empty state: "No closed trades yet."  
Loading state: skeleton rows.

**Section 5 — Recent Journal entries**

Source: `GET /v1/journal/recent?account_id=<id>&limit=5`

Columns: Date, Symbol, Discipline score (1–10, shown as a number or a small bar — Arjun decides), Emotion chip (show `emotion_before`, `emotion_during`, `emotion_after` — Arjun decides display format, e.g., a single chip for the most prominent or all three).

Clicking a row navigates to `/journal/<trade_id>` (wired for Phase 1; full journal detail is embedded in Trade Detail in Step 19).

Empty state: "No journal entries yet."  
Loading state: skeleton rows.

**Account switching:** All five sections re-fetch when `selectedAccount` changes in `AccountContext`. Use a `useEffect` with `selectedAccount.id` as a dependency in each section's data-fetching hook (or consolidate into a single hook at the page level).

---

### Task F-18-D — MSW Handlers and Fixtures

Add to `src/__tests__/msw/handlers.ts`:

| Handler | Fixtures |
|---------|---------|
| `GET /v1/dashboard/summary` | `DASHBOARD_SUMMARY` (200, all fields populated including `starting_capital` and `realized_equity`), `DASHBOARD_SUMMARY_EMPTY` (200, all P&L = 0, counts = 0, `starting_capital = null`, `realized_equity = null`) |
| `GET /v1/trades` | `TRADES_LIST` (200, 10 TradeListItemOut rows with CLOSED status), `TRADES_LIST_EMPTY` (200, empty list) |
| `GET /v1/journal/recent` | `JOURNAL_RECENT` (200, 5 RecentJournalItemOut rows with `emotion_before`, `emotion_during`, `emotion_after` populated), `JOURNAL_RECENT_EMPTY` (200, empty list) |

`GET /v1/analytics/summary` and `GET /v1/analytics/streaks` MSW handlers already exist from Steps 12–13. Do not redefine them.

---

### Task F-18-E — Router and Navigation Updates

**`frontend/src/app.tsx`:**

Add `/dashboard` route:
```tsx
<Route path="/dashboard" element={<DashboardPage />} />
```

Make `/` redirect to `/dashboard` (logged-in users land on the dashboard):
```tsx
<Route path="/" element={<Navigate to="/dashboard" replace />} />
```

**`AppShell.tsx`:** Add "Dashboard" as the first nav link in the sidebar, pointing to `/dashboard`. Arjun decides icon and visual placement consistent with the existing nav style.

---

### Frontend Tests (Arjun)

**New file:** `src/features/dashboard/__tests__/DashboardPage.test.tsx`

| Test ID | Description |
|---------|-------------|
| F-18-01 | Dashboard renders Account Overview tile with account name from `AccountContext` |
| F-18-02 | Account Overview tile shows all-time, MTD, WTD P&L values from `DASHBOARD_SUMMARY` fixture |
| F-18-03 | Account Overview tile shows `starting_capital` and `realized_equity` when both are non-null; display label reads "Realized Equity" |
| F-18-04 | When `starting_capital` is null, starting capital and realized equity rows are not rendered |
| F-18-05 | Performance tile shows win rate, expectancy, profit factor from analytics summary fixture |
| F-18-06 | Streaks tile shows current win streak and current loss streak |
| F-18-07 | Recent Trades list renders 10 rows with symbol, direction, net P&L, R-multiple |
| F-18-08 | Recent Trades row contains an `<a>` or router `<Link>` with `href` including the trade id |
| F-18-09 | Recent Trades empty state shows "No closed trades yet." when fixture returns empty list |
| F-18-10 | Recent Journal entries renders 5 rows with discipline score and at least one emotion field (`emotion_before`, `emotion_during`, or `emotion_after`) |
| F-18-11 | Recent Journal empty state shows "No journal entries yet." when fixture returns empty list |
| F-18-12 | Changing `selectedAccount` in context triggers re-fetch of dashboard summary (mock `dashboardApi.getSummary` and assert it is called with new account id after context update) |
| F-18-13 | Dashboard route is accessible from the nav sidebar ("Dashboard" link renders and navigates to `/dashboard`) |
| F-18-14 | Navigating to `/` redirects to `/dashboard` |
| F-18-15 | Loading state: skeleton placeholder renders while dashboard summary is fetching (before fixture resolves) |

**Total new frontend tests:** 15.

---

## Explicitly NOT in Step 18

| Deferred to | What |
|-------------|------|
| Step 19 | Trade Detail screen — `/trades/<id>` (the link from Recent Trades is wired but the destination is a stub) |
| Step 19 | Full paginated Trade List screen |
| Phase 2 | Unrealized P&L from open/partial positions included in equity display (realized_equity currently shows closed-trade P&L only) |
| Phase 2 | Daily P&L chart / equity curve |
| Phase 2 | Risk utilization gauge on dashboard |
| Phase 2 | Behavioral pattern summary tile |
| Phase 2 | Notification feed |
| Phase 2 | Market context summary |
| Phase 2 | Deposits / withdrawals effect on equity |
| Phase 2 | Dashboard auto-refresh (poll or WebSocket) |

---

## Open Items for Step 18

| # | Item | Owner | Status | Required by |
|---|------|-------|--------|------------|
| OI-18-1 | **A-18-1: `starting_capital` migration** | Mayasura | ✅ **Resolved — Option A approved 2026-09-08** | Unblocked |
| OI-4 | Yudhishthira: confirm Phase 1 scope of Strategy/Setup (carried from Phase 1 plan) | Yudhishthira | ❌ Open — **Dashboard itself does not show setup breakdowns**, so OI-4 does not block Step 18 implementation. It remains open for the Analytics filter bar (already delivered in Steps 12–13 with hardcoded enum). Recommend closing OI-4 as "hardcoded enum accepted for Phase 1" unless Yudhishthira objects. | Unblocked for Step 18 |

---

## Order of Work

### Bhima (backend)

1. Write migration, update `TradingAccount` ORM, `TradingAccountRepository.update()`, `TradingAccountService.update()`, and `accounts.py` schemas (all five locations from B-18-A).
2. Create `backend/src/tradeforge/api/v1/dashboard.py` with `DashboardSummaryResponse` and `GET /v1/dashboard/summary`.
3. Add `GET /v1/trades` (list endpoint) to `backend/src/tradeforge/api/v1/trades.py`.
4. Add `GET /v1/journal/recent` to `backend/src/tradeforge/api/v1/journal.py`.
5. Wire `dashboard` router into `main.py`.
6. Write backend tests B-18-01 through B-18-29.

### Arjun (frontend — can start steps 1–2 immediately while Bhima works)

1. Create `src/features/dashboard/types.ts`.
2. Create `src/features/dashboard/api.ts`.
3. Add MSW fixtures and handlers (DASHBOARD_SUMMARY, TRADES_LIST, JOURNAL_RECENT variants).
4. Implement `src/features/dashboard/DashboardPage.tsx` — five sections, account-aware, loading + empty states.
5. Update `app.tsx` — add `/dashboard` route, redirect `/` → `/dashboard`.
6. Update `AppShell.tsx` — add "Dashboard" nav link.
7. Write frontend tests F-18-01 through F-18-15.

**Arjun dependency on Bhima:** All frontend work develops against MSW fixtures. No blocker on Bhima — MSW fixtures cover both `starting_capital` populated and null cases. Arjun makes both cases render correctly.

---

## Gate Criteria

| Gate | Owner | Criteria |
|------|-------|---------|
| **Sahadeva QA** | Sahadeva | All new backend tests pass (B-18-01 through B-18-29 including B-18-13b); all new frontend tests pass (F-18-01 through F-18-15); no regressions in Steps 15–17 tests; `GET /v1/trades` list excludes `is_deleted = true` trades (B-18-19); WTD anchors to Monday (B-18-03); deactivated-account dashboard returns 200 (B-18-06); account switching triggers re-fetch (F-18-12); `/` redirect confirmed (F-18-14); Recent Trades row links include trade id (F-18-08); `status=OPEN` returns only OPEN (not PARTIAL) trades (B-18-13); `status=invalid` and `status=closed` (lowercase) each return 422 `INVALID_STATUS` (B-18-13b); `sort_dir` with a value other than `asc`/`desc` returns the same result as `desc` without error; Recent Journal ordered by trade date descending — editing an old journal entry does not reorder the tile (B-18-23); `realized_equity` field present (not `current_equity`) in dashboard summary response (B-18-08) |
| **Nakula CI** | Nakula | `pytest` coverage thresholds pass; `npm run coverage` passes; `tsc --noEmit` clean; ESLint 0 warnings; migration applies cleanly with `alembic upgrade head`; `GET /v1/trades` route confirmed in OpenAPI schema |
| **Yudhishthira ACCEPT** | Yudhishthira | Dashboard accessible from nav; Account Overview shows three P&L periods and displays "Realized Equity" label (not "Current Equity") when `starting_capital` is set; Performance tile shows win rate, expectancy, profit factor; Streaks tile shows current streak; Recent Trades list renders last 10 closed trades with P&L coloured correctly; Recent Journal shows most recently traded instruments (not most recently edited journal entries); switching accounts refreshes all tiles |

---

## Effort Estimate

| Owner | Work | Estimate |
|-------|------|----------|
| Bhima | Migration + all five `starting_capital` wiring locations | ~0.1 session |
| Bhima | `dashboard.py` — summary endpoint with IST date arithmetic | ~0.2 session |
| Bhima | `GET /v1/trades` list endpoint | ~0.2 session |
| Bhima | `GET /v1/journal/recent` endpoint | ~0.15 session |
| Bhima | Wire dashboard router into `main.py` | ~0.05 session |
| Bhima | Backend tests B-18-01 through B-18-29 | ~0.5 session |
| Arjun | Types + API client + MSW fixtures | ~0.2 session |
| Arjun | `DashboardPage.tsx` — five sections + loading/empty states | ~0.5 session |
| Arjun | Router + AppShell updates | ~0.05 session |
| Arjun | Frontend tests F-18-01 through F-18-15 | ~0.35 session |
| **Total** | | **~2.3 sessions** |

Within the Phase 1 estimate. No scope reduction recommended.

---

## Pre-Conditions

- Steps 15, 16, 17 ✅ merged to `main` (confirmed: branch created from updated `main`, commit `af57349`)
- `feat/step-18-dashboard` ✅ created from `main` (2026-09-08)
- `GET /v1/analytics/summary` ✅ confirmed live — Performance tile reuses it
- `GET /v1/analytics/streaks` ✅ confirmed live (`analytics.py:450`) — Streaks tile reuses it
- `trade_pnl.net_pnl` and `trade_pnl.r_multiple` ✅ confirmed in ORM (`trade_pnl.py:35,37`)
- `TradingAccountService.get()` ✅ confirmed at `trading_account_service.py:70` (ownership check only, no ACTIVE filter)
- `analytics_repo._base_where()` ✅ confirmed: always filters `status = 'CLOSED'` — dashboard `all_time_net_pnl` methodology is consistent with analytics `net_pnl`
- **A-18-1 ruling from Mayasura** ✅ Option A approved 2026-09-08 — B-18-A is unblocked

---

*Krishna — Senior Project Manager*  
*Architectural review: Mayasura — 2026-09-08 (A-18-1 through A-18-7 applied)*  
*Trading domain review: Ganesha — 2026-09-08 (G-18-1 through G-18-3 applied)*  
*Source: `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`, `backend/src/tradeforge/api/v1/analytics.py`, `backend/src/tradeforge/api/v1/trades.py`, `backend/src/tradeforge/api/v1/journal.py`, `backend/src/tradeforge/infrastructure/models/trading_account.py`, `backend/src/tradeforge/infrastructure/models/trade_pnl.py`, `backend/src/tradeforge/infrastructure/models/journal.py`, `backend/src/tradeforge/api/v1/risk.py`, `backend/src/tradeforge/infrastructure/repositories/analytics_repo.py`*
