# Step 20 — Security Hardening (Pre-Deployment Gate)

**Document:** `docs/project-status/STEP-20-EXECUTION-PLAN.md`  
**Author:** Krishna (Project Manager)  
**Date:** 2026-09-10 (revised 2026-09-10 — Mayasura architectural review applied; revised 2026-09-10 — Dhanvantari risk review applied; revised 2026-09-10 — Sahadeva QA review applied)  
**Branch:** `feat/step-20-security-hardening` (base: `main` at `8d7ca66` — PR #13 merged)  
**Phase 1 plan ref:** `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md` §Step 20  
**Gate:** Hanuman sign-off required before Step I-3 (production deployment)

---

## Review Log

| Date | Reviewer | Findings | Status |
|------|----------|----------|--------|
| 2026-09-10 | Mayasura (Architecture) | A-20-1 (BLOCKING), A-20-2 (BLOCKING), A-20-3 (REQUIRED), A-20-4 (REQUIRED), A-20-5 (REQUIRED) | ✅ All applied — plan revised |
| 2026-09-10 | Dhanvantari (Risk) | D-20-1 (BLOCKING), D-20-2 (REQUIRED), D-20-3 (REQUIRED), D-20-4 (REQUIRED) | ✅ All applied — plan revised |
| 2026-09-10 | Sahadeva (QA) | QA-S20-01 (BLOCKER — StubStorage.delete_object missing), Advisory 1 (AttachmentSizeLimitError location), Advisory 2 (KMS CI env var owner) | ✅ All resolved — plan revised |

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

### Finding 1 — Rate limiting: infrastructure exists, threshold is too permissive, and counter key sharing blocks different limits per group

**Status: GAP — Bhima action required (A-20-1 BLOCKING finding applied)**

The existing implementation in `session_repo.py` uses a Redis-backed fixed-window counter with a 60-second TTL. The current key schema is:
- `auth_attempts_ip:{ip}` — register, verify-email, **and** password-reset share this key (60s window)
- `login_attempts_ip:{ip}` — login only (60s window)

The threshold is `IP_ATTEMPT_THRESHOLD = 50` (`backend/src/tradeforge/infrastructure/repositories/session_repo.py:30`).

**The Phase 1 requirement is 5 req/min for login/register and 3 req/min for password-reset.** The current threshold of 50 is 10× too permissive. This is a real gap.

**Critical architecture constraint (A-20-1):** register, verify-email, and password-reset all increment `auth_attempts_ip:{ip}`. Because they share one counter, it is impossible to apply different threshold constants to different endpoints — all three endpoints see the same counter value. Setting two constants against the same counter has no effect. A normal user flow (register + verify-email = 2 increments on the shared key) would consume two-thirds of a 3/min budget, leaving only 1 slot for password-reset. This breaks legitimate use.

**Resolution (decided, see S20-1):** introduce a dedicated `reset_attempts_ip:{ip}` key used exclusively by password-reset endpoints, with a separate repository method and threshold constant.

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

### S20-1 — Tighten rate-limit thresholds and split counter keys (Bhima)

**Files:**
- `backend/src/tradeforge/infrastructure/repositories/session_repo.py`
- `backend/src/tradeforge/application/auth/service.py`

**Architecture decision (A-20-1 resolution):** register, verify-email, and password-reset cannot all share `auth_attempts_ip:{ip}` if they have different limits. Bhima must introduce a dedicated counter key `reset_attempts_ip:{ip}` for password-reset endpoints. This requires: (1) a new repository method, (2) a new threshold constant, (3) updated service calls.

**Changes to `session_repo.py`:**

| What | Change |
|------|--------|
| Rename `IP_ATTEMPT_THRESHOLD = 50` | → `IP_AUTH_THRESHOLD = 5` (register + verify-email) |
| Add new constant | `IP_RESET_THRESHOLD = 3` (password-reset only) |
| `login_attempts_ip:{ip}` threshold | Apply `IP_AUTH_THRESHOLD = 5` (login — uses existing `increment_ip_attempts`) |
| `auth_attempts_ip:{ip}` threshold | Apply `IP_AUTH_THRESHOLD = 5` (register + verify-email only — no longer includes reset) |
| New: `reset_attempts_ip:{ip}` key | New method `increment_reset_attempts_ip(ip)` — same pipeline pattern as `increment_auth_attempts_ip`, TTL = 60s |

**Changes to `auth_service.py`:**
- `register` and `verify_email` — continue calling `increment_auth_attempts_ip(ip)`, compare against `IP_AUTH_THRESHOLD`
- `request_password_reset` — **switch** the existing `increment_auth_attempts_ip(ip)` call to `increment_reset_attempts_ip(ip)` and compare against `IP_RESET_THRESHOLD` (replaces the existing call at `auth_service.py:323`)
- `confirm_password_reset` — **add a new rate-limit call from scratch**. This function currently has NO rate limiting at all (`auth_service.py:356`). Bhima must add `increment_reset_attempts_ip(ip)` at the top of the function body, compare against `IP_RESET_THRESHOLD`, and raise `RateLimitedError` if exceeded. This is not a switch — it is a new addition.
- Update the imported constant: replace `IP_ATTEMPT_THRESHOLD` with `IP_AUTH_THRESHOLD` and add `IP_RESET_THRESHOLD`

**Key schema after this change:**
```
login_attempts_ip:{ip}   → 60s window, threshold 5  — login
auth_attempts_ip:{ip}    → 60s window, threshold 5  — register, verify-email
reset_attempts_ip:{ip}   → 60s window, threshold 3  — password-reset/request, /confirm
```

**Tests required (Bhima):**
- Unit test: 6th `increment_auth_attempts_ip` call within window → `RateLimitedError` for register/verify-email paths
- Unit test: 4th `increment_reset_attempts_ip` call within window → `RateLimitedError` for `request_password_reset` path
- Unit test: 4th `increment_reset_attempts_ip` call within window → `RateLimitedError` for `confirm_password_reset` path (D-20-1: this function had no rate limiting before S20-1; test proves the new call is present and effective)
- Unit test: hitting reset limit does NOT affect register/verify-email counter, and vice versa (counter isolation)
- Existing auth rate-limit tests must continue to pass; mock call sites for the renamed constant

### S20-2 — Implement S3Storage (Bhima)

**Files:**
- `backend/src/tradeforge/application/journal/storage.py` — add `S3Storage` class; correct `StoragePort.presign_put` docstring
- `backend/src/tradeforge/api/v1/journal.py` — wire storage via factory
- `backend/src/tradeforge/settings.py` — add S3 env vars
- `backend/src/tradeforge/main.py` — add startup credential validation

**boto3 vs aioboto3 decision (A-20-4 resolution):** `aioboto3` is NOT an existing project dependency — `pyproject.toml` declares `boto3>=1.35.0` only. `aioboto3` is a separate package. For Phase 1, presigning is a local CPU-bound signing operation (no network call). `head_object` makes one network call but is not on a latency-critical path. Bhima must use synchronous `boto3` wrapped in `asyncio.get_running_loop().run_in_executor(None, ...)` for all `S3Storage` methods. This requires no new production dependency and is the correct choice for low-frequency attachment operations. Do not add `aioboto3`.

**asyncio API note (D-20-3):** The project requires `python >= 3.12`. `asyncio.get_event_loop()` is deprecated in Python 3.10+ when called in an async context. Bhima must use `asyncio.get_running_loop()` — it raises `RuntimeError` immediately if called outside a running event loop (correct fail-loud behaviour) and is the canonical API since Python 3.7. Do not use `get_event_loop()` anywhere in `S3Storage`.

**presign_put spec correction (A-20-2 resolution):** S3 presigned PUT URLs (`generate_presigned_url('put_object')`) carry no embedded policy document and cannot enforce `content-length-range`. That condition is only available in S3 POST policies (multipart form upload). File size is already enforced at the application layer in `JournalService` (`ATTACHMENT_MAX_BYTES` check before `presign_put` is called). Bhima must NOT attempt to add content-length-range to the presigned PUT URL. Bhima must also correct the `StoragePort.presign_put` docstring (line 9 of `storage.py`) to remove the "Content-Type condition + content-length-range condition" claim — replace it with: "Content-Type is included in the signature; size enforcement is the application layer's responsibility."

**Implementation requirements:**
- New class `S3Storage` implementing `StoragePort` using synchronous `boto3` via `run_in_executor`
- `presign_put(key, content_type, byte_size, ttl_seconds)`: returns a pre-signed S3 PUT URL signed for the given `content_type`. Size is NOT enforced at the S3 layer.
- `presign_get(key, filename, content_type, ttl_seconds)`: returns a pre-signed S3 GET URL with `ResponseContentDisposition: attachment; filename=<filename>` and the given TTL
- `head_object(key)`: calls `S3.head_object` in the executor; returns the metadata dict or `None` if the object does not exist (catch `ClientError` with `Error.Code == '404'`)
- **Post-upload size validation (D-20-4):** S3 presigned PUT URLs carry no embedded size constraint — S3 will accept a PUT with any `Content-Length` on the issued URL. The confirm-upload flow in `JournalService` must call `head_object` and then assert `metadata["ContentLength"] <= ATTACHMENT_MAX_BYTES`. If the uploaded object exceeds the limit, `JournalService` must: (1) call `storage.delete_object(key)` to remove the oversized object, and (2) raise `AttachmentSizeLimitError` (HTTP 422). This requires adding a `delete_object(key) -> None` method to `StoragePort`, `S3Storage`, **and `StubStorage`**. The `JournalService.ATTACHMENT_MAX_BYTES` check at presign time only validates the client-declared size; the post-upload check validates the actual uploaded bytes.
  - `S3Storage.delete_object(key)`: calls `s3_client.delete_object(Bucket=..., Key=key)` in the executor.
  - `StubStorage.delete_object(key)`: no-op — returns without error (matches the existing stub pattern; the stub never stores real objects). Required because `StubStorage` implements `StoragePort` and strict mypy (`pyproject.toml: strict = true`) will reject any concrete class missing a protocol method.
  - `AttachmentSizeLimitError`: define in the journal domain errors module (e.g., `tradeforge/domain/journal/errors.py`), following the existing `tradeforge/domain/auth/errors.py` pattern. Maps to HTTP 422 at the router layer.
- `S3Storage.__init__` accepts `endpoint`, `bucket`, `access_key`, `secret_key`, `region` — all from `Settings`. Creates a `boto3.client('s3', ...)` once at construction time (not per-call).

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
- Replace the hardcoded `StubStorage()` in `get_journal_service()` with a factory that reads `settings.s3_bucket`:
  - If `s3_bucket` is empty → use `StubStorage` (local dev / CI)
  - If `s3_bucket` is set → use `S3Storage(settings)` (production)

**Startup credential validation (A-20-3 resolution):** A deployment where `S3_BUCKET` is set but `S3_ACCESS_KEY` or `S3_SECRET_KEY` are absent will start successfully but fail silently at the first attachment request with a boto3 `NoCredentialsError`. Bhima must add a startup guard in `main.py` using FastAPI's lifespan context (or `@app.on_event("startup")`):

```python
if settings.s3_bucket and not (settings.s3_access_key and settings.s3_secret_key):
    raise ValueError(
        "S3_BUCKET is set but S3_ACCESS_KEY or S3_SECRET_KEY is missing. "
        "All three must be set together, or all three must be empty."
    )
```

This guard must run at application startup, not inside the dependency function.

**Explicitly NOT in S20-2:**
- S3 bucket policy configuration (Nakula owns in Step I-1)
- S3 lifecycle rules for PENDING-tagged objects (Nakula owns in Step I-1)
- Switching to S3 POST policy multipart upload (Phase 2 if ever needed)

**Tests required (Bhima):**
- Unit tests for `S3Storage` using `moto` (mocks the boto3 S3 client at the AWS API layer — preferred over manual mocking for S3)
  - `presign_put` returns a URL; does NOT include a content-length-range condition
  - `presign_get` returns a URL with correct `ResponseContentDisposition`
  - `head_object` returns metadata dict when object exists; returns `None` on 404
  - `delete_object` removes the object from S3 (required for D-20-4 cleanup path)
- Unit test (D-20-4): confirm-upload flow where `head_object` returns `ContentLength > ATTACHMENT_MAX_BYTES` → `delete_object` is called and `AttachmentSizeLimitError` is raised
- Unit test (D-20-4): confirm-upload flow where `ContentLength <= ATTACHMENT_MAX_BYTES` → proceeds normally
- Unit test: startup guard raises `ValueError` when `s3_bucket` is set but credentials are absent
- Unit test: startup guard passes when `s3_bucket` is empty (StubStorage path)
- Unit test: startup guard passes when all three S3 fields are non-empty
- `moto` must be added to `[project.optional-dependencies] dev` in `pyproject.toml` if not already present

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

Also update the `.github/workflows/ci.yml` `KMS_KEY_ARN` env var — it is already set to a dummy value. **Nakula** must add an inline comment beside the `KMS_KEY_ARN` line in `ci.yml` marking it as optional (e.g., `# Optional — KMS deferred to Phase 2; field now defaults to "" in settings.py`). Do not remove the env var; the dummy value is harmless and removal has no benefit.

**No new tests required** — existing CI already works; making the field optional removes a fragility, not a feature.

### S20-4 — Add pip-audit to GitHub Actions CI (Nakula)

**Files:**
- `.github/workflows/ci.yml`
- `backend/pyproject.toml` (add `pip-audit` to dev dependencies)

**Step placement:** The audit step runs in the existing `backend` job, immediately after the `Install backend dependencies` step and before the lint steps. This ensures `pip-audit` itself is installed (via `pip install -e ".[dev]"`) before it is invoked.

**Correct command (A-20-5 resolution):** The bare `pip-audit` command with no arguments scans the currently installed Python environment — which is exactly what we want after `pip install -e ".[dev]"`. Do not use `--requirement <(pip freeze)` (redundant, fragile) and do not include `--ignore-vuln` until an actual CVE exception is needed and Hanuman has approved it.

```yaml
- name: Dependency audit (pip-audit)
  working-directory: backend
  run: pip-audit
```

**Specification:**
- `pip-audit` exits non-zero on any finding by default — this is the correct behavior; it fails CI on any CVE regardless of severity
- If a transitive dependency CVE has no upstream patch and must be accepted, Nakula adds `--ignore-vuln <GHSA-id>` with Hanuman's written approval for each entry. Do not add any `--ignore-vuln` entry at setup time.
- Add `pip-audit` to `[project.optional-dependencies] dev` in `backend/pyproject.toml` so it is installed by the existing `pip install -e ".[dev]"` step

**`pyproject.toml` change:**
```toml
[project.optional-dependencies]
dev = [
    ...
    "pip-audit>=2.7.0",
]
```

### S20-5 — Hanuman security sweep and sign-off

Hanuman performs a final security review before Step I-3. This is not an implementation task — it is a gate.

**Hanuman must verify:**

| Item | Verification |
|------|-------------|
| Rate-limit thresholds (S20-1) | Confirm reduced thresholds are implemented and tested; confirm `confirm_password_reset` now has a rate-limit call |
| Fixed-window double-burst (R-20-7) | Explicitly acknowledge accepted risk: attacker can fire 2× threshold in ~1 second at window boundary; sliding-window deferred to Phase 2 |
| File upload allowlist | Confirm `ALLOWED_CONTENT_TYPES` values are tight (no `application/octet-stream` catch-all) |
| Upload bypass paths | Confirm there is no router-layer bypass of `JournalService` validation |
| S3Storage wiring (S20-2) | Confirm production does not fall back to `StubStorage` when env vars are set; confirm startup guard fires on partial config |
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

- [ ] S20-1: Three separate Redis counter keys exist — `login_attempts_ip`, `auth_attempts_ip`, `reset_attempts_ip` — with thresholds 5, 5, and 3 respectively. `confirm_password_reset` has a rate-limit call (new addition — it had none before S20-1). Counter isolation test passes. Rate-limit test for `confirm_password_reset` path passes. All rate-limit unit tests pass. CI GREEN.
- [ ] S20-2: `S3Storage` class implemented using `boto3` + `asyncio.get_running_loop().run_in_executor()`. `presign_put` docstring corrected (no `content-length-range` claim). `delete_object(key) -> None` added to `StoragePort`, `S3Storage` (calls S3 delete in executor), and `StubStorage` (no-op). `AttachmentSizeLimitError` defined in journal domain errors module. Post-upload confirm flow validates `ContentLength <= ATTACHMENT_MAX_BYTES`; calls `delete_object` and raises `AttachmentSizeLimitError` on violation. Startup guard in `main.py` raises `ValueError` on partial S3 config. `StubStorage` used when `s3_bucket` is empty. `S3Storage` used when all S3 env vars are set. `moto`-based unit tests pass (including oversized-upload case). mypy strict passes. CI GREEN.
- [ ] S20-3: `kms_key_arn` has a default of `""`. Application starts without `KMS_KEY_ARN` env var. CI GREEN.
- [ ] S20-4: `pip-audit` in `pyproject.toml` dev deps. `pip-audit` step in `ci.yml` placed after `Install backend dependencies`. No CVEs in current dependency set. CI GREEN.
- [ ] S20-5: Hanuman written sign-off with no open HIGH or CRITICAL findings.

**Gate:** Hanuman sign-off → Nakula executes Step I-3 (production deployment).

---

## Risk Register (Step 20)

| # | Risk | Likelihood | Impact | Owner | Mitigation |
|---|------|-----------|--------|-------|-----------|
| ~~R-20-1~~ | ~~`aioboto3` not in `pyproject.toml`~~ | — | — | — | RETIRED — plan now uses `boto3` + `run_in_executor`; `boto3` is already a declared dependency |
| R-20-2 | pip-audit finds a CVE in a transitive dependency with no patch | Medium | Medium | Nakula | Raise with Hanuman immediately; add `--ignore-vuln <GHSA-id>` only with Hanuman written approval |
| R-20-3 | Tightening rate limits breaks a legitimate test that fires > 5 requests | Medium | Low | Bhima | Review test fixtures; mock `increment_auth_attempts_ip` / `increment_reset_attempts_ip` in fast-firing tests |
| R-20-4 | Hanuman sign-off blocked waiting on S20-2 (S3Storage) | Low | High | Bhima | Prioritise S20-3 and S20-1 first; start S20-2 concurrently, not after |
| R-20-5 | `moto` not in `pyproject.toml` dev deps — S3Storage unit tests cannot run | Medium | Medium | Bhima | Check `pyproject.toml` before writing tests; add `moto[s3]>=5.0.0` to dev deps if absent |
| R-20-6 | `rename IP_ATTEMPT_THRESHOLD → IP_AUTH_THRESHOLD` breaks existing test imports | Medium | Low | Bhima | Grep for all `IP_ATTEMPT_THRESHOLD` usages in `tests/` before renaming; update all import sites |
| R-20-7 | Fixed-window double-burst: attacker can fire up to 2× threshold in ~1 second by straddling the 60s window boundary (e.g. 5 requests at :59.9 + 5 at :00.1 = 10 in under 1 second) | Low | Medium | Bhima | Accepted for Phase 1. Sliding-window mitigation (Redis sorted sets) deferred. Hanuman must explicitly acknowledge this in S20-5 sign-off. Revisit if abuse pattern emerges post-launch. |

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
