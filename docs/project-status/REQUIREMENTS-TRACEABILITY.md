# Requirements Traceability Matrix — TradeForge

**Author:** Krishna (Project Manager)
**Date:** 2026-08-24
**Source document:** `docs/requirements/REQUIREMENTS.md` v1.1
**Compared against:** `docs/project-status/TRADEFORGE-CURRENT-STATE.md` (as of 2026-08-24)

---

## Classification Key

| Status | Meaning |
|---|---|
| **COMPLETE** | Requirement is fully implemented, tested, and on record |
| **PARTIAL** | Requirement is begun but coverage is incomplete |
| **NOT STARTED** | No implementation exists yet |
| **DEFERRED** | Explicitly deferred to Phase 2 or 3 in architecture decisions |
| **UNCLEAR** | Requirement is ambiguous or conflicts with an implemented decision |

---

## §6 — Authentication & User Management

| Requirement | Status | Notes |
|---|---|---|
| User registration | COMPLETE | `/auth/register`, Argon2id, Steps 2–5 |
| Login / logout | COMPLETE | `/auth/login`, `/auth/logout`, opaque sessions |
| Password reset | COMPLETE | `/auth/password-reset/*` flow, HIBP k-anonymity check |
| Email verification | COMPLETE | `/auth/verify-email`, pending_email_verifications table |
| Session management (expiration/revocation) | COMPLETE | Redis-backed sessions, security_audit_log |
| Secure authentication | COMPLETE | ADR-002 — 21 security requirements, CSRF, Origin validation |
| User profile | NOT STARTED | No `/users` or profile endpoints. `users` table exists but no profile fields (time zone, currency, preferences) |
| Time zone | NOT STARTED | Not in schema or API |
| Base currency | NOT STARTED | Not in schema or API |
| Trading preferences | NOT STARTED | Not in schema or API |
| Google OAuth / OAuth providers | DEFERRED | Phase 3 — architecture position reserved in ADR-002 |
| MFA / 2FA | DEFERRED | Phase 3 — architecture position reserved in ADR-002 |
| Passkeys | DEFERRED | Phase 3 — architecture position reserved in ADR-002 |
| Authorization enforced server-side | COMPLETE | `user_id` from session only, enforced at every repository query |
| Sensitive credentials encrypted | PARTIAL | Envelope KMS architecture decided (ADR-002); KMS not provisioned — broker credentials encrypted at rest only when cloud KMS is live |

**Gap:** User profile fields (time zone, base currency, trading preferences) required by §6 are not in the `users` schema and have no implementation path planned in any current step.

---

## §7 — Trading Account Management

| Requirement | Status | Notes |
|---|---|---|
| Multiple trading accounts per user | NOT STARTED | No `trading_accounts` table. All trades carry `user_id` only — no `account_id`. |
| Account name, broker, type, currency, capital | NOT STARTED | No entity exists |
| Deposits / withdrawals tracking | NOT STARTED | No entity exists |
| Account isolation for analytics | NOT STARTED | No account concept in analytics layer |
| Consolidated performance across accounts | NOT STARTED | — |

**Gap (High Severity):** The entire Trading Account Management module is absent from the schema. The current data model attributes trades directly to `user_id`. Introducing `account_id` later will require migrating the `trades`, `execution_fills`, `tax_lots`, `trade_pnl`, and `journal_entries` tables. This is a significant deferred cost that grows with every step implemented without the account entity.

**Recommended decision:** Mayasura must decide whether to introduce `trading_accounts` and `account_id` before Steps 11–13, or explicitly defer to a post-MVP migration. This is a cross-cutting schema decision that should be recorded in an ADR.

---

## §8 — Broker & Data Import

| Requirement | Status | Notes |
|---|---|---|
| Manual trade entry | NOT STARTED | No `/trades` write endpoint. Reconstruction engine exists but has no API for manual fills. |
| CSV/Excel import | NOT STARTED | Step 11 (Sanjaya) — not yet designed |
| File format detection / column mapping | NOT STARTED | Step 11 |
| Duplicate detection | NOT STARTED | Step 11 |
| Import error reporting / preview | NOT STARTED | Step 11 |
| Preserve original import file reference | NOT STARTED | Step 11 |
| Broker API integrations | DEFERRED | Phase 2 — per §38 MVP scope |
| Broker adapter isolation interface | NOT STARTED | Interface not yet defined — Sanjaya must design before Step 11 |

---

## §9 — Order & Execution Management

| Requirement | Status | Notes |
|---|---|---|
| Distinguish orders / executions / positions / trades | PARTIAL | `execution_fills` and `trades` exist. No `orders` table. No `positions` view. |
| Retain underlying executions (not flattened) | COMPLETE | `execution_fills` table stores all fills; trades aggregate them |
| Multiple entry executions per trade | COMPLETE | Reconstruction engine handles scale-in |
| Multiple exit executions per trade | COMPLETE | Reconstruction engine handles scale-out |
| Partial fills | COMPLETE | Supported in reconstruction |
| Partial exits | COMPLETE | Supported via `tax_lots` |

**Gap:** No `orders` entity. Requirements §9 explicitly requires distinguishing orders from executions/fills. An order can generate multiple fills. Currently the system only models fills, not the orders that generated them. This gap may matter when broker CSV imports include order-level data (Step 11).

---

## §10 — Trade Reconstruction Engine

| Requirement | Status | Notes |
|---|---|---|
| Reconstruct logical trades from execution data | COMPLETE | `reconstruction.py` — Steps 6–8 |
| Weighted average entry | COMPLETE | Computed on every fill addition |
| Weighted average exit | COMPLETE | Computed on close |
| Gross P&L | NOT STARTED | Step 10 — `trade_pnl` stub only |
| Charges / Net P&L | NOT STARTED | Step 10 |
| Holding duration | PARTIAL | `first_fill_at` / `last_fill_at` recorded — holding duration derivable but not stored as a field |
| Remaining position | COMPLETE | `trades.status = PARTIAL`, `total_entry_quantity` vs closed quantity |
| FIFO (CNC delivery lots) | PARTIAL | `tax_lots` table and index exist; Phase 1 trivially satisfied (single open lot); multi-lot FIFO deferred (Unresolved 4) |
| Average-cost method (intraday/F&O) | COMPLETE | MIS, NRML_FUT, NRML_OPT all use average cost |
| Scale-in / scale-out | COMPLETE | — |
| Multi-leg strategies | NOT STARTED | No multi-leg trade grouping entity; deferred |
| Re-entry detection | NOT STARTED | Same-day re-entry handling unspecified |

---

## §11 — Journal

| Requirement | Status | Notes |
|---|---|---|
| Journal entry per trade | COMPLETE | `GET/PUT /v1/journal/trades/{trade_id}` |
| Trade ID, instrument, symbol, direction | COMPLETE | Read from `trades` via `TradeContextPanel` |
| Account (in journal context) | NOT STARTED | No `account_id` on trades — journal cannot display account |
| Asset class | COMPLETE | `trade_type` enum covers EQ/FO segments |
| Entry/exit date/time | COMPLETE | `first_fill_at` / `last_fill_at` on trades |
| Quantity, entry/exit price | COMPLETE | `total_entry_quantity`, `average_entry`, `average_exit` |
| Stop loss / target | COMPLETE | `planned_stop`, `planned_target` in journal entry |
| Gross P&L, fees, net P&L | PARTIAL | Fields exist in `trade_pnl` schema; not yet populated (Step 10) |
| Risk amount (planned) | COMPLETE | `planned_risk_amount` computed and stored |
| R-multiple | PARTIAL | Computed by Step 10 from `planned_risk_amount`; not yet populated |
| Holding time | PARTIAL | Derivable from fill timestamps; not a stored field |
| Strategy / setup type | COMPLETE | `setup_type` enum, `strategy_notes` |
| Market condition | NOT STARTED | No `market_condition` field in current schema |
| Entry reason / exit reason | NOT STARTED | Not in current journal schema |
| Trade thesis | COMPLETE | `trade_thesis` field |
| Planned entry | NOT STARTED | No `planned_entry` field — only `planned_stop` and `planned_target` captured |
| Mistakes | COMPLETE | `MistakeTag` enum, multi-select |
| Emotions | COMPLETE | `EmotionTag` enum, chip group |
| Confidence | NOT STARTED | No confidence field in schema |
| Discipline score | COMPLETE | `discipline_score` (1–10 integer) |
| Notes | COMPLETE | `notes` text field |
| Tags | NOT STARTED | No `tags` table or `trade_tags` join table |
| Screenshots | COMPLETE | `AttachmentUploader` — 3-step S3 flow |
| Attachments | COMPLETE | `journal_attachments` table, presign/confirm/delete |
| Audit history for journal edits | COMPLETE | `journal_audit_log`, `AuditHistoryDrawer` |

**Gaps in journal schema:**
- `market_condition` — not captured
- `entry_reason` / `exit_reason` — not captured
- `planned_entry` — only stop and target are captured, not the planned entry price
- `confidence` — not captured (separate from discipline score)
- `tags` — no tagging infrastructure

---

## §12 — Strategy & Setup Management

| Requirement | Status | Notes |
|---|---|---|
| Reusable strategies with name/description/rules | NOT STARTED | `SetupType` is an enum in journal domain; no standalone `Strategy` entity |
| Reusable setups per strategy | NOT STARTED | — |
| Entry/exit conditions, stop/target rules | NOT STARTED | — |
| Tags on strategies/setups | NOT STARTED | — |
| Analytics per strategy / setup | NOT STARTED | Depends on analytics engine (Step 12 / Karna) |

**Gap:** The requirements call for a full Strategy & Setup Management module with persistent entities. Currently, setup type is an inline enum on the journal entry. Users cannot define their own strategies or setups — they select from a hardcoded list.

---

## §13 — Performance Analytics

| Requirement | Status | Notes |
|---|---|---|
| All basic metrics (win rate, expectancy, profit factor, etc.) | NOT STARTED | Step 12 (Karna) — depends on Step 10 P&L data |
| All advanced metrics (Sharpe, MAE/MFE, equity curve, etc.) | NOT STARTED | Step 12 (Karna) |

---

## §14 — Performance Breakdown

| Requirement | Status | Notes |
|---|---|---|
| Breakdown by strategy, setup, instrument, direction, time, etc. | NOT STARTED | Step 12 (Karna) |

---

## §15 — P&L, Charges & Financial Calculation Engine

| Requirement | Status | Notes |
|---|---|---|
| Realized gross P&L (by instrument type) | NOT STARTED | Step 10 — formulas defined in Kubera SKILL.md |
| Unrealized P&L | DEFERRED | Mark-to-market data source not defined; Phase 2+ |
| Average entry / exit price | COMPLETE | Computed by reconstruction engine |
| Partial fills / partial exits / scale-in/out | COMPLETE | Reconstruction engine covers these inputs |
| Brokerage | NOT STARTED | Step 10 |
| STT | NOT STARTED | Step 10 |
| Exchange transaction charges | NOT STARTED | Step 10 |
| GST | NOT STARTED | Step 10 |
| SEBI charges | NOT STARTED | Step 10 |
| Stamp duty | NOT STARTED | Step 10 |
| Slippage recording | NOT STARTED | No `intended_price` or `slippage` field in schema |
| Contract/lot-based P&L (Futures) | NOT STARTED | Step 10 — `lot_size_history` table exists |
| Futures MTM per day | DEFERRED | Phase 2 per `JOURNAL-PNL-INTEGRATION.md` §14 |
| Options premium P&L | NOT STARTED | Step 10 — formula defined in Kubera SKILL.md |
| Multi-leg strategy P&L | NOT STARTED | Deferred — no multi-leg grouping entity |
| Corporate-action adjustments | DEFERRED | Unresolved 3, TRADE-DOMAIN-DATA-MODEL |
| Reconciliation against broker statements | NOT STARTED | Step 11+ |
| Calculation versioning | PARTIAL | `engine_version` column in `trade_pnl` schema; not yet implemented |
| Decimal precision rules | COMPLETE | DECIMAL-USAGE-STANDARD.md — enforced |
| AI excluded from financial calculations | COMPLETE | Architecture enforced — AI layer is Phase 3 and downstream only |

---

## §15 (duplicate section) — Risk Management

| Requirement | Status | Notes |
|---|---|---|
| Risk per trade | PARTIAL | `planned_risk_amount` stored in journal; Step 13 (Dhanvantari) for full engine |
| Risk/reward | NOT STARTED | Step 13 |
| Position sizing calculator | NOT STARTED | Step 13 |
| Account exposure / portfolio risk | NOT STARTED | Step 13 |
| Open risk / daily / weekly risk | NOT STARTED | Step 13 |
| Drawdown | NOT STARTED | Step 13 |
| Consecutive losses | NOT STARTED | Step 13 |
| Strategy/instrument concentration | NOT STARTED | Step 13 |

---

## §16 — Trading Psychology

| Requirement | Status | Notes |
|---|---|---|
| Emotional state capture | COMPLETE | `EmotionTag` enum (CALM, ANXIOUS, CONFIDENT, FOMO, GREEDY, FEARFUL, REVENGE, IMPULSIVE) |
| Discipline score | COMPLETE | 1–10 integer field |
| Mistakes capture | COMPLETE | `MistakeTag` enum (FOMO, OVERSIZED, etc.) |
| FOMO / revenge trading flags | COMPLETE | Covered by `EmotionTag` and `MistakeTag` |
| Confidence field | NOT STARTED | No separate confidence field; discipline score is a proxy |
| Fear / greed / fatigue / stress / sleep quality / rule adherence / trading impulse | NOT STARTED | These granular sub-fields not in schema |
| Behavioral-performance correlation analysis | NOT STARTED | Step 12 / Vidura — depends on analytics engine |

---

## §17 — Market Context

| Requirement | Status | Notes |
|---|---|---|
| Market trend / volatility regime / session | NOT STARTED | No `market_context` table or entity |
| VIX / market breadth import | NOT STARTED | — |

---

## §18 — Dashboard | §19 — Advanced Charts | §22 — Reports | §23 — Notifications | §24 — Search & Filtering

| Module | Status | Notes |
|---|---|---|
| Dashboard | NOT STARTED | Depends on analytics and P&L engine |
| Advanced charts | NOT STARTED | Phase 2 |
| Reports (CSV/Excel/PDF export) | NOT STARTED | Phase 2 |
| Notifications & Alerts | NOT STARTED | Phase 2 |
| Search & Filtering | NOT STARTED | Depends on analytics, strategy, tag entities |

---

## §20 — Trade Detail Page

| Requirement | Status | Notes |
|---|---|---|
| Trade summary (instrument, direction, entry/exit, P&L, R-multiple, risk) | PARTIAL | `JournalPanel` + `TradeContextPanel` + `PnlStatusBlock` cover this; P&L not yet populated |
| Trade plan section | PARTIAL | `planned_stop`, `planned_target`, `trade_thesis` captured; `planned_entry` missing |
| Execution timeline | NOT STARTED | No component for fill-level timeline |
| Market context | NOT STARTED | No market context entity |
| Screenshots / attachments | COMPLETE | `AttachmentUploader`, `AttachmentGrid` |
| Psychology section | COMPLETE | Emotions, mistakes, discipline score |
| Strategy / setup | PARTIAL | `setup_type` captured; no full strategy entity |
| AI analysis panel | DEFERRED | Phase 3 |

---

## §21 — AI Trading Assistant

| Requirement | Status | Notes |
|---|---|---|
| All AI capabilities and restrictions | DEFERRED | Phase 3 — Vishwakarma; architecture position confirmed (downstream of P&L) |

---

## §25 — Data Model (Entity Coverage)

| Entity | Status | Notes |
|---|---|---|
| User | COMPLETE | `users` table |
| TradingAccount | NOT STARTED | **Missing** — highest severity gap |
| Broker | NOT STARTED | Broker identity is a string field on fills; no `brokers` entity |
| Instrument | COMPLETE | `instruments` table |
| Order | NOT STARTED | No orders entity — fills only |
| Execution | COMPLETE | `execution_fills` table |
| Position | PARTIAL | Implied by `trades.status = PARTIAL`; no materialized position view |
| Trade | COMPLETE | `trades` table |
| JournalEntry | COMPLETE | `journal_entries` table |
| Strategy | NOT STARTED | Enum only — no standalone entity |
| Setup | NOT STARTED | Enum only — no standalone entity |
| Tag / TradeTag | NOT STARTED | No tagging system |
| MarketContext | NOT STARTED | — |
| PsychologyEntry | PARTIAL | Captured inline in journal entry, not as a standalone entity |
| RiskEvent | NOT STARTED | — |
| PortfolioSnapshot | NOT STARTED | — |
| PerformanceSnapshot | NOT STARTED | — |
| ImportJob | NOT STARTED | — |
| ImportRecord | NOT STARTED | — |
| Attachment | COMPLETE | `journal_attachments` table |
| Notification | NOT STARTED | — |
| AuditLog | COMPLETE | `journal_audit_log`, `security_audit_log` |
| AIInsight | DEFERRED | Phase 3 |

---

## §26–§31 — Cross-Cutting Requirements

| Area | Status | Notes |
|---|---|---|
| Immutable raw execution records | COMPLETE | `execution_fills` — no UPDATE path for fills |
| Idempotent imports | NOT STARTED | Step 11 |
| Duplicate detection | NOT STARTED | Step 11 |
| Referential integrity | COMPLETE | FK constraints on all join columns |
| Audit history | PARTIAL | Journal and auth audit logs exist; trade domain has no audit log |
| Calculation reproducibility | PARTIAL | `engine_version` in trade_pnl schema; not yet implemented |
| Multi-user, multi-account database | PARTIAL | Multi-user: YES. Multi-account: NOT STARTED |
| Indexing for common filters | PARTIAL | Indexes exist for current access patterns; analytics indexes not yet planned |
| Backend: versioned API | PARTIAL | `/v1/journal/...` versioned; other API domains not yet implemented |
| Backend: logging / auditing | PARTIAL | Auth audit log complete; application-level structured logging not fully implemented |
| Frontend: responsive, accessible | PARTIAL | Tailwind responsive; accessibility not formally audited |
| Frontend: primary screens | PARTIAL | Journal UI only; 13 of 14 required screens not built |
| Security: CSRF, XSS, SQL injection | PARTIAL | CSRF middleware and Origin validation complete; file upload malware scanning not implemented |
| Security: rate limiting | NOT STARTED | No rate limiting middleware |
| Security: secure file uploads | PARTIAL | S3 presign flow designed; StubStorage in use — not production-ready |
| Security: dependency scanning | NOT STARTED | No CI/CD pipeline yet |
| DevOps: CI/CD pipeline | NOT STARTED | No pipeline configured |
| DevOps: separate environments | NOT STARTED | Local Docker Compose only |
| Testing: unit tests | PARTIAL | Domain + API unit tests for auth, trade, journal |
| Testing: integration tests | PARTIAL | API integration tests for all implemented endpoints |
| Testing: E2E tests | NOT STARTED | — |
| Testing: data tests (malformed imports) | NOT STARTED | Step 11 |
| Observability: structured logs, metrics | NOT STARTED | Basic FastAPI logs only |
| Observability: health check | COMPLETE | Health check endpoint in Step 1 |
| Admin panel | NOT STARTED | — |

---

## What Step 10 Covers Against Requirements

Step 10 (P&L Engine) directly addresses **§15 — P&L, Charges & Financial Calculation Engine**:

| §15 Item | Covered by Step 10 | Notes |
|---|---|---|
| Realized gross P&L (equity long/short, futures, options) | YES | Kubera formulas → `PnlCalculator.compute_gross_pnl` |
| Net P&L | YES | `gross_pnl − total_charges` |
| Brokerage (per-order flat/capped) | YES | `charge_schedules` + `compute_charges` |
| STT (by segment and side) | YES | 7-component breakdown |
| Exchange charges (NSE/BSE) | YES | — |
| GST (on brokerage + exchange + SEBI only) | YES | STT and stamp duty correctly excluded from GST base |
| SEBI charges | YES | — |
| Stamp duty (buy side only) | YES | — |
| IPFT | YES | — |
| R-multiple | YES | `net_pnl / planned_risk_amount` |
| Calculation versioning | YES | `engine_version` field |
| Decimal precision rules | YES | DECIMAL-USAGE-STANDARD.md enforced by domain layer |
| Financial unit tests | YES | TC-G3-001 through TC-G3-009, Kubera Section 13 test groups |
| Unrealized P&L | NO | Deferred — no mark price data source |
| Slippage recording | NO | Not in Step 10 scope — `intended_price` field not in schema |
| Futures MTM per day | NO | Deferred to Phase 2 |
| Options exercise P&L | NO | Deferred — Ganesha/Kubera unresolved |
| Multi-leg strategy P&L | NO | No multi-leg grouping entity |
| Corporate-action adjustments | NO | Deferred |
| Reconciliation vs broker statements | NO | Step 11+ |

Step 10 also partially enables **§11 — Journal** (gross/net P&L and R-multiple fields will be populated for closed trades) and **§13 — Performance Analytics** (Step 10 produces the source data Karna needs in Step 12).

---

## Gaps and Recommended Next Steps

### Gap 1 — TradingAccount entity (CRITICAL — grows worse each step)

**Problem:** §7 requires multi-account support. All trades are currently attributed to `user_id` only. Adding `account_id` later requires migrating `trades`, `execution_fills`, `tax_lots`, `trade_pnl`, `journal_entries` — the cost compounds with every step.

**Recommendation:** Mayasura must make an explicit architectural decision before Step 11 (broker import). Options:
1. Introduce `trading_accounts` + `account_id` FK on all trade tables before Step 11.
2. Formally defer to Phase 2 with an ADR documenting the migration risk.

This is the highest-priority open architectural decision not yet recorded.

---

### Gap 2 — Orders entity (MEDIUM)

**Problem:** §9 requires distinguishing orders from executions. No `orders` table exists. The current model maps fills directly to trades.

**Recommendation:** Sanjaya should evaluate whether broker CSV files include order-level data. If they do, an `orders` entity is needed before Step 11. If not, this can be deferred with an explicit ADR note.

---

### Gap 3 — Journal schema completeness (LOW–MEDIUM)

**Problem:** §11 lists fields not currently captured: `market_condition`, `entry_reason`, `exit_reason`, `planned_entry`, `confidence`, `tags`.

**Recommendation:** Yudhishthira should confirm which of these are Phase 1 vs Phase 2. Tags in particular affect search and filtering (§24) and strategy breakdown (§14). Adding them to the journal schema before Step 11 is lower cost than a later migration.

---

### Gap 4 — Strategy & Setup as standalone entities (MEDIUM)

**Problem:** §12 requires persistent Strategy and Setup entities with full metadata. Currently, `setup_type` is a hardcoded enum.

**Recommendation:** Defer is acceptable for Phase 1, but must be an explicit decision. Yudhishthira should confirm whether Phase 1 ships with free-text strategy/setup or structured entities. This affects the analytics breakdown capability (§14) and the Step 12 Karna spec.

---

### Gap 5 — User profile fields (LOW for Phase 1)

**Problem:** §6 requires time zone, base currency, and trading preferences on the user profile. Not in schema.

**Recommendation:** Add to the `users` table before the first production deployment. These fields are low-risk additions but are needed for multi-timezone support and the account overview dashboard.

---

### Gap 6 — Rate limiting (MEDIUM — security)

**Problem:** §31 requires rate limiting. No middleware implemented. Authentication endpoints are currently unprotected against brute-force.

**Recommendation:** Hanuman should review and Bhima should implement rate limiting (e.g., `slowapi`) on auth endpoints before any production deployment. This is not a Step 10 blocker but should not slip past Step 11.

---

### Gap 7 — Slippage (LOW — data model)

**Problem:** §15 includes slippage recording. Kubera SKILL.md defines the slippage formula. No `intended_price` field exists in `execution_fills`.

**Recommendation:** Ganesha should confirm whether `intended_price` (the trigger/signal price) is required in Phase 1 fills. If yes, add to `execution_fills` before Step 11. If deferred, record explicitly.

---

## Implementation Sequence vs Requirements Alignment

The current build sequence (§45 engineering order) is well-aligned to the requirements. Steps 1–9 map to requirements items 1–9. Step 10 maps exactly to item 10 (Deterministic P&L engine).

The engineering order deviates from the requirements in one notable area: **§38 Phase 1 MVP** includes "User/account management" and "CI/CD" in Phase 1 scope. Both are not yet started. This should be acknowledged as an accepted divergence or scheduled before Phase 1 is declared complete.

---

*Krishna — Senior Project Manager*
*Source: `docs/requirements/REQUIREMENTS.md` v1.1, `docs/project-status/TRADEFORGE-CURRENT-STATE.md`*
*Implementation owners as assigned per §40 agent responsibilities*
