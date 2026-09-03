# ADR-006: Trading Accounts — Schema Decisions

**Status:** Accepted  
**Author:** Mayasura  
**Date:** 2026-08-24  
**Implements:** ADR-005 (TradingAccount introduction, deferred to Step 11)  
**Migration:** `0008_trading_accounts.py`

---

## Context

ADR-005 decided *when* to introduce `TradingAccount` (Step 11). This ADR records the specific schema decisions for the `trading_accounts` table, the `account_id` FK wiring, and the idempotent fill deduplication index.

---

## Decisions

### 1. `trading_accounts` Table Schema

| Column | Type | Constraints | Rationale |
|---|---|---|---|
| `id` | UUID | PK | Standard surrogate key |
| `user_id` | UUID | FK → users.id, NOT NULL | Multi-tenant ownership boundary |
| `broker` | VARCHAR(20) | NOT NULL, CHECK | Validated broker identity |
| `display_name` | VARCHAR(100) | NOT NULL | User-facing label for the account |
| `account_type` | VARCHAR(20) | NOT NULL, CHECK | Phase 1: INDIVIDUAL or HUF |
| `base_currency` | VARCHAR(3) | NOT NULL, default INR | All Phase 1 accounts are INR |
| `status` | VARCHAR(10) | NOT NULL, default ACTIVE | Soft disable without deletion |

**CHECK constraints:**
- `broker IN ('ZERODHA', 'UPSTOX', 'ANGEL_ONE', 'MANUAL')` — matches the existing `execution_fills.broker` constraint. New brokers require a migration.
- `account_type IN ('INDIVIDUAL', 'HUF')` — Phase 1 only. Phase 2 adds PROP and CORPORATE when the import pipeline supports them.
- `status IN ('ACTIVE', 'INACTIVE')` — no DELETE path for accounts; deactivation via status update preserves referential integrity.

### 2. `account_id` FK on Core Trade Tables

`account_id UUID NULLABLE` is added to `trades`, `execution_fills`, and `trade_pnl` in migration 0008. It is promoted to NOT NULL in migrations 0009 (backfill) → 0011 (constraint). This is the expand-contract pattern — additive column first, constraint after all rows are populated.

**Why nullable initially:** The import pipeline (Step 11) is the only production path that sets `account_id`. Adding a NOT NULL constraint before the pipeline exists would make the column un-populatable.

### 3. Partial Unique Index for Idempotent Fill Re-import

```sql
CREATE UNIQUE INDEX uq_fills_broker_trade_account
  ON execution_fills (fill_id, account_id)
  WHERE fill_id IS NOT NULL;
```

Re-importing the same broker CSV must not create duplicate fills. The `(fill_id, account_id)` pair is the natural idempotency key: the same broker-assigned fill ID for the same account is always the same fill. `WHERE fill_id IS NOT NULL` excludes manual fills (which have no broker-assigned ID).

### 4. Analytics Dimension (Step 12 interaction)

`account_id` on `trades` becomes a first-class filter dimension in the Step 12 analytics layer (ADR-007). All analytics queries accept `account_id[]` as an optional filter. This is the reason ADR-005 required `account_id` to be present before Step 12 — adding it post-analytics would require refactoring every aggregation query and index.

---

## Consequences

**What becomes easier:**
- Multi-account P&L isolation: filter `trades.account_id = X` for single-account analytics.
- Idempotent CSV re-import: the partial unique index prevents duplicate fills without application-level deduplication logic.

**What becomes harder:**
- New brokers require a migration to extend the CHECK constraint.
- `account_type` additions (PROP, CORPORATE) require a migration.

**Technical debt:**
- `base_currency` is always INR in Phase 1. The column is present for future multi-currency support but is not used in any calculation today.

---

*Mayasura · 2026-08-24*
