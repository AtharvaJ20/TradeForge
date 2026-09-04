# Step 12.5 — Behavioral Analytics: Streaks, Hold Duration, Exit Type

**Status:** PLANNING  
**Branch:** `feat/step-12-5-behavioral-analytics`  
**Based on:** `feat/step-12-4-dynamic-filters` (6d6677b) — CI GREEN  
**Plan date:** 2026-09-04  
**PM:** Krishna  
**Implementation owners:** Bhima (backend), Arjun (frontend)  
**QA owner:** Sahadeva  
**Gate:** Sahadeva GO → Nakula CI GREEN → Yudhishthira ACCEPT

---

## Context

Steps 12.1–12.4 delivered the analytics data layer, 9 summary-metric cards, full filter UI, and dynamic filter dimensions. The Step 12 spec (Karna) requires M-1 through M-14 before Step 12 is closed.

**Remaining must-haves:**
| Metric | Status |
|--------|--------|
| M-6 R-Multiple Distribution | Not built |
| M-10 Dimension Breakdown (Setup, Instrument, TradeType, Segment) | Only Direction built |
| M-12 Consecutive Win/Loss Streaks | Not built |
| M-13 Hold Duration Analysis | Not built |
| M-14 Exit Type Analysis | Not built |

**Step 12.5 scope:** M-12, M-13, M-14 — the three behavioral/temporal metrics.  
**Step 12.6 scope (deferred):** M-6 R-Multiple Distribution + full M-10 Dimension Breakdown.

---

## Mandatory Obligation Carried Forward

**QO-1 (Sahadeva, from Step 12.4):**  
`useFilterDimensions` hook has no RTL + MSW integration test exercising the full TanStack Query + fetch path. Component tests mock the hook; a wiring bug (wrong query key, wrong fetch import) would not be caught.

**Owner:** Arjun  
**Obligation:** One `renderHook` + `QueryClientWrapper` + MSW handler test for `useFilterDimensions` must be authored **before Step 12.5 is considered complete.** This is a gate item on Sahadeva's acceptance.

---

## Scope

### What Step 12.5 builds

**M-12 — Consecutive Win/Loss Streaks**  
Backend: New endpoint `GET /v1/analytics/streaks`. Returns 4 INTEGER scalars + 2 Decimal averages (per `StreakStats` domain type already defined in `types.py`).  
Frontend: New `StreaksCard` component. Displays: current streak (signed color), max win streak, max loss streak, avg trades per reversal.

**M-13 — Hold Duration Analysis**  
Backend: New endpoint `GET /v1/analytics/hold-duration`. Returns 5 bucket rows + avg/median duration minutes (per `HoldDurationDistribution` domain type).  
Frontend: New `HoldDurationCard` component. Displays the 5 buckets as a table with N, win rate, avg net P&L.

**M-14 — Exit Type Analysis**  
Backend: New endpoint `GET /v1/analytics/exit-types`. Uses `DISTINCT ON (trade_id) ORDER BY fill_timestamp DESC` CTE (G-CORR-02). Returns one row per exit type.  
Frontend: New `ExitTypeCard` component. Displays table: exit type, N, win rate, avg net P&L, avg R-multiple. NULL exit_type group labeled "Untagged". Includes a data-quality callout when NULL coverage > 20% (Sanjaya flag from spec).

### What Step 12.5 does NOT build
- M-6 R-Multiple Distribution (histogram chart) — Step 12.6
- M-10 Dimension Breakdown beyond Direction — Step 12.6
- N-1 Rolling Expectancy, N-2 Time-of-Day, N-4 Kelly — Step 12.7
- N-3 Monte Carlo — blocked on background job infrastructure (Phase 2)

---

## Architecture Decisions

### Backend endpoints
All three endpoints follow the established pattern from Step 12.4:
- Route: `GET /v1/analytics/{resource}`
- All 9 global filter dimensions accepted as query params (same `AnalyticsFilter` domain object)
- Auth: session-scoped `user_id` (never from request body)
- No new migrations required — all reads from existing tables

### Calculator placement
Domain layer (`domain/analytics/calculators.py`) — zero framework imports (ADR-001 enforced).

**M-12 calculator:** Pure Python over ordered trade series — takes `list[tuple[UUID, Decimal]]` (trade_id, net_pnl) ordered by (trade_date, last_fill_at, trade_id). Returns `StreakStats`.

**M-13 calculator:** SQL bucket query (5 buckets, EXTRACT EPOCH from hold duration). Application-layer avg/median from raw results.

**M-14 calculator:** SQL query with `DISTINCT ON` CTE (G-CORR-02). Application-layer aggregation into `ExitTypeRow` list.

### Frontend integration
- `AnalyticsSummaryPanel` extended with three new sections (after ChargesCard)
- Three new endpoints → three new hook files in `features/analytics/hooks/`
- Three new Zod schemas in `features/analytics/schemas.ts`
- Three new card components in `features/analytics/components/`
- `App.tsx` passes same `AnalyticsFilterParams` to all new hooks

---

## Dependencies

| Dependency | Owner | Status | Risk |
|------------|-------|--------|------|
| Step 12.4 CI GREEN | Nakula | **DONE** — 6d6677b | None |
| `StreakStats`, `HoldDurationDistribution`, `ExitTypeRow` domain types | Bhima | **DONE** — already in `types.py` | None |
| QO-1 useFilterDimensions MSW test | Arjun | **Pending** — due before Step 12.5 closes | **GATE ITEM** |
| `execution_fills.fill_timestamp` populated correctly | Sanjaya | Design assumption | Low — Step 11 wired this |
| `execution_fills.exit_type` NULL coverage unknown | Sanjaya | Unknown | Medium — data quality risk for M-14 |

---

## Workstreams

### WS-A · Backend (Bhima)

**WS-A-1 — Streaks endpoint**
1. Add `compute_streaks(trades: list[tuple[UUID, Decimal]]) → StreakStats` to `calculators.py`
   - Input ordered by (trade_date, last_fill_at, trade_id) — repo provides this ordering
   - **G-STREAK-01:** Three-branch walk: `net_pnl > 0` → win (advance current_win, reset current_loss); `net_pnl < 0` → loss (advance current_loss, reset current_win); `net_pnl == 0` → breakeven (reset BOTH to 0, starts no new streak)
   - Return: current_win_streak, current_loss_streak, max_win_streak, max_loss_streak, avg_win_streak, avg_loss_streak
2. Add `get_streak_trades(f: AnalyticsFilter) → list[tuple[UUID, Decimal]]` to `analytics_repo.py`
   - Returns `(trade_id, net_pnl)` ordered by `(trades.trade_date ASC, trades.last_fill_at ASC, trades.id ASC)`
   - All 9 filter dimensions applied
3. Add `GET /v1/analytics/streaks` to `api/v1/analytics.py`
4. Unit tests: empty list; all wins; all losses; breakeven resets streak (`W W B L L` → max_win=2, max_loss=2, current_win=0, current_loss=2); breakeven starts no new streak
5. Integration test: seed 5+ trades with known streak pattern including at least one breakeven; assert response shape

**WS-A-2 — Hold Duration endpoint**
1. Add `GET /v1/analytics/hold-duration` to `api/v1/analytics.py`
2. Add `get_hold_duration(f: AnalyticsFilter) → HoldDurationDistribution` to `analytics_repo.py`
   - SQL: `EXTRACT(EPOCH FROM (last_fill_at - first_fill_at)) / 60 AS hold_minutes`
   - 5 CASE buckets: scalp (<5m), intraday_short (5–60m), intraday_long (1–4h), same_day_extended (4–24h), multi_day (≥24h)
   - Aggregate per bucket: count, avg_net_pnl, win_rate, avg_hold_minutes
   - Application-layer: overall avg_duration_minutes, median_duration_minutes from raw rows
3. Integration test: seed trades with different fill timestamps spanning all 5 buckets

**WS-A-3 — Exit Type endpoint**
1. Add `GET /v1/analytics/exit-types` to `api/v1/analytics.py`
2. Add `get_exit_types(f: AnalyticsFilter) → list[ExitTypeRow]` to `analytics_repo.py`
   - CTE `last_exit`: `DISTINCT ON (trade_id) ORDER BY trade_id, fill_timestamp DESC` from `execution_fills WHERE fill_role = 'EXIT'`
   - Join to trades + trade_pnl; group by exit_type; aggregate: count, avg_net_pnl, avg_r_multiple, win_rate
   - Include NULL exit_type group (labeled "Untagged" in the response)
   - Apply all 9 filter dimensions on the trades table
3. Integration test: seed trades with at least 3 different exit types + NULL; assert correct grouping and win_rate calculation

**WS-A deliverable:** 3 new endpoints, all 9 filter dimensions applied, unit + integration tests passing, ruff/mypy clean.

---

### WS-B · Frontend (Arjun)

**WS-B-0 — QO-1 (prerequisite)**
Add `useFilterDimensions.test.tsx` with `renderHook` + `QueryClientWrapper` + 3 MSW handlers (accounts, setups, brokers). Asserts data is returned for each dimension, not mocked at the hook level.

**WS-B-1 — Schemas + types**
Extend `features/analytics/schemas.ts`:
- `StreaksSchema`: 6 fields (all integers/Decimals)
- `HoldDurationSchema`: `{buckets: HoldDurationBucketSchema[], avg_duration_minutes, median_duration_minutes}`
- `ExitTypesSchema`: `{rows: ExitTypeRowSchema[]}` — null `exit_type` allowed

Extend `features/analytics/types.ts` with inferred TS types.

**WS-B-2 — API + hooks**
- `fetchStreaks`, `fetchHoldDuration`, `fetchExitTypes` in `features/analytics/api.ts`
- `useStreaks`, `useHoldDuration`, `useExitTypes` hooks — each `renderHook` + MSW tested (per QO-1 pattern)

**WS-B-3 — StreaksCard component**
- Shows current streak (+ prefix, signed color — green positive, red negative)
- Max win streak, max loss streak as stat tiles
- Avg trades per reversal
- 3 tests: renders with data, handles empty (0 trades), accessibility landmark

**WS-B-4 — HoldDurationCard component**
- `<table>` with 5 rows: bucket label, N, win rate, avg net P&L
- Empty guard (no closed trades)
- 3 tests: full render, empty state, correct bucket ordering

**WS-B-5 — ExitTypeCard component**
- `<table>` with one row per exit type; NULL → "Untagged"
- Data quality callout: `role="alert"` when `untagged_pct > 20%` ("X% of exits have no exit type — check broker adapter configuration")
- 3 tests: full render, Untagged group shown, data quality callout triggers at threshold

**WS-B-6 — AnalyticsSummaryPanel integration**
- Add `StreaksCard`, `HoldDurationCard`, `ExitTypeCard` below `ChargesCard`
- Pass `params` through to all three new hooks
- Panel-level test: assert 3 new card headings present in rendered output

**WS-B deliverable:** QO-1 done, OBS-12.3-02 + OBS-12.3-03 tests added to `AnalyticsFilterBar.test.tsx`, 3 new schemas, 3 new hooks (each with MSW test), 3 new cards (3 tests each), panel integration, tsc clean, all coverage thresholds met.

**WS-B-3.5 — OBS-12.3-02 + OBS-12.3-03 (Sahadeva-ruled, pulled into Step 12.5):**
- **OBS-12.3-02:** In `AnalyticsFilterBar.test.tsx` — enter a `date_to` value, then clear it; assert emitted `AnalyticsFilterParams` does not contain `date_to` (or contains empty/undefined per contract)
- **OBS-12.3-03:** In `AnalyticsFilterBar.test.tsx` — select 2 values in a multi-select group, unselect one; assert emitted params array contains exactly the 1 remaining item

---

### WS-C · QA (Sahadeva)

Sahadeva's gate checklist for Step 12.5:

**Gate items:**
- [ ] QO-1 useFilterDimensions MSW test authored by Arjun (required before GO)
- [ ] OBS-12.3-02 `date_to` clear test passing (PULLED IN — Sahadeva ruling OQ-2, 2026-09-04)
- [ ] OBS-12.3-03 multi-select partial-uncheck test passing (PULLED IN — Sahadeva ruling OQ-2, 2026-09-04)
- [ ] M-12 streaks: G-STREAK-01 verified — breakeven (net_pnl=0) resets streak; fixture must include at least one breakeven
- [ ] M-13 hold duration: 5 buckets exhaustive; no trade unaccounted for
- [ ] M-14 exit type: G-CORR-02 CTE verified; NULL group present; data quality alert triggers at > 20%
- [ ] All 9 filter dimensions applied and tested on all 3 new endpoints

**Explicitly deferred (not silently carried):**
- OBS-12.3-01 (Instrument/Segment render assertion) → **DEFERRED to Step 12.6** — low-risk in 12.5; Step 12.6 M-10 Dimension Breakdown is the natural home. Step 12.6 execution plan must carry this as a named opening obligation.

**Not required for Step 12.5 gate:**
- M-6, M-10 (Step 12.6)
- E2E tests (tracked, not gated here)

---

## Acceptance Criteria

### AC-12.5-01 · Streaks endpoint
**Given** a user has a sequence of closed trades with a known streak pattern (e.g. 3W, 1L, 2W, 1B, 4L)  
**When** `GET /v1/analytics/streaks` is called with all filters cleared  
**Then** the response contains: correct `max_win_streak`, correct `max_loss_streak`, correct `current_*_streak`, and breakeven trades do NOT extend a win or loss streak

### AC-12.5-02 · Hold Duration buckets are exhaustive
**Given** trades spanning all 5 hold-duration buckets  
**When** `GET /v1/analytics/hold-duration` is called  
**Then** every trade appears in exactly one bucket; zero trades are unaccounted for; `avg_duration_minutes` matches manual calculation

### AC-12.5-03 · Exit Type CTE correctness (G-CORR-02)
**Given** a multi-exit scaled trade with 2 EXIT fills with different `exit_type` values  
**When** `GET /v1/analytics/exit-types` is called  
**Then** the trade is counted exactly once, assigned the exit_type of the fill with the latest `fill_timestamp`

### AC-12.5-04 · Untagged exit type group
**Given** some exits have `exit_type = NULL`  
**When** the ExitTypeCard renders  
**Then** a row labeled "Untagged" is shown with the correct count

### AC-12.5-05 · Data quality alert
**Given** `NULL exit_type` trades account for > 20% of the total  
**When** the ExitTypeCard renders  
**Then** a `role="alert"` callout appears with text referencing broker adapter configuration

### AC-12.5-06 · QO-1 hook test
**Given** MSW intercepts the three filter-dimension endpoints  
**When** `renderHook(() => useFilterDimensions(...))` is called with a `QueryClientWrapper`  
**Then** all three queries resolve with their respective data without any mock at the hook level

### AC-12.5-07 · All 9 filter dimensions respected
**Given** a filter applied (e.g. `direction=LONG`)  
**When** each of the 3 new endpoints is called  
**Then** only trades matching the filter appear in the response

---

## Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|-----------|
| R-1 | `execution_fills.exit_type` is NULL for most trades — M-14 returns only "Untagged" | Medium | Low — data quality issue, not a correctness bug | Data quality alert in UI; document known NULL coverage in test fixture |
| R-2 | `first_fill_at` and `last_fill_at` equal for same-bar trades — hold_minutes = 0 → scalp bucket | Low | Low | Explicitly assert in integration test that 0-minute trades land in 'scalp' bucket |
| R-3 | M-12 streak definition ambiguity: does a breakeven reset a win streak? | Low | Medium | Spec is clear: breakeven is a third class (G-CORR-01); it does NOT extend a win or loss streak. Arjun and Bhima must align on this before implementation |
| R-4 | OBS-12.3-01/02/03 re-raised by Sahadeva and included in gate | Low | Low | Sahadeva documents decision at gate entry; if included, Arjun adds tests before GO |

---

## Timeline Estimate

| Workstream | Effort | Notes |
|-----------|--------|-------|
| WS-A (Bhima, backend) | ~3–4 hours | 3 endpoints, calculators, tests |
| WS-B-0 (Arjun, QO-1) | ~1 hour | Hook test with MSW — prerequisite |
| WS-B-1..6 (Arjun, frontend) | ~4–5 hours | Schemas, hooks, 3 cards, panel integration |
| WS-C (Sahadeva, QA gate) | ~1 hour | Gate checklist review |
| Buffer | +25% | Unknown unknowns in hold-duration SQL + exit-type CTE |

**Total estimated duration:** 1 focused session (WS-A and WS-B can run in parallel; WS-C gates on both)

---

## Gate Sequence

```
WS-A complete (3 endpoints + tests)
      │
WS-B-0 complete (QO-1 MSW test) ──────┐
      │                                │
WS-B-1..6 complete (3 cards + panel) ──┤
      │                                │
      └────────────── Sahadeva gate ───┘
                           │
                     Nakula CI GREEN
                           │
                   Yudhishthira ACCEPT
                           │
                  STEP 12.5 CLOSED
                  → start Step 12.6
```

---

## Open Questions (resolve before implementation)

| # | Question | Owner | Deadline |
|---|----------|-------|----------|
| OQ-1 | ~~Does a breakeven trade (net_pnl = 0) reset an active win or loss streak?~~ **RESOLVED — G-STREAK-01: breakeven RESETS both streaks (current_win=0, current_loss=0). Does not extend either streak. Does not start a new one. Ganesha 2026-09-04.** | Ganesha | **CLOSED** |
| OQ-2 | OBS-12.3-01/02/03 — defer again to Step 12.6 or include in Step 12.5? | Sahadeva | At gate entry declaration |

---

*Krishna · Project Management · Step 12.5 Plan · 2026-09-04*  
*Karna spec: `docs/design/STEP-12-ANALYTICS-SPEC.md` (M-12, M-13, M-14)*  
*Backend owner: Bhima · Frontend owner: Arjun · QA: Sahadeva*
