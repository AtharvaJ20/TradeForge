# Charge Schedules — Schema and Seed Data Specification

**Status:** Authoritative — binding on Bhima (migration and charge engine), Nakula (seed data maintenance), Sahadeva (QA rate verification)
**Author:** Kubera (Financial Calculation & P&L Specialist)
**Date:** 2026-08-24
**Binding on:** Step 10 P&L engine
**Depends on:** `DECIMAL-USAGE-STANDARD.md` · `TRADE-DOMAIN-RULES.md` (Rule 3.3) · `JOURNAL-PNL-INTEGRATION.md` (§3.4, §5.3) · ADR-005 (broker-string-based, no account_id in Phase 1)

---

## Purpose

This document defines:

1. The `charge_schedules` table — schema, DDL, constraints, indexes, and lookup algorithm.
2. The formula by which each of the seven charge components is computed from the schedule row.
3. The derivation of `charge_schedule_version` (stored in `trade_pnl`).
4. The Phase 1 seed dataset for Zerodha on NSE (post Union Budget 2024, effective 2024-10-01).
5. The historical seed dataset for Zerodha on NSE (pre-Budget 2024, effective 2023-01-01).
6. The Phase 2 extension point for account-specific rates (per ADR-005 Q1).

**What this document does NOT define:** the GST base exclusion rule (defined in Kubera skill §7), the intermediate rounding rule (DECIMAL-USAGE-STANDARD.md Rule 3), or P&L formulas (defined in Kubera skill §3 and Ganesha FIFO ruling).

---

## Design Decisions

### D1 — Rates are stored in the database, never hardcoded

Every charge rate is a row in `charge_schedules`. The P&L engine contains zero charge rate literals. This is not optional — statutory rates change with each Union Budget and SEBI/NSE/BSE circulars. If a rate is in application code, it will be wrong within 12 months.

### D2 — Effective-date lookup (not a "current rate" flag)

Each row carries an `effective_from` date. The lookup selects the row with the latest `effective_from` that is **≤ the trade's `trade_date`**. This gives correct historical P&L when an old trade is recalculated after a rate change — the rate at the time of the trade is used, not today's rate.

### D3 — Lookup key is `(broker, trade_type, exchange_segment, effective_from)`

Per ADR-005: `account_id` is not present in Phase 1. All users on the same broker share one schedule. The Phase 2 extension point is specified in §12.

### D4 — Brokerage structure is modelled as a type with conditional columns

Three brokerage types exist in Indian markets:
- `ZERO` — zero brokerage (e.g., Zerodha delivery equity).
- `FLAT` — fixed amount per order side regardless of turnover (e.g., Zerodha options: ₹20 flat).
- `PERCENT_CAP` — percentage of side turnover, capped at a maximum (e.g., Zerodha intraday: lower of 0.03% or ₹20).

A `CHECK` constraint enforces column nullability per type, preventing inconsistent rows.

### D5 — Base columns separate TURNOVER from PREMIUM

For options, STT, exchange charges, stamp duty, and IPFT are all applied to the **option premium value** (quantity × premium per unit), not the notional value (quantity × lot size × underlying price). Each charge category has a `_base` column (`TURNOVER` or `PREMIUM`) that tells the engine what to apply the rate against. SEBI charges use the same base as `exchange_charge_base` — no separate column.

### D6 — Rate columns use NUMERIC(18,8)

Eight decimal places accommodate the smallest statutory rate in current use: SEBI charges at ₹10 per crore = `0.00000100` as a decimal fraction. Four decimal places (the monetary standard) would truncate this to zero.

### D7 — GST and IPFT are included as columns despite being uniform

GST is currently statutory at 18%. IPFT is currently a fraction of a rupee per trade. Both are included as columns (not constants) because they have changed in the past and will change again. A constant in code is a future defect.

---

## Table Schema

### Column Definitions

| Column | Type | Null | Description |
|---|---|---|---|
| `id` | `UUID` | NOT NULL PK | Server-generated. |
| `broker` | `VARCHAR(20)` | NOT NULL | Broker identifier: `ZERODHA` \| `UPSTOX` \| `ANGEL_ONE` \| `MANUAL`. |
| `trade_type` | `VARCHAR(20)` | NOT NULL | `MIS` \| `CNC` \| `CNC_SAME_DAY` \| `NRML_FUT` \| `NRML_OPT`. |
| `exchange_segment` | `VARCHAR(20)` | NOT NULL | `NSE_EQ` \| `NSE_FO` \| `BSE_EQ`. |
| `effective_from` | `DATE` | NOT NULL | Rate effective on and after this date. Lookup selects latest `effective_from ≤ trade_date`. |
| `brokerage_type` | `VARCHAR(20)` | NOT NULL | `ZERO` \| `FLAT` \| `PERCENT_CAP`. |
| `brokerage_flat_per_order` | `NUMERIC(18,4)` | NULL | Fixed fee per order side, in INR. Populated only when `brokerage_type = FLAT`. |
| `brokerage_pct` | `NUMERIC(18,8)` | NULL | Brokerage rate as decimal fraction (0.03% → `0.00030000`). Populated only when `brokerage_type = PERCENT_CAP`. |
| `brokerage_cap_per_order` | `NUMERIC(18,4)` | NULL | Maximum brokerage per order side, in INR. Populated only when `brokerage_type = PERCENT_CAP`. |
| `stt_buy_rate` | `NUMERIC(18,8)` | NOT NULL | STT rate on buy-side value. `0.00000000` when STT does not apply to buy side. |
| `stt_sell_rate` | `NUMERIC(18,8)` | NOT NULL | STT rate on sell-side value. |
| `stt_base` | `VARCHAR(10)` | NOT NULL | `TURNOVER` \| `PREMIUM`. Base for STT calculation (§7.2). |
| `exchange_charge_rate` | `NUMERIC(18,8)` | NOT NULL | NSE/BSE transaction charge rate as decimal fraction. Applied to both sides. |
| `exchange_charge_base` | `VARCHAR(10)` | NOT NULL | `TURNOVER` \| `PREMIUM`. Base for exchange charge calculation (§7.3). |
| `sebi_charge_rate` | `NUMERIC(18,8)` | NOT NULL | SEBI regulatory charge rate. Currently `0.00000100` (₹10 per crore). Uses same base as `exchange_charge_base`. |
| `stamp_duty_rate` | `NUMERIC(18,8)` | NOT NULL | Stamp duty rate as decimal fraction. Applied to **buy side only**. |
| `stamp_duty_base` | `VARCHAR(10)` | NOT NULL | `TURNOVER` \| `PREMIUM`. Base for stamp duty calculation (§7.5). |
| `gst_rate` | `NUMERIC(18,8)` | NOT NULL | GST rate as decimal fraction. Currently `0.18000000` (18%). |
| `ipft_rate` | `NUMERIC(18,8)` | NOT NULL | IPFT (Investor Protection Fund Trust) rate as decimal fraction. `0.00000000` for BSE. |
| `ipft_base` | `VARCHAR(10)` | NOT NULL | `TURNOVER` \| `PREMIUM`. Same base as `exchange_charge_base` for each row. |
| `notes` | `TEXT` | NULL | Human-readable source reference (circular number, budget year, broker documentation). |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Row creation timestamp. |

### Constraints

| Name | Definition |
|---|---|
| `uq_charge_schedules_lookup` | `UNIQUE (broker, trade_type, exchange_segment, effective_from)` |
| `ck_charge_schedules_broker` | `broker IN ('ZERODHA', 'UPSTOX', 'ANGEL_ONE', 'MANUAL')` |
| `ck_charge_schedules_trade_type` | `trade_type IN ('MIS', 'CNC', 'CNC_SAME_DAY', 'NRML_FUT', 'NRML_OPT')` |
| `ck_charge_schedules_exchange_segment` | `exchange_segment IN ('NSE_EQ', 'NSE_FO', 'BSE_EQ')` |
| `ck_charge_schedules_brokerage_type` | `brokerage_type IN ('ZERO', 'FLAT', 'PERCENT_CAP')` |
| `ck_charge_schedules_stt_base` | `stt_base IN ('TURNOVER', 'PREMIUM')` |
| `ck_charge_schedules_exchange_base` | `exchange_charge_base IN ('TURNOVER', 'PREMIUM')` |
| `ck_charge_schedules_stamp_duty_base` | `stamp_duty_base IN ('TURNOVER', 'PREMIUM')` |
| `ck_charge_schedules_ipft_base` | `ipft_base IN ('TURNOVER', 'PREMIUM')` |
| `ck_charge_schedules_brokerage_cols` | Brokerage column nullability consistent with type — see §4 |
| `ck_charge_schedules_rates_non_negative` | All rate columns ≥ 0 |

### Brokerage Column Consistency Constraint

```sql
CONSTRAINT ck_charge_schedules_brokerage_cols CHECK (
    (brokerage_type = 'ZERO'
         AND brokerage_flat_per_order IS NULL
         AND brokerage_pct             IS NULL
         AND brokerage_cap_per_order   IS NULL)
    OR
    (brokerage_type = 'FLAT'
         AND brokerage_flat_per_order IS NOT NULL
         AND brokerage_pct             IS NULL
         AND brokerage_cap_per_order   IS NULL)
    OR
    (brokerage_type = 'PERCENT_CAP'
         AND brokerage_flat_per_order IS NULL
         AND brokerage_pct             IS NOT NULL
         AND brokerage_cap_per_order   IS NOT NULL)
)
```

---

## Full DDL

```sql
CREATE TABLE charge_schedules (
    id                       UUID            NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    broker                   VARCHAR(20)     NOT NULL,
    trade_type               VARCHAR(20)     NOT NULL,
    exchange_segment         VARCHAR(20)     NOT NULL,
    effective_from           DATE            NOT NULL,

    -- Brokerage
    brokerage_type           VARCHAR(20)     NOT NULL,
    brokerage_flat_per_order NUMERIC(18,4)   NULL,
    brokerage_pct            NUMERIC(18,8)   NULL,
    brokerage_cap_per_order  NUMERIC(18,4)   NULL,

    -- STT
    stt_buy_rate             NUMERIC(18,8)   NOT NULL,
    stt_sell_rate            NUMERIC(18,8)   NOT NULL,
    stt_base                 VARCHAR(10)     NOT NULL,

    -- Exchange transaction charges
    exchange_charge_rate     NUMERIC(18,8)   NOT NULL,
    exchange_charge_base     VARCHAR(10)     NOT NULL,

    -- SEBI regulatory charges (base = exchange_charge_base for this row)
    sebi_charge_rate         NUMERIC(18,8)   NOT NULL,

    -- Stamp duty (buy side only)
    stamp_duty_rate          NUMERIC(18,8)   NOT NULL,
    stamp_duty_base          VARCHAR(10)     NOT NULL,

    -- GST (on brokerage + exchange charges + SEBI — NOT on STT or stamp duty)
    gst_rate                 NUMERIC(18,8)   NOT NULL,

    -- IPFT
    ipft_rate                NUMERIC(18,8)   NOT NULL,
    ipft_base                VARCHAR(10)     NOT NULL,

    -- Audit
    notes                    TEXT            NULL,
    created_at               TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT uq_charge_schedules_lookup
        UNIQUE (broker, trade_type, exchange_segment, effective_from),

    CONSTRAINT ck_charge_schedules_broker
        CHECK (broker IN ('ZERODHA', 'UPSTOX', 'ANGEL_ONE', 'MANUAL')),

    CONSTRAINT ck_charge_schedules_trade_type
        CHECK (trade_type IN ('MIS', 'CNC', 'CNC_SAME_DAY', 'NRML_FUT', 'NRML_OPT')),

    CONSTRAINT ck_charge_schedules_exchange_segment
        CHECK (exchange_segment IN ('NSE_EQ', 'NSE_FO', 'BSE_EQ')),

    CONSTRAINT ck_charge_schedules_brokerage_type
        CHECK (brokerage_type IN ('ZERO', 'FLAT', 'PERCENT_CAP')),

    CONSTRAINT ck_charge_schedules_stt_base
        CHECK (stt_base IN ('TURNOVER', 'PREMIUM')),

    CONSTRAINT ck_charge_schedules_exchange_base
        CHECK (exchange_charge_base IN ('TURNOVER', 'PREMIUM')),

    CONSTRAINT ck_charge_schedules_stamp_duty_base
        CHECK (stamp_duty_base IN ('TURNOVER', 'PREMIUM')),

    CONSTRAINT ck_charge_schedules_ipft_base
        CHECK (ipft_base IN ('TURNOVER', 'PREMIUM')),

    CONSTRAINT ck_charge_schedules_brokerage_cols CHECK (
        (brokerage_type = 'ZERO'
             AND brokerage_flat_per_order IS NULL
             AND brokerage_pct             IS NULL
             AND brokerage_cap_per_order   IS NULL)
        OR
        (brokerage_type = 'FLAT'
             AND brokerage_flat_per_order IS NOT NULL
             AND brokerage_pct             IS NULL
             AND brokerage_cap_per_order   IS NULL)
        OR
        (brokerage_type = 'PERCENT_CAP'
             AND brokerage_flat_per_order IS NULL
             AND brokerage_pct             IS NOT NULL
             AND brokerage_cap_per_order   IS NOT NULL)
    ),

    CONSTRAINT ck_charge_schedules_rates_non_negative CHECK (
        stt_buy_rate         >= 0
        AND stt_sell_rate    >= 0
        AND exchange_charge_rate >= 0
        AND sebi_charge_rate >= 0
        AND stamp_duty_rate  >= 0
        AND gst_rate         >= 0
        AND ipft_rate        >= 0
    )
);

CREATE INDEX idx_charge_schedules_lookup
    ON charge_schedules (broker, trade_type, exchange_segment, effective_from DESC);
```

---

## Lookup Algorithm

### 5.1 — SQL Query

```sql
SELECT *
FROM   charge_schedules
WHERE  broker           = :broker
  AND  trade_type       = :trade_type
  AND  exchange_segment = :exchange_segment
  AND  effective_from   <= :trade_date
ORDER BY effective_from DESC
LIMIT  1;
```

The index `idx_charge_schedules_lookup` on `(broker, trade_type, exchange_segment, effective_from DESC)` makes this a single index range scan — no table scan.

### 5.2 — Failure Condition

If the query returns zero rows, `ChargeScheduleNotFoundError` is raised. Step 10 does not insert a `trade_pnl` row. The trade remains in `PENDING_CALCULATION` state. This is a data-maintenance error — the seed data must cover every `(broker, trade_type, exchange_segment)` combination present in the `trades` table and must have an `effective_from` ≤ the earliest `trade_date` in the data.

### 5.3 — `charge_schedule_version` Derivation

The `trade_pnl.charge_schedule_version` field (VARCHAR(50)) is constructed from the row that was used:

```
charge_schedule_version = f"{broker}_{trade_type}_{exchange_segment}_{effective_from:%Y%m%d}"

Examples:
  ZERODHA_MIS_NSE_EQ_20241001
  ZERODHA_NRML_OPT_NSE_FO_20230101
  ZERODHA_CNC_SAME_DAY_NSE_EQ_20241001
```

Maximum possible length: `ANGEL_ONE_CNC_SAME_DAY_BSE_EQ_20241001` = 38 characters. VARCHAR(50) is sufficient.

---

## Charge Calculation Formulas

### 6.1 — Turnover and Premium Base Values

Step 10 computes two base values before applying any rate:

```
entry_turnover = trades.average_entry × trades.total_entry_quantity
exit_turnover  = trades.average_exit  × trades.total_entry_quantity

entry_premium  = entry_turnover   (same formula — alias used for PREMIUM rows)
exit_premium   = exit_turnover    (same formula — alias used for PREMIUM rows)
```

For options trades, `average_entry` and `average_exit` are the option premium per unit, not the notional price. So `entry_turnover = premium_per_unit × quantity` is the correct premium turnover. The formula is identical — the distinction is in what `average_entry` represents, which is Bhima's responsibility at reconstruction time.

### 6.2 — Brokerage

Applied **per order side** (entry side and exit side independently), then summed.

```python
def brokerage_per_side(turnover: Decimal, cs: ChargeScheduleRow) -> Decimal:
    if cs.brokerage_type == 'ZERO':
        return Decimal('0')
    elif cs.brokerage_type == 'FLAT':
        return cs.brokerage_flat_per_order
    elif cs.brokerage_type == 'PERCENT_CAP':
        computed = cs.brokerage_pct * turnover
        return min(computed, cs.brokerage_cap_per_order)

brokerage = brokerage_per_side(entry_turnover, cs) + brokerage_per_side(exit_turnover, cs)
```

For `PERCENT_CAP`, `min()` operates on full-precision Decimal values. No rounding before the `min()` comparison.

### 6.3 — STT

```python
if cs.stt_base == 'TURNOVER':
    buy_base  = entry_turnover
    sell_base = exit_turnover
else:  # PREMIUM
    buy_base  = entry_premium
    sell_base = exit_premium

stt = (cs.stt_buy_rate * buy_base) + (cs.stt_sell_rate * sell_base)
```

Note: for `MIS`, `NRML_FUT`, and `NRML_OPT`, `stt_buy_rate = 0` — the buy-side term evaluates to zero without a conditional branch.

### 6.4 — Exchange Charges

Applied to both sides.

```python
if cs.exchange_charge_base == 'TURNOVER':
    total_base = entry_turnover + exit_turnover
else:  # PREMIUM
    total_base = entry_premium + exit_premium

exchange_charges = cs.exchange_charge_rate * total_base
```

### 6.5 — SEBI Charges

SEBI charges use the same base as `exchange_charge_base` for this row.

```python
sebi_charges = cs.sebi_charge_rate * total_base  # same total_base as §6.4
```

### 6.6 — Stamp Duty

**Buy side only.**

```python
if cs.stamp_duty_base == 'TURNOVER':
    stamp_base = entry_turnover
else:  # PREMIUM
    stamp_base = entry_premium

stamp_duty = cs.stamp_duty_rate * stamp_base
```

### 6.7 — GST

```python
gst_base = brokerage + exchange_charges + sebi_charges
# STT and stamp_duty are EXCLUDED from the GST base — this is statutory.
gst = cs.gst_rate * gst_base
```

### 6.8 — IPFT

```python
if cs.ipft_base == 'TURNOVER':
    ipft_base_value = entry_turnover + exit_turnover
else:  # PREMIUM
    ipft_base_value = entry_premium + exit_premium

ipft = cs.ipft_rate * ipft_base_value
```

### 6.9 — Total Charges

```python
total_charges = brokerage + stt + exchange_charges + sebi_charges + stamp_duty + gst + ipft
```

### 6.10 — Rounding and Quantization

All intermediate values (`brokerage`, `stt`, ..., `total_charges`) carry full Python `Decimal` precision throughout. Quantization to `NUMERIC(18,4)` occurs **once**, at the moment each value is assigned to the `trade_pnl` row, using `ROUND_HALF_UP` per DECIMAL-USAGE-STANDARD.md Rule 4.

```python
MONETARY = Decimal('0.0001')

trade_pnl.brokerage         = brokerage.quantize(MONETARY, rounding=ROUND_HALF_UP)
trade_pnl.stt               = stt.quantize(MONETARY, rounding=ROUND_HALF_UP)
trade_pnl.exchange_charges  = exchange_charges.quantize(MONETARY, rounding=ROUND_HALF_UP)
trade_pnl.sebi_charges      = sebi_charges.quantize(MONETARY, rounding=ROUND_HALF_UP)
trade_pnl.stamp_duty        = stamp_duty.quantize(MONETARY, rounding=ROUND_HALF_UP)
trade_pnl.gst               = gst.quantize(MONETARY, rounding=ROUND_HALF_UP)
trade_pnl.ipft              = ipft.quantize(MONETARY, rounding=ROUND_HALF_UP)

# total_charges re-summed from quantized components to satisfy the DB CHECK constraint
trade_pnl.total_charges = (
    trade_pnl.brokerage + trade_pnl.stt + trade_pnl.exchange_charges
    + trade_pnl.sebi_charges + trade_pnl.stamp_duty
    + trade_pnl.gst + trade_pnl.ipft
)
# total_charges is already NUMERIC(18,4) — sum of quantized values, no further quantize needed
```

**Critical:** `total_charges` in `trade_pnl` must equal the sum of the seven quantized component columns. The database `CHECK` constraint enforces this identity. Re-summing from the already-quantized components (not from the pre-quantization intermediates) is what guarantees the identity holds.

---

## Valid Trade-Type × Exchange-Segment Combinations

Not all (trade_type, exchange_segment) combinations are physically meaningful. Charge schedules should only be seeded for valid combinations. Invalid rows do not cause harm (they would never be looked up), but they add noise.

| trade_type | NSE_EQ | NSE_FO | BSE_EQ |
|---|---|---|---|
| `MIS` | ✓ intraday equity | ✓ intraday F&O | ✓ intraday equity |
| `CNC` | ✓ delivery equity | ✗ | ✓ delivery equity |
| `CNC_SAME_DAY` | ✓ derived sub-type | ✗ | ✓ derived sub-type |
| `NRML_FUT` | ✗ | ✓ futures positional | ✗ |
| `NRML_OPT` | ✗ | ✓ options positional | ✗ |

Phase 1 mandatory seed rows: `NSE_EQ` × `{MIS, CNC, CNC_SAME_DAY}` and `NSE_FO` × `{NRML_FUT, NRML_OPT}` — five combinations per broker per effective date.

---

## Seed Data — Zerodha, Post-Budget 2024

**Effective from: 2024-10-01**

These rates cover trades on or after 2024-10-01. The Union Budget 2024 raised F&O STT effective this date.

> **⚠ Verification required before production seeding.** NSE transaction charge rates are adjusted periodically via exchange circulars. The rates below reflect publicly available information as of the time of this specification. Cross-check against:
> - NSE circular on transaction charges (latest issue: NSE/MEM/2024/...)
> - SEBI circular on SEBI charges
> - Finance Ministry notification on STT (Finance Act 2024, effective 2024-10-01)
> - Zerodha brokerage documentation at zerodha.com/charges

### Row 1 — ZERODHA + MIS + NSE_EQ

```sql
INSERT INTO charge_schedules (
    broker, trade_type, exchange_segment, effective_from,
    brokerage_type, brokerage_flat_per_order, brokerage_pct, brokerage_cap_per_order,
    stt_buy_rate, stt_sell_rate, stt_base,
    exchange_charge_rate, exchange_charge_base,
    sebi_charge_rate,
    stamp_duty_rate, stamp_duty_base,
    gst_rate,
    ipft_rate, ipft_base,
    notes
) VALUES (
    'ZERODHA', 'MIS', 'NSE_EQ', '2024-10-01',
    'PERCENT_CAP', NULL, 0.00030000, 20.0000,
    0.00000000, 0.00025000, 'TURNOVER',
    0.00003450, 'TURNOVER',
    0.00000100,
    0.00003000, 'TURNOVER',
    0.18000000,
    0.00000100, 'TURNOVER',
    'Zerodha equity intraday (MIS), NSE. Brokerage: lower of 0.03% or ₹20 per order side. STT sell-side only 0.025% (intraday rate). Exchange charge 0.00345% per side. SEBI ₹10/crore. Stamp duty buy-side 0.003%. IPFT ₹10/crore.'
);
```

### Row 2 — ZERODHA + CNC + NSE_EQ

```sql
INSERT INTO charge_schedules (
    broker, trade_type, exchange_segment, effective_from,
    brokerage_type, brokerage_flat_per_order, brokerage_pct, brokerage_cap_per_order,
    stt_buy_rate, stt_sell_rate, stt_base,
    exchange_charge_rate, exchange_charge_base,
    sebi_charge_rate,
    stamp_duty_rate, stamp_duty_base,
    gst_rate,
    ipft_rate, ipft_base,
    notes
) VALUES (
    'ZERODHA', 'CNC', 'NSE_EQ', '2024-10-01',
    'ZERO', NULL, NULL, NULL,
    0.00100000, 0.00100000, 'TURNOVER',
    0.00003450, 'TURNOVER',
    0.00000100,
    0.00015000, 'TURNOVER',
    0.18000000,
    0.00000100, 'TURNOVER',
    'Zerodha equity delivery (CNC), NSE. Zero brokerage. STT 0.1% both sides (delivery rate). Stamp duty buy-side 0.015%.'
);
```

### Row 3 — ZERODHA + CNC_SAME_DAY + NSE_EQ

CNC opened and closed the same day. Per TRADE-DOMAIN-RULES.md Rule 3.2: delivery STT rates apply (both sides, 0.1%), and Zerodha charges zero brokerage because the product type at order entry was CNC.

```sql
INSERT INTO charge_schedules (
    broker, trade_type, exchange_segment, effective_from,
    brokerage_type, brokerage_flat_per_order, brokerage_pct, brokerage_cap_per_order,
    stt_buy_rate, stt_sell_rate, stt_base,
    exchange_charge_rate, exchange_charge_base,
    sebi_charge_rate,
    stamp_duty_rate, stamp_duty_base,
    gst_rate,
    ipft_rate, ipft_base,
    notes
) VALUES (
    'ZERODHA', 'CNC_SAME_DAY', 'NSE_EQ', '2024-10-01',
    'ZERO', NULL, NULL, NULL,
    0.00100000, 0.00100000, 'TURNOVER',
    0.00003450, 'TURNOVER',
    0.00000100,
    0.00015000, 'TURNOVER',
    0.18000000,
    0.00000100, 'TURNOVER',
    'Zerodha CNC opened and closed same day, NSE. Delivery STT rates apply both sides (0.1%) per TRADE-DOMAIN-RULES Rule 3.2. Zero brokerage (product type at entry was CNC).'
);
```

### Row 4 — ZERODHA + NRML_FUT + NSE_FO

Post-Budget 2024: futures STT raised from 0.0125% to 0.02% on sell side.

```sql
INSERT INTO charge_schedules (
    broker, trade_type, exchange_segment, effective_from,
    brokerage_type, brokerage_flat_per_order, brokerage_pct, brokerage_cap_per_order,
    stt_buy_rate, stt_sell_rate, stt_base,
    exchange_charge_rate, exchange_charge_base,
    sebi_charge_rate,
    stamp_duty_rate, stamp_duty_base,
    gst_rate,
    ipft_rate, ipft_base,
    notes
) VALUES (
    'ZERODHA', 'NRML_FUT', 'NSE_FO', '2024-10-01',
    'PERCENT_CAP', NULL, 0.00030000, 20.0000,
    0.00000000, 0.00020000, 'TURNOVER',
    0.00001880, 'TURNOVER',
    0.00000100,
    0.00002000, 'TURNOVER',
    0.18000000,
    0.00000100, 'TURNOVER',
    'Zerodha NSE futures (NRML_FUT). STT sell-side 0.02% on turnover — raised from 0.0125% by Union Budget 2024, effective 2024-10-01. Exchange charge 0.00188% per side on turnover. Stamp duty buy-side 0.002%.'
);
```

### Row 5 — ZERODHA + NRML_OPT + NSE_FO

Post-Budget 2024: options STT raised from 0.0625% to 0.1% on sell side (applied to premium, not notional).

```sql
INSERT INTO charge_schedules (
    broker, trade_type, exchange_segment, effective_from,
    brokerage_type, brokerage_flat_per_order, brokerage_pct, brokerage_cap_per_order,
    stt_buy_rate, stt_sell_rate, stt_base,
    exchange_charge_rate, exchange_charge_base,
    sebi_charge_rate,
    stamp_duty_rate, stamp_duty_base,
    gst_rate,
    ipft_rate, ipft_base,
    notes
) VALUES (
    'ZERODHA', 'NRML_OPT', 'NSE_FO', '2024-10-01',
    'FLAT', 20.0000, NULL, NULL,
    0.00000000, 0.00100000, 'PREMIUM',
    0.00050300, 'PREMIUM',
    0.00000100,
    0.00003000, 'PREMIUM',
    0.18000000,
    0.00000100, 'PREMIUM',
    'Zerodha NSE options (NRML_OPT). Flat brokerage ₹20 per order side. STT sell-side 0.1% on option premium — raised from 0.0625% by Union Budget 2024, effective 2024-10-01. Exchange charge 0.0503% on premium per side. Stamp duty buy-side 0.003% on premium. SEBI and IPFT on premium.'
);
```

---

## Seed Data — Zerodha, Pre-Budget 2024

**Effective from: 2023-01-01**

These rows cover historical trades before the Budget 2024 STT changes. Only the F&O rows differ from the 2024-10-01 set. The equity rows (MIS, CNC, CNC_SAME_DAY) are identical to the 2024-10-01 versions — seed them with `effective_from = '2023-01-01'` if users have trades before October 2024.

> **Note on NSE exchange charges:** NSE also revised its transaction charge structure in July 2024. The values used for `exchange_charge_rate` in both sets are consistent with commonly cited post-July-2024 rates. If TradeForge ingests trades from before July 2024, a third effective-date set may be required for precise exchange charge accuracy. The STT boundary (2024-10-01) is more material and is the minimum requirement for Phase 1.

### Row 4H — ZERODHA + NRML_FUT + NSE_FO (historical)

```sql
INSERT INTO charge_schedules (
    broker, trade_type, exchange_segment, effective_from,
    brokerage_type, brokerage_flat_per_order, brokerage_pct, brokerage_cap_per_order,
    stt_buy_rate, stt_sell_rate, stt_base,
    exchange_charge_rate, exchange_charge_base,
    sebi_charge_rate,
    stamp_duty_rate, stamp_duty_base,
    gst_rate,
    ipft_rate, ipft_base,
    notes
) VALUES (
    'ZERODHA', 'NRML_FUT', 'NSE_FO', '2023-01-01',
    'PERCENT_CAP', NULL, 0.00030000, 20.0000,
    0.00000000, 0.00012500, 'TURNOVER',
    0.00001880, 'TURNOVER',
    0.00000100,
    0.00002000, 'TURNOVER',
    0.18000000,
    0.00000100, 'TURNOVER',
    'Zerodha NSE futures (NRML_FUT). Pre-Budget-2024 rates. STT sell-side 0.0125% on turnover (Finance Act pre-2024-10-01).'
);
```

### Row 5H — ZERODHA + NRML_OPT + NSE_FO (historical)

```sql
INSERT INTO charge_schedules (
    broker, trade_type, exchange_segment, effective_from,
    brokerage_type, brokerage_flat_per_order, brokerage_pct, brokerage_cap_per_order,
    stt_buy_rate, stt_sell_rate, stt_base,
    exchange_charge_rate, exchange_charge_base,
    sebi_charge_rate,
    stamp_duty_rate, stamp_duty_base,
    gst_rate,
    ipft_rate, ipft_base,
    notes
) VALUES (
    'ZERODHA', 'NRML_OPT', 'NSE_FO', '2023-01-01',
    'FLAT', 20.0000, NULL, NULL,
    0.00000000, 0.00062500, 'PREMIUM',
    0.00050300, 'PREMIUM',
    0.00000100,
    0.00003000, 'PREMIUM',
    0.18000000,
    0.00000100, 'PREMIUM',
    'Zerodha NSE options (NRML_OPT). Pre-Budget-2024 rates. STT sell-side 0.0625% on option premium (Finance Act pre-2024-10-01).'
);
```

Equity rows (MIS, CNC, CNC_SAME_DAY) for `effective_from = '2023-01-01'` are identical to Rows 1–3 above — only the date differs. Bhima inserts three additional rows with `effective_from = '2023-01-01'` and all other values matching.

---

## Seed Data — Zerodha, BSE Equity

**Optional for Phase 1 MVP.** Required if users import BSE equity trades. Effective from: 2024-10-01.

BSE equity differences vs NSE:
- Exchange charges differ (BSE has different transaction fee rates).
- IPFT: BSE does not charge IPFT under the NSE mechanism — use `0.00000000`.

> **⚠ BSE exchange charge rates require verification against current BSE circulars before seeding.** The approximate figures below are for planning purposes only.

| Column | MIS + BSE_EQ | CNC + BSE_EQ | CNC_SAME_DAY + BSE_EQ |
|---|---|---|---|
| brokerage_type | PERCENT_CAP | ZERO | ZERO |
| brokerage_pct | 0.00030000 | NULL | NULL |
| brokerage_cap_per_order | 20.0000 | NULL | NULL |
| stt_buy_rate | 0.00000000 | 0.00100000 | 0.00100000 |
| stt_sell_rate | 0.00025000 | 0.00100000 | 0.00100000 |
| stt_base | TURNOVER | TURNOVER | TURNOVER |
| exchange_charge_rate | 0.00003750 | 0.00000000 | 0.00000000 |
| exchange_charge_base | TURNOVER | TURNOVER | TURNOVER |
| sebi_charge_rate | 0.00000100 | 0.00000100 | 0.00000100 |
| stamp_duty_rate | 0.00003000 | 0.00015000 | 0.00015000 |
| stamp_duty_base | TURNOVER | TURNOVER | TURNOVER |
| gst_rate | 0.18000000 | 0.18000000 | 0.18000000 |
| ipft_rate | 0.00000000 | 0.00000000 | 0.00000000 |
| ipft_base | TURNOVER | TURNOVER | TURNOVER |

---

## Complete Worked Example

**MIS trade, ZERODHA, NSE_EQ, trade_date = 2025-03-15 (uses 2024-10-01 schedule)**

```
Direction:            LONG
average_entry:        ₹2,450.0000
average_exit:         ₹2,480.0000
total_entry_quantity: 100 units

entry_turnover = 2450.0000 × 100 = ₹2,45,000.0000
exit_turnover  = 2480.0000 × 100 = ₹2,48,000.0000
gross_pnl      = (2480.0000 − 2450.0000) × 100 = ₹3,000.0000

--- Charges (full Decimal precision, no intermediate rounding) ---

brokerage_per_entry = min(0.00030000 × 2,45,000, 20.0000) = min(73.5000, 20.0000) = 20.0000
brokerage_per_exit  = min(0.00030000 × 2,48,000, 20.0000) = min(74.4000, 20.0000) = 20.0000
brokerage           = 20.0000 + 20.0000 = 40.0000

stt_buy  = 0.00000000 × 2,45,000 = 0.0000
stt_sell = 0.00025000 × 2,48,000 = 62.0000
stt      = 62.0000

exchange_charges = 0.00003450 × (2,45,000 + 2,48,000)
                 = 0.00003450 × 4,93,000
                 = 17.0085

sebi_charges = 0.00000100 × 4,93,000 = 0.4930

stamp_duty = 0.00003000 × 2,45,000 = 7.3500   (buy side only)

gst_base = 40.0000 + 17.0085 + 0.4930 = 57.5015
gst      = 0.18000000 × 57.5015 = 10.3503 (full precision: 10.350270)

ipft = 0.00000100 × 4,93,000 = 0.4930

total_charges (pre-quantize) = 40.0000 + 62.0000 + 17.0085 + 0.4930 + 7.3500 + 10.3503 + 0.4930
                              = 137.6948 (full precision: 137.694770...)

--- Quantize each component (ROUND_HALF_UP, 4dp) ---

brokerage        stored: 40.0000
stt              stored: 62.0000
exchange_charges stored: 17.0085
sebi_charges     stored:  0.4930
stamp_duty       stored:  7.3500
gst              stored: 10.3503   (10.350270 → rounds to 10.3503)
ipft             stored:  0.4930

total_charges    stored: 40.0000 + 62.0000 + 17.0085 + 0.4930 + 7.3500 + 10.3503 + 0.4930
                       = 137.6948

net_pnl = 3,000.0000 − 137.6948 = 2,862.3052
```

The `CHECK` constraint `total_charges = brokerage + stt + exchange_charges + sebi_charges + stamp_duty + gst + ipft` is satisfied: `137.6948 = 40.0000 + 62.0000 + 17.0085 + 0.4930 + 7.3500 + 10.3503 + 0.4930`.

---

## Phase 2 Extension Point — Account-Specific Rates

Per ADR-005 Q1: account-specific brokerage rates are out of scope for Phase 1.

When Phase 2 introduces account-specific rates, the extension is additive:

1. Add nullable column: `ALTER TABLE charge_schedules ADD COLUMN account_id UUID NULL REFERENCES trading_accounts(id)`.
2. Update the UNIQUE constraint: drop `uq_charge_schedules_lookup`, create new unique index on `(broker, trade_type, exchange_segment, effective_from, account_id)` with `NULLS NOT DISTINCT` if PostgreSQL ≥ 15, or a partial index strategy for earlier versions.
3. Update the lookup query to prefer account-specific rows over broker-level rows:

```sql
SELECT *
FROM   charge_schedules
WHERE  broker           = :broker
  AND  trade_type       = :trade_type
  AND  exchange_segment = :exchange_segment
  AND  effective_from   <= :trade_date
  AND  (account_id = :account_id OR account_id IS NULL)
ORDER BY account_id NULLS LAST, effective_from DESC
LIMIT  1;
```

This query returns the account-specific row if one exists, otherwise falls back to the broker-level row (`account_id IS NULL`).

**No existing Phase 1 rows need to be modified.** All existing rows have `account_id = NULL` and continue to function as broker-level defaults.

**This extension point must not be closed by Step 10.** Specifically: the `charge_schedules` table must not receive a `NOT NULL` constraint on any column that would need to differ between broker-level and account-level rows.

---

## Rate Sources and Verification References

| Charge | Authoritative source |
|---|---|
| STT | Finance Act (annual budget) — Ministry of Finance notification. Budget 2024 raised F&O STT effective 2024-10-01. |
| Exchange transaction charges | NSE / BSE circulars to members. NSE posts circulars at nseindia.com → Regulations → Circulars. |
| SEBI regulatory charges | SEBI circular. Currently ₹10 per crore on gross turnover. |
| Stamp duty | State-level stamp acts; national rates adopted by most states. |
| GST | GST Council notification. Currently 18% statutory. |
| IPFT | NSE circular (specific to NSE-listed instruments). |
| Brokerage structure | Broker's published tariff card (e.g., zerodha.com/charges). |

**Nakula is responsible for keeping `charge_schedules` current** when any of these sources issue a change. A missed rate update is a systematic P&L calculation error across all affected trades. Rate changes should be seeded as new rows with the correct `effective_from` date — never by modifying existing rows.

---

*Kubera — Financial Calculation & P&L Specialist*
*This specification is binding on Bhima (Step 10 migration and engine implementation), Nakula (seed data maintenance), and Sahadeva (charge verification test cases). It does not constitute tax advice.*
