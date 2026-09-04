# TradeForge — Phase 1 MVP Execution Plan

**Document:** `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`  
**Author:** Krishna (Project Manager)  
**Date:** 2026-09-04  
**Base state:** Steps 1–12.5 complete, CI GREEN, branch `feat/step-12-5-behavioral-analytics`  
**Source of truth for scope:** `docs/requirements/REQUIREMENTS.md` v1.1 §38  
**Status:** ACTIVE — update as steps close

---

## What "Phase 1 MVP Deployed" Means

Phase 1 is complete when a real user can do all of the following without developer assistance:

1. Register an account and log in
2. Create a trading account (linked to a broker)
3. Import trades from a broker CSV (Zerodha, Upstox, or Angel One)
4. Add a trade manually
5. Journal any trade (emotions, mistakes, discipline score, attachments)
6. View a dashboard showing their P&L, win rate, and drawdown
7. View analytics (all Step 12 metrics)
8. View a trade list and drill into a trade detail page

**Phase 1 is NOT complete until the product is deployed on production infrastructure and accessible at a real URL.**

---

## Pre-Conditions (Decisions That Must Be Made First)

These are not code tasks. They are decisions that only Atharva can make. Everything on the critical infrastructure path is blocked until they are resolved.

| Decision | Why it blocks | Owner | Status |
|----------|--------------|-------|--------|
| **Cloud provider** (AWS / GCP / Azure) | Blocks: managed PostgreSQL, managed Redis (HA), KMS, email provider selection, S3 provisioning | Atharva | ❌ Not decided |
| **Production domain** | Blocks: CORS config, transactional email sender domain, passkey rpId (irreversible after first user registers a passkey) | Atharva | ❌ Not decided |

**These decisions must be made before any infrastructure provisioning work begins. Nakula cannot proceed on Step I-1 without them.**

---

## What Is Already Complete

Steps 1–12.5 are done. Do not re-do or revisit these. They are foundation — build on them.

| Step | What was delivered | Gate |
|------|-------------------|------|
| 1 | Project scaffold, DecimalConfig, health check | ✅ |
| 2–5 | Full auth system (Argon2id, Redis sessions, HIBP, CSRF, email verification, password reset) | ✅ Yudhishthira |
| 6–8 | Trade domain (7-table schema, FIFO reconstruction, fills, tax_lots) | ✅ |
| 9 | Journal (13 frontend components, attachment flow, audit history) | ✅ Yudhishthira |
| 10 | P&L engine (21-column schema, 7 charge components, R-multiple, 49 tests) | ✅ Yudhishthira 2026-09-01 |
| 11 | Trading accounts + broker CSV import (Zerodha, Upstox, Angel One) | ✅ |
| 12.1–12.5 | Analytics: 9 metric cards, full filter UI (9 dimensions), dynamic filter options, streaks/hold duration/exit type | ✅ Yudhishthira 2026-09-03/04 |

**Test totals as of Step 12.5:** 457 backend tests (84.31% coverage), 141 frontend tests (84.17% coverage).

---

## Remaining Phase 1 Work

Steps are ordered by dependency. Parallel workstreams are identified where possible.

---

### Step 12.6 — Analytics Completion (M-6 + M-10)

**Goal:** Close the remaining Karna analytics spec items required for Phase 1.  
**Owners:** Bhima (backend), Arjun (frontend)  
**Estimate:** 1 session  
**Dependency:** Step 12.5 accepted ✅  

**Scope:**
- **M-6 — R-Multiple Distribution:** `GET /v1/analytics/r-distribution` returning histogram buckets. Frontend: bar chart or bucketed table (buckets: <−2R, −2R to −1R, −1R to 0, 0 to +1R, +1R to +2R, >+2R). Insufficient sample guard.
- **M-10 — Dimension Breakdown (full):** Extend direction breakdown to cover Setup, Instrument, TradeType, Segment. Backend: parameterized breakdown endpoint or extend existing. Frontend: tabbed or selectable dimension breakdown table.
- **OBS-12.3-01:** Instrument/Segment filter bar render assertion (carried from Step 12.3 — Sahadeva gate item).

**Explicitly NOT in 12.6:**
- Rolling Expectancy (N-1), Time-of-Day (N-2), Kelly (N-4) → Step 12.7
- Monte Carlo (N-3) → Phase 2 (blocked on background job infrastructure)

**Gate:** Sahadeva GO → Nakula CI GREEN → Yudhishthira ACCEPT

---

### Step 12.7 — Analytics: Rolling Metrics

**Goal:** Deliver the remaining Karna spec analytics that complete the §13 Phase 1 analytics requirement.  
**Owners:** Bhima (backend), Arjun (frontend)  
**Estimate:** 1–2 sessions  
**Dependency:** Step 12.6 accepted  

**Scope:**
- **N-1 — Rolling Expectancy:** 20-trade rolling window expectancy. Backend: sliding window query. Frontend: sparkline or tabular rolling values.
- **N-2 — Time-of-Day Performance:** Performance breakdown by hour-of-day band (pre-market, morning, midday, afternoon, post-market for NSE session). Backend: EXTRACT(HOUR FROM first_fill_at) bucketed. Frontend: heatmap or bar table.
- **N-4 — Kelly Fraction:** Full Kelly and Half-Kelly from win rate + avg win/loss R. Frontend: single stat with a plain-language risk-of-ruin note.

**Explicitly NOT in 12.7:**
- N-3 Monte Carlo → Phase 2

**Gate:** Sahadeva GO → Nakula CI GREEN → Yudhishthira ACCEPT

---

### Step 13 — Basic Risk Metrics (Dhanvantari)

**Goal:** Deliver the Phase 1 risk requirements from §15 (Risk Management).  
**Owners:** Dhanvantari (spec), Bhima (backend), Arjun (frontend)  
**Estimate:** 2 sessions  
**Dependency:** Step 12 analytics foundation (for data queries). Can run in parallel with Step 12.7.  

**Scope — Phase 1 only:**
- Risk per trade (from `planned_risk_amount` already in journal)
- R-multiple distribution (covered by M-6 above)
- Account drawdown (max, current — already in analytics summary; deduplicate)
- Consecutive loss streak (M-12 covers this — deduplicate with streaks card)
- Daily risk utilization: `GET /v1/risk/daily-summary` — today's total at-risk across open trades
- **Backend:** `GET /v1/risk/summary` — aggregated: max drawdown, current drawdown, longest loss streak, daily loss, total at-risk

**Phase 1 risk scope does NOT include:**
- Position sizing calculator (Phase 2 — Dhanvantari)
- Strategy/instrument concentration (Phase 2)
- Correlated exposure (Phase 2)
- Portfolio heat map (Phase 2)
- Risk of ruin (Phase 2)
- Real-time open position risk (requires live price feed — Phase 2)

**Gate:** Dhanvantari spec sign-off → Sahadeva GO → Nakula CI GREEN → Yudhishthira ACCEPT

---

### Step 14 — Frontend Navigation Shell + Login / Registration Screens

**Goal:** Give the application a navigable structure that a real user can open in a browser.  
**Owner:** Arjun  
**Estimate:** 1 session  
**Dependency:** None (can start immediately, parallel to Steps 12.6, 12.7, 13)  

**Scope:**
- App router: React Router (or equivalent) with protected routes gated on session state
- Navigation sidebar or top bar linking: Dashboard, Journal, Analytics, Risk, Import, Settings
- **Login screen:** Email + password form wired to `POST /auth/login`. Redirect to dashboard on success. Error states (invalid credentials, account locked).
- **Registration screen:** Name, email, password (with strength indicator), confirm password. Wired to `POST /auth/register`. Post-registration: email verification prompt.
- **Email verification landing page:** Handles `/auth/verify-email?token=...` link from email.
- **Password reset flow:** Request reset screen + reset-with-token screen.
- Session-expired redirect: any 401 from API redirects to login with a "session expired" notice.

**Not in Step 14:**
- All other screens (built in subsequent steps)
- OAuth / social login (Phase 3)

**Gate:** Sahadeva GO → Nakula CI GREEN → Yudhishthira ACCEPT

---

### Step 15 — User Profile + Account/Broker Management Screen

**Goal:** Let users set up their profile and manage their trading accounts in the UI.  
**Owner:** Bhima (backend fields) + Arjun (frontend screen)  
**Estimate:** 1 session  
**Dependency:** Step 14 (navigation shell)  

**Backend scope (Bhima):**
- Add `time_zone`, `base_currency`, `display_name` to `users` table (migration)
- `GET/PATCH /v1/users/me` — profile read and update
- `GET /v1/accounts` — list trading accounts for user
- `POST /v1/accounts` — create account (name, broker, type, currency, starting capital)
- `PATCH /v1/accounts/{id}` — update account
- `DELETE /v1/accounts/{id}` — soft-delete (set inactive)

**Frontend scope (Arjun):**
- Settings screen: profile fields (display name, time zone, base currency)
- Account/Broker Management screen: list accounts, add account form, edit/deactivate account
- Account selection persisted in app state (drives all analytics/journal queries)

**Not in Step 15:**
- Deposits/withdrawals tracking (Phase 2)
- Per-account fee configuration UI (charge schedules exist in backend — UI deferred Phase 2)
- OAuth account linking (Phase 3)

**Gate:** Sahadeva GO → Nakula CI GREEN → Yudhishthira ACCEPT

---

### Step 16 — Manual Trade Entry

**Goal:** Let users add trades without a CSV file.  
**Owner:** Bhima (backend endpoint), Arjun (frontend screen)  
**Estimate:** 1–2 sessions  
**Dependency:** Step 15 (account selection)  

**Backend scope (Bhima):**
- `POST /v1/trades` — create a trade from manual fill data
  - Required: instrument, direction, trade_type, exchange_segment, entry fills (price, quantity, timestamp), account_id
  - Optional: exit fills, planned_stop, planned_target
  - Runs fill through reconstruction engine; computes P&L if trade is closed
- `POST /v1/trades/{id}/fills` — add fills to an existing trade (scale-in/out support)
- `DELETE /v1/trades/{id}` — soft-delete; cascades to trade_pnl, journal_entries

**Frontend scope (Arjun):**
- Add Trade screen: instrument search/select, direction, trade type, fill entry form (price, qty, timestamp), account selector
- Multi-fill entry for scale-in/out (add-fill UX)
- Validation: quantities must be positive, timestamps must be ordered, instrument must exist

**Not in Step 16:**
- Bulk manual entry (Phase 2)
- Options leg builder (Phase 2)
- Editing an existing trade's fills post-creation (Phase 2 — reconstruction implications)

**Gate:** Sahadeva GO → Nakula CI GREEN → Yudhishthira ACCEPT

---

### Step 17 — Import Trades Screen

**Goal:** Give users a UI for the CSV broker import that already exists in the backend.  
**Owner:** Arjun (frontend), Sanjaya (broker adapter correctness review)  
**Estimate:** 1 session  
**Dependency:** Step 15 (account selection). Backend adapters (Zerodha, Upstox, Angel One) are already complete.  

**Frontend scope (Arjun):**
- Import Trades screen: broker selector (Zerodha / Upstox / Angel One), file upload (CSV), account selector
- Import preview: show the number of fills detected before committing
- Import result: success count, skip count (duplicates), any errors
- Import history: list of previous imports (date, broker, fills imported, status)

**Backend scope (Bhima) — additions needed:**
- `POST /v1/imports` — initiate import; returns import job summary
- `GET /v1/imports` — list past import jobs for user
- Import idempotency: duplicate detection by (broker, fill_timestamp, instrument, quantity, price) — flag duplicates rather than error

**Not in Step 17:**
- Real-time import progress (Phase 2 — requires async job infrastructure)
- Column mapping UI for unknown broker formats (Phase 2)
- Broker API integrations (Phase 2 — Sanjaya)

**Gate:** Sahadeva GO → Nakula CI GREEN → Yudhishthira ACCEPT

---

### Step 18 — Dashboard

**Goal:** Give users a home screen that summarizes their trading state at a glance.  
**Owner:** Arjun (frontend), Bhima (any new backend aggregations needed)  
**Estimate:** 1–2 sessions  
**Dependency:** Steps 15 (account selection), 12 analytics foundation (data already computed)  

**Scope:**
- **Account Overview tile:** Net P&L (all-time, MTD, WTD), current drawdown, starting capital, current equity
- **Performance tile:** Win rate, expectancy, profit factor (sourced from existing analytics summary endpoint)
- **Streaks tile:** Current win/loss streak (sourced from Step 12.5 streaks endpoint)
- **Recent Trades list:** Last 10 closed trades — instrument, direction, net P&L, R-multiple, date. Clicking opens trade detail.
- **Recent Journal entries:** Last 5 journaled trades with discipline score and emotion summary
- **Account selector:** Switch between accounts; all dashboard tiles update

**New backend needed (Bhima):**
- `GET /v1/dashboard/summary` — aggregates: MTD P&L, WTD P&L, all-time P&L, current equity (starting capital + sum of net_pnl), account-scoped
- `GET /v1/trades?account_id=...&limit=10&status=CLOSED&order=last_fill_at:desc` — trade list endpoint (also needed for Step 19)

**Not in the Phase 1 dashboard:**
- Daily P&L chart / equity curve (Phase 2 — advanced charts)
- Risk utilization gauge (Phase 2)
- Behavioral pattern summary (Phase 2)
- Notification feed (Phase 2)
- Market context summary (Phase 2)

**Gate:** Sahadeva GO → Nakula CI GREEN → Yudhishthira ACCEPT

---

### Step 19 — Trade List + Trade Detail Screen

**Goal:** Let users navigate their trade history and see full detail on each trade.  
**Owner:** Arjun (frontend), Bhima (trade list API)  
**Estimate:** 1–2 sessions  
**Dependency:** Step 18 (trade list endpoint already needed there). Step 14 (navigation).  

**Trade List screen:**
- Paginated list: instrument, direction, entry date, exit date, net P&L, R-multiple, discipline score, emotion chip
- Filter bar: date range, account, direction, trade type, instrument — reuses `AnalyticsFilterBar` patterns
- Sort: by date (default), P&L, R-multiple
- Click → Trade Detail

**Trade Detail screen:**
- Trade summary: instrument, direction, quantity, average entry, average exit, P&L, R-multiple, hold duration
- Execution timeline: ordered list of fills (price, quantity, role, timestamp)
- Journal section: full journal entry (all fields from JournalPanel — already built, wire in here)
- P&L breakdown: gross P&L + 7 charge line items + net P&L (already exists in trade_pnl, build the display)
- Attachments grid (already built in JournalPanel — embed here)
- Audit history (already built — embed here)

**Backend needed (Bhima):**
- `GET /v1/trades` — paginated, filtered, sorted trade list
- `GET /v1/trades/{id}` — single trade with fills, trade_pnl, journal_entry in one response

**Not in Phase 1 trade detail:**
- Execution chart overlaid on price data (Phase 2 — requires market data)
- AI analysis panel (Phase 3)
- Market context section (Phase 2)

**Gate:** Sahadeva GO → Nakula CI GREEN → Yudhishthira ACCEPT

---

### Step 20 — Security Hardening (Pre-Deployment Gate)

**Goal:** Close the security gaps that block production deployment.  
**Owners:** Hanuman (review), Bhima (implementation)  
**Estimate:** 1 session  
**Dependency:** Must complete before Step I-3 (production deployment). Can run in parallel with Steps 16–19.  

**Scope:**
- **Rate limiting:** `slowapi` or equivalent on all auth endpoints (`/auth/register`, `/auth/login`, `/auth/password-reset/*`). Limits: 5 req/min per IP for login/register, 3 req/min for password reset. Return 429 with `Retry-After` header.
- **File upload validation:** Validate MIME type and file size on attachment uploads. Reject files above size limit. Log rejected attempts to `security_audit_log`.
- **S3Storage wired:** `S3Storage` implementation replacing `StubStorage`. Environment-variable-driven. `StubStorage` retained for local dev only.
- **Dependency scanning:** Add `pip-audit` or `safety` to GitHub Actions CI. Fail on high/critical CVEs.
- **Secret rotation baseline:** Confirm all secrets (session signing key, KMS KEK) are environment-variable sourced and not hardcoded. Hanuman to verify.

**Not in Step 20:**
- MFA / 2FA (Phase 3)
- PostgreSQL RLS (Phase 2 — Bhima + Nakula)
- Malware scanning on attachments (Phase 2)
- Penetration testing (Phase 2)

**Hanuman sign-off required before Step I-3.**

---

### Track I — Infrastructure (Parallel, Owner: Nakula)

This track runs in parallel with feature steps once Atharva makes the cloud/domain decisions. It does not block most feature development but is the final gate before production deployment.

#### Step I-1 — Cloud Infrastructure Provisioning

**Owner:** Nakula  
**Dependency:** Cloud provider decision + domain decision (Atharva) ← **CRITICAL PATH**  
**Estimate:** 1–2 sessions  

- Provision managed PostgreSQL (production + staging)
- Provision managed Redis (HA, production + staging)
- Provision KMS for broker credential KEK
- Provision S3 bucket for attachments (with lifecycle policy)
- Provision transactional email provider (SES / SendGrid / Postmark — Nakula decides)
- Create staging environment (separate DB, separate Redis)
- Document infrastructure topology in `docs/infrastructure/INFRA-TOPOLOGY.md`
- All credentials to environment variables; never in code

#### Step I-2 — CI/CD on Hosted Runner

**Owner:** Nakula  
**Dependency:** Step I-1  
**Estimate:** 1 session  

- Move GitHub Actions from local to GitHub-hosted runner
- Add deployment stage to CI: staging deploy on merge to `main`, production deploy on tagged release
- Add `pip-audit` security scan to CI pipeline
- Rollback procedure documented and tested on staging
- Environment parity check: staging DB migration must pass before production deploy is permitted

#### Step I-3 — Production Deployment

**Owner:** Nakula  
**Dependency:** Step I-2 + Step 20 (security hardening, Hanuman sign-off) + Sahadeva E2E gate (Step QA-1)  

- Deploy to production environment
- Run Alembic migrations on production DB
- Smoke test: health check, login, CSV import, journal entry, analytics summary
- Monitor error rate for 24 hours post-deploy
- Rollback plan on standby

---

### Track QA — E2E Tests

#### Step QA-1 — E2E Test Suite

**Owner:** Sahadeva  
**Dependency:** Steps 14–19 complete (screens must exist to test user journeys)  
**Estimate:** 1–2 sessions  

**Mandatory E2E journeys (all must pass before Step I-3):**

| Journey | Description |
|---------|-------------|
| J-1 | Register → verify email → log in |
| J-2 | Create trading account |
| J-3 | Import CSV (Zerodha) → confirm trade list populated |
| J-4 | Add trade manually → confirm P&L computed |
| J-5 | Journal a trade (emotion + discipline score + attachment) → audit history appears |
| J-6 | View analytics dashboard → all 9 metric cards render with data |
| J-7 | Apply filter (Direction: Long) → analytics update |
| J-8 | View trade detail page → all sections present |
| J-9 | Log out → session invalidated → protected routes redirect to login |

**E2E tooling:** Playwright (preferred — consistent with Vite + React; Sahadeva decides).  
**Test environment:** Staging environment (Step I-1).

---

## Phase 1 MVP Completion Criteria

Phase 1 is DONE when all of the following are true simultaneously:

- [ ] Steps 12.6, 12.7, 13, 14, 15, 16, 17, 18, 19 accepted by Yudhishthira
- [ ] Step 20 security hardening accepted by Hanuman
- [ ] Track I (I-1, I-2, I-3) complete — product live on production infrastructure
- [ ] Track QA E2E suite (J-1 through J-9) passing on staging
- [ ] No open HIGH or CRITICAL security findings from Hanuman
- [ ] Nakula: production deployment GREEN, no critical errors in first 24h monitoring

---

## Execution Sequence and Dependencies

```
[Atharva] Cloud + Domain Decision
              │
    ┌─────────┴──────────────────────────────┐
    │ Nakula: Track I starts                  │ Feature track starts (parallel)
    │ I-1 Infrastructure                      │
    │      ↓                                  │ Step 14: Navigation + Login  ←── can start NOW
    │ I-2 CI/CD on hosted runner              │       ↓
    │      ↓                                  │ Step 15: Profile + Accounts
    │ (waits for QA-1 + Step 20)              │       ↓
    │                                         │ Step 16: Manual Trade Entry
    │                                         │       ↓
    │                                         │ Step 17: Import Trades UI (parallel w/ 16)
    │                                         │       ↓
    │                                         │ Step 18: Dashboard (parallel w/ 16/17)
    │                                         │       ↓
    │                                         │ Step 19: Trade List + Detail
    │                                         │
    │ Step 12.6 → 12.7 (parallel w/ 14-19)   │
    │ Step 13 (parallel w/ 14-19)             │
    │ Step 20: Security (parallel w/ 14-19)   │
    │                                         │
    └──────── Steps QA-1: E2E ───────────────┘
                    │
              I-3: Production Deploy
```

**Steps that can start immediately (no pending decision):**
- Step 12.6 (Bhima + Arjun)
- Step 13 spec (Dhanvantari)
- Step 14 (Arjun)
- Step 20 design (Hanuman)

**Steps blocked on Atharva's cloud/domain decisions:**
- I-1 (Nakula) — nothing in the infrastructure track can begin

---

## Effort Summary

| Step | Owner(s) | Estimate | Parallel? |
|------|----------|----------|-----------|
| 12.6 Analytics completion | Bhima + Arjun | 1 session | Yes |
| 12.7 Rolling metrics | Bhima + Arjun | 1–2 sessions | Yes |
| 13 Basic risk metrics | Dhanvantari → Bhima + Arjun | 2 sessions | Yes |
| 14 Navigation + Login | Arjun | 1 session | Yes — start immediately |
| 15 Profile + Accounts UI | Bhima + Arjun | 1 session | After 14 |
| 16 Manual trade entry | Bhima + Arjun | 1–2 sessions | After 15 |
| 17 Import trades UI | Arjun + Bhima | 1 session | After 15, parallel w/ 16 |
| 18 Dashboard | Arjun + Bhima | 1–2 sessions | After 15, parallel w/ 16/17 |
| 19 Trade list + detail | Arjun + Bhima | 1–2 sessions | After 18 |
| 20 Security hardening | Hanuman → Bhima | 1 session | Parallel, any time |
| I-1 Infrastructure | Nakula | 1–2 sessions | Blocked on Atharva |
| I-2 CI/CD hosted | Nakula | 1 session | After I-1 |
| QA-1 E2E tests | Sahadeva | 1–2 sessions | After Steps 14–19 |
| I-3 Production deploy | Nakula | 0.5 session | After all above |

**Total remaining Phase 1 effort:** approximately **12–18 focused sessions** (with good parallelism, realistically 8–12 calendar sessions).

---

## Risk Register (Phase 1)

| # | Risk | Likelihood | Impact | Owner | Mitigation |
|---|------|-----------|--------|-------|-----------|
| R-1 | Cloud/domain decisions remain deferred | High | High | Atharva | Escalate: every session delayed is a session lost on infra. Set a decision deadline. |
| R-2 | Rate limiting not shipped before any users onboarded | Medium | High | Hanuman | Step 20 is a hard deployment gate. Hanuman sign-off required before I-3. |
| R-3 | S3Storage not wired → attachments fail silently in production | Medium | Medium | Nakula | Step 20 scope. StubStorage clearly flagged in staging smoke test. |
| R-4 | Production domain rpId wrong → passkeys permanently broken for early users | Low | High | Atharva | Domain decision before any production registration. No workaround once users register. |
| R-5 | Manual trade entry endpoint too narrowly scoped for import parity | Low | Medium | Bhima | Sanjaya to review endpoint design before implementation to confirm adapter compatibility |
| R-6 | E2E tests reveal backend bugs in journeys that weren't integration-tested | Medium | Medium | Sahadeva | Staging environment catches this before production. Buffer time in QA-1 estimate. |
| R-7 | PostgreSQL RLS absent → application-level user_id scoping is only security backstop | Accepted | Medium | Bhima + Nakula | Accepted risk for Phase 1. ADR to document. Bhima must ensure no path bypasses `user_id` scoping. Phase 2 adds RLS. |

---

## Open Items That Must Be Resolved During Phase 1

| # | Item | Owner | Required by |
|---|------|-------|------------|
| OI-1 | Cloud provider decision | Atharva | Before Step I-1 |
| OI-2 | Production domain decision | Atharva | Before Step I-1 |
| OI-3 | Ganesha: confirm FIFO multi-lot treatment for CNC delivery — is single-lot assumption acceptable for Phase 1? | Ganesha | Before Step 13 or Step 16 |
| OI-4 | Yudhishthira: confirm Phase 1 scope of Strategy/Setup — hardcoded enum acceptable, or must users define their own before MVP? | Yudhishthira | Before Step 18 (dashboard design) |
| OI-5 | Dhanvantari: produce Phase 1 risk metrics spec (scope of Step 13) | Dhanvantari | Before Step 13 implementation |
| OI-6 | Nakula: select transactional email provider | Nakula | Before Step I-1 |

---

## What Is NOT in Phase 1 (Upcoming — Phase 2)

The following are explicitly deferred to Phase 2. Do not implement, do not scope, do not design during Phase 1.

**Analytics:**
- N-3 Monte Carlo simulation (blocked on background job infrastructure)
- Advanced chart library: equity curve, drawdown curve, MAE/MFE scatter, monthly heatmap, calendar P&L (§19)
- Rolling period analytics (beyond rolling expectancy from Step 12.7)

**Risk Management (advanced):**
- Position sizing calculator with configurable risk rules
- Strategy/instrument concentration limits
- Correlated exposure monitoring
- Portfolio heat map
- Risk-of-ruin calculation
- Real-time open position risk (requires live price feed)

**Broker Integrations:**
- Broker API integrations (Zerodha Kite Connect, Upstox API, Angel One SmartAPI) — Sanjaya
- Real-time trade sync
- Column mapping UI for unknown broker CSV formats

**Journal / Trade capture:**
- Bulk trade editing
- Options leg builder (multi-leg strategy entry)
- Editing fills on an already-reconstructed trade
- Slippage recording (`intended_price` field)

**Account Management:**
- Deposits and withdrawals tracking
- Per-account fee configuration UI
- Account-level P&L reports with capital returns

**Psychology (deep):**
- Behavioral-P&L correlation analysis (Vidura) — e.g. FOMO trades vs. planned trades performance
- Confidence field, fear/greed/fatigue granular sub-fields
- Full psychology module screen

**Market Context:**
- Market context capture (trend, volatility regime, VIX)
- External market data enrichment

**Infrastructure:**
- PostgreSQL Row-Level Security (RLS)
- Celery + Redis workers for async jobs (replaces BackgroundTasks for loss-intolerant work)
- External audit log shipping
- Admin panel
- Advanced observability: structured logs, API metrics, import-job monitoring

**Testing:**
- Performance / load testing
- Security penetration testing (Hanuman)
- Data tests for malformed/corrupted broker files

**Reports:**
- Daily, weekly, monthly reports (CSV/Excel/PDF export)
- Strategy report, risk report, behavioral report

**Notifications & Alerts:**
- Daily loss limit alerts
- Drawdown threshold alerts
- In-app, email, push notifications

**Search:**
- Global trade search (by symbol, emotion, mistake, tag)
- Tag infrastructure (`tags` table, `trade_tags` join table)

---

## What Is NOT in Phase 2 (Upcoming — Phase 3)

The following are explicitly Phase 3. Do not plan, design, or scope during Phase 1 or Phase 2.

- AI Trading Assistant — all capabilities in §21 (Vishwakarma)
- MFA / 2FA
- Google OAuth / other OAuth providers
- Passkeys
- Mobile client
- Trading team / prop desk support
- Multi-market expansion (crypto, currency, international)
- Options exercise P&L (Ganesha/Kubera unresolved edge case)
- Futures MTM per day
- Corporate-action adjustments

---

## Document Maintenance

This document is the single reference for Phase 1 delivery. It must be updated as steps close.

- When a step closes: mark it with ✅ and the acceptance date
- When an open item resolves: update the OI table
- When a risk materializes or is retired: update the risk register
- **Do not add Phase 2/3 scope to this document.** Open a separate plan when Phase 2 begins.

**Owner:** Krishna  
**Review cadence:** At the start of every new step (before implementation begins)

---

*Krishna — Senior Project Manager*  
*Source: `docs/requirements/REQUIREMENTS.md` v1.1, `docs/project-status/TRADEFORGE-CURRENT-STATE.md`, `docs/project-status/REQUIREMENTS-TRACEABILITY.md`*  
*Step owners per §40 agent responsibilities*
