# ADR-002: Authentication and Authorization Architecture

**Status:** Accepted
**Author:** Mayasura
**Security authority:** Hanuman
**Decision authority:** Atharva
**Date:** 2026-08-22
**Depends on:** ADR-001 (Python + FastAPI backend, Redis provisioned)
**Binding security inputs:** SR-AUTH-001 through SR-AUTH-021 (Hanuman)
**Resolved decision map:** Hanuman items 1–13 (2026-08-22)

---

## Context

TradeForge requires an authentication and authorization system that secures:

1. User identity (login, registration, session management)
2. Access to trading data (trades, journal, analytics — all user-owned)
3. Broker API credentials (API keys with direct access to live trading accounts)
4. Administrative functions

The security requirements for this system are unusually demanding for an early-stage application because broker credential compromise has immediate, irreversible financial consequences for users. Hanuman's threat analysis (SR-AUTH-001 through SR-AUTH-021) and the 13-item decision map resolution define the constraints. This ADR translates those constraints into an architecture.

The core architectural question is: **self-managed authentication or a managed auth provider?**

Hanuman's resolved constraints collectively answer this question before Mayasura needs to:

- Opaque tokens with instant revocation require Redis-backed server-side session storage. Most managed providers issue JWTs (stateless), not opaque tokens. Instant revocation of JWTs requires a denylist — adding exactly the Redis infrastructure self-managed sessions already require. (Hanuman Item 2)
- Broker credential KMS encryption must be self-managed regardless of auth provider chosen, because no managed auth provider handles application-domain secret encryption. The application must call a cloud KMS directly. (Hanuman Item 1)
- The repository-pattern authorization requirement — mandatory `user_id` filter in every data-fetching query — is application code, not provider configuration. (Hanuman Item 3)
- All 21 SRs are stated as implementation requirements. Delegating auth to a managed provider would require verifying each SR against the provider's behavior and accepting a gap wherever the provider does not support the requirement. Self-management gives direct control over every SR.

**Decision: self-managed authentication within the FastAPI application.**

This is not a preference for complexity. It is the conclusion forced by Hanuman's security constraints and the broker credential architecture. The operational cost (building session management, password hashing, token issuance) is bounded and well-understood. The security benefit (direct control over every SR) is concrete.

---

## Decision

Self-managed authentication and authorization architecture running within the FastAPI application, using PostgreSQL for user credential storage and Redis for session management.

### Component Summary

| Component | Technology | Phase | Hanuman item |
|---|---|---|---|
| Password hashing | Argon2id | 1 | SR-AUTH-001 |
| Session tokens | Opaque (256-bit CSPRNG) | 1 | Item 2 |
| Session store | Redis | 1 | Item 2, 12 |
| Authorization enforcement | Repository pattern + user_id filter | 1 | Item 3 |
| CSRF protection | SameSite=Strict + Origin validation | 1 | Item 4 |
| Registration enumeration | Always-200 + contextual email | 1 | Item 5 |
| Email verification token | 256-bit opaque, SHA-256 stored | 1 | Item 6 |
| Security headers + CSP | Full set, no unsafe-inline | 1 | Item 7 |
| CORS | Origin-specific allowlist | 1 | Item 8 |
| TLS (internal) | sslmode=require on PG + Redis | 1 | Item 9 |
| Audit logging | PostgreSQL write-only table | 1 | Item 10 |
| Audit logging (external) | Log shipping service | 2 | Item 10 |
| Broker credential KMS | Managed cloud KMS (HSM-backed) | 2* | Item 1 |
| App-level secrets | Platform secrets manager | 1 | Item 1 |
| Broker credential schema | Envelope encryption columns | 2* | Item 11 |
| Session revocation | Redis DEL + user index + forced_reauth | 1 | Item 12 |
| MFA / Passkey readiness | Architecture leaves room — not implemented | 3 | Item 13, SR-AUTH-016 |
| WebAuthn rpId | Apex domain — documented now | 3 | Item 13 |
| Row-Level Security (PG) | Backstop authorization layer | 2 | Item 3 |

\* Broker credential KMS is a Phase 2 implementation but must be decided and provisioned now,
  because it determines the broker_connections table schema which cannot be changed after first use.

---

## Architecture

### Trust Boundary Overview

```
┌─────────────────────────────────────────────────────────────┐
│  INTERNET                                                   │
│                                                             │
│  [Browser / Mobile]                                         │
│       │                                                     │
│       │ HTTPS (TLS 1.2+ enforced at reverse proxy)         │
│       ↓                                                     │
├──────────────────────────────────────── TB-1 ───────────────┤
│  APPLICATION PERIMETER                                      │
│                                                             │
│  [Reverse Proxy / CDN]                                      │
│    Security headers, HSTS, rate limiting                    │
│       │                                                     │
│       ↓                                                     │
│  [FastAPI Application]                                      │
│    ├── Auth Router    (/auth/*)                             │
│    ├── API Router     (/v1/*)    ← session verified here    │
│    └── Auth Middleware           ← session lookup in Redis  │
│       │               │                                     │
├───────│───────────────│──────────── TB-2 ───────────────────┤
│       │               │                                     │
│  [Redis]          [PostgreSQL]                              │
│  Session store    ├── users                                 │
│  Rate limit       ├── sessions (backup reference)          │
│  forced_reauth    ├── broker_connections (encrypted)        │
│                   ├── security_audit_log (write-only)       │
│                   └── pending_email_verifications           │
├──────────────────────────────────── TB-3 ───────────────────┤
│  EXTERNAL                                                   │
│                                                             │
│  [Cloud KMS]          [Broker APIs]                        │
│  KEK storage          Zerodha / Upstox / Angel One         │
│  DEK wrap/unwrap                                            │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow: Authentication

```
Login Request
     │
     ▼
[FastAPI /auth/login]
     │
     ├── Rate limit check (Redis) ──── exceeded? → 429 + lock account
     │
     ├── Load user by email (PostgreSQL)
     │       not found? → same response as wrong password (no enumeration)
     │
     ├── Verify password (Argon2id)
     │       failed? → increment failure counter (Redis) → log LOGIN_FAILURE
     │
     ├── Generate session token (256-bit CSPRNG)
     │
     ├── Store session in Redis
     │       Key:   sessions:{session_token}
     │       Value: {user_id, issued_at, expires_at, ip, ua_hash}
     │       TTL:   30 days
     │
     ├── Add to user session index
     │       SADD user_sessions:{user_id} {session_token}
     │
     ├── Write LOGIN_SUCCESS to security_audit_log
     │
     └── Return: session token in HttpOnly Secure SameSite=Strict cookie
                 + user profile in response body
```

### Data Flow: Authenticated Request

```
API Request (cookie present)
     │
     ▼
[FastAPI Auth Middleware]
     │
     ├── Extract session token from cookie
     │
     ├── GET sessions:{session_token} from Redis
     │       missing or expired? → 401
     │
     ├── Check forced_reauth:{user_id} in Redis
     │       present? → 401 (force re-authentication)
     │
     ├── Attach user_id to request context
     │
     └── Pass to route handler
           │
           ▼
     [Route Handler]
           │
           └── [Service Layer]
                 │
                 └── [Repository]
                       │
                       ├── Query ALWAYS includes:
                       │   WHERE resource.user_id = :authenticated_user_id
                       │   (user_id from request context — never from request body)
                       │
                       └── Return data or 404 if not found for this user
```

### Data Flow: Session Revocation

```
Logout
  ├── DEL sessions:{session_token}
  ├── SREM user_sessions:{user_id} {session_token}
  ├── Expire session cookie (Set-Cookie with past date)
  └── Log SESSION_INVALIDATED

Admin-forced logout (suspected compromise)
  ├── SMEMBERS user_sessions:{user_id}  → list all session tokens
  ├── DEL sessions:{token} for each token
  ├── DEL user_sessions:{user_id}
  ├── SET forced_reauth:{user_id} = 1  EX 86400  (24-hour block)
  └── Log ADMIN_FORCED_LOGOUT

Password change
  └── Triggers admin-forced logout flow (all sessions revoked)
```

---

## Session Architecture

**Source:** Hanuman Items 2 and 12, SR-AUTH-005, SR-AUTH-006

### Token Properties

| Property | Value |
|---|---|
| Token type | Opaque (not JWT) |
| Entropy | 256 bits from `secrets.token_hex(32)` (Python stdlib) |
| Session TTL | 30 days (absolute, not rolling) |
| Storage | Redis primary; no persistent cookie of the token itself |
| Cookie flags | HttpOnly, Secure, SameSite=Strict |
| Cookie path | `/` (full application — not scoped to refresh endpoint because there is no separate refresh endpoint in the opaque token model) |

### Why Opaque Tokens, Not JWTs

JWTs are stateless and cannot be revoked within their lifetime without a denylist — which requires Redis. Adding a Redis denylist for JWTs introduces exactly the same infrastructure as opaque sessions, with the additional complexity of JWT verification and the additional attack surface of algorithm confusion (SR-AUTH-015). With opaque tokens and Redis sessions, revocation is a single Redis DEL — effective on the next request. For a financial application handling broker credentials, this is the correct posture. (Hanuman Item 2)

### Session Failure Mode

If Redis is unavailable:
- All authenticated requests return 503 (Service Unavailable)
- The application does not fall back to an in-memory session cache or JWT verification
- This is intentional fail-closed behavior (SR-AUTH-021, Rule D)
- Redis must be provisioned as a high-availability instance (Nakula responsibility)

### `forced_reauth` Control

A Redis key `forced_reauth:{user_id}` with 24-hour TTL. Set by admin-forced logout or password change. While present, any new session creation for that user requires email confirmation before the session is issued. The check occurs at session issuance — not at every request (to avoid Redis overhead). (Hanuman Item 12)

### `user_sessions` Set — Stale Member Cleanup

When a session expires naturally via its Redis TTL, `sessions:{session_token}` is deleted automatically. However, the corresponding member in `user_sessions:{user_id}` (a Redis Set) is not automatically removed. Over time, the Set accumulates references to expired session tokens. Left unmanaged, this causes two problems: (1) unbounded memory growth for active users; (2) unnecessary DEL calls during bulk revocation.

**Cleanup strategy:** On every successful login, after the new session is created:

```
SMEMBERS user_sessions:{user_id}
  → for each token: EXISTS sessions:{token}
  → if not exists: SREM user_sessions:{user_id} {token}
```

This piggybacks cleanup on the login event — the only moment all existing session tokens for a user are guaranteed to be enumerated. It adds O(n) EXISTS checks where n is the number of prior sessions (typically small). No separate background cleanup job is required.

An alternative using a Redis Sorted Set (with `expires_at` as the score) would allow range deletion of expired members in O(log n) via `ZREMRANGEBYSCORE`. This is the preferred migration if the Set approach produces observable Redis overhead at scale. Bhima selects the implementation; this note documents both options.

---

## Authorization Architecture

**Source:** Hanuman Item 3, SR-AUTH-008, SR-AUTH-009, SR-AUTH-010, SR-AUTH-021

### Repository Pattern — Structural Enforcement

Every data-fetching infrastructure method that returns user-owned data must:

1. Accept `user_id: UUID` as a **non-optional** typed parameter
2. Include the ownership filter directly in the SQL query (not as a post-retrieval check)
3. Return `None` or an empty result — never raise an authorization exception that leaks resource existence to the wrong user

```
Correct pattern (ownership filter in query):
  SELECT * FROM trades
  WHERE id = :trade_id
  AND user_id = :authenticated_user_id    ← ownership in the query

Incorrect pattern (post-retrieval check):
  trade = SELECT * FROM trades WHERE id = :trade_id
  if trade.user_id != current_user.id: raise 403   ← data already fetched
```

The incorrect pattern is prohibited by code review. A PR that introduces it is rejected. (SR-AUTH-021 Rule A)

### Dependency Directions for Authorization

```
FastAPI Route Handler
  → extracts user_id from request context (set by Auth Middleware)
  → calls Application Service with user_id
      → calls Repository method with user_id
          → SQL query includes user_id filter
```

`user_id` flows down from the verified session — it never originates from the request body, query parameters, or URL path. (SR-AUTH-021 Rule E)

### Admin Endpoints

All routes under `/v1/admin/*` carry an additional `require_admin` dependency that verifies the `is_admin` flag on the user record (fetched fresh from PostgreSQL — not from the session payload). (SR-AUTH-021 Rule C)

### Phase 2: PostgreSQL Row-Level Security

PostgreSQL RLS policies will be introduced in Phase 2 as a database-level backstop. The application sets `SET LOCAL app.current_user_id = :user_id` per transaction. RLS policies enforce that queries on user-owned tables only return rows matching this variable.

RLS is a secondary control — it does not replace the repository pattern. It catches application-layer mistakes that slip through code review. RLS policy definitions must be reviewed by Hanuman before enabling. (Hanuman Item 3)

---

## Credential and Secret Architecture

### Two-Tier Secret Management

**Source:** Hanuman Item 1, SR-AUTH-014

```
Tier 1 — Broker credential Key Encryption Keys (KEKs)
  Storage:   Managed cloud KMS (HSM-backed)
             AWS KMS / GCP Cloud KMS / Azure Key Vault
             (specific provider: Nakula to confirm with cloud platform decision)
  Access:    Application calls KMS WrapKey / UnwrapKey API
             Application never holds KEK material — only a key reference
  Rotation:  KEK rotation re-wraps DEKs; broker credentials (ciphertext) unchanged
  Failure:   KMS unavailable → broker credential retrieval returns 503 (fail-closed)

Tier 2 — Application secrets
  (PostgreSQL URL, Redis URL, email provider key, rate-limit keys)
  Storage:   Platform secrets manager
             (AWS Secrets Manager / GCP Secret Manager / equivalent)
             Injected as environment variables at runtime
             Never in source code, Dockerfiles, or committed config files
  Rotation:  Manual rotation with zero-downtime rolling update
```

### Broker Credential Envelope Encryption

**Source:** Hanuman Items 1 and 11, SR-AUTH-011, SR-AUTH-012, SR-AUTH-013, SR-AUTH-019

```
Encryption path (on broker credential creation):
  1. Generate 256-bit DEK using CSPRNG
  2. Encrypt broker_api_key using AES-256-GCM:
       ciphertext = AES-256-GCM(key=DEK, plaintext=broker_api_key, nonce=random_12_bytes)
  3. Call KMS WrapKey(DEK) → encrypted_dek
  4. Store: encrypted_credential, encrypted_dek, iv_nonce, key_version, encryption_algorithm
       Note: encrypted_credential = ciphertext || authentication_tag (concatenated)
             GCM authentication tag is 16 bytes, appended after the ciphertext.
             Decryption path splits at: len(ciphertext) = len(encrypted_credential) - 16
             No separate column for the authentication tag is required or permitted.
  5. Discard DEK from memory

Decryption path (on broker API call):
  1. Retrieve record from broker_connections
  2. Call KMS UnwrapKey(encrypted_dek) → DEK
  3. Decrypt: AES-256-GCM(key=DEK, ciphertext=encrypted_credential, nonce=iv_nonce)
  4. Use plaintext credential for the immediate request
  5. Discard DEK and plaintext credential from memory
  6. Log BROKER_CREDENTIAL_USED to security_audit_log
```

**broker_connections table — required columns:**

```
broker_connection_id    UUID PRIMARY KEY
user_id                 UUID NOT NULL REFERENCES users(id)
broker_id               UUID NOT NULL REFERENCES brokers(id)
display_name            VARCHAR(100)
credential_type         VARCHAR(32) NOT NULL    -- API_KEY, OAUTH_TOKEN
permission_scope        VARCHAR(32) NOT NULL    -- READ_ONLY, READ_WRITE
status                  VARCHAR(16) NOT NULL    -- ACTIVE, REVOKED, EXPIRED
created_at              TIMESTAMPTZ NOT NULL
last_used_at            TIMESTAMPTZ
revoked_at              TIMESTAMPTZ

-- Envelope encryption (Hanuman SR-AUTH-019)
encrypted_credential    BYTEA NOT NULL
encrypted_dek           BYTEA NOT NULL
encryption_algorithm    VARCHAR(32) NOT NULL    -- AES_256_GCM
key_version             VARCHAR(64) NOT NULL
iv_nonce                BYTEA NOT NULL          -- 12 bytes, unique per encryption
```

`encrypted_credential`, `encrypted_dek`, and `iv_nonce` are never included in any API response. The GET broker connections endpoint returns: `broker_connection_id`, `display_name`, `broker_id`, `permission_scope`, `status`, `created_at`, `last_used_at`, and a masked credential hint (first 4 + last 4 characters only). (SR-AUTH-012)

---

## Password and Account Security

**Source:** SR-AUTH-001, SR-AUTH-002, SR-AUTH-003, SR-AUTH-004, SR-AUTH-007

### Password Hashing

Argon2id with minimum parameters: memory=64MB, iterations=3, parallelism=2.

Passwords are verified and hashed exclusively in the application service layer. No password field — hashed or otherwise — is ever logged, returned in an API response, or passed outside the auth service.

### Password Policy (SR-AUTH-002)

**Length:** Minimum 12 characters. No maximum below 128 characters (a hard ceiling at 128 prevents client-side DoS via pathologically long inputs to Argon2id, without restricting legitimate use).

**Complexity rules:** No mandatory character class requirements (no "must include uppercase, number, symbol" rules). These constraints push users toward predictable patterns such as `Password1!` without improving entropy. Length and breach-check are the enforced controls.

**HIBP breached-password check:** The SHA-1 hash of the candidate password is computed. The first 5 characters (hex prefix) are sent to the Have I Been Pwned k-Anonymity API (`api.pwnedpasswords.com/range/{prefix}`). The response is checked for a suffix match. This ensures the full password and full hash are never transmitted externally.

- **Checked at:** registration (`POST /auth/register`) and password change (`POST /auth/password/change`)
- **On a positive HIBP match:** reject the password with a user-visible message: "This password has appeared in known data breaches — please choose a different one." The user is not told what breaches or how many times.
- **On HIBP API unavailable:** fail open — the password is accepted and a `HIBP_CHECK_FAILED` event is written to `security_audit_log` with the failure reason. Registration and password change must not be blocked by third-party API uptime.
- **HIBP is not checked on login.** Checking on login would require hashing the attempted password before verifying it, which creates a timing side-channel and serves no security purpose (a breached password at login time should trigger a prompt to change, handled separately).

### Brute Force Protection

Per-account and per-IP rate limiting implemented in Redis:

```
Key:   login_failures:{account_email}
TTL:   15 minutes sliding window
Limit: 5 failures → account lock + unlock email sent

Key:   login_attempts_ip:{ip_address}
TTL:   60 seconds
Limit: 50 attempts → IP blocked
```

### Registration — Enumeration Prevention

`POST /auth/register` always returns HTTP 200 regardless of whether the email exists. (SR-AUTH-004, Hanuman Item 5)

- New email: verification email sent
- Existing email: "account already exists" notification sent

Rate limit: maximum 5 registration attempts per IP per hour.

### Email Verification Token

Generated as 256-bit CSPRNG token (64 hex characters). Stored as SHA-256 hash. (Hanuman Item 6)

```
pending_email_verifications
  id              UUID PRIMARY KEY
  email           VARCHAR(255) NOT NULL
  token_hash      VARCHAR(64) NOT NULL   -- SHA-256 of raw token
  expires_at      TIMESTAMPTZ NOT NULL   -- issued_at + 24 hours
  created_at      TIMESTAMPTZ NOT NULL
```

- Single-use: row deleted immediately on successful verification
- Superseded: new verification request deletes all prior rows for the same email
- Rate limit: maximum 3 verification emails per email address per hour

### Session Fixation

A new session token is generated on every successful login. Any session established before login is discarded. (SR-AUTH-007)

### Password Reset (SR-AUTH-004)

Password reset is a distinct flow from email verification and carries higher risk — a predicted or intercepted reset token grants full account takeover without the attacker knowing the current password. It must be specified separately.

**Enumeration prevention:** `POST /auth/password-reset/request` always returns HTTP 200 regardless of whether the email is registered (identical to registration — Item 5 applies to this endpoint). No response field, timing difference, or header reveals whether the email exists.

**Reset token specification:**

| Property | Value |
|---|---|
| Generation | 256-bit CSPRNG (`secrets.token_hex(32)`) |
| Storage | SHA-256 hash only — raw token is never persisted |
| TTL | 1 hour (shorter than email verification — reset tokens are higher risk) |
| Single-use | Row deleted immediately on successful password reset |
| Superseded | New request deletes all prior rows for the same email |
| Rate limit | Maximum 3 reset emails per email address per hour |

**Reset link delivery:** The raw token is embedded in the reset link URL. The link directs the user to a frontend page that immediately submits the token via `POST /auth/password-reset/confirm` (not GET). This prevents the token from being consumed by link prefetchers, browser history sync, or Referer headers on subsequent navigation.

**On successful password reset:**
1. Validate token against stored SHA-256 hash
2. Verify TTL not exceeded
3. Delete the `pending_password_resets` row (single-use enforcement)
4. Hash the new password (Argon2id) and update the `users` record
5. Trigger the admin-forced logout flow: revoke all existing sessions for this user, set `forced_reauth:{user_id}` for 24 hours
6. Log `PASSWORD_RESET_COMPLETED` to `security_audit_log`

Step 5 is required by SR-AUTH-010. A compromised account where the attacker has active sessions must not retain those sessions after the legitimate user resets the password.

**Schema:**

```
pending_password_resets
  id              UUID PRIMARY KEY
  email           VARCHAR(255) NOT NULL
  token_hash      VARCHAR(64) NOT NULL   -- SHA-256 of raw token (hex)
  expires_at      TIMESTAMPTZ NOT NULL   -- issued_at + 1 hour
  created_at      TIMESTAMPTZ NOT NULL
```

---

## CSRF Protection

**Source:** Hanuman Item 4

The session cookie carries `SameSite=Strict`. This is the primary CSRF defense — the browser will not send the cookie on any cross-site request.

Server-side Origin header validation on all state-changing endpoints as defense-in-depth:

```
If Origin header is present in the request:
  If Origin not in ALLOWED_ORIGINS:
    Return 403
    Log CSRF_ATTEMPT to security_audit_log
If Origin header is absent:
  Allow (same-origin browser requests typically omit Origin)
```

`ALLOWED_ORIGINS` is sourced from environment variable. It uses the same allowlist as the CORS policy. (Hanuman Item 4)

---

## Security Headers and CSP

**Source:** Hanuman Item 7

**Applied at reverse proxy / CDN level (Nakula):**

```
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()
```

**Applied by FastAPI middleware on all authenticated API responses (Bhima):**

```
Cache-Control: no-store
```

**Content Security Policy (enforced from first deployment):**

```
Content-Security-Policy:
  default-src 'self';
  script-src 'self';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: blob:;
  font-src 'self';
  connect-src 'self' {API_ORIGIN};
  frame-ancestors 'none';
  form-action 'self';
  base-uri 'self';
  object-src 'none';
```

**`script-src` does not include `'unsafe-inline'` or `'unsafe-eval'`.** (SR-AUTH-005; Hanuman Item 7)

Constraint on Arjun: no inline scripts in HTML. No `eval()`. Bundled Vite output (external JS files) is compliant by default. Any third-party library that requires `unsafe-eval` must be reviewed by Hanuman before adoption.

`Content-Security-Policy-Report-Only` header used during initial development to identify violations before switching to enforcement mode.

---

## CORS Policy

**Source:** Hanuman Item 8

```
ALLOWED_ORIGINS:  environment variable (comma-separated)
                  Production: https://{frontend_domain}
                  Development: http://localhost:5173

Headers:
  Access-Control-Allow-Origin:      {matched origin from allowlist}
  Access-Control-Allow-Credentials: true
  Access-Control-Allow-Methods:     GET, POST, PUT, PATCH, DELETE, OPTIONS
  Access-Control-Allow-Headers:     Content-Type, Authorization, X-Requested-With
  Access-Control-Max-Age:           600
```

Wildcard (`*`) with `allow-credentials: true` is explicitly prohibited and must be rejected in code before it reaches a response header. Production `ALLOWED_ORIGINS` must not include `localhost`. (Hanuman Item 8)

---

## TLS on Internal Connections

**Source:** Hanuman Item 9

| Connection | Requirement |
|---|---|
| Application → PostgreSQL | `sslmode=require` minimum; `sslmode=verify-full` with CA cert if provider supports it |
| Application → Redis | TLS connection string; required if managed Redis provider supports it (all major providers do) |
| Application → Cloud KMS | HTTPS — enforced by the KMS SDK by default |

Connection strings are stored in the platform secrets manager. They are never in source code, `.env` files committed to version control, or Dockerfile layers. (SR-AUTH-014)

---

## Security Audit Logging

**Source:** Hanuman Item 10, SR-AUTH-018

### Phase 1 — PostgreSQL append-only table

```sql
CREATE TABLE security_audit_log (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type   VARCHAR(64) NOT NULL,
  user_id      UUID,
  ip_address   INET NOT NULL,
  user_agent   TEXT,
  event_data   JSONB,
  session_id   UUID,
  occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

The application database role has `INSERT` privilege only on `security_audit_log`. No `UPDATE`, `DELETE`, or `TRUNCATE`. A separate read-only audit role is used for log review. This is enforced at the database permission level — not application code. (Hanuman Item 10)

No secrets, passwords, tokens, or broker credentials may appear in `event_data`. (SR-AUTH-018)

### Events that must be logged (SR-AUTH-018)

```
LOGIN_SUCCESS, LOGIN_FAILURE, ACCOUNT_LOCKED, PASSWORD_RESET_REQUESTED,
PASSWORD_RESET_COMPLETED, PASSWORD_CHANGED, SESSION_INVALIDATED,
ADMIN_FORCED_LOGOUT, BROKER_CREDENTIAL_CREATED, BROKER_CREDENTIAL_REVOKED,
BROKER_CREDENTIAL_USED, REGISTRATION_ATTEMPTED, EMAIL_VERIFIED,
CSRF_ATTEMPT, ADMIN_ACTION
```

### Phase 2 — External log shipping

A log shipping agent (Fluent Bit, Vector, or cloud-native equivalent) ships `security_audit_log` entries to an external SIEM or log service in real time. Enables cross-event correlation (credential stuffing across accounts, geographic anomalies). Nakula owns the log shipping infrastructure.

---

## Future Readiness

**Source:** Hanuman Items 13, SR-AUTH-016, SR-AUTH-017

### MFA (Phase 3)

The session architecture accommodates MFA without redesign. On login, if the user has MFA enabled:

```
Password verified → MFA challenge issued → MFA verified → session issued
                         ↑
               Temporary pre-MFA token in Redis (5-minute TTL)
               Not a full session — cannot access protected resources
```

Supported MFA methods in order of preference: TOTP (RFC 6238), FIDO2/WebAuthn hardware key. SMS OTP is excluded. (SR-AUTH-016)

### OAuth (Phase 3)

OAuth 2.0 / OIDC integration is additive to this architecture. OAuth users are represented as `users` records with `auth_method = OAUTH`. Session issuance (opaque token → Redis) is identical to password-based users after the OAuth callback. The OAuth callback handler must: validate `state` parameter, verify ID token signature against provider JWKS, use `sub` as the stable identifier (not `email`). (SR-AUTH-017)

### WebAuthn / Passkeys (Phase 3)

**`rpId` = apex domain of the production deployment.**

This value is permanent. Changing it after users register passkeys invalidates all existing passkeys. It must be set to the apex domain (eTLD+1) of the final production URL — not a subdomain, not a staging domain, not a development domain. (Hanuman Item 13)

**Action required before Phase 3:** Atharva must confirm the production domain. `rpId` cannot be implemented until the domain is finalized. Nakula must ensure that no passkey-capable endpoint is deployed to any environment other than production until the `rpId` is stable.

---

## Binding Security Requirements

The following Security Requirements are binding on every implementation that falls under this ADR. They are owned by Hanuman and validated by Sahadeva.

| SR | Subject |
|---|---|
| SR-AUTH-001 | Argon2id password hashing |
| SR-AUTH-002 | Password policy + HIBP check |
| SR-AUTH-003 | Brute force protection |
| SR-AUTH-004 | Password reset token security |
| SR-AUTH-005 | Client-side token storage |
| SR-AUTH-006 | Token entropy and lifecycle |
| SR-AUTH-007 | Session fixation prevention |
| SR-AUTH-008 | Service-layer authorization |
| SR-AUTH-009 | Multi-account data isolation |
| SR-AUTH-010 | Permission revocation speed |
| SR-AUTH-011 | Broker credential encryption at rest |
| SR-AUTH-012 | Broker credential handling in code |
| SR-AUTH-013 | Broker credential lifecycle |
| SR-AUTH-014 | Application secrets management |
| SR-AUTH-015 | N/A — JWT algorithm constraints (not applicable; JWTs not used) |
| SR-AUTH-016 | MFA architecture readiness |
| SR-AUTH-017 | OAuth architecture readiness |
| SR-AUTH-018 | Security audit logging |
| SR-AUTH-019 | Broker credential KMS key management |
| SR-AUTH-020 | Token storage and transmission |
| SR-AUTH-021 | Service-layer authorization enforcement |

SR-AUTH-015 (JWT algorithm rules) is not applicable because this architecture uses opaque tokens, not JWTs. The requirement is retained as a named item in case JWTs are introduced in a future ADR.

---

## Consequences

### What Becomes Easier

- **Instant revocation:** a Redis DEL takes effect on the next request — no 15-minute JWT window. Forced logout, suspected compromise response, and password-change session invalidation are all immediate.
- **Full SR compliance:** every SR is directly implementable in application code. No per-SR gap analysis against a managed provider's behavior.
- **Broker credential security:** KMS envelope encryption is self-contained. No dependency on an auth provider to support a non-standard credential storage requirement.
- **Audit log fidelity:** every security event is under application control. The log captures exactly what is needed and nothing it should not contain.
- **Horizontal scaling:** opaque sessions in Redis mean the application is stateless at the process level. Multiple FastAPI worker processes share the same Redis session store with no sticky-session requirement.

### What Becomes Harder

- **More code to own and maintain:** password hashing, token generation, session management, email verification, rate limiting — all must be built and maintained. A managed auth provider would abstract these.
- **Email delivery dependency:** transactional email (registration, verification, account lock, password reset) is required from the first deployment. Nakula must provision a transactional email service before any auth flow is complete.
- **Redis is a critical-path dependency:** every authenticated request requires a Redis lookup. Redis availability is now directly tied to application availability for all authenticated users. Redis must be provisioned as a high-availability instance.
- **KMS adds latency to broker credential retrieval:** one KMS API call per broker credential access. At TradeForge's scale this is negligible (single-digit milliseconds), but it is a new external dependency for every broker API call.
- **MFA and OAuth require additional implementation work in Phase 3:** the architecture supports both, but neither is built. They are additive, not structural changes.

### Technical Debt Accepted

- **SR-AUTH-015 is deferred** as not applicable. If JWTs are introduced in a future feature (e.g., a public API, a mobile SDK), a new ADR must be written that brings SR-AUTH-015 back into scope.
- **PostgreSQL RLS is Phase 2.** The repository pattern is the Phase 1 authorization backstop. A missed ownership filter in Phase 1 is an application bug without the RLS safety net. Hanuman code review on every data-fetching endpoint mitigates this risk until Phase 2.
- **External audit log shipping is Phase 2.** Phase 1 audit logs are in PostgreSQL only. Cross-event correlation (e.g., detecting credential stuffing across multiple accounts) requires a SIEM and is not available until Phase 2.

### Must Monitor

- Redis latency and availability: the critical-path dependency for all authenticated sessions
- Failed login rate per account and per IP: primary indicator of credential stuffing attacks
- KMS call latency: degradation indicates broker credential retrieval is affected before users report it
- Audit log write failures: if the application cannot write to `security_audit_log`, security events are lost silently — alert on write errors

---

## Assumptions

1. The cloud hosting provider (AWS, GCP, or Azure) is selected by Nakula before the KMS is provisioned. The KMS tier of this architecture is cloud-provider-specific. This is an open dependency.
2. Redis is available as a managed, high-availability service from the chosen cloud provider (ElastiCache, Cloud Memorystore, Azure Cache for Redis, Upstash). Self-hosted Redis is not assumed.
3. A transactional email provider (Resend, Postmark, AWS SES, or equivalent) is provisioned before any auth endpoint is deployed. The registration, verification, account lock, and password reset flows all require email delivery.
4. The production domain is known and stable before Phase 3 passkey implementation. If the domain is not yet final, passkeys cannot be implemented — not just not deployed.
5. Python's `secrets` module (stdlib) is used for all CSPRNG token generation. No third-party randomness library is required or permitted in the auth flow.

---

## Open Items — Must Be Resolved Before Implementation

| Item | Decision needed | Owner | Blocks |
|---|---|---|---|
| Cloud provider selection | AWS / GCP / Azure | Nakula | KMS provisioning |
| KMS provisioning | AWS KMS / GCP Cloud KMS / Azure Key Vault | Nakula | Broker credential schema |
| Transactional email provider | Resend / Postmark / SES / other | Nakula | Auth flow deployment |
| Production domain | Final apex domain for rpId | Atharva | Phase 3 passkey work |
| Redis high-availability tier | Managed HA Redis instance | Nakula | All authenticated requests |

---

## References

- ADR-001: Backend Framework (Python + FastAPI) — accepted 2026-08-22
- Hanuman Security Requirements: SR-AUTH-001 through SR-AUTH-021
- Hanuman Decision Map Resolution: Items 1–13 (2026-08-22)
- Kubera Decimal Usage Standard — accepted 2026-08-22
- Ganesha Domain Rules: Trade Matching and Classification (2026-08-22)

---

*Mayasura — Senior Software Architect*
*ADR-002 status: Accepted 2026-08-22*
*Approved by: Atharva*
*Security review: Hanuman (cleared 2026-08-22, revision 2)*
