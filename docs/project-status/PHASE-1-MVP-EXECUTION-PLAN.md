# TradeForge — Phase 1 MVP Execution Plan

**Document:** `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`  
**Author:** Krishna (Project Manager)  
**Date:** 2026-09-05  
**Base state:** Steps 1–14 complete, CI GREEN, branch `main` (after `feat/step-14-execution-plan` merged)  
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

| Decision | Why it blocks | Owner | Status |
|----------|--------------|-------|--------|
| **Deployment platform** | Determines how services are provisioned | Atharva | ✅ **RESOLVED — Railway** (no upfront cost, free tiers for PostgreSQL + Redis) |
| **Production domain** | Blocks: CORS config, transactional email sender domain, passkey rpId (irreversible after first user registers a passkey) | Atharva | ⚠️ **Partially resolved** — Railway provides a free `*.up.railway.app` subdomain usable for Phase 1. Custom domain can be added later. If Atharva wants a custom domain at launch, decide before Step I-1. |
| **KMS approach for broker credentials** | ADR-002 specifies envelope KMS for broker credential encryption. Railway has no native KMS. | Hanuman | ❌ **Needs Hanuman ruling** — see OI-KMS below |

**OI-KMS — Broker Credential Encryption on Railway:**  
ADR-002 calls for an envelope KMS (Key Encryption Key) to protect broker API credentials. Railway has no managed KMS. Three options — Hanuman must rule before Step I-1:
1. **Env-var symmetric encryption (simplest):** Use a `BROKER_MASTER_KEY` environment variable set in Railway dashboard. Encrypt credentials with AES-256-GCM using this key. No external dependency. Acceptable for Phase 1 if Hanuman approves. Risk: key rotation requires re-encrypting all records.
2. **HashiCorp HCP Vault (free tier):** External KMS-as-a-service, free tier available. Adds external dependency but proper key management. More operational overhead for a solo developer.
3. **Defer broker credential storage:** Phase 1 users import via CSV only — broker credentials not needed until broker API integrations (Phase 2). Deferring the KMS requirement to Phase 2 is architecturally sound and eliminates the blocker entirely for Phase 1.

**Krishna's recommendation:** Option 3 — defer. Phase 1 uses CSV import only. Broker API credentials are a Phase 2 feature (Sanjaya). Implementing KMS complexity now for a feature that doesn't exist yet is premature. Hanuman confirms this is acceptable for Phase 1.

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
| 12.6–12.7 | Analytics completion: R-distribution, dimension breakdown, rolling expectancy, time-of-day, Kelly fraction | ✅ Yudhishthira 2026-09-04 |
| 13 | Basic risk metrics (RiskSummaryCard, `/v1/risk/summary`) | ✅ Yudhishthira 2026-09-05 |
| 14 | Frontend Navigation Shell + Auth Screens (React Router, AuthContext, 6 auth screen components, AppShell, RequireAuth, session-expired redirect, skip-link a11y) | ✅ Yudhishthira 2026-09-05 |

**Test totals as of Step 14:** 501 backend tests (84.91% coverage), 245 frontend tests (87.43% coverage).

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
**Status:** ✅ **ACCEPTED — 2026-09-04** (Sahadeva GO WITH RISKS → Nakula CI GREEN → Yudhishthira ACCEPT)  
**Test totals:** 474 backend tests (84.79% coverage), 165 frontend tests (85.01% coverage)  
**Branch:** `feat/step-12-6-analytics-completion` (merge to `main` via PR)

---

### Step 12.7 — Analytics: Rolling Metrics

**Goal:** Deliver the remaining Karna spec analytics that complete the §13 Phase 1 analytics requirement.  
**Owners:** Bhima (backend), Arjun (frontend)  
**Estimate:** 1–2 sessions  
**Dependency:** Step 12.6 accepted ✅  
**Execution plan:** `docs/project-status/STEP-12-7-EXECUTION-PLAN.md`

**Scope:**
- **N-1 — Rolling Expectancy:** 20-trade sliding-window expectancy. Backend: pure Python over ordered equity curve. Frontend: scrollable table (last 20 points visible).
- **N-2 — Time-of-Day Performance:** Performance by NSE session band (Pre-Open, Open Volatility, Mid-Morning, Lunch, Afternoon, Close) bucketed from `first_fill_at AT TIME ZONE 'Asia/Kolkata'`. Frontend: 6-row table.
- **N-4 — Kelly Fraction:** Full Kelly and Half-Kelly from Expectancy_R / AVG(positive R). Frontend: two stat numbers + plain-language note. Min N: 30 trades with valid R.

**Order of work:** N-4 → N-2 → N-1 (increasing complexity).

**Explicitly NOT in 12.7:**
- N-3 Monte Carlo → Phase 2
- N-5 MAE/MFE → Phase 2
- Sparkline chart for rolling expectancy → Phase 2 (table is MVP)

**Gate:** Sahadeva GO → Nakula CI GREEN → Yudhishthira ACCEPT  
**Status:** ✅ **ACCEPTED — 2026-09-04** (Sahadeva GO WITH RISKS → Nakula LOCAL CI GREEN → Yudhishthira ACCEPT)  
**Test totals:** 488 backend tests (84.27% coverage), 190 frontend tests (85.6% statements / 87.88% branches)  
**Branch:** `feat/step-12-7-rolling-metrics` (merge to `main` via PR — GitHub Actions CI confirmation required before merge)  
**Note:** §13 Phase 1 analytics requirement is now fully closed (Steps 12.1–12.7 complete).

---

### Step 13 — Basic Risk Metrics (Dhanvantari)

**Goal:** Deliver the Phase 1 risk requirements from §15 (Risk Management).  
**Owners:** Dhanvantari (spec), Bhima (backend), Arjun (frontend)  
**Estimate:** 2 sessions  
**Dependency:** Step 12 analytics foundation (for data queries). Can run in parallel with Step 12.7.  
**Execution plan:** `docs/project-status/STEP-13-EXECUTION-PLAN.md`

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
**Status:** ✅ **ACCEPTED — 2026-09-05** (Dhanvantari signed off 2026-09-04 · Sahadeva GO · Nakula CI GREEN · Yudhishthira ACCEPT)  
**Test totals:** 506 backend tests, 141 frontend tests  
**Branch:** `feat/step-13-basic-risk-metrics` (merged to `main` via PR)

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

**Execution plan:** `docs/project-status/STEP-14-EXECUTION-PLAN.md`  
**Gate:** Sahadeva GO → Nakula CI GREEN → Yudhishthira ACCEPT  
**Status:** ✅ **ACCEPTED — 2026-09-05** (Sahadeva GO · Nakula CI GREEN · Yudhishthira ACCEPT)  
**Test totals:** 245 frontend tests (87.43% coverage), 501 backend tests (84.91% coverage)  
**Branch:** `feat/step-14-execution-plan` (merged to `main`)  
**Note:** VerifyEmailPage auto-redirect (2s) replaced with explicit "Continue to sign in" button — accepted product improvement per Yudhishthira + Usha (WCAG, user control). WCAG 2.1 SC 2.4.1 skip-link added to AppShell.

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

**Platform: Railway** (railway.app) — chosen for zero upfront cost and free tiers. No traditional cloud provider (AWS/GCP/Azure) is used in Phase 1.

This track runs in parallel with feature steps. It does not block most feature development but is the final gate before production deployment.

#### Step I-1 — Railway Service Provisioning

**Owner:** Nakula  
**Dependency:** OI-KMS decision (Hanuman) — recommend deferring broker credential KMS to Phase 2 (see Pre-Conditions)  
**Estimate:** 1 session  

**Railway services to provision:**
- **PostgreSQL:** Railway managed PostgreSQL plugin. Production environment + staging environment (separate Railway projects or environments).
- **Redis:** Railway managed Redis plugin. Needed for session management (`SessionRepo`).
- **FastAPI backend:** Deployed as a Railway service from the GitHub repo. `Dockerfile` or Nixpacks. Port from `uvicorn`.
- **Vite frontend:** Deployed as a Railway static service or separate service (or Vercel/Cloudflare Pages for free static hosting — Nakula decides which is simpler).

**External free-tier services (not Railway-native):**
- **Attachment storage (S3-compatible):** Cloudflare R2 (free: 10 GB storage, zero egress fees) — recommended. Alternatively Backblaze B2 (free 10 GB). Both are S3-compatible; `S3Storage` implementation only needs endpoint + bucket + key env vars. **Nakula provisions, Bhima wires `S3Storage`.**
- **Transactional email:** Resend (free: 3,000 emails/month, 100/day) — recommended for simplicity. Alternatively Mailgun free tier. Nakula selects and provisions. Bhima updates `EmailService` to use the chosen provider's SMTP or API.

**Environment variables (all secrets via Railway dashboard — never in code):**
- `DATABASE_URL` — Railway injects automatically for the PostgreSQL plugin
- `REDIS_URL` — Railway injects automatically for the Redis plugin
- `SESSION_SECRET` — generate with `openssl rand -hex 32`
- `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` — from Cloudflare R2 / Backblaze
- `EMAIL_API_KEY` — from Resend / Mailgun
- `ALLOWED_ORIGINS` — production domain (e.g. `https://tradeforge.up.railway.app` or custom domain)

**Domain:**
- Phase 1: use Railway's free `*.up.railway.app` subdomain. No custom domain required to deploy.
- Custom domain: add via Railway dashboard at any time — does not require a redeploy.
- **Important:** Do not register any users with passkeys until the domain is finalised — passkey rpId is tied to the domain and cannot be changed per registered key.

**Deliverable:** Document service topology + env var list in `docs/infrastructure/RAILWAY-TOPOLOGY.md`.

#### Step I-2 — CI/CD on GitHub Actions (GitHub-hosted runner)

**Owner:** Nakula  
**Dependency:** Step I-1  
**Estimate:** 0.5 session  

- Move GitHub Actions from local to GitHub-hosted runner (free tier: 2,000 min/month for public repos, 500 min for private)
- Add Railway deployment step to CI: on merge to `main` → Railway redeploy via `RAILWAY_TOKEN` secret in GitHub
- Add `pip-audit` security scan step to CI pipeline
- Alembic migration runs as part of Railway deploy (Railway start command: `alembic upgrade head && uvicorn ...`)
- Staging environment: separate Railway project. CI deploys to staging first; production deploy is a manual trigger or tagged release.

#### Step I-3 — Production Deployment

**Owner:** Nakula  
**Dependency:** Step I-2 + Step 20 (security hardening, Hanuman sign-off) + Sahadeva E2E gate (Step QA-1)  

- Trigger production Railway deploy
- Confirm Alembic migrations applied cleanly (check Railway logs)
- Smoke test against production URL: health check, login, CSV import, journal entry, analytics summary
- Monitor Railway metrics (memory, CPU, error rate) for 24 hours
- Rollback: Railway supports one-click redeploy of any prior deployment

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

- [x] Step 12.6 accepted by Yudhishthira ✅ 2026-09-04
- [x] Step 12.7 accepted by Yudhishthira ✅ 2026-09-04
- [x] Step 13 accepted by Yudhishthira ✅ 2026-09-05
- [x] Step 14 accepted by Yudhishthira ✅ 2026-09-05
- [ ] Steps 15, 16, 17, 18, 19 accepted by Yudhishthira
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
- Step 15 (Bhima + Arjun) — Step 14 is now complete
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
| R-1 | ~~Cloud provider deferred~~ | — | — | — | ✅ RETIRED — Railway decision made 2026-09-04 |
| R-1b | Railway free tier limits hit before production is stable | Low | Medium | Nakula | Monitor Railway usage. Free PostgreSQL has storage limits; free Redis has memory limits. Upgrade to paid tier (~$5/mo) if needed — cost is low. |
| R-2 | Rate limiting not shipped before any users onboarded | Medium | High | Hanuman | Step 20 is a hard deployment gate. Hanuman sign-off required before I-3. |
| R-3 | S3Storage not wired → attachments fail silently in production | Medium | Medium | Nakula | Step 20 scope. StubStorage clearly flagged in staging smoke test. |
| R-4 | Production domain rpId wrong → passkeys permanently broken for early users | Low | High | Atharva | Domain decision before any production registration. No workaround once users register. |
| R-5 | Manual trade entry endpoint too narrowly scoped for import parity | Low | Medium | Bhima | Sanjaya to review endpoint design before implementation to confirm adapter compatibility |
| R-6 | E2E tests reveal backend bugs in journeys that weren't integration-tested | Medium | Medium | Sahadeva | Staging environment catches this before production. Buffer time in QA-1 estimate. |
| R-7 | PostgreSQL RLS absent → application-level user_id scoping is only security backstop | Accepted | Medium | Bhima + Nakula | Accepted risk for Phase 1. ADR to document. Bhima must ensure no path bypasses `user_id` scoping. Phase 2 adds RLS. |

---

## Open Items That Must Be Resolved During Phase 1

| # | Item | Owner | Status | Required by |
|---|------|-------|--------|------------|
| OI-1 | Cloud provider decision | Atharva | ✅ **RESOLVED — Railway** (2026-09-04) | — |
| OI-2 | Production domain decision | Atharva | ⚠️ **Partially resolved** — `*.up.railway.app` free subdomain usable for Phase 1. Custom domain optional. | Before Step I-1 (decide if custom domain needed at launch) |
| OI-KMS | Broker credential KMS approach on Railway | Hanuman | ❌ **Pending ruling** — Krishna recommends deferring to Phase 2 (CSV-only Phase 1 doesn't need broker API credentials) | Before Step I-1 |
| OI-3 | Ganesha: confirm FIFO multi-lot treatment for CNC delivery — single-lot assumption acceptable for Phase 1? | Ganesha | ✅ **RESOLVED 2026-09-04** — ruling G-RISK-01: use `status IN ('OPEN', 'PARTIAL')`, full `planned_risk_amount` no pro-ration, label "Planned At-Risk" | — |
| OI-4 | Yudhishthira: confirm Phase 1 scope of Strategy/Setup — hardcoded enum acceptable, or must users define their own before MVP? | Yudhishthira | ❌ Open | Before Step 18 (dashboard design) |
| OI-5 | Dhanvantari: produce Phase 1 risk metrics spec (scope of Step 13) | Dhanvantari | ✅ **RESOLVED 2026-09-04** — spec signed off, two corrections applied (open trade date scoping removed; `current_loss_streak` added) | — |
| OI-6 | Nakula: select transactional email provider (Resend recommended — free 3,000/month) | Nakula | ❌ Open | Before Step I-1 |
| OI-7 | Nakula: select attachment storage provider (Cloudflare R2 recommended — free 10 GB, zero egress) | Nakula | ❌ Open | Before Step 20 (S3Storage wiring) |

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
