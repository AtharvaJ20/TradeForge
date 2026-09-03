# ADR-007A: Step 12.1 Addendum — Sharpe & Sortino Risk-Adjusted Metrics

**Status:** Accepted
**Author:** Mayasura
**Date:** 2026-09-03
**Amends:** ADR-007 (Step 12 Analytics Layer Architecture)
**Context inputs:** Karna STEP-12-ANALYTICS-SPEC.md (M-8, M-9) · Yudhishthira Step 12 acceptance decision (D-1, D-2) · Krishna Step 12.1 delivery plan

---

## Why This Addendum Exists

### Root Cause of the Omission

ADR-007 defined 14 must-have analytics metrics across 8 endpoints. The count of 14 was correct. The composition was not. Karna's authoritative spec (STEP-12-ANALYTICS-SPEC.md) lists:

- **M-8 Sharpe Ratio** (Trade-Based): `(mean_return / std_return) × √N_per_year`
- **M-9 Sortino Ratio** (Trade-Based): `(mean_return / downside_dev) × √N_per_year`

When ADR-007 was authored, Karna's M-7 (Equity Curve + MDD) was split into two ADR-007 entries:
- ADR-007 M-7 = Equity Curve
- ADR-007 M-8 = Drawdown (previously co-located with M-7 in Karna's spec)

This split consumed one index slot. Karna's M-10 (Dimension Breakdown, with 5 sub-dimensions) was simultaneously split:
- ADR-007 M-9 = By Setup
- ADR-007 M-10 = By Direction

This consumed a second slot. The two splits together displaced Karna's M-8 and M-9 from the numbered sequence, and no corresponding entries were added elsewhere. The metric count reached 14 without Sharpe or Sortino. The omission was not a deliberate deferral — there is no statement in ADR-007 that Sharpe and Sortino were deferred to Phase 2. They were absent from the metric-to-layer table and therefore not built.

Yudhishthira identified this gap during Step 12 product acceptance review and classified both as P1 deferred obligations: **they must be present before any frontend analytics work begins.**

This addendum corrects the gap. It does not change the Step 12 implementation already shipped. It adds two domain functions, two result types, and extends the existing `/summary` response with a `risk_adjusted` sub-object.

---

## Decisions

### Decision 1 — Endpoint Placement: Extend `/summary`, not a new endpoint

**Options considered:**

| Option | Pros | Cons |
|---|---|---|
| **A: Extend `/summary` with `risk_adjusted` sub-object** | Zero new DB queries (data already in scope); Sortino is "preferred primary metric" — belongs alongside expectancy on the dashboard; additive non-breaking change | `/summary` response grows by two metric objects |
| **B: New `/risk-adjusted` endpoint** | Clean separation; independently fetchable | Requires 9th endpoint; frontend must make a second call to render the main dashboard; forces a second round-trip for what is a first-class dashboard metric |

**Decision: Option A.**

The `get_summary()` method in `AnalyticsService` already calls `get_r_multiple_series(f)`, which returns `win_r: Sequence[Decimal]` and `loss_r: Sequence[Decimal]` for the expectancy calculation. Sharpe and Sortino require exactly the same data combined: `all_r = list(win_r) + list(loss_r)`. This means the new calculators receive data already fetched — no new repository method, no second SQL round-trip, no additional DB connection time.

Karna described Sortino as "Preferred primary risk-adjusted metric for TradeForge users." A primary metric belongs on the main summary dashboard, co-located with expectancy, win rate, and profit factor — not behind a second API call. Placing it in `/summary` is correct at both the API semantics level and the UX level.

Adding `risk_adjusted` to `AnalyticsSummaryResponse` is a non-breaking additive change. Existing frontend clients that ignore unknown fields (the standard pattern) are unaffected.

**The endpoint table in ADR-007 §G is updated as follows:**

| Endpoint | Metrics |
|---|---|
| `GET /v1/analytics/summary` | M-1, M-2, M-3, M-4, M-5, M-8, M-10, M-11, **M-8K (Sharpe), M-9K (Sortino)** |
| `GET /v1/analytics/equity-curve` | M-7 |
| `GET /v1/analytics/r-distribution` | M-6 |
| `GET /v1/analytics/by-setup` | M-9 |
| `GET /v1/analytics/streaks` | M-12 |
| `GET /v1/analytics/hold-duration` | M-13 |
| `GET /v1/analytics/by-exit-type` | M-14 |
| `GET /v1/analytics/monte-carlo` | N-3 |

*Notation: M-8K / M-9K = Karna's original numbering, to distinguish from ADR-007 M-8 (Drawdown) and M-9 (By Setup).*

---

### Decision 2 — Metric-to-Layer Assignment (addendum rows)

The ADR-007 §E table is extended with two new rows:

| Metric | SQL Strategy | Python (domain/service) |
|---|---|---|
| **M-8K Sharpe Ratio** | Reuses r_multiple series already fetched for M-3 expectancy | `compute_sharpe_ratio()` in `domain/analytics/calculators.py`; called from `get_summary()` |
| **M-9K Sortino Ratio** | Reuses r_multiple series already fetched for M-3 expectancy | `compute_sortino_ratio()` in `domain/analytics/calculators.py`; called from `get_summary()` |

**No new repository method is required.** The application layer combines the already-fetched `win_r` and `loss_r` sequences and passes them to the domain calculators. Zero additional SQL.

The data flow inside `get_summary()` becomes:

```
win_r, loss_r = await self._repo.get_r_multiple_series(f)
expectancy    = compute_expectancy(win_r, loss_r, total_count)   # existing
all_r         = list(win_r) + list(loss_r)                       # NEW — no DB hit
sharpe        = compute_sharpe_ratio(all_r, n_per_year=252)      # NEW
sortino       = compute_sortino_ratio(all_r, n_per_year=252)     # NEW
```

---

### Decision 3 — Domain Result Types

Two new frozen dataclasses are added to `domain/analytics/types.py`. A third wraps them for the service layer.

```python
@dataclass(frozen=True)
class SharpeResult:
    sharpe_ratio: Decimal | None         # None when insufficient_sample or std_r == 0
    mean_r: Decimal | None               # mean R-multiple across all trades in filter
    std_r: Decimal | None                # population std-dev of R-multiples
    n_per_year: int                      # annualization factor (default 252)
    r_coverage_count: int                # number of trades with r_multiple populated
    insufficient_sample: bool            # True when r_coverage_count < 30


@dataclass(frozen=True)
class SortinoResult:
    sortino_ratio: Decimal | None        # None when insufficient_sample or downside_dev == 0
    mean_r: Decimal | None               # mean R-multiple across all trades in filter
    downside_dev: Decimal | None         # std-dev of trades where r_multiple < 0
    n_per_year: int                      # annualization factor (default 252)
    r_coverage_count: int                # number of trades with r_multiple populated
    insufficient_sample: bool            # True when r_coverage_count < 30
    no_downside_trades: bool             # True when no trades have r_multiple < 0


@dataclass(frozen=True)
class RiskAdjustedResult:
    sharpe: SharpeResult
    sortino: SortinoResult
```

`AnalyticsSummary` (in `domain/analytics/types.py`) gains one new field:

```python
risk_adjusted: RiskAdjustedResult
```

`AnalyticsSummaryResponse` (in `api/v1/analytics.py`) gains a corresponding Pydantic field.

---

### Decision 4 — Domain Calculator Contracts

#### `compute_sharpe_ratio`

```python
def compute_sharpe_ratio(
    r_multiples: Sequence[Decimal],
    *,
    n_per_year: int = 252,
) -> SharpeResult:
    """Compute trade-based Sharpe Ratio.

    Formula: (mean_r / std_r) × √n_per_year
    Karna M-8. Min sample: 30 trades with r_multiple populated.

    Returns sharpe_ratio=None when:
      - r_coverage_count < 30 (insufficient_sample=True)
      - std_r == 0 (all trades have identical R-multiple — undefined ratio)
    """
```

Standard deviation used: **population std-dev** (divide by N, not N-1). Rationale: we are computing the descriptive statistic of the actual trades in the filter, not estimating a population parameter. This is consistent with how `STDDEV_POP` is used elsewhere in the analytics SQL.

#### `compute_sortino_ratio`

```python
def compute_sortino_ratio(
    r_multiples: Sequence[Decimal],
    *,
    n_per_year: int = 252,
) -> SortinoResult:
    """Compute trade-based Sortino Ratio.

    Formula: (mean_r / downside_dev) × √n_per_year
    Karna M-9. Min sample: 30 trades with r_multiple populated.
    Downside: trades where r_multiple < 0 (strict negative; MAR = 0).

    Returns sortino_ratio=None when:
      - r_coverage_count < 30 (insufficient_sample=True)
      - no trades have r_multiple < 0 (no_downside_trades=True; downside_dev=0)
    """
```

**Downside deviation definition:** std-dev of trades where `r_multiple < 0` (MAR = 0, strictly negative). Breakeven trades (`r_multiple = 0`) are excluded from downside. Rationale: consistent with Karna's G-CORR-01 strict win/loss classification; a breakeven trade is not a losing trade and should not inflate downside risk.

**Ganesha confirmation pending on two parameters:**
1. `n_per_year = 252` — provisional. Ganesha must confirm whether 252 (standard finance convention) or a user-specific trades-per-year average is the canonical value for TradeForge's trade-based formulas. If Ganesha specifies a different value, Bhima changes the default — the function signature is designed to accept it as a parameter.
2. MAR = 0 (strict negative) — provisional. Ganesha may specify MAR > 0 if there is a domain reason. The formula is parameterized; the default is 0.

**Bhima must not start implementation until Ganesha has confirmed both parameters in writing.** This is a hard gate per Krishna's Step 12.1 delivery plan.

---

### Decision 5 — Failure Modes and Guards

| Condition | Sharpe behaviour | Sortino behaviour |
|---|---|---|
| `r_coverage_count < 30` | `sharpe_ratio=None`, `insufficient_sample=True` | `sortino_ratio=None`, `insufficient_sample=True` |
| All R-multiples identical (std_r = 0) | `sharpe_ratio=None`, `std_r=Decimal("0")` | Unaffected (downside_dev is computed from losses only) |
| No losing trades (downside_dev = 0) | Unaffected | `sortino_ratio=None`, `no_downside_trades=True`, `downside_dev=None` |
| No R-multiples at all (empty series) | `sharpe_ratio=None`, `insufficient_sample=True`, all fields None | Same |

The `no_downside_trades=True` flag is a distinct signal for the frontend: a user who never lost money deserves a clear message ("no losing trades in filter"), not a generic "insufficient data" message.

---

## Layer Boundary Confirmation

The boundary rule from ADR-007 §B is unchanged. No new layers, no new files beyond what is listed.

**Files touched in Step 12.1:**

| File | Change |
|---|---|
| `domain/analytics/types.py` | Add `SharpeResult`, `SortinoResult`, `RiskAdjustedResult`; add `risk_adjusted` field to `AnalyticsSummary` |
| `domain/analytics/calculators.py` | Add `compute_sharpe_ratio()`, `compute_sortino_ratio()` |
| `application/analytics_service.py` | Extend `get_summary()`: combine `win_r + loss_r`, call both new calculators, include `risk_adjusted` in returned `AnalyticsSummary` |
| `api/v1/analytics.py` | Add `SharpeResult`, `SortinoResult`, `RiskAdjustedResult` Pydantic response models; add `risk_adjusted` field to `AnalyticsSummaryResponse` |
| `tests/unit/domain/test_analytics_calculators.py` | Add TC-SR and TC-SO test classes |
| `tests/integration/api/test_analytics.py` | Extend summary endpoint integration tests to assert `risk_adjusted` shape and `insufficient_sample` behaviour |

**Files not touched:**
- `infrastructure/repositories/analytics_repo.py` — no new query
- `alembic/versions/` — no migration (pure compute, no schema change)
- All other analytics files

---

## Hard Boundaries (unchanged from ADR-007)

These boundaries from ADR-007 §Hard Boundaries apply equally to Step 12.1:

- No MAE/MFE (G-DEFER-01 prohibition stands)
- No Redis caching of analytics results
- No materialized views
- No Celery tasks for Sharpe or Sortino computation
- Analytics layer owns zero writes to any table

---

## Consequences

**What becomes easier:**
- Frontend has Sharpe and Sortino available from the same `/summary` call it already makes — no new API integration work.
- Both calculators are pure domain functions — unit-testable without infrastructure, consistent with ADR-001 and ADR-007 §D.
- Zero SQL added — performance characteristics of `/summary` are unchanged.

**What becomes harder:**
- `AnalyticsSummary` now has nine top-level fields. The pattern remains consistent (each field is a typed result dataclass), but the summary object is larger. If more primary metrics are added in future steps, a sub-grouping of `AnalyticsSummary` should be considered.

**Risk accepted:**
- `n_per_year = 252` is provisional until Ganesha confirms. If Ganesha specifies a different value, all existing test fixtures for TC-SR and TC-SO must be updated. This is a low-risk edit but must be tracked as an open item until confirmed.

---

## Open Items (Ganesha confirmations required before Phase 1 implementation)

| # | Item | Owner | Due |
|---|---|---|---|
| G-CONF-12.1-A | Confirm `n_per_year` canonical value (provisional: 252) | Ganesha | Before Bhima Phase 1 start |
| G-CONF-12.1-B | Confirm Sortino downside definition: MAR = 0, strictly `r < 0` (provisional: confirmed) | Ganesha | Before Bhima Phase 1 start |

---

*Mayasura · Senior Software Architect · 2026-09-03*
*Addendum to ADR-007 (2026-09-02). ADR-007 remains Accepted and is not superseded.*
