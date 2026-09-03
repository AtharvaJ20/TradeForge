# TradeForge — Current Project State

**Last updated:** 2026-09-03  
**Author:** Nakula (DevOps) — CI gate Step 12.3  
**Purpose:** Handoff document for future Claude sessions. Milestone-level only — not an implementation log.

---

## What TradeForge Is

A trading journal and analytics platform for Indian retail traders (NSE EQ, NSE FO, BSE EQ). Core value: authoritative P&L reconstruction from broker fill data, layered with behavioral journal annotations and Karna's quant analytics. Target user: independent retail day/swing trader, 1–3 years of experience, actively trying to improve their edge.

**Build is sequential (Steps 1 → N).** Earlier steps are not revisited unless defects are found.

---

## Architecture Decisions (All Accepted)

| ADR | Decision | Date |
|-----|----------|------|
| ADR-001 | Python 3.12+ / FastAPI / SQLAlchemy 2.x / Alembic / Pydantic v2 / Decimal | 2026-08-22 |
| ADR-002 | Self-managed auth: Argon2id, opaque sessions in Redis, envelope KMS for broker creds | 2026-08-22 |
| ADR-003 | Journal annotation layer: read-subscriber of trade domain, StoragePort abstraction, two-step S3 upload | 2026-08-23 |
| ADR-004 | Frontend: Vite 5 + React 18 + TypeScript strict, feature-first dirs, TanStack Query, MSW tests | 2026-08-23 |
| ADR-006 | Trading accounts: account_id FK on trades/trade_pnl/charge_schedules; multi-broker support | 2026-09-02 |
| ADR-007 | Step 12 analytics layer: Bhima computes, Karna specifies, Ganesha validates domain rules | 2026-09-02 |
| ADR-007A | Sharpe/Sortino: n_per_year=252 fixed; Decimal boundary; insufficient_sample sentinel | 2026-09-02 |

**Domain boundary rule (non-negotiable, ADR-001):** Domain layer imports zero framework or infrastructure code. Enforced by code review on every PR.

---

## Completed Milestones

### Foundation (Step 1)
- Project scaffold: `backend/src/tradeforge/` with domain / application / infrastructure / api layer structure
- `DecimalConfig` domain module; Decimal Usage Standard (`docs/standards/DECIMAL-USAGE-STANDARD.md`) — accepted, blocks all financial calculation code
- Health check endpoint, test scaffolding (pytest), `pyproject.toml`

### Authentication (Steps 2–5)
**Backend — fully implemented and CI-gated:**
- Domain: `password.py` (Argon2id), `tokens.py` (256-bit opaque), `events.py`, `errors.py`
- Application: `AuthService`, HIBP k-anonymity check, email notifications, forced-reauth control
- Infrastructure: `UserModel`, `AuthModel`, `UserRepo`, `AuthRepo`, `SessionRepo`, `RedisClient`, `DBSession`
- API: `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/verify-email`, `/auth/password-reset/*`; CSRF middleware; Origin validation
- Migration: `0001_auth_tables.py`

### Trade Domain (Steps 6–8)
**Backend — fully implemented:**
- Domain: `trade/types.py` (enums, value objects), `trade/errors.py`
- Infrastructure ORM: `trade_domain.py` (instruments, lot_size_history, trades, execution_fills, management_events, tax_lots)
- Application: `reconstruction.py` — trade reconstruction engine (FIFO lot tracking, fill → trade aggregation)
- Migrations: `0002_trade_domain_tables.py`, `0003_fill_exclusions.py`

### Journal (Step 9)
**Backend — fully implemented:**
- Domain: `journal/types.py`, `journal/errors.py`
- Application: `JournalService` (upsert_entry, get_entry, get_audit_history, presign/confirm/delete attachment); `StoragePort` Protocol + `StubStorage`
- API: `GET/PUT /v1/journal/trades/{trade_id}`, audit history, 3-endpoint attachment flow
- Migration: `0004_journal_tables.py`

**Frontend — fully implemented:**
- 13 components: `JournalPanel`, `JournalQuickCapture`, `JournalFullForm`, `TradeContextPanel`, `PnlStatusBlock`, `DisciplineScoreInput`, `EmotionChipGroup`, `MistakesCheckboxGroup`, `AttachmentUploader`, `AttachmentGrid`, `AuditHistoryDrawer`, `AuditPromptInline`, `SkeletonPnlBlock`
- Hooks: `useJournalEntry`, `useUpsertJournalEntry`, `useAuditHistory`, `useAttachmentUpload`, `useDeleteAttachment`

### P&L Engine (Step 10 — CI gate GREEN 2026-09-01)
**Backend — fully implemented:**
- Domain: `domain/pnl/calculator.py`, `domain/pnl/types.py` (PNL_ENGINE_VERSION = "1.0.0"), `domain/pnl/errors.py`
- Infrastructure ORM: `trade_pnl.py` (21-column schema), `charge_schedule.py`
- Migrations: `0005_pnl_engine.py`, `0006_make_ip_address_nullable.py`, `0007_expand_trade_pnl_columns.py`
- 7 charge components: brokerage, stt, exchange_charges, sebi_charges, stamp_duty, gst, ipft
- 49 total tests (26 domain unit + 22 integration + 1 service unit)
- Yudhishthira ACCEPTED 2026-09-01

### Trading Accounts + Broker Import (Step 11 — Complete)
**Backend — fully implemented (commit: `feat(ws-4)`):**
- `TradingAccount` entity introduced; `account_id` FK wired into trades, trade_pnl, charge_schedules
- Broker CSV import adapters: Zerodha, Upstox, Angel One
- Fill reconciliation against reconstruction engine output
- `backfill_all_closed` wired into import pipeline
- Migrations: `0008` through `0011` (trading_accounts table, account_id columns, broker credential columns, analytics indexes)
- ADR-006 accepted
- CI gate: BUG-3, BUG-4, BUG-5 resolved; Redis[str] subscript fix applied to FastAPI runtime
- Design docs: `docs/adr/ADR-006-trading-accounts-schema-decisions.md`, `docs/design/NORMALIZED-FILL-CONTRACT.md`, `docs/project-status/STEP-11-EXECUTION-PLAN.md`

### Analytics Layer — Backend (Step 12 backend — Complete, NOT YET COMMITTED)
**Backend — implemented but untracked/uncommitted:**
- Domain: `domain/analytics/` — calculators for win_rate, expectancy, profit_factor, planned_rr, drawdown, direction breakdown, charges, Sharpe, Sortino
- Application: `analytics_service.py` — `AnalyticsService.compute_summary(account_id, params)`
- Infrastructure: `analytics_repo.py` — fills/trades/trade_pnl queries scoped by account + filter params
- API: `api/v1/analytics.py` — `GET /v1/analytics/summary` (9 dimensions in response)
- Migration: `0012_analytics_indexes.py`
- `main.py` updated to include analytics router (modified, not staged)
- Tests: `tests/integration/test_analytics_summary.py`, `tests/unit/domain/test_analytics_calculators.py`
- Design docs: `docs/adr/ADR-007-step12-analytics-layer.md`, `docs/adr/ADR-007A-step12.1-sharpe-sortino.md`, `docs/design/STEP-12-ANALYTICS-SPEC.md`, `docs/design/GANESHA-STEP12-DOMAIN-VALIDATION.md`, `docs/design/GANESHA-G1-G4-RULING.md`, `docs/design/GANESHA-G-CONF-12.1.md`
- **ACTION REQUIRED:** Bhima/Nakula must commit backend analytics files before next backend CI gate

### Analytics Dashboard + Filter UI — Frontend (Steps 12.1–12.3 — ACCEPTED 2026-09-03)
**Frontend — fully implemented, committed at `8c990af`:**

**Step 12.1 — Data layer:**
- `features/analytics/schemas.ts` — Zod schemas; Pydantic Decimal → JSON string → `z.string().nullable()`
- `features/analytics/types.ts` — `AnalyticsSummary`, `AnalyticsFilterParams` (9 dimensions), 8 sub-types
- `features/analytics/api.ts` — `fetchAnalyticsSummary`, `buildQueryString` (repeated keys for arrays)
- `features/analytics/hooks/useAnalyticsSummary.ts` — TanStack Query v5 hook, typed query-key factory

**Step 12.2 — 9 analytics card components:**
- `RiskAdjustedCard` — Sharpe + Sortino; `insufficient_sample` sentinel rendered as `role="note"`
- `PnlSummaryCard` — Net/Gross P&L + charges; net P&L signed colour
- `OutcomeCard` — Win/Loss/Breakeven rate (fraction format × 100)
- `ExpectancyCard` — Expectancy R, avg win/loss R; insufficient_sample guard
- `ProfitFactorCard` — PF value; null guard (no losing trades)
- `PlannedRRCard` — avg R:R; null guard (no stop+target set)
- `DrawdownCard` — all-null guard; 2×2 grid (max/avg/current drawdown)
- `DirectionBreakdownTable` — semantic `<table>`; empty-array guard
- `ChargesCard` — 7 line items + total; G-CORR-03: charge_drag_pct null → charges_added_to_loss
- `AnalyticsSummaryPanel` — assembles all 9 sections; skeleton + error + null states
- `features/analytics/formatters.ts` — `formatINR`, `formatPctFraction`, `formatPctDirect`, `formatSigned`, `formatDecimal`
- 26 component tests (3 per card/table, 5 for panel container)

**Step 12.3 — Filter UI:**
- `AnalyticsFilterBar` — controlled component; date range + 4 enum multi-select groups (Direction/TradeType/Instrument/Segment); Clear All; `<section aria-label="Analytics filters">`
- `AnalyticsSummaryPanel` updated: accepts `params?: AnalyticsFilterParams`; existing callers unaffected
- `App.tsx` updated: `useState<AnalyticsFilterParams>({})` lifted; filter bar + panel share state
- 6 `AnalyticsFilterBar` tests; OBS-12.2-01 closed (4 section landmark assertions in panel test)
- Sahadeva: GO · Nakula: GREEN · Yudhishthira: ACCEPTED (2026-09-03)

**Frontend test totals: 87 tests, 87 passing**  
**Coverage: stmts 77.75% / branches 83.82% / fns 57.03% / lines 77.75% — all configured thresholds met**

---

## Design & Spec Documents

| File | What it specifies |
|------|-------------------|
| `docs/adr/ADR-001-backend-framework.md` | Python/FastAPI stack, async model, layer boundary rules |
| `docs/adr/ADR-002-authentication-authorization-architecture.md` | Full auth architecture + 21 security requirements |
| `docs/decisions/ADR-003-journal-annotation-architecture.md` | 10 journal architecture decisions, attachment protocol |
| `docs/decisions/ADR-004-journal-frontend-architecture.md` | Frontend toolchain and structural decisions |
| `docs/adr/ADR-006-trading-accounts-schema-decisions.md` | account_id FK decisions; multi-broker schema |
| `docs/adr/ADR-007-step12-analytics-layer.md` | Analytics layer architecture: who computes what |
| `docs/adr/ADR-007A-step12.1-sharpe-sortino.md` | Sharpe/Sortino spec: n_per_year=252, insufficient_sample sentinel |
| `docs/design/TRADE-DOMAIN-DATA-MODEL.md` | 7-table trade domain schema + ER diagram |
| `docs/design/TRADE-RECONSTRUCTION-SPEC.md` | Fill → trade reconstruction algorithm |
| `docs/design/JOURNAL-UX-SPEC.md` | 10 component specs (C-01 through C-10) |
| `docs/design/JOURNAL-API-SPEC.md` | Full journal API contract |
| `docs/design/STEP-12-ANALYTICS-SPEC.md` | Analytics summary endpoint contract; all 9 response sections |
| `docs/design/GANESHA-STEP12-DOMAIN-VALIDATION.md` | Ganesha's domain validation of analytics calculators |
| `docs/design/GANESHA-G1-G4-RULING.md` | Ganesha G1–G4 ruling on trade domain classification |
| `docs/design/GANESHA-G-CONF-12.1.md` | Ganesha G-CONF-12.1: Sharpe/Sortino conventions |
| `docs/design/NORMALIZED-FILL-CONTRACT.md` | Normalized fill format for broker adapters |
| `docs/standards/DECIMAL-USAGE-STANDARD.md` | Rounding mode, precision per output type, init rules |
| `docs/standards/TRADE-DOMAIN-RULES.md` | Trade matching, classification, FIFO rules |
| `docs/standards/JOURNAL-DOMAIN-RULES.md` | Journal business rules (G1 — 9 rule groups) |
| `docs/standards/JOURNAL-SECURITY-REQUIREMENTS.md` | SR-JOUR-001–013, SR-ATT-001–010 |
| `docs/standards/JOURNAL-PNL-INTEGRATION.md` | How journal reads P&L for PnlStatus / R-multiple |

---

## Infrastructure Status

| Component | Status |
|-----------|--------|
| Docker Compose (local) | Configured — PostgreSQL + Redis locally |
| Cloud provider | **Not selected** — AWS / GCP / Azure (Nakula owns) |
| Managed PostgreSQL | **Not provisioned** |
| Managed Redis (HA) | **Not provisioned** |
| KMS (broker credential KEK) | **Not provisioned** — requires cloud provider decision |
| S3 bucket (attachment storage) | **Not provisioned** — `StubStorage` in use |
| Transactional email provider | **Not provisioned** |
| CI/CD pipeline | GitHub Actions defined in `.github/workflows/ci.yml` — not yet running on hosted runner |
| Production environment | **Not deployed** |

---

## QA Status

- **Step 12.3 (Analytics Filter UI):** Sahadeva GO · Nakula CI GREEN · Yudhishthira ACCEPTED (2026-09-03)
- **Step 12.2 (Analytics Dashboard):** Sahadeva GO · Nakula CI GREEN · Yudhishthira ACCEPTED (2026-09-03)
- **Step 12.1 (Analytics Data Layer):** Part of Step 12.2 acceptance
- **Step 11 (Broker Import):** CI gate GREEN (BUG-3/4/5 resolved)
- **Step 10 (P&L Engine):** Sahadeva GO · Nakula CI GREEN · Yudhishthira ACCEPTED (2026-09-01)
- Frontend: 87 tests, 87 passing; all coverage thresholds met
- Backend analytics tests: present but uncommitted — CI not yet run against analytics backend
- No E2E tests exist yet
- Pre-existing mypy issues (redis_client.py, session_repo.py, journal_repo.py, journal/service.py, settings.py, deps.py) — tracked for future code-health pass

---

## Outstanding Actions (Before Next Session Proceeds)

| Action | Owner | Priority |
|--------|-------|----------|
| **Commit backend analytics files** (`domain/analytics/`, `analytics_service.py`, `analytics_repo.py`, `api/v1/analytics.py`, `0012_analytics_indexes.py`, updated `main.py`, tests, docs) | Bhima / Nakula | **HIGH — blocks Step 12.4** |
| Run backend CI gate for analytics backend | Nakula | HIGH — after commit |

---

## Deferred Risks & Open Items

| Item | Risk / Consequence | Owner | Phase |
|------|--------------------|-------|-------|
| Production domain not decided | Blocks CORS, email domain, passkey rpId (irreversible if wrong) | Atharva | Pre-deployment |
| Cloud provider not selected | Blocks KMS, managed Redis, managed PG, email service | Nakula | Pre-deployment |
| S3Storage implementation | Attachment upload non-functional in production | Nakula | Phase 1 deployment |
| PostgreSQL RLS | No database-level authorization backstop until Phase 2 | Bhima + Nakula | Phase 2 |
| Celery + Redis workers | Async jobs use BackgroundTasks (loss-tolerant only) until Phase 2 | Bhima | Phase 2 |
| External audit log shipping | Security event correlation not available until Phase 2 | Nakula | Phase 2 |
| Trade matching rules (FIFO vs avg cost) | ADR-001 open item — Ganesha to confirm | Ganesha | — |
| Stale PENDING attachment rows | No sweep job; cosmetic DB issue, not a quota bug | Bhima | Phase 2 |
| MFA / OAuth / Passkeys | Architecture ready; not implemented | All | Phase 3 |
| AI interpretation layer | Architecture position decided (downstream of P&L); not designed | Vishwakarma | Phase 3 |
| OBS-12.3-01 | AnalyticsFilterBar render test doesn't assert Instrument/Segment groups explicitly | Arjun | Next cycle |
| OBS-12.3-02 | date_to change/clear not directly tested (symmetry with date_from) | Arjun | Next cycle |
| OBS-12.3-03 | Multi-select partial-uncheck path not tested (same toggleArrayParam logic) | Arjun | Next cycle |
| Active filter indicator | No visual badge showing how many filters are active | Arjun | Step 12.4 |

---

## Next Development Milestone

**Step 12.4 — Dynamic Filter Dimensions + Active Filter Indicator**

Step 12.3 (Analytics Filter UI) is complete and accepted. Step 12.4 adds the three deferred filter dimensions that require backend list endpoints, plus the active-filter UX improvement flagged by Yudhishthira.

**Step 12.4 scope (to be planned by Krishna before implementation):**
1. Backend: `GET /v1/analytics/filter-options` — returns `{ account_ids, setup_names, brokers }` populated from the user's actual data
2. Frontend: `account_ids`, `setup_names`, `brokers` multi-select controls wired into `AnalyticsFilterBar`
3. Frontend: Active filter badge on the filter bar ("3 filters active")
4. Optional: URL search param persistence if a router is introduced

**Pre-condition:** Backend analytics files must be committed and CI-gated before Step 12.4 proceeds.

---

## Key Constraints for Future Sessions

1. **Domain layer has zero framework imports** — enforced by code review; never add FastAPI/SQLAlchemy to domain code
2. **Journal service is a read-subscriber** — `JournalRepo` has no write methods targeting `trades` or `trade_pnl`; ADR-003 Decision 1
3. **`user_id` always from session, never from request body** — ADR-002, enforced at every repository query
4. **Full-replacement PUT** for journal entries — client must re-send all fields on every save; ADR-003 Decision 3
5. **Decimal arithmetic** — always initialize from string (`Decimal('0.1')`), rounding mode per output type per DECIMAL-USAGE-STANDARD.md
6. **Attachment download URLs are ephemeral** — never cache across page loads; 1-hour TTL S3 presign
7. **`StubStorage` is in use** — real attachment uploads will fail until Nakula provisions S3 and wires `S3Storage`
8. **Pydantic Decimal → JSON string** — backend serializes Decimal as string; frontend Zod schemas use `z.string().nullable()` at the boundary, not `z.number()`
9. **`account_id` is on all financial tables** — trades, trade_pnl, charge_schedules all have `account_id`; all analytics queries must scope by account
10. **`AnalyticsFilterParams` is the shared filter contract** — 9 dimensions (date_from, date_to, account_ids, instrument_types, exchange_segments, trade_types, directions, setup_names, brokers); frontend serializes arrays as repeated query params
