# Step 12.7 — Analytics: Rolling Metrics (N-1, N-2, N-4)

**Document:** `docs/project-status/STEP-12-7-EXECUTION-PLAN.md`  
**Author:** Krishna (Project Manager)  
**Date:** 2026-09-04  
**Parent plan:** `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`  
**Branch base:** `main` (after `feat/step-12-6-analytics-completion` is merged via PR)  
**Status:** READY TO START — pending Step 12.6 PR merge to main

---

## Goal

Deliver the three remaining Karna analytics spec items — N-1 Rolling Expectancy, N-2 Time-of-Day Performance, and N-4 Kelly Fraction — that complete the §13 Phase 1 analytics requirement.

Done means: all three metrics implemented backend + frontend + tested, Sahadeva GO, Nakula CI GREEN, Yudhishthira ACCEPT.

---

## What "Done" Looks Like

A user on the analytics page can:

1. See a Rolling Expectancy section showing how their 20-trade sliding-window expectancy has evolved across their trade history — with an insufficient-sample guard when fewer than 20 trades are present.
2. See a Time-of-Day Performance table showing how each NSE session band (Pre-Open, Open Volatility, Mid-Morning, Lunch, Afternoon, Close) performs — trade count, win rate, expectancy in ₹, and total net P&L — filtered by the active analytics filter.
3. See a Kelly Fraction stat: Full Kelly % and Half-Kelly %, with a plain-language note, guarded by a minimum-sample requirement of 30 trades with valid R-multiple.

All three respect the active analytics filter (account_id, direction, setup, instrument, trade_type, segment, from_date, to_date).

---

## Opening Obligations

Step 12.6 discharged all carried obligations. There are **no opening obligations** for Step 12.7.

Begin with N-4 (simplest — pure scalars), then N-2 (new SQL, tabular output), then N-1 (most complex — sliding window computation). This order reduces risk: N-4 and N-2 are isolated; N-1 reuses the equity curve query and adds Python computation.

---

## Scope

### N-4 — Kelly Fraction

**What it is:** Two position-sizing scalars derived from historical R-multiples. Answers "How much of my capital should I be risking per trade, given my historical edge?"

**Formula (from Karna spec):**
```
Kelly_pct  = Expectancy_R / AVG(r_multiple WHERE r_multiple > 0)
Half_Kelly = Kelly_pct / 2
```

**Guard:** Minimum 30 trades with a non-null `r_multiple`. If fewer, return `insufficient_sample: true` and null scalars.

**Backend (Bhima)**

*Domain types — add to `types.py`:*
```python
@dataclass
class KellyResult:
    kelly_pct: Decimal | None       # null when insufficient sample
    half_kelly_pct: Decimal | None  # null when insufficient sample
    trades_with_r: int              # count of trades with non-null r_multiple
    insufficient_sample: bool
    min_n: int = 30
```

*Repo method — add to `AnalyticsRepository`:*
```python
async def get_kelly_inputs(self, f: AnalyticsFilter) -> dict[str, Any]:
    # Returns: {"expectancy_r": Decimal | None, "avg_positive_r": Decimal | None, "trades_with_r": int}
    # expectancy_r: uses existing compute_expectancy logic over r_multiples
    # avg_positive_r: AVG(r_multiple) WHERE r_multiple > 0 AND r_multiple IS NOT NULL
    # trades_with_r: COUNT(*) WHERE r_multiple IS NOT NULL
```

Note: `get_r_multiple_series` already exists and returns ordered `(r_multiple, entry_date)` tuples. The Kelly repo method should use a single aggregate query rather than fetching the full series, to avoid unnecessary data transfer when the trade count is large.

*Service method — add to `AnalyticsService`:*
```python
async def get_kelly_fraction(self, f: AnalyticsFilter) -> KellyResult:
    inputs = await self._repo.get_kelly_inputs(f)
    trades_with_r: int = inputs["trades_with_r"]
    MIN_N = 30
    if trades_with_r < MIN_N or inputs["expectancy_r"] is None or inputs["avg_positive_r"] is None:
        return KellyResult(kelly_pct=None, half_kelly_pct=None, trades_with_r=trades_with_r, insufficient_sample=True)
    kelly = inputs["expectancy_r"] / inputs["avg_positive_r"]
    return KellyResult(kelly_pct=kelly, half_kelly_pct=kelly / 2, trades_with_r=trades_with_r, insufficient_sample=False)
```

**Division-by-zero guard:** If `avg_positive_r` is zero or null (no winning trades with valid R), return `insufficient_sample: true`.

*API endpoint — add to `analytics.py`:*
```
GET /v1/analytics/kelly
```
Response:
```json
{
  "insufficient_sample": false,
  "kelly_pct": 0.3142,
  "half_kelly_pct": 0.1571,
  "trades_with_r": 45,
  "min_n": 30
}
```

**Frontend (Arjun)**

*Hook:* `useKelly(params: AnalyticsFilterParams)` — TanStack Query wrapping `fetchKelly`. Query key: `["analytics", "kelly", params]`.

*API client:* `fetchKelly(params): Promise<KellyResult>` — `GET /v1/analytics/kelly${qs}`.

*Component:* `KellyCard.tsx`
- Layout: two large stat numbers side-by-side — Full Kelly (e.g. **31.4%**) and Half-Kelly (e.g. **15.7%**)
- Below the stats: one sentence of plain-language context, e.g. "Half-Kelly is the recommended starting point. Full Kelly maximises long-run growth but risks steep drawdowns."
- Insufficient-sample state: muted card with "Needs 30+ trades with a planned stop to calculate." message
- Null kelly_pct (any guard case): render "—" rather than 0 or NaN

*Tests (Arjun):*
- Happy path: `KellyCard` renders Full Kelly and Half-Kelly values correctly
- Insufficient sample: renders guidance message, no numeric values
- Null kelly_pct (guard case): renders "—" for both values

---

### N-2 — Time-of-Day Analysis

**What it is:** A breakdown of performance by NSE session band, bucketed on the IST entry time of each trade. Answers "Which part of the trading day is most profitable for me?"

**Session buckets (from Karna spec — IST = UTC+5:30):**

| Bucket key | Label | IST range |
|-----------|-------|-----------|
| `pre_open` | Pre-Open | 09:15–09:30 |
| `open_volatility` | Open Volatility | 09:30–10:00 |
| `mid_morning` | Mid-Morning | 10:00–11:30 |
| `lunch` | Lunch | 11:30–13:30 |
| `afternoon` | Afternoon | 13:30–15:00 |
| `close` | Close (≥15:00) | 15:00+ |

Trades entered outside these hours (rare — e.g. after-market adjustments) fall into `close`.

**Per-bucket output:** `{bucket, N, win_count, win_rate, expectancy_inr, total_net_pnl}`

Note on `expectancy_inr`: this is mathematically equivalent to `AVG(net_pnl)` across the bucket (win_rate × avg_win − (1−win_rate) × avg_loss = avg(net_pnl)). Use the direct SQL `AVG(trade_pnl.net_pnl)` — simpler and consistent with the existing P&L schema.

**Backend (Bhima)**

*Domain types — add to `types.py`:*
```python
@dataclass
class TimeOfDayBucket:
    bucket: str          # e.g. "pre_open"
    label: str           # e.g. "Pre-Open"
    trade_count: int
    win_count: int
    win_rate: Decimal    # 0–1
    expectancy_inr: Decimal | None  # null if trade_count == 0
    total_net_pnl: Decimal

@dataclass
class TimeOfDayResult:
    buckets: list[TimeOfDayBucket]
```

*Repo method — add to `AnalyticsRepository`:*
```python
async def get_time_of_day(self, f: AnalyticsFilter) -> list[dict[str, Any]]:
```

SQL logic:
```sql
WITH bucketed AS (
    SELECT
        trade_pnl.net_pnl,
        (trade_pnl.net_pnl > 0)::int AS is_win,
        CASE
            WHEN (t.first_fill_at AT TIME ZONE 'Asia/Kolkata')::time BETWEEN '09:15' AND '09:30' THEN 'pre_open'
            WHEN (t.first_fill_at AT TIME ZONE 'Asia/Kolkata')::time BETWEEN '09:30' AND '10:00' THEN 'open_volatility'
            WHEN (t.first_fill_at AT TIME ZONE 'Asia/Kolkata')::time BETWEEN '10:00' AND '11:30' THEN 'mid_morning'
            WHEN (t.first_fill_at AT TIME ZONE 'Asia/Kolkata')::time BETWEEN '11:30' AND '13:30' THEN 'lunch'
            WHEN (t.first_fill_at AT TIME ZONE 'Asia/Kolkata')::time BETWEEN '13:30' AND '15:00' THEN 'afternoon'
            ELSE 'close'
        END AS bucket
    FROM trades t
    JOIN trade_pnl ON trade_pnl.trade_id = t.id
    WHERE t.status = 'CLOSED'
      AND <base_where clauses from _base_where(f)>
)
SELECT
    bucket,
    COUNT(*)                              AS trade_count,
    SUM(is_win)                           AS win_count,
    AVG(net_pnl)                          AS expectancy_inr,
    SUM(net_pnl)                          AS total_net_pnl
FROM bucketed
GROUP BY bucket
```

The service layer fills in the `label` field and ensures all 6 buckets appear in the response (zero-filling missing buckets with `trade_count=0, win_count=0, win_rate=Decimal(0), expectancy_inr=None, total_net_pnl=Decimal(0)`).

**Timezone note:** `AT TIME ZONE 'Asia/Kolkata'` requires the `timezone` extension — already present on Railway's managed PostgreSQL. No migration needed.

**Filter pass-through:** `_base_where(f)` already handles account_id, direction, date range, setup, instrument, trade_type, segment. No special handling needed for N-2 — all filters apply to which trades are bucketed.

*Service method — add to `AnalyticsService`:*
```python
async def get_time_of_day(self, f: AnalyticsFilter) -> TimeOfDayResult:
```

*API endpoint — add to `analytics.py`:*
```
GET /v1/analytics/time-of-day
```
Response:
```json
{
  "buckets": [
    {"bucket": "pre_open", "label": "Pre-Open", "trade_count": 12, "win_count": 7, "win_rate": 0.5833, "expectancy_inr": 420.50, "total_net_pnl": 5046.00},
    {"bucket": "open_volatility", "label": "Open Volatility", "trade_count": 0, "win_count": 0, "win_rate": 0.0, "expectancy_inr": null, "total_net_pnl": 0.0},
    ...
  ]
}
```

Always returns all 6 buckets in display order. Buckets with `trade_count=0` are included (not omitted).

**Frontend (Arjun)**

*Hook:* `useTimeOfDay(params: AnalyticsFilterParams)` — TanStack Query wrapping `fetchTimeOfDay`.

*API client:* `fetchTimeOfDay(params): Promise<TimeOfDayResult>` — `GET /v1/analytics/time-of-day${qs}`.

*Component:* `TimeOfDayCard.tsx`
- Layout: 6-row table. Columns: Session Band | Trades | Win Rate | Expectancy (₹) | Total P&L
- Rows ordered by session time, not by performance
- Zero-count rows: render with "—" for win rate and expectancy_inr (not "0%")
- Highest-total-net-pnl bucket: bold or background-tinted row (visual callout only — no chart needed)
- No insufficient-sample guard — all users with trades get a result; zero-count buckets are informative

*Tests (Arjun):*
- All 6 buckets render in the correct order
- Zero-count bucket renders "—" for win rate and expectancy, not "0%"
- Best-performing bucket is visually distinguished

---

### N-1 — Rolling Expectancy (20-trade window)

**What it is:** A time-series showing how the 20-trade sliding-window expectancy evolves across a user's trade history. The primary edge-stability signal. Answers "Is my edge improving, degrading, or consistent?"

**Computation (from Karna spec):**
```python
# For each trade index i >= 20 (0-indexed):
window = trades[i-20:i]          # 20 most recent trades ending at index i
rolling_exp_r   = expectancy_r(window)    # M-3 formula applied to window's r_multiples
rolling_exp_inr = expectancy_inr(window)  # M-3 formula applied to window's net_pnl values
```

Ordered by: `trade_date ASC, last_fill_at ASC, trade_id ASC` (tie-break consistent with M-7 equity curve ordering).

**Guard:** Minimum 20 trades (with valid `r_multiple` for `rolling_exp_r` — if fewer than 20 trades have R, the R series starts later). For `rolling_exp_inr`, all closed trades are eligible. The series starts at the 20th point; `insufficient_sample: true` when the total closed trade count is < 20.

**Backend (Bhima)**

*Domain types — add to `types.py`:*
```python
@dataclass
class RollingExpectancyPoint:
    trade_index: int          # 1-based (starts at 20)
    trade_date: date
    rolling_exp_r: Decimal | None   # null if window has no trades with valid r_multiple
    rolling_exp_inr: Decimal

@dataclass
class RollingExpectancyResult:
    window: int               # always 20
    insufficient_sample: bool
    data: list[RollingExpectancyPoint]
```

*Repo method:* **Reuse `get_equity_curve(f)`** — it already returns `EquityCurvePoint` objects with `{trade_date, net_pnl, r_multiple}` in chronological order. No new SQL needed.

*Compute helper — add to `calculators.py`:*
```python
MIN_N_ROLLING = 20

def compute_rolling_expectancy(
    points: Sequence[EquityCurvePoint],
    window: int = MIN_N_ROLLING,
) -> RollingExpectancyResult:
    """Pure sliding-window computation over an ordered trade series."""
    if len(points) < window:
        return RollingExpectancyResult(window=window, insufficient_sample=True, data=[])
    
    result: list[RollingExpectancyPoint] = []
    for i in range(window, len(points) + 1):
        w = points[i - window : i]
        r_vals = [p.r_multiple for p in w if p.r_multiple is not None]
        exp_r = compute_expectancy(r_vals).expectancy_r if r_vals else None
        pnl_vals = [p.net_pnl for p in w]
        exp_inr = compute_expectancy(pnl_vals).expectancy_r  # reuse formula; input is INR series
        result.append(RollingExpectancyPoint(
            trade_index=i,
            trade_date=w[-1].trade_date,
            rolling_exp_r=exp_r,
            rolling_exp_inr=exp_inr,
        ))
    return RollingExpectancyResult(window=window, insufficient_sample=False, data=result)
```

Note: `compute_expectancy` already exists in `calculators.py` (used by M-3). Verify its signature accepts `Sequence[Decimal]` before calling — if it expects `EquityCurvePoint`s, extract the scalar series first. Do not modify the existing function; add the rolling wrapper alongside it.

*Service method — add to `AnalyticsService`:*
```python
async def get_rolling_expectancy(self, f: AnalyticsFilter) -> RollingExpectancyResult:
    curve = await self._repo.get_equity_curve(f)
    return compute_rolling_expectancy(curve)
```

*API endpoint — add to `analytics.py`:*
```
GET /v1/analytics/rolling-expectancy
```
Response (insufficient sample):
```json
{"window": 20, "insufficient_sample": true, "data": []}
```
Response (sufficient sample):
```json
{
  "window": 20,
  "insufficient_sample": false,
  "data": [
    {"trade_index": 20, "trade_date": "2025-01-15", "rolling_exp_r": 0.42, "rolling_exp_inr": 850.00},
    {"trade_index": 21, "trade_date": "2025-01-16", "rolling_exp_r": 0.38, "rolling_exp_inr": 760.00},
    ...
  ]
}
```

**Frontend (Arjun)**

*Hook:* `useRollingExpectancy(params: AnalyticsFilterParams)` — TanStack Query wrapping `fetchRollingExpectancy`.

*API client:* `fetchRollingExpectancy(params): Promise<RollingExpectancyResult>` — `GET /v1/analytics/rolling-expectancy${qs}`.

*Component:* `RollingExpectancyCard.tsx`
- **MVP rendering: scrollable table** showing the last 20 data points (most recent 20 rows visible without scroll). Columns: Trade # | Date | Rolling Exp (R) | Rolling Exp (₹)
- Rows are in chronological order (oldest at top, newest at bottom)
- Rolling Exp (R): render as `+0.42R` or `−0.18R` with sign; colour-code positive (text-green) and negative (text-red)
- Insufficient-sample state: muted card with "Needs 20+ closed trades to compute rolling expectancy." message
- `rolling_exp_r` null (window has no R-multiple trades): render "—" in that column

**Note:** A sparkline chart is the preferred Phase 2 enhancement. Table is the correct MVP approach — avoids chart library dependency and keeps this step within the 1-session estimate.

*Tests (Arjun):*
- Happy path: last 20 rows render; correct sign and colour for positive/negative exp_r
- Insufficient sample: renders guidance message
- null `rolling_exp_r` in a row: renders "—", does not throw

---

## Files to Create or Modify

### Backend

| File | Change |
|------|--------|
| `domain/analytics/types.py` | Add `KellyResult`, `TimeOfDayBucket`, `TimeOfDayResult`, `RollingExpectancyPoint`, `RollingExpectancyResult` |
| `domain/analytics/calculators.py` | Add `compute_rolling_expectancy(points, window=20)` |
| `infrastructure/repositories/analytics_repo.py` | Add `get_kelly_inputs(f)`, `get_time_of_day(f)` |
| `application/analytics_service.py` | Add `get_kelly_fraction(f)`, `get_time_of_day(f)`, `get_rolling_expectancy(f)` |
| `api/v1/analytics.py` | Add response models + 3 new route handlers |

### Frontend

| File | Change |
|------|--------|
| `features/analytics/api.ts` | Add `fetchKelly`, `fetchTimeOfDay`, `fetchRollingExpectancy` |
| `features/analytics/hooks/useKelly.ts` | New file |
| `features/analytics/hooks/useTimeOfDay.ts` | New file |
| `features/analytics/hooks/useRollingExpectancy.ts` | New file |
| `features/analytics/components/KellyCard.tsx` | New file |
| `features/analytics/components/TimeOfDayCard.tsx` | New file |
| `features/analytics/components/RollingExpectancyCard.tsx` | New file |
| Analytics page component | Wire new cards into the page layout |

### Tests

| File | Owner |
|------|-------|
| `tests/unit/analytics/test_rolling_expectancy.py` | Bhima |
| `tests/unit/analytics/test_kelly.py` | Bhima |
| `tests/integration/analytics/test_rolling_expectancy_endpoint.py` | Bhima |
| `tests/integration/analytics/test_time_of_day_endpoint.py` | Bhima |
| `tests/integration/analytics/test_kelly_endpoint.py` | Bhima |
| `features/analytics/components/__tests__/KellyCard.test.tsx` | Arjun |
| `features/analytics/components/__tests__/TimeOfDayCard.test.tsx` | Arjun |
| `features/analytics/components/__tests__/RollingExpectancyCard.test.tsx` | Arjun |

---

## Test Obligations (Sahadeva gate items)

Sahadeva will block acceptance if any of these are absent.

### Backend (Bhima)

| ID | Obligation |
|----|-----------|
| B-N4-01 | Unit test: `KellyResult` correctly computed from known inputs; division-by-zero guard returns `insufficient_sample: true`; < 30 trades returns `insufficient_sample: true` |
| B-N4-02 | Integration test: `GET /v1/analytics/kelly` — insufficient sample, filter pass-through (account_id, direction, date range) |
| B-N2-01 | Integration test: `GET /v1/analytics/time-of-day` — all 6 buckets present in response; correct bucket assignment for a trade at boundary time; zero-count bucket has `expectancy_inr: null` (not 0) |
| B-N2-02 | Integration test: filter pass-through — trades outside the filter are excluded from bucket counts |
| B-N1-01 | Unit test: `compute_rolling_expectancy` — exactly 19 trades returns `insufficient_sample: true`; exactly 20 trades returns one data point; window slides correctly at trade 21 (window is trades 2–21, not 1–21) |
| B-N1-02 | Unit test: null `r_multiple` in window — `rolling_exp_r` is null for that point, `rolling_exp_inr` still computed |
| B-N1-03 | Integration test: `GET /v1/analytics/rolling-expectancy` — insufficient sample response; filter pass-through |

### Frontend (Arjun)

| ID | Obligation |
|----|-----------|
| F-N4-01 | `KellyCard`: happy path renders Full Kelly % and Half-Kelly % |
| F-N4-02 | `KellyCard`: insufficient-sample state renders guidance message, not numeric values |
| F-N2-01 | `TimeOfDayCard`: all 6 buckets render in session-time order |
| F-N2-02 | `TimeOfDayCard`: zero-count bucket renders "—" for win rate and expectancy, not "0%" |
| F-N1-01 | `RollingExpectancyCard`: renders last 20 rows of data; sign-and-colour applied to `rolling_exp_r` |
| F-N1-02 | `RollingExpectancyCard`: insufficient-sample state renders guidance message |
| F-N1-03 | `RollingExpectancyCard`: null `rolling_exp_r` in a row renders "—", no crash |

---

## Order of Work

```
N-4 Kelly (simplest — pure scalars, reuses existing expectancy)
  ↓ Commit
N-2 Time-of-Day (new SQL, clear output shape)
  ↓ Commit
N-1 Rolling Expectancy (reuses equity curve query, Python compute layer)
  ↓ Commit
Wire all three cards into analytics page
  ↓ Commit
Sahadeva gate
  ↓
Nakula CI GREEN
  ↓
Yudhishthira ACCEPT
```

Work N-4 backend + frontend together, then N-2, then N-1. Do not mix backend and frontend commits across different metrics — keep each metric's full stack (backend + frontend + tests) in its own commit. This makes the Sahadeva review clean.

---

## Risks and Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|-----------|
| R-1 | `compute_expectancy` in `calculators.py` expects a different input shape than `Sequence[Decimal]` — rolling wrapper cannot call it directly | Low | Low | Bhima: inspect `compute_expectancy` signature before writing `compute_rolling_expectancy`. If the input shape differs, extract a private `_expectancy_r(vals: Sequence[Decimal])` helper rather than modifying the existing function. |
| R-2 | `AT TIME ZONE 'Asia/Kolkata'` slow on large `trades` table — N-2 query times out | Low | Medium | The `trades` table is indexed by `(user_id, status, trade_date)`. N-2 adds a time-of-day CASE over `first_fill_at` — no additional index needed for Phase 1 scale. Bhima: benchmark the query in the integration test fixture with ≥ 100 trades to confirm response time is acceptable. |
| R-3 | Rolling expectancy returns a large JSON payload for users with 500+ trades | Low | Low | Data is returned as a flat array. At 500 trades, 481 data points × ~4 fields ≈ 15–20 KB — well within acceptable limits. No pagination needed for Phase 1. |
| R-4 | Kelly formula not defined when `avg_positive_r = 0` (all winning trades have R = 0.0) | Very Low | Low | Division-by-zero guard already specified in `get_kelly_fraction`. Return `insufficient_sample: true`. |

---

## Acceptance Checklist (Sahadeva gate)

- [ ] `GET /v1/analytics/kelly` — returns `kelly_pct`, `half_kelly_pct`, `insufficient_sample` correctly
- [ ] `GET /v1/analytics/time-of-day` — returns all 6 buckets, zero-count buckets have `expectancy_inr: null`
- [ ] `GET /v1/analytics/rolling-expectancy` — returns `insufficient_sample: true` for < 20 trades; data array for ≥ 20
- [ ] All 3 endpoints respect active analytics filter (account_id, direction, date range)
- [ ] All B-N4/N2/N1 integration tests pass
- [ ] All F-N4/N2/N1 component tests pass (RTL + MSW)
- [ ] No TypeScript errors (`tsc --noEmit`)
- [ ] `ruff check` AND `ruff format --check` both pass (both are separate CI gates)
- [ ] `KellyCard`, `TimeOfDayCard`, `RollingExpectancyCard` wired into analytics page and render visibly
- [ ] CI GREEN on GitHub Actions

**Sahadeva:** Report in format "Go" / "Go with risks [list]" / "No Go".

---

## What Is NOT in Step 12.7

| Item | Status |
|------|--------|
| N-3 Monte Carlo Simulation | Phase 2 — blocked on background job infrastructure |
| N-5 MAE/MFE | Phase 2 — requires OHLC bar data (Ganesha ruling G-DEFER-01) |
| Sparkline chart for Rolling Expectancy | Phase 2 enhancement — table is correct MVP |
| Rolling period analytics beyond N-1 (e.g. 50-trade window) | Phase 2 |

---

## Next Step After Acceptance

Per the Phase 1 execution sequence, Step 13 (Basic Risk Metrics) and Step 14 (Navigation Shell) can proceed in parallel after Step 12.7 is accepted. Both are unblocked — Step 13 is parallel to the feature track; Step 14 can start immediately.

Update `PHASE-1-MVP-EXECUTION-PLAN.md` to mark Step 12.7 accepted when Yudhishthira signs off.

---

*Krishna — Senior Project Manager*  
*Source: `docs/requirements/REQUIREMENTS.md` v1.1 §13, `docs/design/STEP-12-ANALYTICS-SPEC.md` (N-1, N-2, N-4), `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`*  
*Step owners per §40 agent responsibilities*
