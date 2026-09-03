# Ganesha Domain Confirmations — Step 12.1 Sharpe & Sortino

**Reviewer:** Ganesha (Trading Domain Analyst)
**Date:** 2026-09-03
**Requested by:** ADR-007A (Mayasura, 2026-09-03) open items G-CONF-12.1-A and G-CONF-12.1-B
**Context:** Krishna Step 12.1 delivery plan — two domain parameters required before Bhima begins implementation

---

## Summary

| Confirmation | Subject | Decision |
|---|---|---|
| **G-CONF-12.1-A** | `N_per_year` annualization factor for trade-based Sharpe and Sortino | **252 (fixed convention)** |
| **G-CONF-12.1-B** | Sortino downside deviation definition — MAR and strict/inclusive boundary | **MAR = 0; strictly `r < 0`; breakeven trades excluded** |

Both decisions are authoritative. Bhima may begin Phase 1 implementation. No further domain gating is required for Step 12.1.

---

## G-CONF-12.1-A — Annualization Factor `N_per_year`

### The Question

Karna's M-8 and M-9 formulas include `× √N_per_year`. Mayasura's ADR-007A specified a provisional default of 252. Ganesha is asked to confirm the canonical value.

Three candidate approaches were evaluated:

| Approach | Formula | Problem |
|---|---|---|
| **Fixed 252** | Always annualize as if 252 trades per year | Distorts ratios for traders with very high or very low trade frequency |
| **Dynamic — actual trades/year** | `n_per_year = r_coverage_count × (252 / trading_days_in_filter)` | Requires date range in domain calculator; Sharpe changes with filter window |
| **No annualization** | Report raw `mean_r / std_r` without `√N` | Breaks comparability with industry-standard Sharpe conventions |

### Domain Analysis

**What does `N_per_year` actually do for a trade-based Sharpe?**

For time-series returns (daily, weekly), `× √N_per_year` scales a per-period return ratio up to an annualized equivalent, enabling comparison against benchmark Sharpes (e.g., a stock index at 0.5–1.0 annually). The derivation is:

```
Annual mean   = mean_r × N
Annual std    = std_r × √N
Annual Sharpe = (mean_r × N) / (std_r × √N) = (mean_r / std_r) × √N
```

For **trade-based** Sharpe, N is the number of trades per year — the rate at which the system generates observations. A trader who takes 500 trades per year has N = 500; a swing trader with 40 trades per year has N = 40. If N is set dynamically per user, Sharpes become non-comparable across users and even across filter periods for the same user.

**The core problem with dynamic N:** a user narrowing their filter to a 3-month window would see their Sharpe artificially deflated relative to the full-year view, because the same filter that reduces trade count also changes N. This creates a confusing experience where "which date range should I use?" becomes a question that changes the metric's meaning, not just its sample.

**The core problem with no annualization:** TradeForge users may eventually compare their performance to published Sharpe benchmarks (funds, indices). The unadjusted `mean_r / std_r` is not the Sharpe ratio by any convention — it is the coefficient of variation of R-multiples. It is a valid metric but should be named differently.

**Why 252 is correct for TradeForge:**

1. **NSE alignment:** NSE trading days per calendar year average 250–252 across recent years. The 252 convention (the same used by US and international equity markets) is numerically consistent with Indian market reality.

2. **Comparability is the purpose of annualization.** 252 as a fixed convention allows the Sharpe reported for a user's January filter to be directly compared to the Sharpe for their full-year view — the scale is the same. Dynamic N destroys this comparability.

3. **Industry precedent:** Every major trading analytics platform (QuantConnect, Alphalens, pyfolio, Zipline) uses a fixed annualization factor regardless of actual strategy trade frequency. The convention trades mathematical precision for cross-user, cross-period comparability. This is the right trade for a journal product.

4. **The domain function is already parameterized.** ADR-007A's function signature accepts `n_per_year: int = 252`. If TradeForge later introduces personalized annualization (e.g., based on a user's average annual trade count over their history), the application layer passes a different value — the domain function does not change.

### Decision: G-CONF-12.1-A

**`N_per_year = 252` — fixed convention, NSE-aligned.**

Bhima passes `n_per_year=252` from `AnalyticsService.get_summary()` to both `compute_sharpe_ratio()` and `compute_sortino_ratio()`. This value is not stored in the database and is not user-configurable in Phase 1.

**Phase 2 note (not a Phase 1 concern):** If user research reveals that traders are confused by a fixed annualization when their filter spans only 2 weeks, Ganesha will revisit. The design supports dynamic N without structural change.

---

## G-CONF-12.1-B — Sortino Downside Deviation Definition

### The Question

Sortino's denominator is the downside deviation — the standard deviation of returns that fall below a minimum acceptable return (MAR). Two definitions are in common use:

- **Option 1 — Strict negative:** `r < 0` only. A trade where `r_multiple < 0` is downside. Breakeven (`r = 0`) is not downside.
- **Option 2 — Below-MAR inclusive:** `r ≤ MAR` for some MAR ≥ 0. With MAR = 0, this includes breakeven trades (`r = 0`) in the downside calculation.

### Domain Analysis

**The domain meaning of `r_multiple = 0` for a trader:**

A breakeven trade is one where `net_pnl = 0` — the trader exited at exactly their average entry price, net of charges. G-CORR-01 established that this is a **third outcome class** distinct from wins and losses. It is not a loss. The trader did not lose money. The capital at risk was recovered in full.

Treating a breakeven trade as "downside" overstates the system's risk profile. A trading system that takes 100 trades — 50 wins, 10 breakevens, 40 losses — with MAR-inclusive Sortino would penalize the 10 breakevens as if they were losses. This penalizes risk discipline: a trader who closes a marginal trade at breakeven (rather than letting it become a loss) would see their Sortino artificially reduced.

**Practical consideration — how the data flows:**

The existing `get_r_multiple_series(f)` repository method returns two sequences:
- `win_r`: R-multiples for trades where `net_pnl > 0` (strictly positive, `r > 0`)
- `loss_r`: R-multiples for trades where `net_pnl < 0` (strictly negative, `r < 0`)

Breakeven trades produce `net_pnl = 0`, which means:
1. They are excluded from both `win_r` and `loss_r`
2. Their `r_multiple` value, if set, would be `≈ 0` but is not returned by the existing query

When Bhima constructs `all_r = list(win_r) + list(loss_r)` in `get_summary()`, breakeven R-multiples are structurally absent from the combined series. The downside calculation on `loss_r` therefore already excludes breakevens — the G-CONF-12.1-B ruling formalizes what the data model naturally produces.

**The `no_downside_trades` flag:**

A trader in a filter period where every trade is a win or breakeven — no losses at all — would produce `loss_r = []`, meaning `downside_dev = 0`. Dividing by zero produces an undefined Sortino. The ADR-007A type design correctly handles this with `no_downside_trades: bool = True` and `sortino_ratio = None`.

This is not an edge case for exceptional traders — it is a realistic scenario for any user who filters to a narrow "best week" window. The flag must be implemented and surfaced to the frontend with a meaningful message.

### Decision: G-CONF-12.1-B

**MAR = 0; strictly `r < 0`; breakeven trades excluded from downside deviation.**

Downside deviation is the population standard deviation of R-multiples in `loss_r` (trades where `net_pnl < 0`, which means `r_multiple < 0`). Breakeven trades are excluded. This is consistent with G-CORR-01's strict classification and with the existing data structure of `get_r_multiple_series()`.

The implementation consequence for `compute_sortino_ratio()`:

```
# all_r = list(win_r) + list(loss_r)  ← breakevens already absent
# Downside is the loss_r subset only

downside_vals = [r for r in all_r if r < Decimal("0")]  # equivalent to loss_r
```

Because `all_r` already contains no breakeven trades (they are excluded by the SQL query), the filter `r < 0` on `all_r` is equivalent to using `loss_r` directly. Either implementation is correct. Bhima may use whichever is cleaner — Ganesha's ruling is on the domain definition, not the Python expression.

---

## Implementation Constraints Arising From These Decisions

These are binding constraints for Bhima's Phase 1 implementation:

| Constraint | Source |
|---|---|
| `compute_sharpe_ratio(r_multiples, *, n_per_year: int = 252)` — 252 is the only permitted default | G-CONF-12.1-A |
| `compute_sortino_ratio(r_multiples, *, n_per_year: int = 252)` — same | G-CONF-12.1-A |
| Population std-dev (divide by N, not N-1) for both Sharpe std and Sortino downside std | Consistent with existing SQL (`STDDEV_POP`); Ganesha confirms |
| Breakeven trades (`net_pnl = 0`) contribute to neither mean_r nor downside_dev | G-CONF-12.1-B and G-CORR-01 |
| `no_downside_trades=True` and `sortino_ratio=None` when `loss_r` is empty | G-CONF-12.1-B |
| `insufficient_sample=True` and both ratios `None` when `r_coverage_count < 30` | Karna M-8/M-9 minimum N; consistent with G-ADV-01 |
| `sharpe_ratio=None` (not zero) when `std_r == 0` (all R-multiples identical) | Domain ruling: a zero-std series is undefined, not zero-risk |

---

## A Note on Interpreting These Metrics for Indian Retail Traders

Ganesha flags one forward-looking concern for when the frontend is designed (for Arjun's benefit when that gate opens):

**Sharpe and Sortino have a specific interpretation failure mode for asymmetric-payoff traders.** A system with a high win rate and small winners but occasional large losses will show a favourable Sharpe (low std overall) but high Sortino downside (the rare large losses dominate the downside std). The opposite is also true: a low-win-rate high-R system (common among breakout traders) will show a lower Sharpe than its actual quality because large wins inflate std.

This is precisely why Karna described Sortino as "preferred primary risk-adjusted metric for TradeForge users" — Indian retail day traders often run asymmetric payoff systems. Sortino penalizes only the downside, so a system with large wins and controlled losses is correctly recognized as higher quality than Sharpe would suggest.

The frontend should present Sortino as the primary metric and Sharpe as secondary context. This is a product design note, not a domain correction — Ganesha is recording it here because it should inform Arjun's UX choices.

---

## Status After These Confirmations

| Open Item | Status |
|---|---|
| G-CONF-12.1-A — N_per_year | **CLOSED** — 252 confirmed |
| G-CONF-12.1-B — Sortino downside | **CLOSED** — MAR=0, strict r < 0 confirmed |
| ADR-007A Bhima implementation gate | **CLEARED** — all domain questions resolved |

Bhima may proceed to Phase 1 of the Krishna Step 12.1 delivery plan.

---

*Ganesha · Trading Domain Analyst · 2026-09-03*
