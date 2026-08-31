# ADR-005: TradingAccount Introduction — Deferred to Step 11

**Status:** Accepted
**Author:** Mayasura (Software Architect)
**Requested by:** Krishna (Project Manager) — traceability gap §7
**Date:** 2026-08-24
**Decision authority:** Atharva

---

## Context

The trade domain tables (`trades`, `execution_fills`, `tax_lots`, `trade_pnl`, `journal_entries`) currently use `user_id` as the sole authorization and grouping boundary. No `TradingAccount` entity exists. The requirements (§7) require multi-account support. The traceability review (2026-08-24) flagged the absence of `account_id` as a growing migration risk — one that compounds with every step implemented without it.

The data model (`TRADE-DOMAIN-DATA-MODEL.md`) already documents that `execution_fills.broker` will remain a `VARCHAR` in Phase 1 and will FK to `broker_accounts(id)` in Phase 2 (ADR-002). `TradingAccount` is the same decision — never formally recorded as an ADR.

The question triggering this ADR: **must `TradingAccount` be introduced before Step 10 (P&L Engine)?**

---

## Findings

**1. The data model already made the Phase 1 / Phase 2 call — partially.**

`TRADE-DOMAIN-DATA-MODEL.md` line 277 documents this explicitly:

> `broker` | `VARCHAR(20)` | NOT NULL | Phase 1 VARCHAR; Phase 2 will FK to `broker_accounts(id)` when KMS credential storage is introduced (ADR-002).

The `broker_accounts` / credential table deferral is already on record. `TradingAccount` is the same decision.

**2. Step 10 has no dependency on account context.**

Step 10 reads `trades`, `execution_fills`, `lot_size_history`, and `journal_entries`. It writes `trade_pnl`. Its only account-adjacent input is `execution_fills.broker` (a string), which it uses to look up charge schedules. That lookup is broker-string-based, not account-based. There is no Step 10 code path that would use `account_id` even if it existed.

**3. Every table uses `user_id` for authorization today.**

`trades`, `execution_fills`, `tax_lots`, `trade_pnl`, `journal_entries` — all carry `user_id` and use it as the RLS boundary. Adding `account_id` later is an additive `ALTER TABLE … ADD COLUMN UUID NULL`. In PostgreSQL this is a metadata-only operation — no table rewrite, no downtime. The `NOT NULL` constraint is applied after backfill.

**4. Step 11 is the natural binding point, not Step 10.**

Account selection happens at import time. When the user uploads a broker CSV, they choose which trading account it belongs to. That assignment flows from the import into fills, and from fills into trades. There is no import mechanism before Step 11 — adding `account_id` before Step 11 creates a column that can never be populated by any production path.

**5. Deferring past Step 12 creates a refactor risk.**

Karna's aggregation queries (Step 12) will be built against the then-current schema. If `account_id` is not present, those queries will have no account dimension. Adding it post-Step 12 means refactoring every aggregation, every index, and every API response shape Karna defines. That is the true deferral cost — not Step 10.

---

## Options Considered

### Option A — Introduce TradingAccount at Step 11 *(Recommended)*

Add `trading_accounts` table in Step 11's migration. Add nullable `account_id` FK to `trades`, `execution_fills`, and `trade_pnl` in the same migration. The Step 11 import pipeline binds every imported fill to a user-selected account at ingestion time. Trades inherit `account_id` from their fills at reconstruction time. After the first successful import, the nullable constraint is promoted to `NOT NULL` via a follow-on migration. Step 10 code requires zero changes. Karna (Step 12) designs all aggregation queries with `account_id` present from day one.

**Consequences:**
- Step 10 is unblocked. No risk to the P&L engine timeline.
- Step 11 migration owns the full account model — no orphaned schema.
- Step 12 analytics are account-aware from the start.
- `trade_pnl` rows created by Step 10 test runs will have `account_id = NULL`. The Step 11 migration must backfill these or accept them as NULL in local dev only.
- If account-specific brokerage rates become a Phase 1 requirement, the charge schedule lookup must be extended before Step 12. Currently out of scope — see Open Questions.

---

### Option B — Introduce TradingAccount before Step 10 *(Not Recommended)*

Add `trading_accounts` in a new migration (0005) before Step 10 starts. Add `NOT NULL account_id` FK to `trades` and `execution_fills` immediately. Include `account_id` in `trade_pnl` from the start.

**Why rejected:**
- Creates a `NOT NULL` FK on `trades` with no import mechanism to populate it. Every existing test trade needs a seeded default account — coupling test infrastructure to a production entity before it is designed.
- Step 10's P&L engine does not use account context. The schema change adds implementation cost with zero functional benefit to Step 10.
- Forces the reconstruction engine (completed in Step 8) to be modified to accept and propagate `account_id` before any import path exists to provide it.
- The account model, once created with seed data, will accumulate assumptions that the real Step 11 import design may contradict.

---

### Option C — Defer TradingAccount to Phase 2 *(Not Recommended)*

Ship Phase 1 (Steps 10–12 plus deployment) without any account model. Retrofit after launch.

**Why rejected:**
- Step 12 (Karna) will define aggregation queries, indexes, and API response shapes without an account dimension. Retrofitting account-level filtering into a live analytics layer is a major refactor, not an additive migration.
- §38 Phase 1 MVP explicitly includes "User/account management." Deferring to Phase 2 contradicts the baseline requirements.

---

## Decision

**Adopt Option A. Introduce `TradingAccount` at Step 11, not before Step 10.**

**Step 10 is not blocked.** The decision to defer was already partially made and documented in the trade domain data model (`broker` as VARCHAR, `broker_accounts` deferred to Phase 2 per ADR-002). This ADR formalises the boundary: `TradingAccount` arrives with the import pipeline, not before it.

---

## Step 11 Migration Responsibilities

When Step 11 begins, the following schema changes must be applied before any import logic is written:

**New table:**

```sql
CREATE TABLE trading_accounts (
    id           UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id      UUID        NOT NULL REFERENCES users(id),
    broker       VARCHAR(20) NOT NULL,  -- ZERODHA | UPSTOX | ANGEL_ONE | MANUAL
    display_name VARCHAR(100) NOT NULL,
    account_type VARCHAR(20) NOT NULL,  -- e.g. INDIVIDUAL, HUF
    base_currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    status       VARCHAR(10) NOT NULL DEFAULT 'ACTIVE',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_trading_accounts_user_id ON trading_accounts (user_id);
```

**Additive FK columns (nullable initially):**

```sql
ALTER TABLE trades           ADD COLUMN account_id UUID NULL REFERENCES trading_accounts(id);
ALTER TABLE execution_fills  ADD COLUMN account_id UUID NULL REFERENCES trading_accounts(id);
ALTER TABLE trade_pnl        ADD COLUMN account_id UUID NULL REFERENCES trading_accounts(id);

CREATE INDEX idx_trades_account_id          ON trades          (account_id);
CREATE INDEX idx_execution_fills_account_id ON execution_fills (account_id);
CREATE INDEX idx_trade_pnl_account_id       ON trade_pnl       (account_id);
```

**Promote to NOT NULL** after all existing rows are backfilled to a default / dev account. This is a follow-on migration applied only once backfill is verified.

---

## Consequences

### Easier

- Step 10 proceeds without schema dependency on `TradingAccount`.
- Karna (Step 12) designs aggregations account-aware from day one.
- `account_id` is always populated in production (import path enforces it at ingestion).

### Harder

- Step 11 migration carries a larger surface area: account model + import pipeline + `account_id` FK additions on three tables.
- `trade_pnl` rows from Step 10 test runs will have `account_id = NULL`. Step 11 migration must handle this: seed a dev account and backfill local test rows, or accept NULL in local dev only and enforce NOT NULL in production only.

### What Must Be Monitored

- Step 11 migration must not apply `NOT NULL` on `account_id` until all existing rows are backfilled. A failed backfill on a live system is a blocking incident.
- Karna must not begin writing aggregation queries until Step 11's `account_id` FK is confirmed in the schema — not before.
- The `trades` indexes (`idx_trades_user_status`, `idx_trades_user_date`, `idx_trades_user_instrument_status`) are currently keyed on `user_id`. Once `account_id` is present, Step 12 will likely need composite indexes on `(account_id, status)` and `(account_id, trade_date)`. Karna must identify these before Step 12 begins.

---

## Resolved Questions

### Q1 — Account-Specific Brokerage Rates *(Resolved 2026-08-24)*

**Decision:** Broker-level charge schedules are accepted for Phase 1.

The `charge_schedules` table (Step 10) stores rates keyed by `(broker, trade_type, exchange, effective_from)`. All users on the same broker share one rate schedule. Account-specific negotiated rates are out of scope for Phase 1.

**Consequence:** The charge schedule design in `JOURNAL-PNL-INTEGRATION.md` stands as written. Kubera proceeds with the broker-string-keyed schema. No change to Step 10's migration or charge schedule lookup is required.

**Phase 2 extension point:** If account-specific brokerage rates are required in Phase 2, the `charge_schedules` schema will need an optional `account_id` FK and the lookup will need to prefer account-level rows over broker-level rows (account-specific rate takes precedence, falls back to broker default). This extension is noted here so Kubera's Step 10 schema does not inadvertently close this path.

---

*Mayasura — Senior Software Architect*
*Inputs: `docs/design/TRADE-DOMAIN-DATA-MODEL.md`, `docs/standards/JOURNAL-PNL-INTEGRATION.md`, `docs/project-status/REQUIREMENTS-TRACEABILITY.md`, `docs/adr/ADR-002-authentication-authorization-architecture.md`*
*Implementation owners upon acceptance: Bhima (Step 11 migration), Nakula (backfill operations)*
