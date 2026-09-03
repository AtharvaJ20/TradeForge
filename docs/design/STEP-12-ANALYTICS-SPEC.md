# Step 12 — Karna Analytics Specification

**Author:** Karna (Quant Research)  
**Date:** 2026-09-02  
**Status:** Conditional pass — awaiting G-CORR-01, G-CORR-02, G-CORR-03 corrections (see `GANESHA-STEP12-DOMAIN-VALIDATION.md`)  
**Gate:** Sahadeva Step 11 "Go" required before implementation begins  
**Implementation owner:** Bhima  
**QA owner:** Sahadeva  

---

## Contents

1. [Must-Have Cut Line](#must-have-cut-line)
2. [Schema Foundation](#schema-foundation)
3. [Global Filtering Dimensions](#global-filtering-dimensions)
4. [Must-Have Metrics M-1 through M-14](#must-have-metrics)
5. [Nice-to-Have Metrics N-1 through N-4](#nice-to-have-metrics)
6. [Deferred N-5 MAE/MFE](#deferred-n-5-maemfe)

---

## Must-Have Cut Line

Step 12 ships when **M-1 through M-14** all pass Sahadeva's acceptance gate, with all 9 global filters wired to every metric endpoint.

**Exception:** N-1 (rolling expectancy) is borderline. If Bhima can ship it without delaying the Step 12 gate, promote it to must-have. N-5 (MAE/MFE) is hard-blocked on market data — must not ship as a fill-price approximation under any circumstances (see Ganesha ruling G-DEFER-01).

---

## Schema Foundation

All Step 12 queries join across these tables. Every query must include `trades.user_id = :user_id` (from session) and `trades.status = 'CLOSED'` as base predicates. A trade without a matching `trade_pnl` row is excluded from all analytics.

| Table | Key columns | Notes |
|---|---|---|
| `trades` | `trade_date · direction · trade_type · setup_name · planned_risk_amount · planned_entry · planned_stop · planned_target · average_entry · average_exit · first_fill_at · last_fill_at · account_id` | `account_id` nullable until Step 11 NOT NULL migration applied |
| `trade_pnl` | `gross_pnl · net_pnl · total_charges · r_multiple · brokerage · stt · exchange_charges · sebi_charges · stamp_duty · gst · ipft · broker` | `r_multiple` NULL when `planned_risk_amount` was not set at trade entry |
| `instruments` | `symbol · exchange_segment · instrument_type · expiry_date · strike_price` | Joined via `trades.instrument_id` for all instrument-level filters |
| `execution_fills` | `fill_timestamp · session · fill_role · exit_type · quantity · price · product_type` | Used for exit type analysis (M-14) and time-of-day (N-2) |
| `trading_accounts` | `id · broker · display_name · account_type` | Step 11 — `account_id` filter applies to `trades`, `execution_fills`, `trade_pnl` |

---

## Global Filtering Dimensions

All 9 parameters below **must** be supported on every analytics endpoint. Parameters are ANDed. An empty array means no filter on that dimension (include all).

| Parameter | Type | Source column | Notes |
|---|---|---|---|
| `date_from` | DATE | `trades.trade_date ≥` | Inclusive lower bound |
| `date_to` | DATE | `trades.trade_date ≤` | Inclusive upper bound |
| `account_id` | UUID[] | `trades.account_id` | Multi-select; Step 11 FK; cross-account aggregation supported |
| `instrument_type` | VARCHAR[] | `instruments.instrument_type` | `EQ · FUT · CE · PE` |
| `exchange_segment` | VARCHAR[] | `instruments.exchange_segment` | `NSE_EQ · NSE_FO · BSE_EQ` |
| `trade_type` | VARCHAR[] | `trades.trade_type` | `MIS · CNC · CNC_SAME_DAY · NRML_FUT · NRML_OPT` |
| `direction` | VARCHAR[] | `trades.direction` | `LONG · SHORT` |
| `setup_name` | VARCHAR[] | `trades.setup_name` | Multi-select; NULL `trades.setup_name` is a valid group ("Untagged") |
| `broker` | VARCHAR[] | `trade_pnl.broker` | `ZERODHA · UPSTOX · ANGEL_ONE · MANUAL` |

---

## Must-Have Metrics

### M-1 · Summary Dashboard

Scalar aggregate over all closed trades in the filtered set.

**Outputs:**
```
total_closed_trades    = COUNT(*) WHERE status = 'CLOSED'
total_net_pnl          = SUM(net_pnl)
total_gross_pnl        = SUM(gross_pnl)
total_charges          = SUM(total_charges)
win_count              = COUNT(*) WHERE net_pnl > 0
loss_count             = COUNT(*) WHERE net_pnl < 0          -- G-CORR-01: strict <
breakeven_count        = COUNT(*) WHERE net_pnl = 0          -- G-CORR-01: third class
avg_net_pnl_per_trade  = AVG(net_pnl)
avg_winning_trade      = AVG(net_pnl) WHERE net_pnl > 0
avg_losing_trade       = AVG(net_pnl) WHERE net_pnl < 0
```

**Output type:** Scalar aggregates (INR, Decimal)  
**Min N:** 1 trade  
**Filters:** All 9 global

---

### M-2 · Win Rate

```
Win Rate  = COUNT(net_pnl > 0) / COUNT(*) × 100
Loss Rate = COUNT(net_pnl < 0) / COUNT(*) × 100    -- G-CORR-01: strict <
```

Always report alongside sample N. **Flag when N < 30 (insufficient sample).**

**Output type:** NUMERIC % scalars + {win_count, loss_count, breakeven_count, total_n}  
**Filters:** All 9 global

---

### M-3 · Expectancy

Ship both variants. R-based requires `planned_risk_amount` — coverage will be partial at first. INR-based is always computable.

**R-based (preferred, partial coverage):**
```
Expectancy_R = (Win_Rate × AVG(r_multiple WHERE r_multiple > 0))
             − (Loss_Rate × ABS(AVG(r_multiple WHERE r_multiple < 0)))    -- G-CORR-01: strict <

where:
  Win_Rate  = COUNT(net_pnl > 0) / COUNT(*)
  Loss_Rate = COUNT(net_pnl < 0) / COUNT(*)   -- G-CORR-01: breakevens excluded
  coverage  = COUNT(r_multiple IS NOT NULL) / COUNT(*)
```

**INR-based (always computable):**
```
Expectancy_INR = (Win_Rate  × AVG(net_pnl WHERE net_pnl > 0))
               + (Loss_Rate × AVG(net_pnl WHERE net_pnl < 0))
```

When r_multiple coverage is below 50%, surface INR-based as primary and flag that `planned_risk_amount` was unset for N trades.

**Flag when:** `COUNT(r_multiple IS NOT NULL) < 30` (G-ADV-01 amendment — coverage N, not total N)  
**Output type:** Two NUMERIC scalars + r_multiple coverage %  
**Filters:** All 9 global

---

### M-4 · Profit Factor

```
Profit Factor = SUM(net_pnl WHERE net_pnl > 0) / ABS(SUM(net_pnl WHERE net_pnl < 0))
```

NULL when denominator = 0 (no losing trades). Report as NULL with note "no losing trades in set."

**Flag when N < 30**  
**Output type:** NUMERIC scalar (NULL-safe)  
**Filters:** All 9 global

---

### M-5 · Planned vs Realized R:R

**Planned R:R (per trade, where stop + target set):**
```
Planned_RR = (planned_target − average_entry) / (average_entry − planned_stop)
```

> Note: this formula is correct for both LONG and SHORT trades — signs cancel for short trades
> (G-CONF-01 confirmed). A negative Planned_RR indicates a malformed stop/target relationship
> and should be excluded from the average. Bhima must add a unit test asserting positive output
> for well-formed short trades.

```
Planned_RR_avg = AVG(Planned_RR over trades where planned_stop IS NOT NULL AND planned_target IS NOT NULL)
coverage       = COUNT(planned_stop IS NOT NULL AND planned_target IS NOT NULL) / COUNT(*)
```

**Realized R:R (winning trades only):**
```
Realized_RR_avg = AVG(r_multiple WHERE net_pnl > 0 AND r_multiple IS NOT NULL)
Capture_ratio   = Realized_RR_avg / Planned_RR_avg    -- < 1 means leaving money early
```

**Output type:** 3 NUMERIC scalars + coverage %  
**Filters:** All 9 global

---

### M-6 · R-Multiple Distribution

```sql
SELECT
  ROUND(r_multiple::numeric, 1) AS r_bin,
  COUNT(*) AS trade_count
FROM trade_pnl tp
JOIN trades t ON t.id = tp.trade_id
WHERE t.user_id = :user_id
  AND t.status = 'CLOSED'
  AND tp.r_multiple IS NOT NULL
  -- + all applied global filters
GROUP BY r_bin
ORDER BY r_bin
```

Distribution statistics (application layer):
```
mean     = AVG(r_multiple)
median   = PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY r_multiple)
std_dev  = STDDEV(r_multiple)
skewness = computed in Python from raw series
```

**Flag when** `COUNT(r_multiple IS NOT NULL) < 30`  
**Output type:** Histogram array `[{r_bin, count}]` + `{mean, median, std_dev, skewness}`  
**Filters:** All 9 global

---

### M-7 · Equity Curve + Maximum Drawdown

```sql
WITH ordered AS (
  SELECT
    t.trade_date,
    t.last_fill_at,
    t.id,
    tp.net_pnl,
    SUM(tp.net_pnl) OVER (
      ORDER BY t.trade_date ASC, t.last_fill_at ASC, t.id ASC   -- G-CONF-03: t.id for deterministic tie-break
      ROWS UNBOUNDED PRECEDING
    ) AS cumulative_pnl
  FROM trades t
  JOIN trade_pnl tp ON tp.trade_id = t.id
  WHERE t.user_id = :user_id AND t.status = 'CLOSED'
  -- + filters
)
SELECT
  trade_date, net_pnl, cumulative_pnl,
  MAX(cumulative_pnl) OVER (ORDER BY trade_date ASC, last_fill_at ASC, id ASC ROWS UNBOUNDED PRECEDING) AS peak,
  cumulative_pnl
    - MAX(cumulative_pnl) OVER (ORDER BY trade_date ASC, last_fill_at ASC, id ASC ROWS UNBOUNDED PRECEDING)
    AS drawdown_inr
FROM ordered
```

MDD scalars (application layer):
```
MDD_INR = MIN(drawdown_inr)
MDD_pct = MDD_INR / MAX(peak) × 100
```

**Output type:** Time-series `[{trade_date, cumulative_pnl, drawdown_inr}]` + `{MDD_INR, MDD_pct}`  
**Filters:** All 9 global

---

### M-8 · Sharpe Ratio (Trade-Based)

```
mean_return = AVG(net_pnl)       -- per trade
std_return  = STDDEV(net_pnl)    -- per trade
N_per_year  = total_closed_trades / years_of_data

Sharpe = (mean_return / std_return) × SQRT(N_per_year)
```

Risk-free rate omitted — not meaningful for trade-based Sharpe. Always pair with Sortino (M-9).

**Min N:** 30  
**Output type:** NUMERIC scalar  
**Filters:** All 9 global

---

### M-9 · Sortino Ratio

```
mean_return  = AVG(net_pnl)
downside_dev = SQRT(AVG(LEAST(net_pnl, 0)^2))    -- computed application-side
N_per_year   = total_closed_trades / years_of_data

Sortino = (mean_return / downside_dev) × SQRT(N_per_year)
```

Preferred primary risk-adjusted metric for TradeForge users (asymmetric payoff systems).

**Min N:** 30  
**Output type:** NUMERIC scalar  
**Filters:** All 9 global

---

### M-10 · Dimension Breakdown Table

Full M-2 through M-4 metric set computed independently for each value of a chosen breakdown dimension.

**Output shape (one row per dimension value):**
```
{dimension_value, N, win_rate, expectancy_r, expectancy_inr,
 profit_factor, avg_net_pnl_inr, total_net_pnl_inr, avg_r_multiple}
```

**Breakdown dimensions (each independently queryable):**

| Dimension | Column | Values |
|---|---|---|
| Setup | `trades.setup_name` | All setup labels; NULL group = "Untagged" |
| Direction | `trades.direction` | LONG · SHORT |
| Instrument type | `instruments.instrument_type` | EQ · FUT · CE · PE |
| Trade type | `trades.trade_type` | MIS · CNC · CNC_SAME_DAY · NRML_FUT · NRML_OPT |
| Exchange segment | `instruments.exchange_segment` | NSE_EQ · NSE_FO · BSE_EQ |

**Flag any group with N < 30 as "insufficient sample."**  
**Output type:** Table rows  
**Filters:** All 9 global (breakdowns applied within filtered set)

---

### M-11 · Charges Breakdown

```
total_brokerage        = SUM(brokerage)
total_stt              = SUM(stt)
total_exchange_charges = SUM(exchange_charges)
total_sebi_charges     = SUM(sebi_charges)
total_stamp_duty       = SUM(stamp_duty)
total_gst              = SUM(gst)
total_ipft             = SUM(ipft)
total_charges          = SUM(total_charges)

avg_charge_per_trade   = total_charges / COUNT(*)

-- Charge drag (G-CORR-03: suppress when gross P&L ≤ 0):
IF SUM(gross_pnl) > 0:
  charge_drag_pct = total_charges / SUM(gross_pnl) × 100
ELSE:
  charge_drag_pct = NULL
  charges_added_to_loss = total_charges    -- "charges added ₹X to losses"
```

**Output type:** 9 INR totals + conditional drag metric  
**Filters:** All 9 global

---

### M-12 · Consecutive Win / Loss Streaks

Computed application-side from ordered trade series (trade_date ASC, last_fill_at ASC, trade_id ASC):

```
current_streak_value    -- +N = winning streak, −N = losing streak
max_win_streak          -- longest run of consecutive net_pnl > 0
max_loss_streak         -- longest run of consecutive net_pnl < 0   (G-CORR-01: strict <)
avg_trades_per_reversal -- AVG run length across all runs
```

**Output type:** 4 INTEGER scalars  
**Filters:** All 9 global

---

### M-13 · Hold Duration Analysis

```sql
hold_minutes = EXTRACT(EPOCH FROM (last_fill_at - first_fill_at)) / 60

bucket =
  CASE
    WHEN hold_minutes < 5    THEN 'scalp (<5m)'
    WHEN hold_minutes < 60   THEN 'intraday_short (5–60m)'
    WHEN hold_minutes < 240  THEN 'intraday_long (1–4h)'
    WHEN hold_minutes < 1440 THEN 'same_day_extended'
    ELSE                          'multi_day'
  END
```

Output per bucket: `{bucket, total_trades, win_count, loss_count, avg_net_pnl_inr, avg_hold_minutes}`

**Source:** `trades.first_fill_at · trades.last_fill_at` (G-CONF-04: last_fill_at correctly represents trade closure for scaled exits)  
**Output type:** Table (5 bucket rows)  
**Filters:** All 9 global

---

### M-14 · Exit Type Analysis

**Domain ruling (G-CORR-02):** Assign one exit_type per trade — the exit_type of the EXIT fill with the latest `fill_timestamp`. Multi-exit scaled trades must not be double-counted.

```sql
WITH last_exit AS (
  SELECT DISTINCT ON (trade_id)
    trade_id,
    exit_type
  FROM execution_fills
  WHERE fill_role = 'EXIT'
  ORDER BY trade_id, fill_timestamp DESC    -- last fill per trade
)
SELECT
  le.exit_type,
  COUNT(t.id)                                              AS trade_count,
  AVG(tp.net_pnl)                                         AS avg_net_pnl_inr,
  AVG(tp.r_multiple)                                       AS avg_r_multiple,
  AVG(CASE WHEN tp.net_pnl > 0 THEN 1.0 ELSE 0.0 END)    AS win_rate
FROM trades t
JOIN trade_pnl tp ON tp.trade_id = t.id
JOIN last_exit le  ON le.trade_id = t.id
WHERE t.status = 'CLOSED'
  AND t.user_id = :user_id
  -- + global filters on t
GROUP BY le.exit_type
```

Exit types: `FORCED · STOP_HIT · TARGET_HIT · DISCRETIONARY · NORMAL · NULL (Untagged)`

> **Sanjaya flag:** NULL exit_type coverage is a data quality signal. Confirm that ZerodhaAdapter
> correctly populates `exit_type = 'FORCED'` for auto-square-off fills and `'STOP_HIT'` for
> trigger-order exits. If NULL coverage is high, M-14 output is misleading.

**Output type:** Table (one row per exit_type value)  
**Filters:** All 9 global

---

## Nice-to-Have Metrics

### N-1 · Rolling Expectancy (20-trade window) — Promote if feasible

Expectancy computed over a sliding 20-trade window, ordered chronologically. The primary edge-stability signal.

```python
# Application layer — for each window ending at trade index i (i >= 20):
window = trades[i-20:i]   # ordered by trade_date, last_fill_at, trade_id

rolling_exp_r   = expectancy_r(window)     # formula per M-3
rolling_exp_inr = expectancy_inr(window)

# Output: [{trade_index, trade_date, rolling_exp_r, rolling_exp_inr}]
```

No additional SQL required — pure application-layer computation over the ordered M-7 series.

**Output type:** Time-series array (starts at trade #20)

---

### N-2 · Time-of-Day Analysis

From `first_fill_at` bucketed in IST (UTC+5:30):

```sql
first_fill_ist = first_fill_at AT TIME ZONE 'Asia/Kolkata'

bucket =
  CASE
    WHEN first_fill_ist::time BETWEEN '09:15' AND '09:30' THEN 'pre_open'
    WHEN first_fill_ist::time BETWEEN '09:30' AND '10:00' THEN 'open_volatility'
    WHEN first_fill_ist::time BETWEEN '10:00' AND '11:30' THEN 'mid_morning'
    WHEN first_fill_ist::time BETWEEN '11:30' AND '13:30' THEN 'lunch'
    WHEN first_fill_ist::time BETWEEN '13:30' AND '15:00' THEN 'afternoon'
    ELSE                                                       'close'
  END
```

Output per bucket: `{bucket, N, win_rate, expectancy_inr, total_net_pnl}`

**Output type:** Table (6 session bucket rows)

---

### N-3 · Monte Carlo Simulation — Requires background job infrastructure

Simulates 1,000–10,000 random resamplings of the historical R-multiple series. Must run as a background task, not a synchronous response.

```python
for sim in range(1000):
    resampled = random_sample_with_replacement(r_multiple_series, N)
    equity    = cumsum(resampled × initial_risk_per_trade_inr)
    mdd[sim]  = max_drawdown(equity)
    ruined[sim] = (equity.min() < ruin_threshold)   # e.g. −50% of start

outputs = {
    p5_mdd:         percentile(mdd, 5),
    p1_mdd:         percentile(mdd, 1),
    risk_of_ruin:   mean(ruined) × 100,
    p95_max_streak: percentile(max_consec_losses_per_sim, 95),
}
```

**Min N recommended:** 100 trades  
**Requires:** Background task infrastructure (Celery / BackgroundTask)

---

### N-4 · Kelly Criterion Position Sizing

```
Kelly_pct  = Expectancy_R / AVG(r_multiple WHERE r_multiple > 0)
Half_Kelly = Kelly_pct / 2
```

Always present alongside half-Kelly. Requires r_multiple coverage.

**Output type:** 2 NUMERIC scalars (Kelly %, Half-Kelly %)  
**Min N:** 30

---

## Deferred N-5 MAE/MFE

**Status:** Hard deferred — Phase 2. Fill-price approximation prohibited.

True MAE/MFE requires OHLC bar data for every bar while the trade is open — not available in Phase 1. A fill-price approximation would reduce to relabeled P&L data and produce incorrect stop-placement conclusions.

**Phase 2 requirement:** OHLC bar feed (1-min or finer) for NSE_EQ, NSE_FO instruments. For options trades, the underlying's OHLC is required — not the option premium's OHLC.

See Ganesha ruling G-DEFER-01 in `GANESHA-STEP12-DOMAIN-VALIDATION.md` for full prohibition rationale.

---

## Pending Corrections

Before Bhima writes any Step 12 implementation code, the following Ganesha corrections must be applied. They are already reflected in the formulas above.

| Correction | Affected metrics | Change |
|---|---|---|
| G-CORR-01 | M-2, M-3, M-12 | Use strict `< 0` for loss classification; expose breakeven as third outcome class |
| G-CORR-02 | M-14 | Use `DISTINCT ON (trade_id) ORDER BY fill_timestamp DESC` CTE; one exit_type per trade |
| G-CORR-03 | M-11 | Suppress `charge_drag_pct` when `SUM(gross_pnl) ≤ 0`; expose absolute INR instead |

---

*Karna · Quant Research · Step 12 Analytics Specification · 2026-09-02*  
*Domain validation: Ganesha · Implementation: Bhima · QA: Sahadeva*
