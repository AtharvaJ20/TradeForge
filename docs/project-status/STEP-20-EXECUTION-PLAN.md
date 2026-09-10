# Step 20 — Security Hardening (Pre-Deployment Gate)

**Document:** `docs/project-status/STEP-20-EXECUTION-PLAN.md`  
**Author:** Krishna (Project Manager)  
**Date:** 2026-09-10  
**Branch:** `feat/step-20-security-hardening` (base: `main` at `8d7ca66` — PR #13 merged)  
**Phase 1 plan ref:** `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md` §Step 20  
**Gate:** Hanuman sign-off required before Step I-3 (production deployment)

---

## Purpose

Step 20 closes the security gaps that block production deployment. Nothing in this step is optional — Hanuman must sign off before Nakula executes Step I-3.

This plan is grounded in a codebase audit conducted on 2026-09-10. Several scope items from the Phase 1 plan are already partially or fully implemented. Those are noted explicitly — do not re-implement them.

---

## Owners

| Role | Owner | Responsibility |
|------|-------|----------------|
| Security review | Hanuman | Threat review, verify each item, final sign-off |
| Backend implementation | Bhima | S3Storage, rate-limit threshold, settings cleanup |
| CI/CD | Nakula | `pip-audit` step in GitHub Actions |
| Product acceptance | Yudhishthira | Confirm scope matches Phase 1 requirements |

---

## What Was Found in the Codebase Audit

Before writing the task breakdown, Krishna audited the actual codebase state. Hanuman must verify each finding.

### Finding 1 — Rate limiting: infrastructure exists, threshold is too permissive

**Status: GAP — Bhima action required**

The existing implementation in `session_repo.py` uses a Redis-backed fixed-window counter with a 60-second TTL. The counter keys are:
- `auth_attempts_ip:{ip}` — register, verify-email, password-reset (60s window)
- `login_attempts_ip:{ip}` — login only (60s window)

The threshold is `IP_ATTEMPT_THRESHOLD = 50` (`backend/src/tradeforge/infrastructure/repositories/session_repo.py:30`).

**The Phase 1 requirement is 5 req/min for login/register and 3 req/min for password-reset.** The current threshold of 50 is 10× too permissive. This is a real gap.

**Note on `slowapi`:** The existing Redis-based approach is architecturally sound — it is durable across restarts and shared across instances, which is better than `slowapi`'s default in-memory counters. Hanuman should confirm whether lowering the existing threshold is sufficient or whether `slowapi` middleware is still required in addition.

### Finding 2 — File upload validation: already implemented at service layer

**Status: IMPLEMENTED — Hanuman to verify coverage is sufficient**

`JournalService` enforces (source: `backend/src/tradeforge/application/journal/service.py`):
- `ALLOWED_CONTENT_TYPES` allowlist check before presign (`SR-ATT-001`)
- `ATTACHMENT_MAX_BYTES` per-file size enforcement (`SR-ATT-002`)
- `ATTACHMENT_PER_TRADE_MAX_BYTES` and `ATTACHMENT_PER_USER_MAX_BYTES` quotas
- Filename extension vs. content-type matching (`SR-ATT-005`)
- Rejected attempts logged to `security_audit_log` (`SR-ATT-009`)

Hanuman should verify the allowlist values are tight and that there is no bypass path at the HTTP router layer.

### Finding 3 — S3Storage: not wired, StubStorage hardcoded in router

**Status: NOT IMPLEMENTED — Bhima action required**

`StubStorage` is imported and instantiated directly in `backend/src/tradeforge/api/v1/journal.py:29` and `journal.py:73`. No `S3Storage` class exists. The storage port protocol exists in `backend/src/tradeforge/application/journal/storage.py`.

### Finding 4 — Dependency scanning: pip-audit not in CI

**Status: NOT IMPLEMENTED — Nakula action required**

The GitHub Actions workflow at `.github/workflows/ci.yml` has no dependency scanning step. `pip-audit` or `safety` must be added.

### Finding 5 — Settings: kms_key_arn is a required field but KMS is deferred to Phase 2

**Status: DEFECT — Bhima action required**

`backend/src/tradeforge/settings.py:33` declares `kms_key_arn: str` with no default. KMS was deferred to Phase 2 (Phase 1 uses CSV import only — broker credentials are not stored). This field will cause a startup failure in production unless the env var is set to a dummy value, or the field is made optional.

Bhima must make `kms_key_arn` optional (`str = ""`) and remove the `kms_endpoint_url` requirement from production settings. Hanuman to confirm this is acceptable given the KMS-defer decision.

### Finding 6 — Secret rotation: all secrets are env-var sourced (no hardcoded secrets found)

**Status: CONFIRMED — Hanuman to do final sweep**

All security-sensitive settings (`secret_key`, `database_url`, `redis_url`, `session signing`) are sourced from environment variables via `Settings`. CI uses clearly-marked dummy values. No hardcoded production secrets were found in the codebase.

Hanuman should perform a final sweep of the full repo (including git history) before sign-off.

---

## Task Breakdown

### S20-1 — Tighten rate-limit thresholds (Bhima)

**File:** `backend/src/tradeforge/infrastructure/repositories/session_repo.py`

Change the constants to match Phase 1 requirements:

| Endpoint group | Constant | Current | Target |
|---|---|---|---|
| register, verify-email | `IP_ATTEMPT_THRESHOLD` (auth_attempts_ip) | 50 | 5 |
| login | (login_attempts_ip counter) | 50 | 5 |
| password-reset/request, /confirm | (auth_attempts_ip counter, shared) | 50 | 3 |

**Problem:** The same `IP_ATTEMPT_THRESHOLD` constant is used for both auth_attempts (register/verify/reset) and login. Password-reset requires a stricter limit (3/min) than register/login (5/min). The two counter keys (`auth_attempts_ip` vs `login_attempts_ip`) suggest a separation of concerns exists — but both use the same threshold constant.

**Bhima must either:**
- Introduce a separate `IP_RESET_ATTEMPT_THRESHOLD = 3` constant and apply it in `auth_service.py` for the `request_password_reset` and `confirm_password_reset` paths, OR
- Accept a shared threshold of 3/min (stricter, simpler, no new constant)

**Hanuman to confirm acceptable approach.** Default recommendation: introduce two constants (`IP_LOGIN_REGISTER_THRESHOLD = 5`, `IP_RESET_THRESHOLD = 3`), apply to the respective service methods.

**Tests required (Bhima):**
- Unit tests verifying that the 6th request within the window raises `RateLimitedError` for login/register
- Unit tests verifying that the 4th request within the window raises `RateLimitedError` for password-reset

### S20-2 — Implement S3Storage (Bhima)

**File:** `backend/src/tradeforge/application/journal/storage.py` (add class), `backend/src/tradeforge/api/v1/journal.py` (wire via factory), `backend/src/tradeforge/settings.py` (add env vars)

**Implementation requirements:**
- New class `S3Storage` implementing `StoragePort` using `aioboto3` (already in the project for journal presign flows per the `storage.py` docstring)
- `presign_put`: returns a pre-signed S3 PUT URL with `Content-Type` condition + `content-length-range` condition matching declared `byte_size`
- `presign_get`: returns a pre-signed S3 GET URL with `Content-Disposition: attachment` and 1-hour TTL
- `head_object`: returns S3 object metadata dict, or `None` if object does not exist

**Settings additions** (`settings.py`):
```python
# Attachment storage (S3-compatible — Cloudflare R2 in production)
s3_endpoint: str = ""          # empty = AWS; set to R2 endpoint for R2
s3_bucket: str = ""
s3_access_key: str = ""
s3_secret_key: str = ""
s3_region: str = "auto"        # "auto" is correct for Cloudflare R2
```

**Wire in journal router** (`api/v1/journal.py`):
- Replace the hardcoded `StubStorage()` instantiation in `get_journal_service()` with a factory that reads `settings.s3_bucket`:
  - If `s3_bucket` is empty → use `StubStorage` (local dev / CI)
  - If `s3_bucket` is set → use `S3Storage` (production)

**Explicitly NOT in S20-2:**
- S3 bucket policy configuration (Nakula owns in Step I-1)
- S3 lifecycle rules for PENDING-tagged objects (Nakula owns in Step I-1)

**Tests required (Bhima):**
- Unit tests for `S3Storage` using `moto` or `pytest-mock` (mock the aioboto3 client)
- Integration test confirming `StubStorage` is used when `s3_bucket` is empty
- Integration test confirming `S3Storage` is instantiated when `s3_bucket` is set

### S20-3 — Fix kms_key_arn required field (Bhima)

**File:** `backend/src/tradeforge/settings.py`

Change:
```python
kms_key_arn: str
kms_endpoint_url: str = ""
```
To:
```python
kms_key_arn: str = ""          # Phase 2 — broker credential KMS; empty in Phase 1
kms_endpoint_url: str = ""
```

Also update the `.github/workflows/ci.yml` `KMS_KEY_ARN` env var — it is already set to a dummy value. Remove or document that it is no longer required at startup.

**No new tests required** — existing CI already works; making the field optional removes a fragility, not a feature.

### S20-4 — Add pip-audit to GitHub Actions CI (Nakula)

**File:** `.github/workflows/ci.yml`

Add a new job (or a step in the `backend` job) that runs `pip-audit` after the dependency install step:

```yaml
- name: Dependency audit (pip-audit)
  working-directory: backend
  run: pip-audit --requirement <(pip freeze) --ignore-vuln GHSA-xxxx-xxxx-xxxx
  # Fail on high/critical CVEs. Add ignore entries for accepted low/medium CVEs.
```

**Specification:**
- Fail the CI job on any HIGH or CRITICAL CVE
- MEDIUM and LOW: report only, do not fail (configurable — Hanuman to confirm threshold)
- Add `pip-audit` to `backend/pyproject.toml` dev dependencies so it is installed by `pip install -e ".[dev]"`

**Note for Nakula:** `pip-audit` supports a `--format=json` flag for machine-readable output and `--ignore-vuln` for accepted exceptions. Start with fail-on-critical only to avoid blocking CI on irrelevant transitive dependency churn.

### S20-5 — Hanuman security sweep and sign-off

Hanuman performs a final security review before Step I-3. This is not an implementation task — it is a gate.

**Hanuman must verify:**

| Item | Verification |
|------|-------------|
| Rate-limit thresholds (S20-1) | Confirm reduced thresholds are implemented and tested |
| File upload allowlist | Confirm `ALLOWED_CONTENT_TYPES` values are tight (no `application/octet-stream` catch-all) |
| Upload bypass paths | Confirm there is no router-layer bypass of `JournalService` validation |
| S3Storage wiring (S20-2) | Confirm production does not fall back to `StubStorage` when env vars are set |
| Secret sourcing | Final repo sweep for hardcoded secrets (source + git history) |
| CORS config | Confirm `ALLOWED_ORIGINS` has no wildcards in production |
| Cookie flags | Confirm `SECURE_COOKIES=true` is enforced in production settings (cannot deploy with `false`) |
| KMS deferral (S20-3) | Confirm no broker credentials are stored in Phase 1 and that the absence of KMS is acceptable |
| CI audit (S20-4) | Confirm `pip-audit` step fails appropriately on critical CVEs |
| R-7 accepted risk | Confirm ADR is written documenting PostgreSQL RLS absence as accepted risk for Phase 1 |

**Deliverable:** Hanuman written sign-off (a comment in the PR or a signed-off finding document). No gaps beyond accepted risks may remain open.

---

## What Is NOT in Step 20

The following are explicitly deferred. Do not implement, suggest, or scope during Step 20.

- MFA / 2FA (Phase 3)
- PostgreSQL Row-Level Security — accepted risk R-7, documented in Phase 1 risk register
- Malware scanning on attachments (Phase 2)
- Penetration testing (Phase 2)
- Broker credential KMS — deferred to Phase 2; no broker credentials stored in Phase 1
- slowapi middleware — the existing Redis-based rate limiting is the implementation; Hanuman to confirm it meets the requirement without the slowapi dependency

---

## Order of Work

```
Day 1
  Bhima: S20-3 (kms_key_arn fix — trivial, unblocks CI safety)
  Bhima: S20-1 (rate-limit threshold tightening + tests)
  Nakula: S20-4 (pip-audit CI step)

Day 1–2
  Bhima: S20-2 (S3Storage implementation + wiring + tests)

Day 2
  Hanuman: S20-5 (security sweep + sign-off — requires S20-1, S20-2, S20-3, S20-4 complete)
```

S20-1, S20-3, and S20-4 are independent and can run in parallel.  
S20-2 can run in parallel with S20-1, S20-3, and S20-4.  
S20-5 is blocked on all of S20-1 through S20-4 complete.

---

## Acceptance Criteria

Step 20 is DONE when:

- [ ] S20-1: Rate limits in `session_repo.py` are ≤5/min for login/register and ≤3/min for password-reset. New threshold unit tests pass. CI GREEN.
- [ ] S20-2: `S3Storage` class implemented and wired. `StubStorage` used when `s3_bucket` is empty. `S3Storage` used when env vars are set. Unit tests pass using mocked aioboto3. CI GREEN.
- [ ] S20-3: `kms_key_arn` has a default of `""`. CI no longer requires the `KMS_KEY_ARN` dummy env var to start the application. CI GREEN.
- [ ] S20-4: `pip-audit` runs in GitHub Actions. No HIGH or CRITICAL CVEs in the current dependency set. CI GREEN.
- [ ] S20-5: Hanuman written sign-off with no open HIGH or CRITICAL findings.

**Gate:** Hanuman sign-off → Nakula executes Step I-3 (production deployment).

---

## Risk Register (Step 20)

| # | Risk | Likelihood | Impact | Owner | Mitigation |
|---|------|-----------|--------|-------|-----------|
| R-20-1 | `aioboto3` not in `pyproject.toml` — `S3Storage` cannot import | Medium | Medium | Bhima | Check pyproject.toml before writing S3Storage; add if missing |
| R-20-2 | pip-audit finds a CVE in a transitive dependency with no patch | Medium | Medium | Nakula | Use `--ignore-vuln` for accepted entries; Hanuman approves each exception |
| R-20-3 | Tightening rate limits breaks a legitimate test that fires > 5 requests | Medium | Low | Bhima | Review test fixtures; mock the Redis counter in fast-firing tests |
| R-20-4 | Hanuman sign-off blocked waiting on S20-2 (S3Storage) | Low | High | Bhima | Prioritise S20-3 and S20-1 first; start S20-2 concurrently, not after |

---

## Document Maintenance

Update this document as tasks complete. When all acceptance criteria are met:

1. Mark Step 20 ✅ in `PHASE-1-MVP-EXECUTION-PLAN.md` with acceptance date
2. Update the Phase 1 completion checklist

**Owner:** Krishna  
**Review:** At the start of each implementation session

---

*Krishna — Senior Project Manager*  
*Codebase audit date: 2026-09-10*  
*Base branch: `main` at `8d7ca66` (PR #13 merged — Step 19 Trade List + Detail)*
