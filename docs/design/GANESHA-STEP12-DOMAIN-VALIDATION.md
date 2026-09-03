# Ganesha Domain Validation — Step 12 Analytics Spec

**Reviewer:** Ganesha (Trading Domain Analyst)  
**Date:** 2026-09-02  
**Validates:** `STEP-12-ANALYTICS-SPEC.md` (Karna, 2026-09-02)  
**Sources reviewed:** `STEP-12-ANALYTICS-SPEC.md` · `backend/src/tradeforge/domain/pnl/calculator.py` · `backend/src/tradeforge/infrastructure/models/trade_pnl.py` · `TRADE-DOMAIN-DATA-MODEL.md`

---

## Verdict: Conditional Pass — 3 Corrections Required

Karna's spec is structurally sound and correctly grounded in the schema. Three formulas require domain correction before Bhima writes any implementation code. The high-severity correction (G-CORR-02, M-14 exit type grouping) changes the SQL shape for that metric. All three corrections are amendments to existing metrics — no metrics are dropped.

The MAE/MFE deferral (N-5) is confirmed and strengthened at the domain level: a fill-price approximation is formally prohibited.

**Summary:**

| Category | Count |
|---|---|
| Corrections (must resolve before implementation) | 3 |
| Confirmed (no change needed) | 4 |
| Hard defer confirmed | 1 |
| Advisories (no formula change required) | 2 |

---

## Corrections

### G-CORR-01 · M-2, M-3 — Breakeven Trade Classification

**Severity:** Medium  
**Affects:** M-2 (Win Rate), M-3 (Expectancy)

#### Problem

Karna uses `net_pnl ≤ 0` to define the loss group, which classifies breakeven trades (`net_pnl = 0`) as losses. In the expectancy formula this inflates Loss Rate and dilutes avg loss r_multiple toward zero — both errors pull expectancy toward pessimism.

**As written (incorrect):**
```
Loss Rate  = COUNT(net_pnl <= 0) / COUNT(*)       -- includes breakevens as losses
Avg_R_loss = AVG(r_multiple WHERE r_multiple <= 0) -- r_multiple = 0 dilutes average
```

#### Domain Ruling

A breakeven trade is a third outcome class, not a loss. It should be counted in total N and excluded from both the win and loss groups in expectancy computation. Breakeven trades contribute nothing to the avg_r components — they are structurally neutral outcomes.

**Corrected:**
```
Win_count       = COUNT(net_pnl > 0)
Loss_count      = COUNT(net_pnl < 0)       -- strict: excludes breakevens
Breakeven_count = COUNT(net_pnl = 0)
Total_N         = COUNT(*)                 -- all three groups

Win_rate  = Win_count  / Total_N
Loss_rate = Loss_count / Total_N           -- breakevens not in loss rate

Expectancy_R =
  (Win_rate  × AVG(r_multiple WHERE r_multiple > 0))
- (Loss_rate × ABS(AVG(r_multiple WHERE r_multiple < 0)))   -- strict <
```

**Bhima:** The M-2 API response must expose all three counts: `win_count`, `loss_count`, `breakeven_count`, `total_n`. The M-12 streak computation must also use strict `< 0` for losing trades.

---

### G-CORR-02 · M-14 — Multi-Exit Trades Double-Counted in Exit Type Grouping

**Severity:** High  
**Affects:** M-14 (Exit Type Analysis)

#### Problem

Karna's M-14 SQL joins `execution_fills WHERE fill_role = 'EXIT'` and groups by `exit_type`. A trade with a scaled exit — e.g., T1 fill tagged `TARGET_HIT` and the runner fill tagged `STOP_HIT` — will appear in both exit_type groups. `COUNT(DISTINCT t.id)` per group still double-counts the trade. The total trade count across all exit_type groups can exceed total closed trades.

**As written (incorrect):**
```sql
SELECT f.exit_type, COUNT(DISTINCT t.id) AS trade_count ...
FROM execution_fills f
WHERE f.fill_role = 'EXIT'
GROUP BY f.exit_type
-- Multi-exit trades appear in multiple groups
```

#### Domain Ruling

Every trade receives exactly one exit_type for analytics purposes: the `exit_type` of the EXIT fill with the latest `fill_timestamp`. Rationale: the final fill is what ultimately closed the position — a runner stopped out by a trailing stop is remembered by the trader as a stop-hit exit, even if a partial target was hit earlier.

**Corrected SQL:**
```sql
WITH last_exit AS (
  SELECT DISTINCT ON (trade_id)
    trade_id,
    exit_type
  FROM execution_fills
  WHERE fill_role = 'EXIT'
  ORDER BY trade_id, fill_timestamp DESC    -- last fill per trade wins
)
SELECT
  le.exit_type,
  COUNT(t.id)                                           AS trade_count,
  AVG(tp.net_pnl)                                       AS avg_net_pnl_inr,
  AVG(tp.r_multiple)                                    AS avg_r_multiple,
  AVG(CASE WHEN tp.net_pnl > 0 THEN 1.0 ELSE 0.0 END) AS win_rate
FROM trades t
JOIN trade_pnl tp ON tp.trade_id = t.id
JOIN last_exit le  ON le.trade_id = t.id
WHERE t.status = 'CLOSED'
  AND t.user_id = :user_id
  -- + global filters on t
GROUP BY le.exit_type
```

If `exit_type` is NULL on the last exit fill (adapter did not populate it), the trade lands in the NULL group ("Untagged exits") — a data quality signal.

---

### G-CORR-03 · M-11 — Charge Drag % Undefined When Gross P&L Is Negative

**Severity:** Low  
**Affects:** M-11 (Charges Breakdown)

#### Problem

`charge_drag_pct = total_charges / ABS(SUM(gross_pnl)) × 100` is semantically incoherent when the filtered set has a negative total gross P&L. The percentage reads as meaningful but cannot be interpreted — you cannot be "dragged by 18%" of a loss you would have incurred anyway.

#### Domain Ruling

Charge drag as a percentage is defined only when the trader is net profitable on a gross basis.

**Corrected conditional:**
```python
if SUM(gross_pnl) > 0:
    charge_drag_pct = total_charges / SUM(gross_pnl) × 100
else:
    charge_drag_pct = None                        # suppress
    charges_added_to_loss = total_charges         # surface as INR absolute
    # UI: "charges added ₹X,XXX to losses"
```

---

## Confirmations

### G-CONF-01 · M-5 — Short Trade Planned R:R Formula Is Correct

The formula `(planned_target − average_entry) / (average_entry − planned_stop)` is correct for both LONG and SHORT trades — signs cancel algebraically for short trades.

**Verification:**
```
-- LONG: entry=100, stop=95, target=110
(110 − 100) / (100 − 95)  =  10 / 5  = 2.0 ✓

-- SHORT: entry=100, stop=105, target=90
(90 − 100) / (100 − 105)  =  (−10) / (−5)  = 2.0 ✓
-- Signs cancel: both numerator and denominator are negative for shorts
```

The non-obviousness is a risk. **Bhima must add a domain unit test** that asserts the formula produces a positive value for well-formed short trades. A negative result indicates a malformed stop/target relationship and should be excluded from the average.

---

### G-CONF-02 · M-3, M-6, M-8, M-9 — R-Multiple Sign Convention Confirmed

R-multiple sign convention is direction-agnostic, confirmed via `calculator.py`:

```
-- compute_gross_pnl handles direction:
LONG:  gross_pnl = (avg_exit − avg_entry) × qty   -- positive when exit > entry
SHORT: gross_pnl = (avg_entry − avg_exit) × qty   -- positive when entry > exit

-- net_pnl = gross_pnl − charges   (charges always positive)
-- r_multiple = net_pnl / planned_risk_amount   (planned_risk_amount > 0)

∴ r_multiple > 0 ↔ winning trade, independent of direction ✓
∴ r_multiple < 0 ↔ losing trade, independent of direction ✓
∴ r_multiple = None when planned_risk_amount is NULL or zero ✓
```

All Karna formulas that split on `r_multiple > 0 / < 0` are valid (subject to the G-CORR-01 amendment changing `≤ 0` to `< 0`).

---

### G-CONF-03 · M-7 — Add Deterministic Tie-Break to Equity Curve Ordering

Karna's `ORDER BY trade_date, last_fill_at` is correct in principle. Two trades closed within the same second produce non-deterministic window sums — the equity curve could differ across runs.

**Amendment:** Add `t.id ASC` as tertiary sort key on all M-7 window functions. The UUID ordering is arbitrary but stable — the equity curve is identical across runs for the same data.

```sql
ORDER BY t.trade_date ASC, t.last_fill_at ASC, t.id ASC
```

---

### G-CONF-04 · M-13 — Hold Duration Computation Is Correct

`last_fill_at − first_fill_at` correctly captures the full trade duration for scaled exits. `last_fill_at` is set only when `status = 'CLOSED'` — it reflects the final exit fill, which is the correct endpoint for hold duration. Bucket assignment based on `first_fill_at` (entry session, not exit session) is also correct — what matters for time-of-day purposes is when the trader decided to enter. The bucket boundaries (09:15–15:30 IST) map correctly to NSE/BSE trading sessions.

---

## Hard Defer Confirmed

### G-DEFER-01 · N-5 — MAE/MFE Fill-Price Approximation Prohibited

Karna correctly deferred MAE/MFE. Ganesha confirms and formalises the prohibition on approximation.

**What TradeForge has vs. what MAE/MFE requires:**
```
-- Available (fill-level only):
entry_fill_price = trades.average_entry   -- weighted avg of all entry fills
exit_fill_price  = trades.average_exit    -- weighted avg of all exit fills

-- Required for true MAE/MFE:
min_price_during_trade   -- intrabar LOW for every bar while position is open
max_price_during_trade   -- intrabar HIGH for every bar while position is open

-- What approximation would actually give:
Fake_MAE = max(0, average_entry − average_exit)   -- just losing trade P&L in price terms
Fake_MFE = max(0, average_exit  − average_entry)  -- just winning trade P&L in price terms
-- Both collapse MAE/MFE into P&L — analytically useless and actively misleading
```

**Prohibition:** A fill-price MAE/MFE approximation is formally prohibited. It does not measure adverse or favorable excursion — it measures whether the trade was a winner or loser, which is already captured by `net_pnl`. Shipping this approximation would mislead traders into making stop-placement and exit-timing decisions based on P&L data relabelled as MAE/MFE. The harm is greater than the absence of the metric.

**Phase 2 requirements:**
- OHLC bar feed (1-min or finer) for NSE_EQ and NSE_FO instruments
- For options trades: underlying's OHLC is required, not the option premium's OHLC — option premium is dominated by Greeks, not raw adverse excursion on the underlying

---

## Advisories

### G-ADV-01 · M-3, M-6 — R-Multiple Coverage Flag Uses Wrong N

Karna's spec says "Flag when N < 30." The floor should apply to the r_multiple-covered subset, not total N.

A trader with 200 total trades but only 12 with `planned_risk_amount` set should see R-based expectancy flagged as insufficient, even though total N = 200.

**Amendment:** Change insufficient-sample flag condition to `COUNT(r_multiple IS NOT NULL) < 30`. The coverage percentage Karna already reports makes this visible — the flag is a safety net on top of it.

---

### G-ADV-02 · M-3, M-6 (NRML_OPT / CE / PE) — Short Options planned_risk_amount Undefined

For long options, `planned_risk_amount` = premium paid — semantically correct. For short options (sold puts, sold calls), traders may enter: premium collected, margin requirement, or max loss of the spread. R-multiples across these three interpretations are not comparable.

**No change for Phase 1.** Analytics for options are computed from whatever `planned_risk_amount` the trader entered. A future Ganesha ruling will define canonical `planned_risk_amount` semantics for each options strategy type before options analytics become reliable. This is a Phase 1-B design item.

---

## Summary Table

| ID | Affects | Ruling |
|---|---|---|
| G-CORR-01 | M-2 · M-3 · M-12 | Use strict `< 0` for loss classification. Expose `win_count`, `loss_count`, `breakeven_count` separately. |
| G-CORR-02 | M-14 | Use `DISTINCT ON (trade_id) ORDER BY fill_timestamp DESC` CTE. One exit_type per trade. |
| G-CORR-03 | M-11 | Suppress `charge_drag_pct` when `SUM(gross_pnl) ≤ 0`. Expose absolute INR instead. |
| G-CONF-01 | M-5 | Planned R:R formula correct for both directions (sign cancels). Bhima must add unit test. |
| G-CONF-02 | M-3 · M-6 · M-8 · M-9 | R-multiple sign convention confirmed direction-agnostic via `calculator.py`. |
| G-CONF-03 | M-7 | Add `t.id ASC` as tertiary sort on all M-7 window functions. |
| G-CONF-04 | M-13 | Hold duration and bucket assignment confirmed correct. |
| G-DEFER-01 | N-5 | MAE/MFE hard deferred confirmed. Fill-price approximation formally prohibited. |
| G-ADV-01 | M-3 · M-6 | Coverage flag threshold should use `COUNT(r_multiple IS NOT NULL) < 30`, not total N. |
| G-ADV-02 | M-3 · M-6 (options) | Short options `planned_risk_amount` semantics undefined in Phase 1. Phase 1-B design item. |

---

*Ganesha · Trading Domain Analyst · 2026-09-02*  
*Three corrections required before Bhima implements. High-severity correction (G-CORR-02) changes M-14 SQL shape.*
