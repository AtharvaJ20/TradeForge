# Trade Domain Rules

**Status:** Authoritative — binding on all TradeForge implementation
**Author:** Ganesha (Trading Domain Analyst)
**Date:** 2026-08-22
**Binding on:** Bhima (backend implementation), Kubera (P&L and charge engine), Karna (analytics), Sanjaya (broker integration and import), Sahadeva (QA)
**Reviewed by:** Kubera (open questions resolved), Krishna (pre-development readiness check)

---

## Purpose

This document contains every trading-domain rule that has been formally resolved for TradeForge. It is the authoritative reference for the Indian equity and derivatives market domain model. Bhima must not implement any trade, order, or execution data model without first satisfying every rule here.

Any rule not covered here is **unresolved** and must be brought to Ganesha before implementation touches the affected domain.

---

## Scope

TradeForge Phase 1 covers the following instruments on Indian exchanges (NSE and BSE):

| Instrument class | Exchange segment | Examples |
|---|---|---|
| Equity (cash segment) | NSE EQ, BSE EQ | RELIANCE, INFY, NIFTY ETFs |
| Equity Futures | NSE FO | RELIANCE JAN FUT, NIFTY JAN FUT |
| Index Futures | NSE FO | NIFTY JAN FUT, BANKNIFTY JAN FUT |
| Equity Options | NSE FO | RELIANCE 2600 JAN CE |
| Index Options | NSE FO | NIFTY 24000 JAN CE, BANKNIFTY 52000 JAN PE |

Currency derivatives, commodity derivatives, and international instruments are **out of Phase 1 scope**.

---

## Part 1 — Trade Identity

### Rule 1.1 — A Trade Is Not a Fill

**Authoritative definition:**

A **trade** is a complete cycle: entry → management → exit. It represents a single idea expressed in the market. A trade begins when the first entry fill executes and ends when the net position in that instrument returns to zero.

A **fill** (also called an execution) is a single order execution at a single price and timestamp. One trade can contain multiple fills — both on entry and on exit.

An **order** is an instruction sent to the broker. It is not a trade. An order may result in one fill, multiple fills (partial fills over time), or no fill (cancelled, rejected).

**Implications for the data model:**

```
trade (1) ──────────────────── (*) execution_fills
trade (1) ──────────────────── (*) management_events
trade (1) has a stable trade_id that spans all its fills
```

A `trade_id` is assigned when the first entry fill executes and must not change across subsequent fills, partial exits, or management events on that position.

**What this is NOT:**

- One order = one trade: incorrect. A position built via three separate limit orders over 20 minutes is still one trade.
- One day = one trade: incorrect. A trade opened on Tuesday and closed on Wednesday is one trade (a swing trade), not two trades.
- One broker API event = one trade: incorrect. Broker execution messages are raw fills. TradeForge's trade reconstruction engine (Sanjaya → Bhima) groups fills into trades by instrument, direction, and position lifecycle.

---

### Rule 1.2 — Trade Lifecycle and Position Tracking

A trade is **open** from the first entry fill until the net position reaches zero.

**Partial position tracking:**

```
State after Fill 1 (BUY 100): net_position = +100, trade = OPEN
State after Fill 2 (BUY 100): net_position = +200, trade = OPEN
State after Fill 3 (SELL 150): net_position = +50,  trade = PARTIAL (partial exit recorded)
State after Fill 4 (SELL 50):  net_position = 0,    trade = CLOSED
```

The trade closes when `net_position = 0`. The `closed_at` timestamp is the timestamp of the final exit fill.

**Same instrument, new trade:**

If a trader closes a position completely and then re-enters the same instrument in the same session, that is a **new trade** with a new `trade_id`. Position returning to zero is the boundary condition.

---

## Part 2 — Average Entry and Exit Price

### Rule 2.1 — Average Entry Price for Fills Within a Single Trade

When a single trade is built through multiple fills (scaled entry), the **average entry price** is the weighted average of all entry fills by quantity:

```
average_entry = Σ(fill_quantity_i × fill_price_i) / Σ(fill_quantity_i)
```

**Example:**

```
Fill 1: BUY 100 shares @ ₹251.20  →  value = ₹25,120.00
Fill 2: BUY 100 shares @ ₹250.50  →  value = ₹25,050.00
Fill 3: BUY 200 shares @ ₹252.00  →  value = ₹50,400.00

Total quantity: 400 shares
Total value: ₹100,570.00
Average entry price: ₹100,570.00 / 400 = ₹251.4250
```

The average entry price is the canonical entry for all P&L and R-multiple calculations on this trade. Kubera uses `average_entry` — never an individual fill price — as the entry input to the gross P&L formula.

**The same rule applies to exit fills:**

```
average_exit = Σ(exit_fill_quantity_i × exit_fill_price_i) / Σ(exit_fill_quantity_i)
```

**Rounding:** average_entry and average_exit are stored at 4 decimal places (PRICE constant from DECIMAL-USAGE-STANDARD.md). Intermediate calculations carry full Decimal precision before quantization.

---

### Rule 2.2 — Partial Exit P&L

When a position is partially closed across multiple exit fills, the P&L for each exit event is calculated against the **current average entry at the time of that exit**. The average entry does not change on a partial exit (only on a scale-in).

```
partial_pnl = (exit_price − average_entry) × exit_quantity   [for LONG]
partial_pnl = (average_entry − exit_price) × exit_quantity   [for SHORT]
```

The total trade P&L is the sum of all partial exit P&Ls:

```
gross_pnl = Σ(partial_pnl_i for all exit fills)
```

This is equivalent to the simplified formula:

```
gross_pnl = (average_exit − average_entry) × total_quantity   [for LONG]
```

Both formulations produce the same result and Kubera may use either. The per-partial-exit representation is required for the journal's per-management-event P&L breakdown.

---

## Part 3 — Trade Classification (Indian Market)

### Rule 3.1 — `product_type` Is the Authoritative Classification Trigger

In TradeForge's Indian market context, the **classification of a trade as intraday or delivery (or F&O) is determined by the `product_type` field on the order at the time of order entry.** It is not inferred from trading behavior after the fact.

**This rule is absolute.** The system never reclassifies a trade based on whether it was actually squared off same-day or carried overnight. The `product_type` set at order entry is the permanent classification trigger for:

- STT (Securities Transaction Tax) rate selection
- Stamp duty rate selection
- Exchange transaction charge rate selection
- SEBI charge rate selection
- Brokerage calculation formula
- Tax lot accounting method

**The authoritative `product_type` enum:**

| Value | Full name | Meaning |
|---|---|---|
| `MIS` | Margin Intraday Square-off | Intraday equity or F&O. Must be squared off by the broker's MIS cutoff time (typically 3:20 PM for equities, varies by broker). If not squared off by the trader, the broker auto-squares the position. |
| `CNC` | Cash and Carry | Delivery equity. Overnight hold is intended and permitted. Debit from trading account on T+1, shares delivered on T+1. |
| `NRML` | Normal | F&O (futures and options) positional. Overnight hold permitted. Uses full SPAN margin. |
| `CNC_SAME_DAY` | CNC bought and sold same day | A CNC delivery order that happens to be opened and closed within the same trading session. See Rule 3.2. |

**The `product_type` is recorded on each execution fill.** When Sanjaya imports broker data, this field must be preserved from the raw broker record — it must not be recomputed.

---

### Rule 3.2 — `CNC_SAME_DAY` Is a Distinct Sub-type

`CNC_SAME_DAY` is not a separate product type offered by the broker. It is a TradeForge classification applied during trade reconstruction when both of the following are true:

1. The execution fills carry `product_type = CNC`.
2. The trade's entry and exit occur on the same calendar date (i.e., `first_fill.trade_date == last_fill.trade_date`).

**Why `CNC_SAME_DAY` is a distinct sub-type:**

For STT purposes, a CNC trade that is opened and closed on the same day is treated differently than a CNC delivery trade. SEBI applies the **delivery STT rate** (currently 0.1% on both buy and sell legs) rather than the intraday STT rate (0.025% on sell leg only), because the order type at placement was CNC, not MIS. This has a material impact on the STT charge calculation.

**`CNC_SAME_DAY` is a derived field, not a user-entered field.** Bhima's trade reconstruction engine computes it. It is never stored in the raw execution fill record — it is set on the reconstructed trade record.

**Summary of the classification hierarchy:**

```
product_type (from broker, per fill) → determines base classification
    MIS   → intraday equity
    CNC   → delivery equity
    NRML  → F&O positional

trade reconstruction (Bhima) → adds derived sub-type
    CNC + same-day open and close → trade.trade_type = CNC_SAME_DAY
    CNC + overnight hold          → trade.trade_type = CNC
    MIS                           → trade.trade_type = MIS
    NRML                          → trade.trade_type = NRML
```

---

### Rule 3.3 — `trade_type` Is the Authoritative Input to the Charge Engine

The **`trade_type`** field on the reconstructed trade record is what Kubera's charge engine reads to select the correct charge schedule. It is the single source of truth for charge calculation.

**`trade_type` enum (stored on the `trades` table):**

| `trade_type` value | Source | STT basis | Brokerage |
|---|---|---|---|
| `MIS` | `product_type = MIS` | Intraday — sell side only, 0.025% | Per broker MIS schedule |
| `CNC` | `product_type = CNC`, overnight | Delivery — both sides, 0.1% each | Per broker CNC schedule |
| `CNC_SAME_DAY` | `product_type = CNC`, same-day close | Delivery STT rates apply (both sides, 0.1%) | Per broker CNC schedule |
| `NRML_FUT` | `product_type = NRML`, futures contract | Futures — sell side only, 0.0125% | Per broker NRML schedule |
| `NRML_OPT` | `product_type = NRML`, options contract | Options — sell side only, 0.0625% on premium | Per broker NRML schedule |

**`NRML_FUT` vs. `NRML_OPT` disambiguation:** Both use `product_type = NRML`. Bhima's trade reconstruction distinguishes them by the instrument class of the underlying fill — whether the fill's `instrument_class` is `FUTURES` or `OPTIONS`. This is resolved at reconstruction time, not at order entry.

**Kubera receives `trade_type` as a given.** Kubera does not re-derive the classification. If `trade_type` is wrong, the charge calculation is wrong. Correctness of `trade_type` is Bhima and Sanjaya's responsibility.

---

## Part 4 — Tax Lot Accounting

### Rule 4.1 — FIFO for Tax Lots Across Separate Delivery Trades

When a trader holds multiple separate purchases of the same equity in the delivery segment (multiple CNC trades on different dates that are all currently open), and begins to sell, the **FIFO (First In, First Out)** method determines which purchase lot is being closed.

**The rule:**

> The oldest open tax lot (earliest purchase date) is closed first, regardless of the price at which it was purchased.

**Example:**

```
Lot A: BUY 100 RELIANCE @ ₹2,400  on 2026-01-15  (oldest)
Lot B: BUY 200 RELIANCE @ ₹2,600  on 2026-02-10
Lot C: BUY 150 RELIANCE @ ₹2,550  on 2026-03-05  (newest)

SELL 150 RELIANCE on 2026-04-01 (CNC):
  → 100 shares from Lot A are closed (entire Lot A)
  → 50 shares from Lot B are closed (partial close of Lot B)
  → Lot C is untouched

Remaining after the sale:
  Lot B (remaining): 150 RELIANCE @ ₹2,600 (original lot, partial)
  Lot C: 150 RELIANCE @ ₹2,550
```

**FIFO applies across the portfolio** for the same instrument in the delivery segment. It does not apply within a single intraday trade (see Rule 4.2).

**FIFO is a tax lot accounting rule, not a trade identity rule.** Each original purchase is still its own trade. FIFO determines the cost basis allocation when an exit fill partially closes multiple open lots.

**Scope:** FIFO applies to `CNC` and `CNC_SAME_DAY` trades in the equity segment. For F&O (`NRML_FUT`, `NRML_OPT`), no tax lot carryover applies — F&O positions settle at expiry or are closed explicitly. F&O tax lot rules are **unresolved** (see Part 6).

---

### Rule 4.2 — FIFO Does Not Apply Within a Single Intraday Trade

For MIS (intraday) trades, a position is always opened and closed within the same session. There is no multi-day tax lot accumulation. The average cost rule from Rule 2.1 applies to all fills within that single trade.

FIFO is irrelevant for MIS trades.

---

### Rule 4.3 — `tax_lots` Table Is Required

The FIFO rule requires Bhima to maintain a `tax_lots` table (or equivalent) that tracks individual purchase lots for the delivery segment. The minimum fields required:

```
tax_lot_id         — unique identifier
trade_id           — the originating CNC trade
user_id            — owner
instrument_id      — the instrument
purchase_date      — trade_date of the opening fill
quantity_remaining — shares still open in this lot (decremented on each closing fill)
cost_per_share     — average_entry of the originating trade (4dp)
status             — open / partially_closed / closed
```

When a CNC sell fill arrives during trade reconstruction:
1. Identify all open tax lots for this instrument for this user, ordered by `purchase_date ASC` (FIFO order).
2. Allocate the sell quantity against lots starting from the oldest.
3. Decrement `quantity_remaining` on affected lots.
4. Record the cost basis (from the lot's `cost_per_share`) used for that portion of the exit fill.
5. The P&L for a closed tax lot uses the lot's `cost_per_share` as the entry cost.

**This data model is required before Bhima implements trade reconstruction for the delivery segment.**

---

## Part 5 — Indian Market Specifics

### Rule 5.1 — Exchange Segments and Instrument Identification

Every instrument in TradeForge must be identified by its combination of:

- **Symbol** (e.g., `RELIANCE`, `NIFTY`)
- **Exchange segment** (e.g., `NSE_EQ`, `NSE_FO`, `BSE_EQ`)
- **Instrument type** (e.g., `EQ`, `FUT`, `CE`, `PE`)
- **Expiry date** (for derivatives — `None` for equity)
- **Strike price** (for options — `None` for equity and futures)

The same company (e.g., Reliance Industries) trades in multiple segments with different ISINs, contract specifications, and applicable charges. The combination of these five fields uniquely identifies an instrument.

**ISIN** is the persistent identifier for equity instruments across corporate actions (name changes, mergers). It must be stored alongside the trading symbol. The trading symbol may change; the ISIN does not.

---

### Rule 5.2 — Trade Date vs. Settlement Date

**Trade date** (`trade_date`): the calendar date on which the order was executed. This is the date used for:
- Trade classification (same-day close detection for `CNC_SAME_DAY`)
- FIFO tax lot ordering
- P&L date attribution in analytics
- Journal entry date

**Settlement date**: the date on which securities are delivered and cash settles. For Indian equities, settlement is T+1 (effective since 2023). Settlement date is **not** used for trade classification, P&L attribution, or tax lot ordering in TradeForge. Settlement date may be stored for reference in broker reconciliation but carries no domain logic in Phase 1.

---

### Rule 5.3 — Session Definition

Indian equity market regular session: **09:15 IST to 15:30 IST**, Monday through Friday, NSE/BSE trading days.

Pre-open session: 09:00–09:15 IST. Orders placed in the pre-open session execute at the pre-open equilibrium price. Fills in the pre-open session carry `session = PRE_OPEN`.

Post-close session: 15:40–16:00 IST (closing price session). Fills in this session carry `session = POST_CLOSE`.

All fills must record their `session` tag:

| `session` value | Time window |
|---|---|
| `PRE_OPEN` | 09:00–09:14:59 IST |
| `REGULAR` | 09:15–15:30:00 IST |
| `POST_CLOSE` | 15:40–16:00:00 IST |

MIS positions that are not squared off by the trader are auto-squared by the broker between 15:10 and 15:20 IST (exact cutoff varies by broker). These auto-square fills must be tagged `exit_type = FORCED` and `session = REGULAR`.

---

### Rule 5.4 — Lot Size for Derivatives

All futures and options contracts in the Indian market have a **lot size** defined by the exchange. The lot size is the minimum tradeable quantity.

The lot size for index contracts changes periodically (SEBI revises lot sizes based on contract value thresholds). **Lot size must be stored per instrument per effective date** — it cannot be a static constant in the application code.

The P&L for a futures/options position is:

```
gross_pnl = (exit_price − entry_price) × lot_size × number_of_lots   [for LONG FUT]
gross_pnl = (entry_price − exit_price) × lot_size × number_of_lots   [for SHORT FUT]

gross_pnl = (exit_premium − entry_premium) × lot_size × number_of_lots   [for LONG OPT]
gross_pnl = (entry_premium − exit_premium) × lot_size × number_of_lots   [for SHORT OPT]
```

Kubera receives `lot_size` as a field on the instrument record, not as a hardcoded value.

---

## Part 6 — Unresolved Domain Questions

The following questions have **not** been formally resolved by Ganesha. Bhima must not implement logic that depends on these until they are resolved.

### Unresolved 1 — F&O Expiry Handling

**Question:** When an options contract expires worthless (premium goes to zero at expiry, no exercise), how is the trade record closed? Is the `exit_price = 0`, is the exit fill timestamp the expiry time, and is the `exit_type = EXPIRY_WORTHLESS`?

When a futures contract expires, it settles at the final settlement price published by NSE. How is this closing fill recorded — does it arrive from the broker as a fill, or does TradeForge synthesize it from the settlement price?

**Blocked:** Options and futures expiry handling in Sanjaya's import pipeline and Bhima's trade reconstruction.

---

### Unresolved 2 — Options Exercise and Assignment

**Question:** When a long ITM option is exercised by the holder, or when a short option is assigned, the resulting position is in the underlying. What is the cost basis of that underlying position? How is the transition from the options trade to the equity position recorded — as a closing fill on the option and an opening fill on the equity?

**Blocked:** Options exercise/assignment flow in Bhima's trade reconstruction and Kubera's P&L treatment of the resulting position.

---

### Unresolved 3 — Corporate Actions on Delivery Holdings

**Question:** When a stock split or bonus issue occurs on an equity instrument that has open tax lots, how are historical cost bases adjusted? Example: a 2:1 bonus means the trader now holds twice the shares at half the cost per share. Are the tax lot records retroactively updated, or is a corporate action event recorded and the adjustment applied prospectively?

**Blocked:** Corporate action handling in the tax lot engine and historical P&L display.

---

### Unresolved 4 — Multi-Day Partial Exits for Delivery Trades

**Question:** When a delivery trade (CNC) with multiple tax lots has partial exits on different days, how is the per-day P&L attributed? Example: Lot A (100 shares) was bought on Jan 15. On Feb 10, 50 shares are sold (partial, FIFO closes 50 from Lot A). On Feb 20, the remaining 50 shares are sold (Lot A fully closed). Does the trade record show two exit events with FIFO-attributed P&L, or is there one trade record with a single aggregated P&L?

**Resolution needed from Ganesha.** Sanjaya and Bhima need this before implementing delivery segment trade reconstruction with multi-day exits.

---

### Unresolved 5 — F&O Tax Lot Accounting

**Question:** For `NRML_FUT` and `NRML_OPT` trades, does FIFO apply if a trader builds a futures position across multiple days (rolling adds, not contract rollovers)? Or does each add-to-position event extend the same trade, and the average cost rule applies?

**Blocked:** F&O positional trade reconstruction where the position is built incrementally.

---

## Handoff Notes for Bhima

The following schema elements follow directly from the rules in this document and must be reflected in the database design:

1. **`trades` table** must have a `trade_type` column of type `VARCHAR` or an `ENUM` with values: `MIS`, `CNC`, `CNC_SAME_DAY`, `NRML_FUT`, `NRML_OPT`. This is a mandatory field — no trade record may exist without a `trade_type`.

2. **`execution_fills` table** must have a `product_type` column preserving the broker-reported value: `MIS`, `CNC`, `NRML`. This is the immutable raw record from the broker. It must not be altered during reconstruction.

3. **`tax_lots` table** is required before delivery segment P&L can be computed. See Rule 4.3 for minimum fields.

4. **`trades.average_entry`** and **`trades.average_exit`** are computed fields, stored at `NUMERIC(18, 4)` per DECIMAL-USAGE-STANDARD.md Rule 7.

5. **`instruments` table** must include `lot_size` (for derivatives) and `isin` (for equity). Lot size is a dated attribute — its effective date must be tracked for historical accuracy.

6. **`execution_fills.session`** must be set during import/reconstruction. Values: `PRE_OPEN`, `REGULAR`, `POST_CLOSE`.

---

*Ganesha — Trading Domain Analyst*
*This document supersedes any informal domain discussions preceding it. All rules herein are binding unless formally revised by Ganesha.*
