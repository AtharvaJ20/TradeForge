# TradeForge — Current Project State

**Last updated:** 2026-08-24  
**Author:** Yudhishthira (Product)  
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

**Domain boundary rule (non-negotiable, ADR-001):** Domain layer imports zero framework or infrastructure code. Enforced by code review on every PR.

---

## Completed Milestones

### Foundation (Step 1)
- Project scaffold: `backend/src/tradeforge/` with domain / application / infrastructure / api layer structure
- `DecimalConfig` domain module; Decimal Usage Standard (`docs/standards/DECIMAL-USAGE-STANDARD.md`) — accepted, blocks all financial calculation code
- Health check endpoint, test scaffolding (pytest), `pyproject.toml`

### Authentication (Steps 2–5)
**Backend — fully implemented:**
- Domain: `password.py` (Argon2id), `tokens.py` (256-bit opaque), `events.py`, `errors.py`
- Application: `AuthService`, HIBP k-anonymity check, email notifications, forced-reauth control
- Infrastructure: `UserModel`, `AuthModel`, `UserRepo`, `AuthRepo`, `SessionRepo`, `RedisClient`, `DBSession`
- API: `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/verify-email`, `/auth/password-reset/*`; CSRF middleware; Origin validation
- Migration: `0001_auth_tables.py` (users, sessions backup ref, security_audit_log, pending_email_verifications, pending_password_resets)
- Defect D-009 closed (Step 9 defect cycle)

### Trade Domain (Steps 6–8)
**Backend — fully implemented:**
- Domain: `trade/types.py` (enums, value objects), `trade/errors.py`
- Infrastructure ORM: `trade_domain.py` (instruments, lot_size_history, trades, execution_fills, management_events, tax_lots)
- Infrastructure repositories: `FillRepo`, `TradeRepo`, `TaxLotRepo`, `FillExclusionRepo`
- Application: `reconstruction.py` — trade reconstruction engine (FIFO lot tracking, fill → trade aggregation)
- Migrations: `0002_trade_domain_tables.py`, `0003_fill_exclusions.py`
- Standards: `TRADE-DOMAIN-RULES.md`, `DECIMAL-USAGE-STANDARD.md`
- Design: `TRADE-DOMAIN-DATA-MODEL.md`, `TRADE-RECONSTRUCTION-SPEC.md`

### Journal / Step 9 (Complete — defects closed)
**Backend — fully implemented:**
- Domain: `journal/types.py` (enums: EmotionTag, MistakeTag, SetupType; PnlStatus computed value), `journal/errors.py`
- Infrastructure ORM: `journal.py` (journal_entries, journal_attachments, journal_audit_log), `trade_pnl.py` (stub ORM for EXISTS check)
- Infrastructure: `JournalRepo` — reads trades/trade_pnl (SELECT only), writes journal tables
- Application: `JournalService` (upsert_entry, get_entry, get_audit_history, presign/confirm/delete attachment); `StoragePort` Protocol + `StubStorage`
- API: `GET/PUT /v1/journal/trades/{trade_id}`, audit history, 3-endpoint attachment flow (presign → direct-to-S3 → confirm)
- Migration: `0004_journal_tables.py`
- Defects closed: D-001, D-002, D-003, D-004 (journal), D-009 (auth)

**Frontend — fully implemented:**
- Toolchain: Vite 5 / React 18 / TypeScript strict / Tailwind v3 / TanStack Query v5
- 10 components: `JournalPanel`, `JournalQuickCapture`, `JournalFullForm`, `TradeContextPanel`, `PnlStatusBlock`, `DisciplineScoreInput`, `EmotionChipGroup`, `MistakesCheckboxGroup`, `AttachmentUploader`, `AttachmentGrid`, `AuditHistoryDrawer`, `AuditPromptInline`, `SkeletonPnlBlock`
- Hooks: `useJournalEntry`, `useUpsertJournalEntry`, `useAuditHistory`, `useAttachmentUpload`, `useDeleteAttachment`
- Tests: 4 unit tests (component level) + 1 integration test (`JournalPanel` with MSW intercepting all 7 API endpoints)
- MSW v2 handler layer in `src/__tests__/msw/`

---

## Design & Spec Documents

| File | What it specifies |
|------|-------------------|
| `docs/adr/ADR-001-backend-framework.md` | Python/FastAPI stack, async model, layer boundary rules |
| `docs/adr/ADR-002-authentication-authorization-architecture.md` | Full auth architecture + 21 security requirements |
| `docs/decisions/ADR-003-journal-annotation-architecture.md` | 10 journal architecture decisions, attachment protocol |
| `docs/decisions/ADR-004-journal-frontend-architecture.md` | Frontend toolchain and structural decisions |
| `docs/design/TRADE-DOMAIN-DATA-MODEL.md` | 7-table trade domain schema + ER diagram |
| `docs/design/TRADE-RECONSTRUCTION-SPEC.md` | Fill → trade reconstruction algorithm |
| `docs/design/JOURNAL-UX-SPEC.md` | 10 component specs (C-01 through C-10) |
| `docs/design/JOURNAL-API-SPEC.md` | Full journal API contract |
| `docs/standards/DECIMAL-USAGE-STANDARD.md` | Rounding mode, precision per output type, init rules |
| `docs/standards/TRADE-DOMAIN-RULES.md` | Trade matching, classification, FIFO rules |
| `docs/standards/JOURNAL-DOMAIN-RULES.md` | Journal business rules (G1 — 9 rule groups) |
| `docs/standards/JOURNAL-SECURITY-REQUIREMENTS.md` | SR-JOUR-001–013, SR-ATT-001–010 (G4, Hanuman) |
| `docs/standards/JOURNAL-PNL-INTEGRATION.md` | How journal reads P&L for PnlStatus / R-multiple |
| `docs/decisions/PROD-DOMAIN-DECISION-BRIEF.md` | Why production domain must be decided before deployment |
| `docs/decisions/LOCAL-DEV-INFRASTRUCTURE.md` | Local dev equivalents (Docker Compose config) |

---

## Infrastructure Status

| Component | Status |
|-----------|--------|
| Docker Compose (local) | Configured — PostgreSQL + Redis locally |
| Cloud provider | **Not selected** — AWS / GCP / Azure (Nakula owns) |
| Managed PostgreSQL | **Not provisioned** |
| Managed Redis (HA) | **Not provisioned** |
| KMS (broker credential KEK) | **Not provisioned** — requires cloud provider decision |
| S3 bucket (attachment storage) | **Not provisioned** — `StubStorage` in use; attachments non-functional end-to-end |
| Transactional email provider | **Not provisioned** — auth email flows not testable in production |
| CI/CD pipeline | **Not configured** |
| Production environment | **Not deployed** |

`scripts/init-kms.sh` exists but KMS provider is undecided.

---

## QA Status

- Sahadeva acceptance gate for Step 9 (10-item checklist in `JOURNAL-SECURITY-REQUIREMENTS.md`) — **not formally signed off**
- No QA release recommendation on record
- Backend test coverage: unit (domain) + integration (API) — passing locally
- Frontend test coverage: 5 test files (4 unit, 1 integration) — passing locally
- No E2E tests exist yet

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

---

## Not Yet Started

| Milestone | Owner | Depends On |
|-----------|-------|-----------|
| **Step 10 — P&L Engine (Kubera)** | Bhima + Kubera | Trade domain (done); `trade_pnl` ORM stub exists |
| **Step 11 — Broker Import (Sanjaya)** | Bhima + Sanjaya | Trade domain (done); broker adapter interface not yet defined |
| **Step 12 — Karna Analytics** | Bhima + Karna | P&L engine (Step 10) |
| **Step 13 — Risk Layer (Dhanvantari)** | Bhima + Dhanvantari | P&L + analytics |
| **Broker credential KMS integration** | Bhima + Nakula | Cloud provider + KMS provisioned |
| **Production deployment** | Nakula | Domain, cloud, KMS, Redis HA, S3, email provider |

---

## Next Development Milestone

**Step 10 — P&L Engine (Kubera)**

The `trade_pnl` ORM stub is already in place (needed by the journal's PnlStatus check). The next task is to implement the actual P&L calculation engine:

1. Bhima designs the `trade_pnl` table with full schema (charges, STT, net P&L, gross P&L, R-multiple inputs)
2. Kubera specifies the charge calculation rules per instrument type (EQ vs FO, CNC vs MIS, brokerage caps)
3. Bhima implements the P&L service and migration
4. Sahadeva validates against Kubera's test cases

**Prerequisite check before starting:** Confirm `FIFO vs average cost` trade matching decision (Ganesha open item from ADR-001) is resolved, as it affects lot-level P&L attribution.

---

## Key Constraints for Future Sessions

1. **Domain layer has zero framework imports** — enforced by code review; never add FastAPI/SQLAlchemy to domain code
2. **Journal service is a read-subscriber** — `JournalRepo` has no write methods targeting `trades` or `trade_pnl`; ADR-003 Decision 1
3. **`user_id` always from session, never from request body** — ADR-002, enforced at every repository query
4. **Full-replacement PUT** for journal entries — client must re-send all fields on every save; ADR-003 Decision 3
5. **Decimal arithmetic** — always initialize from string (`Decimal('0.1')`), rounding mode per output type per DECIMAL-USAGE-STANDARD.md
6. **Attachment download URLs are ephemeral** — never cache across page loads; 1-hour TTL S3 presign
7. **`StubStorage` is in use** — real attachment uploads will fail until Nakula provisions S3 and wires `S3Storage`
