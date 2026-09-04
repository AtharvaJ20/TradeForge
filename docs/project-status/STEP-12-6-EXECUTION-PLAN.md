# Step 12.6 — Analytics Completion (M-6 + M-10)

**Document:** `docs/project-status/STEP-12-6-EXECUTION-PLAN.md`  
**Author:** Krishna (Project Manager)  
**Date:** 2026-09-04  
**Parent plan:** `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`  
**Branch base:** `feat/step-12-5-behavioral-analytics` (Step 12.5 CLOSED, CI GREEN, commit `28f6ad0`)  
**Status:** READY TO START

---

## Goal

Close the two remaining Karna analytics spec items required for Phase 1 — R-Multiple Distribution (M-6) and full Dimension Breakdown (M-10) — and discharge three obligations carried forward from prior steps before they become blockers.

Done means: all obligations cleared, M-6 and M-10 backend + frontend implemented and tested, Sahadeva GO, Nakula CI GREEN, Yudhishthira ACCEPT.

---

## What "Done" Looks Like

A user on the analytics page can:

1. See an R-Multiple Distribution chart (bar chart or bucketed table) showing how many trades fell into each R bucket (< −2R, −2R to −1R, −1R to 0, 0 to +1R, +1R to +2R, > +2R), with an insufficient-sample guard when fewer than 5 trades have a valid R-multiple.
2. See a Dimension Breakdown section where they can select the breakdown dimension — **Direction** (already exists), **Setup**, **Instrument**, **TradeType**, **Segment** — and the table updates to show P&L, win rate, trade count, and average R per group, respecting the active analytics filter.
3. The filter bar correctly renders Instrument and Segment chips (OBS-12.3-01 fix verified by a render assertion test).

---

## Opening Obligations (Must Complete Before New Feature Work)

These are quality debts from prior steps. They are not optional — Sahadeva will block Step 12.6 acceptance if they are absent.

| ID | Owner | Obligation | Source |
|----|-------|-----------|--------|
| OBS-12.3-01 | Arjun | Add RTL render assertion: FilterBar renders Instrument chip and Segment chip when those dimensions are present in filter options. Test must use MSW-mocked filter dimension response. | Carried from Step 12.3 — Sahadeva gate item |
| COV-12.5-01 | Bhima | Add integration tests covering all 5 hold-duration buckets: `intraday`, `overnight`, `multi_day`, `weekly`, `long_term`. The `multi_day` bucket (2–6 days) was absent from the existing test suite. | Sahadeva finding from Step 12.5 |
| COV-12.5-02 | Bhima | Add filter dimension pass-through tests for the behavioral analytics endpoints (streaks, hold duration, exit type) — confirm each endpoint correctly filters by `account_id`, `direction`, `from_date`, `to_date`. One parametrized test per endpoint is sufficient. | Sahadeva finding from Step 12.5 |

**Order of work:** discharge obligations first, commit them, then proceed to M-6 and M-10. This keeps the obligation fix reviewable in isolation.

---

## Scope

### M-6 — R-Multiple Distribution

**What it is:** A histogram showing the distribution of closed trades across six R-multiple buckets. Answers "Am I cutting losses at 1R or letting them run to 2R+?"

**Backend (Bhima)**

- New endpoint: `GET /v1/analytics/r-distribution`
- Query parameters: same filter shape as existing analytics endpoints (`account_id`, `from_date`, `to_date`, `direction`, `trade_type`, `instrument_symbol`, `exchange_segment`, `setup_name`, `broker_name`, `exit_type`)
- Logic: query `trade_pnl.r_multiple` for CLOSED trades passing the filter. Bucket each value:
  - `lt_neg2` — R < −2
  - `neg2_to_neg1` — −2 ≤ R < −1
  - `neg1_to_0` — −1 ≤ R < 0
  - `0_to_1` — 0 ≤ R < +1
  - `1_to_2` — +1 ≤ R < +2
  - `gt2` — R ≥ +2
- Response: `{ buckets: [ { label, lower_bound, upper_bound, count } ], total_with_r: int, insufficient_sample: bool }`
- `insufficient_sample: true` when `total_with_r < 5` — frontend renders a "Not enough trades" placeholder instead of the chart
- Trades where `r_multiple IS NULL` (no planned stop) are excluded from all buckets; `total_with_r` counts only included trades
- No new migration required — all data is in `trade_pnl.r_multiple`

**Frontend (Arjun)**

- New component: `RDistributionCard` — a metric card housing the histogram
- Chart: horizontal bar chart (preferred for label legibility on mobile) or vertical bar chart — Arjun decides based on layout fit
- Each bar: bucket label, count, and percentage of `total_with_r`
- Insufficient sample guard: when `insufficient_sample: true`, show a `<EmptyState>` placeholder ("Need at least 5 trades with a planned stop to show R distribution")
- Respects active analytics filter (same `useAnalyticsFilters` hook driving all other cards)
- Placed in the analytics page layout between the existing metric cards and the Dimension Breakdown section

**Acceptance criteria for M-6:**

- [ ] `GET /v1/analytics/r-distribution` returns correct bucket counts for a seeded dataset
- [ ] All six buckets present in response even when count is 0
- [ ] `insufficient_sample: true` when fewer than 5 trades have a non-null R-multiple
- [ ] Filter parameters reduce the result set correctly (integration test: filter by direction)
- [ ] Frontend renders the chart with correct bar heights / count labels
- [ ] Frontend shows `EmptyState` when `insufficient_sample: true`
- [ ] Frontend respects active filter (changing direction filter updates the chart)

---

### M-10 — Full Dimension Breakdown

**What it is:** A breakdown table showing per-group performance metrics. Step 12.x already implemented Direction breakdown — this step generalises it to four additional dimensions.

**Backend (Bhima)**

- Existing endpoint: `GET /v1/analytics/breakdown` (or equivalent — confirm the actual route from Step 12 implementation)
- Extend to accept a `dimension` query parameter: `direction` (existing) | `setup` | `instrument` | `trade_type` | `segment`
- For each dimension, `GROUP BY` the corresponding column:
  - `direction` → `trades.direction`
  - `setup` → `trades.setup_name` (NULL → `"(no setup)"`, consistent with filter dimension convention)
  - `instrument` → `trades.instrument_symbol`
  - `trade_type` → `trades.trade_type`
  - `segment` → `trades.exchange_segment`
- Per-group metrics: `trade_count`, `win_count`, `win_rate`, `total_net_pnl`, `avg_net_pnl`, `avg_r_multiple` (NULL-safe avg), `avg_hold_duration_minutes`
- Respects the same filter parameters as all other analytics endpoints
- Response: `{ dimension, groups: [ { label, trade_count, win_count, win_rate, total_net_pnl, avg_net_pnl, avg_r_multiple, avg_hold_duration_minutes } ] }`
- Empty result: return `{ dimension, groups: [] }` — not a 404

**Frontend (Arjun)**

- New component: `DimensionBreakdownCard`
- Dimension selector: tab strip or dropdown — Direction | Setup | Instrument | TradeType | Segment
- Table columns: Dimension label | Trades | Wins | Win Rate | Total P&L | Avg P&L | Avg R | Avg Hold
- Sorted by `total_net_pnl` descending by default; column headers are sortable
- Empty state: "No trades match the current filter" when `groups` is empty
- Direction tab is selected by default (preserves existing Direction breakdown behavior)
- Respects active analytics filter

**Acceptance criteria for M-10:**

- [ ] `GET /v1/analytics/breakdown?dimension=setup` returns correct groups for seeded data with multiple setups
- [ ] NULL setup_name groups as `"(no setup)"`
- [ ] `dimension=instrument` groups by symbol correctly
- [ ] `dimension=trade_type` groups by trade type correctly
- [ ] `dimension=segment` groups by segment correctly
- [ ] Each dimension returns correct `win_rate`, `avg_r_multiple` (handles NULL R gracefully — NULL R trades excluded from avg, not treated as 0)
- [ ] Filter pass-through: `direction=LONG` filter reduces groups to LONG trades only (integration test)
- [ ] Frontend renders correct columns for each dimension selection
- [ ] Frontend re-fetches when dimension selector changes
- [ ] Frontend re-fetches when analytics filter changes
- [ ] Empty state renders when `groups` is empty

---

## Explicitly NOT in Step 12.6

| Item | Where it goes |
|------|--------------|
| Rolling Expectancy (N-1) | Step 12.7 |
| Time-of-Day performance (N-2) | Step 12.7 |
| Kelly Fraction (N-4) | Step 12.7 |
| Monte Carlo (N-3) | Phase 2 — blocked on background job infrastructure |
| Behavioral-P&L correlation deep analysis | Phase 2 (Vidura) |

---

## Work Breakdown by Owner

### Bhima — Backend

| # | Task | Notes |
|---|------|-------|
| B-1 | COV-12.5-01: add integration tests for all 5 hold-duration buckets | `multi_day` bucket coverage gap |
| B-2 | COV-12.5-02: filter pass-through tests for streaks, hold duration, exit type endpoints | One parametrized test per endpoint |
| B-3 | `GET /v1/analytics/r-distribution` — endpoint, query, bucketing logic | No migration needed |
| B-4 | Unit tests: bucket boundary correctness, NULL r_multiple exclusion, insufficient_sample guard | |
| B-5 | Integration tests: M-6 with seeded data; filter by direction reduces count | |
| B-6 | Extend `GET /v1/analytics/breakdown` to accept `dimension` parameter | Confirm existing route name before coding |
| B-7 | GROUP BY logic for all 5 dimensions; NULL-safe avg_r_multiple | NULL R excluded from avg, not zeroed |
| B-8 | Unit tests: per-dimension grouping, NULL setup_name → "(no setup)" | |
| B-9 | Integration tests: M-10 filter pass-through (direction filter on instrument breakdown) | |

**Commit sequence Bhima should follow:**
1. Commit: opening obligations (B-1, B-2) — keep reviewable in isolation
2. Commit: M-6 backend (B-3, B-4, B-5)
3. Commit: M-10 backend (B-6, B-7, B-8, B-9)

### Arjun — Frontend

| # | Task | Notes |
|---|------|-------|
| A-1 | OBS-12.3-01: RTL render assertion — FilterBar renders Instrument and Segment chips | MSW mock of filter dimension response |
| A-2 | `RDistributionCard` component — chart + empty state | |
| A-3 | Wire `RDistributionCard` to analytics page; respect active filter | |
| A-4 | RTL tests: chart renders correct bars; empty state renders on insufficient_sample | |
| A-5 | `DimensionBreakdownCard` component — dimension selector + table | |
| A-6 | Fetch logic: re-fetch on dimension change + filter change | |
| A-7 | Wire `DimensionBreakdownCard` to analytics page; Direction selected by default | |
| A-8 | RTL tests: dimension selector changes trigger re-fetch; table columns render; empty state | |

**Commit sequence Arjun should follow:**
1. Commit: OBS-12.3-01 (A-1) — obligation in isolation
2. Commit: M-6 frontend (A-2, A-3, A-4)
3. Commit: M-10 frontend (A-5, A-6, A-7, A-8)

---

## Key Technical Decisions (Pre-Aligned)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| M-6 chart orientation | Arjun decides (horizontal preferred) | Horizontal bars fit long bucket labels; Arjun owns frontend layout |
| M-10 UI control | Arjun decides (tab strip or dropdown) | Tab strip preferred for ≤5 dimensions; dropdown if layout is tight |
| M-10 default sort | `total_net_pnl` descending | Most actionable view first |
| NULL R-multiple in M-10 avg | Exclude from avg (not zero) | Zeroing NULL R would distort the average downward — trades without a stop are not 0R losers |
| NULL setup_name grouping | `"(no setup)"` | Consistent with existing filter dimension convention from Step 12.4 |
| Insufficient sample threshold | `total_with_r < 5` | Below 5 trades the distribution is too sparse to be meaningful |

---

## Gate Criteria

### Sahadeva — QA Gate

Sahadeva will block acceptance if any of the following are absent:

- [ ] OBS-12.3-01 covered by a render assertion test (RTL + MSW)
- [ ] COV-12.5-01 covered — all 5 hold-duration buckets tested in integration
- [ ] COV-12.5-02 covered — filter pass-through tested per behavioral endpoint
- [ ] M-6: backend unit + integration tests present; frontend RTL tests present
- [ ] M-10: backend unit + integration tests present; frontend RTL tests present (all 5 dimensions)
- [ ] `tsc --noEmit` clean
- [ ] `ruff check` clean
- [ ] All existing tests still passing (no regression)

**Sahadeva verdict format:** "Go" / "Go with risks [list]" / "No Go"

### Nakula — CI Gate

- [ ] GitHub Actions CI passes on the step branch
- [ ] All backend tests GREEN (`pytest`)
- [ ] All frontend tests GREEN (`vitest`)
- [ ] `tsc` clean
- [ ] `ruff` clean
- [ ] No new migration (confirm before closing — if Bhima introduces one, Nakula verifies it runs cleanly in CI)

### Yudhishthira — Acceptance

Yudhishthira will ACCEPT when:

- [ ] R-Multiple Distribution renders with correct data on the analytics page (demo with seeded trades)
- [ ] Insufficient-sample guard works (demo with < 5 R-multiple trades)
- [ ] Dimension Breakdown renders for all 5 dimensions
- [ ] Switching dimensions updates the table
- [ ] Filter changes update both M-6 and M-10
- [ ] Sahadeva GO recorded
- [ ] Nakula CI GREEN recorded

---

## Branch and Commit Convention

| Item | Value |
|------|-------|
| Branch | `feat/step-12-6-analytics-completion` |
| Base branch | `feat/step-12-5-behavioral-analytics` |
| Merge target | `main` (via PR, after Yudhishthira ACCEPT) |
| Commit prefix | `feat(step-12.6):` for features, `test(step-12.6):` for obligation tests |

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Existing breakdown endpoint doesn't support `dimension` param cleanly — requires a refactor | Medium | Low | Bhima reads existing implementation before designing; if the endpoint is tightly coupled to Direction, a new generic endpoint is acceptable — do not contort existing code |
| M-10 dimension table becomes wide on mobile | Low | Low | Arjun: horizontal scroll inside the card container; do not break the page layout |
| `avg_r_multiple` for setups with all NULL r_multiple returns NULL → frontend crashes | Medium | Medium | Bhima: return `null` explicitly in JSON; Arjun: render "—" for null avg R, not 0 or NaN |
| Opening obligation tests reveal a real bug in existing code | Low | Medium | Fix the bug in the obligation commit; do not suppress it. If fix is non-trivial, surface to Krishna before proceeding |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Backend test count | ≥ 457 + ~15 new tests (obligations + M-6 + M-10) |
| Frontend test count | ≥ 141 + ~10 new tests |
| Backend coverage | Maintain ≥ 84% |
| Frontend coverage | Maintain ≥ 84% |
| tsc errors | 0 |
| ruff violations | 0 |

---

## Sequence of Events

```
Bhima: obligations (COV-12.5-01, COV-12.5-02) — commit
Arjun: obligation (OBS-12.3-01) — commit (parallel with Bhima)
         ↓
Bhima: M-6 backend — commit
Arjun: M-6 frontend — commit (parallel with Bhima M-6)
         ↓
Bhima: M-10 backend — commit
Arjun: M-10 frontend — commit (parallel with Bhima M-10)
         ↓
Sahadeva: review all obligations + M-6 + M-10 → GO / No Go
         ↓
Nakula: CI GREEN
         ↓
Yudhishthira: ACCEPT → merge to main → update PHASE-1-MVP-EXECUTION-PLAN.md
```

---

## On Close — Required Actions

When Yudhishthira accepts Step 12.6:

1. Update `PHASE-1-MVP-EXECUTION-PLAN.md`: mark Step 12.6 ✅ with acceptance date
2. Update `memory/project_step12_analytics.md`: Step 12.6 status, new test totals, any lessons
3. Open Step 12.7 plan (Rolling Metrics: N-1, N-2, N-4) — or begin Step 14 (Navigation shell) in parallel per the execution sequence

---

*Krishna — Senior Project Manager*  
*Parent plan: `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`*  
*Step owners: Bhima (backend), Arjun (frontend), Sahadeva (QA), Nakula (CI/CD), Yudhishthira (acceptance)*
