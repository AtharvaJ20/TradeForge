# ADR-007: Step 12 Analytics Layer Architecture

**Status:** Accepted  
**Author:** Mayasura  
**Date:** 2026-09-02  
**Inputs:** Karna WS-0.A (STEP-12-ANALYTICS-SPEC.md) · Ganesha WS-0.B (GANESHA-STEP12-DOMAIN-VALIDATION.md)  
**Incorporates:** G-CORR-01, G-CORR-02, G-CORR-03  

---

## Verdict

**Architecture approved — conditional on six pre-implementation requirements (see § Pre-Implementation Conditions).**

---

## Context

Step 12 adds 14 must-have analytics metrics to TradeForge. These metrics are pure read operations against authoritative data produced by Steps 10 (P&L engine) and 11 (trading accounts). The architecture question is: how does the analytics layer fit into the four-layer clean architecture (ADR-001), what new SQL infrastructure is required, and what is the explicit layer boundary before Bhima writes code?

---

## Assumptions

- Retail Indian traders. Power users: 2,000–5,000 closed trades. Upper bound Phase 1: 10,000 trades per user.
- All 14 metrics compute in ≤ 100 ms at this data volume with proper indexes.
- Materialized views and Redis caching are Phase 2 concerns.
- Eventual consistency is acceptable: analytics read live data; a newly imported trade that has not yet had P&L computed simply does not appear (filtered by `status = 'CLOSED'` + trade_pnl JOIN).

---

## Decision

### A. Dedicated AnalyticsService — not an extension of existing services

Step 12 analytics are read-only aggregate queries producing non-entity responses. Mixing them into `PnlService`, `JournalService`, or `TradingAccountService` would violate single responsibility. A dedicated `AnalyticsService` owns all analytics orchestration.

### B. Explicit Layer Boundary

| Layer | New File | Responsibility |
|---|---|---|
| **API** | `api/v1/analytics.py` | FastAPI router; Pydantic query-param → `AnalyticsFilter`; Pydantic response models |
| **Application** | `application/analytics_service.py` | Orchestrates repo + domain calculators; applies G-CORR-03 charge-drag suppression |
| **Domain** | `domain/analytics/types.py` | `AnalyticsFilter` frozen dataclass (9 filter dimensions); metric result dataclasses |
| **Domain** | `domain/analytics/calculators.py` | Pure functions: expectancy from components, streak counter, drawdown series, Monte Carlo |
| **Infrastructure** | `infrastructure/repositories/analytics_repo.py` | All SQL; parameterized WHERE clauses from `AnalyticsFilter`; no business logic |

ADR-001 boundary rule is non-negotiable: domain layer has zero imports from FastAPI, SQLAlchemy, or any other framework.

### C. AnalyticsFilter Domain Object

```python
# domain/analytics/types.py
@dataclass(frozen=True)
class AnalyticsFilter:
    user_id: UUID
    date_from: date | None = None
    date_to:   date | None = None
    account_ids:        tuple[UUID, ...] = field(default_factory=tuple)
    instrument_types:   tuple[str,  ...] = field(default_factory=tuple)
    exchange_segments:  tuple[str,  ...] = field(default_factory=tuple)
    trade_types:        tuple[str,  ...] = field(default_factory=tuple)
    directions:         tuple[str,  ...] = field(default_factory=tuple)
    setup_names:        tuple[str,  ...] = field(default_factory=tuple)
    brokers:            tuple[str,  ...] = field(default_factory=tuple)
```

Frozen + tuples = hashable. Enables future cache keying on `hash(filter)` without API changes.

### D. Query Pattern — Base WHERE Clause

Every analytics query shares a common base predicate built by `AnalyticsRepository`:

```sql
FROM  trades t
JOIN  trade_pnl tp  ON  tp.trade_id = t.id
WHERE t.user_id = :user_id
  AND t.status  = 'CLOSED'
  AND (:date_from IS NULL OR t.trade_date >= :date_from)
  AND (:date_to   IS NULL OR t.trade_date <= :date_to)
  AND (:account_ids       = '{}'::uuid[] OR t.account_id  = ANY(:account_ids))
  AND (:trade_types       = '{}'::text[] OR t.trade_type  = ANY(:trade_types))
  AND (:directions        = '{}'::text[] OR t.direction   = ANY(:directions))
  AND (:setup_names       = '{}'::text[] OR t.setup_name  = ANY(:setup_names))
  AND (:brokers           = '{}'::text[] OR tp.broker     = ANY(:brokers))
  -- instrument_type / exchange_segment require instruments JOIN (appended when non-empty)
```

### E. Metric-to-Layer Assignment

| Metric | SQL Strategy | Python (domain/service) |
|---|---|---|
| M-1 Total P&L | SUM aggregates on trade_pnl | None |
| M-2 Win Rate | COUNT(CASE WHEN net_pnl > 0/< 0/= 0) — G-CORR-01 | Rate division |
| M-3 Expectancy | AVG(r_multiple) per win/loss group | Expectancy formula in calculators.py |
| M-4 Profit Factor | SUM(positive net_pnl) / ABS(SUM(negative)) | Zero-loss edge case in service |
| M-5 Avg R:R | AVG((planned_target − avg_entry) / (avg_entry − planned_stop)) | None |
| M-6 R-Distribution | AVG, STDDEV, percentile_cont() | Histogram bins in service |
| M-7 Equity Curve | Window SUM(net_pnl) ORDER BY trade_date, last_fill_at, id | Drawdown series in calculators.py |
| M-8 Drawdown | Reuses M-7 rows | MDD, duration in calculators.py |
| M-9 By Setup | GROUP BY setup_name | None |
| M-10 By Direction | GROUP BY direction | None |
| M-11 Charges | SUM per charge column + SUM(gross_pnl) | G-CORR-03 suppression in service |
| M-12 Streaks | SELECT net_pnl ordered | Streak counter in calculators.py |
| M-13 Hold Duration | EXTRACT(EPOCH) with CASE bucket | None |
| M-14 Exit Type | DISTINCT ON (trade_id) ORDER BY fill_timestamp DESC CTE — G-CORR-02 | None |
| N-3 Monte Carlo | SELECT r_multiple ordered | Full simulation in calculators.py |

### F. New DB Indexes Required

**1. `idx_trades_analytics` on `trades (user_id, status, trade_date)`**

Every analytics query's base predicate is `user_id = X AND status = 'CLOSED' AND trade_date BETWEEN Y AND Z`. The existing `idx_trades_user_status` covers `(user_id, status)` but does not include `trade_date` — the planner heap-scans closed trades for the date range. This composite index turns all 14 base queries into index-range scans.

```sql
CREATE INDEX idx_trades_analytics ON trades (user_id, status, trade_date);
```

**2. `idx_fills_exit_by_trade` (partial) on `execution_fills (trade_id, fill_timestamp DESC) WHERE fill_role = 'EXIT'`**

M-14 uses `DISTINCT ON (trade_id) ORDER BY trade_id, fill_timestamp DESC` scoped to `fill_role = 'EXIT'`. Without this partial index, PostgreSQL scans all fills. The partial index pre-filters to exit fills and stores them in the required order — the DISTINCT ON becomes an index scan with no sort step.

```sql
CREATE INDEX idx_fills_exit_by_trade
  ON execution_fills (trade_id, fill_timestamp DESC)
  WHERE fill_role = 'EXIT';
```

**No materialized views.** At ≤ 10,000 closed trades per user, real-time computation with these indexes is sufficient. Materialized views require invalidation on every import, P&L recalculation, and trade edit — fragility with no measurable gain.

### G. Endpoint Structure

Dedicated `/v1/analytics` router. Analytics endpoints return aggregate results and distributions, not entity resources — separate from `/v1/trades`.

| Endpoint | Metrics |
|---|---|
| `GET /v1/analytics/summary` | M-1, M-2, M-3, M-4, M-5, M-8, M-10, M-11 |
| `GET /v1/analytics/equity-curve` | M-7 |
| `GET /v1/analytics/r-distribution` | M-6 |
| `GET /v1/analytics/by-setup` | M-9 |
| `GET /v1/analytics/streaks` | M-12 |
| `GET /v1/analytics/hold-duration` | M-13 |
| `GET /v1/analytics/by-exit-type` | M-14 |
| `GET /v1/analytics/monte-carlo` | N-3 |

All endpoints accept the same 9 global filter query parameters. A shared FastAPI dependency function maps them to `AnalyticsFilter`.

### H. No Celery Required

Monte Carlo on ≤ 5,000 r_multiple values with 1,000 simulations using `stdlib random.choices` runs in ~30–150 ms synchronously. It meets neither BackgroundTasks condition (it is user-observable synchronously; it is fast). Phase 2 flag: if P95 latency exceeds 500 ms at >10,000 trades, move to Celery task. Domain function signature stays unchanged — only execution context changes.

---

## Pre-Implementation Conditions

Bhima must satisfy all six before writing `AnalyticsService` or `AnalyticsRepository`:

1. **`AnalyticsFilter` domain dataclass created first.** No SQL or service code may reference filter fields directly.
2. **Two Alembic migrations committed before service is tested against real data.** `idx_trades_analytics` and `idx_fills_exit_by_trade`.
3. **All SQL confined to `AnalyticsRepository`.** No raw SQL in `AnalyticsService`.
4. **Domain calculators are pure functions in `domain/analytics/calculators.py` with domain-layer unit tests** that run without a DB connection.
5. **G-CORR-03 charge drag suppression is Python in `AnalyticsService`, not SQL.**
6. **G-CONF-01 unit test for short-trade planned R:R** added before M-5 is used in analytics.

---

## Hard Boundaries — Not in Phase 1

- MAE/MFE: formally prohibited by Ganesha (G-DEFER-01). Requires OHLC bar feed.
- Redis caching of analytics results.
- Materialized views.
- Celery tasks for any analytics metric.
- Analytics writes: the analytics layer owns zero writes to any table.

---

## Consequences

**What becomes easier:**
- Bhima has a clear build sequence (domain types → domain calculators → migration → repo → service → API).
- Domain calculators are fully testable without infrastructure.
- The `AnalyticsFilter` hashable design enables future Redis caching with no API changes.
- The partial index on fills makes M-14 fast without scanning the full fills table.

**What becomes harder:**
- Bhima must resist the temptation to put post-processing logic in SQL (expectancy, streak counting, charge drag) — those belong in Python.
- The instruments JOIN condition (only when instrument-dimension filters are non-empty) requires conditional query building in the repo.

**Technical debt accepted:**
- The broker filter is on `trade_pnl.broker`, not `trades`. This requires a JOIN to `trade_pnl` even for queries that don't need P&L data (e.g., a future count query). Acceptable at Phase 1 — revisit if the trades table grows a `broker` column.

---

## Bhima Handoff Sequence

| Deliverable | Layer | Order |
|---|---|---|
| `domain/analytics/types.py` | Domain | 1 |
| `domain/analytics/calculators.py` + unit tests | Domain | 2 |
| Alembic migration: two new indexes | Infrastructure | 3 |
| `infrastructure/repositories/analytics_repo.py` | Infrastructure | 4 |
| `application/analytics_service.py` | Application | 5 |
| `api/v1/analytics.py` + Pydantic schemas + `main.py` registration | API | 6 |

---

*Mayasura · Senior Software Architect · 2026-09-02*
