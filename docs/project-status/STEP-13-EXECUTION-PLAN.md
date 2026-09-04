# Step 13 — Basic Risk Metrics

**Document:** `docs/project-status/STEP-13-EXECUTION-PLAN.md`  
**Author:** Krishna (Project Manager)  
**Date:** 2026-09-04  
**Parent plan:** `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`  
**Branch base:** `main` (after `feat/step-12-7-rolling-metrics` is merged via PR)  
**Status:** READY TO PLAN — OI-5 Dhanvantari sign-off required before implementation begins

---

## Goal

Deliver the Phase 1 §15 Risk Management requirement without duplicating analytics data already computed in Step 12. A user should be able to open a Risk card and understand: how deep their worst drawdown was, where they are now, how many losses they strung together, how much is at risk today in open trades, and how much they have lost today.

Done means: two new backend endpoints, one new frontend card, all tested, Sahadeva GO, Nakula CI GREEN, Yudhishthira ACCEPT.

---

## What "Done" Looks Like

A user on the analytics page can see a Risk Summary card that shows:

1. **Max Drawdown** — the deepest trough in their equity curve: amount (₹) and percentage.
2. **Current Drawdown** — how far below the current peak they are sitting right now: amount (₹) and percentage.
3. **Longest Loss Streak** — the most consecutive losing trades in their history.
4. **Today's Realized Loss** — the net P&L sum of trades closed today that were losers (₹). Shows ₹0.00 if no losses today.
5. **Total At-Risk (Open Trades)** — the sum of `planned_risk_amount` across all currently open trades for the selected account (₹). Shows "—" when no trades are open or no planned risk was set.

All metrics are scoped to the user's selected account. The card uses the active analytics filter for **historical** metrics (drawdown, streak). Daily risk figures are always "today" and ignore date-range filters.

---

## Opening Obligations

This step closes OI-5 in the open-items table. Before implementation begins:

- **Dhanvantari must review and sign off on this execution plan** — specifically the Phase 1 scope definition and the deduplication decisions. Sign-off is acknowledgment that the spec is correct and complete for Phase 1.
- Step 12.7 PR must be merged to `main`.

---

## Deduplication Rules (Critical — Read Before Implementing)

The following are already computed by `GET /v1/analytics/summary`. **Do not re-implement the underlying SQL.** Step 13 pulls from the existing analytics service, not raw DB.

| Metric | Already in analytics summary | Step 13 action |
|--------|------------------------------|----------------|
| `max_drawdown_inr` | ✅ `drawdown.max_drawdown_inr` | Surface in risk endpoint — source from analytics service |
| `max_drawdown_pct` | ✅ `drawdown.max_drawdown_pct` | Surface in risk endpoint — source from analytics service |
| `current_drawdown_inr` | ✅ `drawdown.current_drawdown_pct` (as INR: add INR field) | Surface in risk endpoint |
| `current_drawdown_pct` | ✅ `drawdown.current_drawdown_pct` | Surface in risk endpoint — source from analytics service |
| `max_loss_streak` | ✅ `streaks.max_loss_streak` | Surface in risk endpoint — source from analytics service |
| R-multiple distribution | ✅ `GET /v1/analytics/r-distribution` (Step 12.6) | Not in Step 13 |

The following are **new** and require new SQL:

| Metric | Source | Step 13 action |
|--------|--------|----------------|
| `daily_loss_inr` | Sum `net_pnl` where `trade_date = today` AND `net_pnl < 0` | New query in risk service |
| `total_at_risk_inr` | Sum `planned_risk_amount` on trades where `status = 'OPEN'` and `trade_date = today` (account-scoped) | New query in risk service |
| `open_trade_count` | Count of open trades for account today | New query in risk service |

---

## Scope

### Backend (Bhima)

#### New router: `backend/src/tradeforge/api/v1/risk.py`

Registers under `/v1/risk`. No new migration required — all data is in existing tables.

---

##### `GET /v1/risk/summary`

Returns the full Phase 1 risk picture for one account. Accepts the same query params as analytics filter for `account_id`, `direction`, `from_date`, `to_date` (the historical metrics respect these). Daily metrics always use today's date.

**Response schema (`RiskSummaryResponse`):**

```python
class RiskSummaryResponse(BaseModel):
    # Historical metrics — sourced from analytics service (no new SQL)
    max_drawdown_inr: Decimal | None        # None when < 2 closed trades
    max_drawdown_pct: Decimal | None        # None when < 2 closed trades
    current_drawdown_inr: Decimal | None    # None when equity at all-time high
    current_drawdown_pct: Decimal | None    # None when equity at all-time high
    max_loss_streak: int                    # 0 when no losses

    # Daily metrics — always today, account-scoped (new SQL)
    daily_loss_inr: Decimal                 # 0.00 when no losing trades today
    daily_loss_trade_count: int             # 0 when no losing trades today
    total_at_risk_inr: Decimal | None       # None when no open trades with planned_risk
    open_trade_count: int                   # 0 when no open trades today

    trade_date: str                         # ISO date string: today in IST
```

**Implementation note (Bhima):** Call `AnalyticsService.compute_summary(filter)` to get drawdown and streak stats. Extract `drawdown.max_drawdown_inr`, `drawdown.max_drawdown_pct`, `drawdown.current_drawdown_pct`, `streaks.max_loss_streak`. Compute `current_drawdown_inr` from `current_drawdown_pct × peak_equity` (or expose `current_drawdown_inr` directly in the drawdown dataclass if not already there — check `AnalyticsService` before deciding). Then run two new queries for the daily figures.

This is an intentional Phase 1 coupling — `RiskService` calls `AnalyticsService`. Document it; refactor to shared query utilities in Phase 2.

---

##### `GET /v1/risk/daily-summary`

Lightweight endpoint: today's open-trade risk only. No historical metrics. Useful for a quick "am I overexposed today?" check.

**Response schema (`DailyRiskResponse`):**

```python
class DailyRiskResponse(BaseModel):
    trade_date: str                         # ISO date in IST
    open_trade_count: int
    total_at_risk_inr: Decimal | None       # None when no planned_risk_amount set
    daily_loss_inr: Decimal                 # 0.00 when no losses today
    daily_loss_trade_count: int
```

**Query: total_at_risk_inr**

```sql
SELECT
    COUNT(*)                            AS open_trade_count,
    COALESCE(SUM(planned_risk_amount), NULL) AS total_at_risk_inr
FROM trades
WHERE account_id = :account_id
  AND status = 'OPEN'
  AND trade_date = CURRENT_DATE AT TIME ZONE 'Asia/Kolkata'
  AND planned_risk_amount IS NOT NULL
```

Note: `total_at_risk_inr` is `None` (not 0) when no open trades have `planned_risk_amount` set — the user has open trades but didn't record their risk. This must be communicated to the frontend as "—" (data unavailable), not "₹0".

**Query: daily_loss_inr**

```sql
SELECT
    COALESCE(SUM(tp.net_pnl), 0)       AS daily_loss_inr,
    COUNT(*)                            AS daily_loss_trade_count
FROM trades t
JOIN trade_pnl tp ON tp.trade_id = t.id
WHERE t.account_id = :account_id
  AND t.trade_date = CURRENT_DATE AT TIME ZONE 'Asia/Kolkata'
  AND tp.net_pnl < 0
```

---

#### New domain types: `backend/src/tradeforge/domain/risk/types.py`

```python
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class DailyRiskResult:
    trade_date: str
    open_trade_count: int
    total_at_risk_inr: Decimal | None
    daily_loss_inr: Decimal
    daily_loss_trade_count: int

@dataclass
class RiskSummaryResult:
    max_drawdown_inr: Decimal | None
    max_drawdown_pct: Decimal | None
    current_drawdown_inr: Decimal | None
    current_drawdown_pct: Decimal | None
    max_loss_streak: int
    daily_loss_inr: Decimal
    daily_loss_trade_count: int
    total_at_risk_inr: Decimal | None
    open_trade_count: int
    trade_date: str
```

#### New application service: `backend/src/tradeforge/application/risk_service.py`

```python
class RiskService:
    def __init__(self, db: AsyncSession, analytics_svc: AnalyticsService) -> None: ...
    async def get_daily_risk(self, account_id: UUID) -> DailyRiskResult: ...
    async def get_summary(self, filter: AnalyticsFilter) -> RiskSummaryResult: ...
```

#### Router registration

Add to `backend/src/tradeforge/api/v1/__init__.py`:
```python
from .risk import router as risk_router
app.include_router(risk_router, prefix="/v1/risk", tags=["risk"])
```

---

#### Tests (Bhima)

**Unit tests** (`tests/unit/application/test_risk_service.py`):

| Test ID | Description |
|---------|-------------|
| U-13-01 | `get_daily_risk` returns correct at-risk total when 2 open trades have `planned_risk_amount` |
| U-13-02 | `get_daily_risk` returns `total_at_risk_inr=None` when no open trades have `planned_risk_amount` |
| U-13-03 | `get_daily_risk` returns `daily_loss_inr=0.00` when no closed losing trades today |
| U-13-04 | `get_summary` aggregates drawdown and streak from analytics service correctly |
| U-13-05 | `get_summary` returns `max_drawdown_inr=None` when analytics returns no drawdown data |

**Integration tests** (`tests/integration/test_risk_api.py`):

| Test ID | Description |
|---------|-------------|
| I-13-01 | `GET /v1/risk/daily-summary` returns 200 with correct totals for account with 1 open trade |
| I-13-02 | `GET /v1/risk/daily-summary` returns `total_at_risk_inr=null` when open trade has no `planned_risk_amount` |
| I-13-03 | `GET /v1/risk/summary` returns 200 with all fields present |
| I-13-04 | `GET /v1/risk/summary` returns 401 for unauthenticated request |
| I-13-05 | `GET /v1/risk/daily-summary` scopes to correct account — trade from another account does not appear |

---

### Frontend (Arjun)

#### New hook: `frontend/src/features/analytics/hooks/useRiskSummary.ts`

Fetches from `GET /v1/risk/summary`. Accepts `AnalyticsFilterParams`. Returns `{ data, isLoading, isError }`.

Zod schema for response:
```typescript
const RiskSummarySchema = z.object({
  max_drawdown_inr: decimalString.nullable(),
  max_drawdown_pct: decimalString.nullable(),
  current_drawdown_inr: decimalString.nullable(),
  current_drawdown_pct: decimalString.nullable(),
  max_loss_streak: z.number().int(),
  daily_loss_inr: decimalString,
  daily_loss_trade_count: z.number().int(),
  total_at_risk_inr: decimalString.nullable(),
  open_trade_count: z.number().int(),
  trade_date: z.string(),
})
```

Use `decimalString` (`z.string()`) consistent with all other analytics hooks.

#### New component: `frontend/src/features/analytics/components/RiskSummaryCard.tsx`

- `section` with `aria-labelledby` pointing to heading "Risk Summary"
- Six stat cells laid out in a 2×3 or 3×2 grid:
  - **Max Drawdown** — `max_drawdown_pct` formatted as `−X.XX%` (always negative or "—")
  - **Current Drawdown** — `current_drawdown_pct` formatted as `−X.XX%` or "—" if at peak
  - **Longest Loss Streak** — `max_loss_streak` as `N trades`
  - **Today's Loss** — `daily_loss_inr` formatted as `−₹X,XXX.XX` (red) or `₹0.00` (neutral)
  - **At Risk (Open)** — `total_at_risk_inr` formatted as `₹X,XXX.XX` or "—" if null
  - **Open Trades** — `open_trade_count` as plain integer
- Loading skeleton: `role="status"`, `aria-label="Loading risk summary"`
- Error state: text "Failed to load risk summary"
- Insufficient data: when `max_drawdown_inr === null`, show "—" for drawdown cells without crashing

#### Wire into `app.tsx`

Add `<RiskSummaryCard params={filterParams} />` after `DimensionBreakdownCard` (before KellyCard).

---

#### Tests (Arjun)

**Component tests** (`frontend/src/features/analytics/components/__tests__/RiskSummaryCard.test.tsx`):

Use hook mock pattern (`vi.mock` + `vi.mocked().mockReturnValue`).

| Test ID | Description |
|---------|-------------|
| F-13-01 | Renders section landmark and heading |
| F-13-02 | Renders max drawdown pct formatted as `−8.50%` |
| F-13-03 | Renders current drawdown pct formatted as `−2.80%` |
| F-13-04 | Renders longest loss streak as `4 trades` |
| F-13-05 | Renders today's loss formatted as `−₹2,500.00` |
| F-13-06 | Renders `—` for `total_at_risk_inr` when null |
| F-13-07 | Renders `—` for drawdown fields when `max_drawdown_inr` is null |
| F-13-08 | Shows loading skeleton with `role="status"` while loading |
| F-13-09 | Shows error message on fetch failure |

Add MSW fixtures to `frontend/src/__tests__/msw/handlers.ts`:
- `RISK_SUMMARY_FIXTURE` — full data response
- `RISK_SUMMARY_NO_DRAWDOWN_FIXTURE` — all drawdown fields null (< 2 trades)
- `RISK_SUMMARY_NO_AT_RISK_FIXTURE` — `total_at_risk_inr: null` (no planned risk on open trades)

---

## Explicitly NOT in Step 13

| Deferred to | What |
|-------------|------|
| Phase 2 | Position sizing calculator with configurable risk rules |
| Phase 2 | Strategy/instrument concentration limits |
| Phase 2 | Correlated exposure monitoring |
| Phase 2 | Portfolio heat map |
| Phase 2 | Risk of ruin calculation |
| Phase 2 | Real-time open position risk (requires live price feed) |
| Phase 2 | Daily / weekly / monthly risk limit configuration and alerts |
| Phase 2 | Drawdown tier system (e.g. 5% → reduce size, 10% → pause trading) |
| Not Step 13 | R-multiple distribution — already delivered in Step 12.6 (M-6) |
| Not Step 13 | Drawdown SQL — already computed in analytics summary; deduplication is the rule |

---

## Order of Work

1. **Dhanvantari** — review and sign off on this plan (closes OI-5)
2. **Bhima** — domain types + risk service + unit tests
3. **Bhima** — `/v1/risk` router + integration tests
4. **Arjun** — `useRiskSummary` hook + Zod schema + MSW fixtures
5. **Arjun** — `RiskSummaryCard` component + tests
6. **Arjun** — wire `RiskSummaryCard` into `app.tsx`
7. **Sahadeva** — QA gate
8. **Nakula** — CI gate
9. **Yudhishthira** — acceptance

Bhima and Arjun work can proceed in parallel after step 1.

---

## Risk Register (Step 13)

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|-----------|
| R-13-1 | `current_drawdown_inr` not exposed by analytics service — requires adding INR field to drawdown dataclass | Medium | Low | Check `AnalyticsService` before starting. If missing, add INR field to existing drawdown dataclass in the same PR — it is a non-breaking addition. |
| R-13-2 | Open trades in test DB don't exist today (trade_date = today) — daily queries return zero rows in tests | Medium | Low | Integration test fixtures must insert trades with `trade_date = CURRENT_DATE` dynamically, not a hardcoded past date. |
| R-13-3 | Coupling RiskService → AnalyticsService adds hidden test complexity (must mock AnalyticsService in unit tests) | Low | Low | Use constructor injection. Pass a mock AnalyticsService in unit tests. Flag the coupling in a brief inline comment. |

---

## Open Items Before Implementation

| # | Item | Owner | Required by |
|---|------|-------|-------------|
| OI-5 | Dhanvantari: review and sign off on this execution plan as the Phase 1 risk spec | Dhanvantari | Before Bhima starts backend |
| OI-3 | Ganesha: FIFO multi-lot treatment for CNC delivery — does it affect open trade at-risk calculation? | Ganesha | Before Step 13 implementation (check if partial fills affect `planned_risk_amount` scoping) |

---

## Gate Criteria

| Gate | Owner | Criteria |
|------|-------|---------|
| Dhanvantari spec sign-off | Dhanvantari | This document reviewed; scope confirmed correct and complete for Phase 1 |
| Sahadeva QA | Sahadeva | All 5 backend integration tests pass; all 9 frontend component tests pass; no regressions in existing test suite |
| Nakula CI | Nakula | `pytest --cov-fail-under=80` green; `npm run coverage` passes thresholds; ESLint/ruff/tsc clean |
| Yudhishthira accept | Yudhishthira | Risk Summary card renders correctly; deduplication decisions reviewed and accepted |

---

## Effort Estimate

| Owner | Work | Estimate |
|-------|------|----------|
| Bhima | Domain types, risk service, unit tests, router, integration tests | ~1 session |
| Arjun | Hook, schema, fixtures, component, component tests, wire-up | ~0.5 session |
| **Total** | | **~1.5 sessions** |

Lower than the 2-session phase plan estimate because the deduplication with analytics is clean — no new SQL for drawdown/streak.

---

*Krishna — Senior Project Manager*  
*Source: `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`, `docs/design/STEP-12-ANALYTICS-SPEC.md`, `docs/requirements/REQUIREMENTS.md` §15*
