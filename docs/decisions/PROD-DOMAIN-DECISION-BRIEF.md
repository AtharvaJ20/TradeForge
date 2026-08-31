# Production Domain Decision Brief

**Status:** Deferred — decision required before production deployment, not before development
**Author:** Mayasura
**Date:** 2026-08-22
**Decision authority:** Atharva
**Blocking:** Production deployment (CORS), production email (custom sending domain), Phase 3 passkeys (WebAuthn rpId). Does not block local development.
**Inputs from:** ADR-002 (Hanuman, Items 4/8/13), Nakula infrastructure decisions (2026-08-22)
**See also:** LOCAL-DEV-INFRASTRUCTURE.md — local equivalents that allow development to proceed without a production domain

---

## Why This Decision Must Be Made Before Implementation Begins

Three separate systems in TradeForge's Phase 1 architecture require the production domain to be known before they can be correctly configured. Two of those systems (CORS and transactional email) block Phase 1 deployment. One (WebAuthn rpId) blocks Phase 3, but the constraint on it must be documented now because a wrong intermediate choice creates an irreversible user-data problem later.

These are not configuration values that can be filled in at the last moment. They are baked into environment variables, DNS records, and security policies that take time to provision and propagate. They must be decided and committed to before Nakula begins environment setup.

---

## The Decision Required

Atharva must provide two things:

**1. The apex domain (eTLD+1) for TradeForge in production.**

Examples: `tradeforge.in`, `tradeforge.com`, `usetradeforge.in`, `tradeforgeapp.com`.

This is the domain that will appear in the browser address bar, in emails sent to users, and in passkey registration (Phase 3). It must be a domain Atharva owns or will register.

**2. The URL structure: path-based split or subdomain split.**

This governs how the frontend and API are addressed. Two viable options exist (a third is ruled out — see below). Each has different operational and security trade-offs.

---

## URL Structure Options

### Option A — Subdomain Split (Recommended)

```
Frontend:  https://app.{apex-domain}
API:       https://api.{apex-domain}
```

Example with apex domain `tradeforge.in`:
```
Frontend:  https://app.tradeforge.in
API:       https://api.tradeforge.in
```

**What this gives:**
- Frontend and API are deployed and scaled independently. A frontend deploy does not touch the API reverse proxy, and vice versa.
- Both subdomains share the apex domain (`tradeforge.in`). Browser cookie rules treat them as the same "site" (same eTLD+1). ADR-002's `SameSite=Strict` session cookies set by `api.tradeforge.in` are sent on requests to `api.tradeforge.in` initiated from `app.tradeforge.in` — CSRF protection holds.
- CORS is required (different origins despite shared apex), but is straightforward: `ALLOWED_ORIGINS = https://app.{apex-domain}`.
- WebAuthn rpId = `{apex-domain}`. Passkeys registered to the apex domain are valid on any subdomain. Users who register a passkey on `app.tradeforge.in` can authenticate from any future `*.tradeforge.in` subdomain.
- Clean URL hierarchy for future subdomains: `admin.tradeforge.in`, `docs.tradeforge.in`, etc.

**What this costs:**
- One additional DNS record (CNAME for `app.`) versus Option B.
- CORS configuration is required and must be kept correct as environments multiply.

---

### Option B — Path-Based Split

```
Frontend:  https://{apex-domain}/
API:       https://{apex-domain}/api/
```

Example:
```
Frontend:  https://tradeforge.in/
API:       https://tradeforge.in/api/
```

**What this gives:**
- Frontend and API share the same origin. CORS is not required for first-party browser requests — the browser does not apply cross-origin restrictions when both are on `https://tradeforge.in`. `ALLOWED_ORIGINS` is still configured but not exercised for the web client.
- Operationally simpler: one TLS certificate, one domain to configure, one entry in Resend for email.
- WebAuthn rpId = `{apex-domain}`.

**What this costs:**
- The reverse proxy (Nakula) must route `/api/*` to FastAPI and everything else to the frontend. This couples frontend and API deployments at the routing layer — a config change to API path routing requires a reverse proxy change that affects both.
- Cannot independently rate-limit, monitor, or apply WAF rules to the API origin vs. the frontend origin at the CDN level.
- If the API is ever extracted to a separate host (Phase 3 AI service, mobile API), the path routing architecture must be revisited.

---

### Option C — Separate Apex Domains (Ruled Out)

```
Frontend:  https://{domain-A}
API:       https://{domain-B}
```

This option is architecturally incompatible with ADR-002 and is not a viable choice.

**Why it is ruled out:**
- `SameSite=Strict` cookies: when the frontend and API are on different apex domains (different eTLD+1), the browser classifies requests from the frontend to the API as cross-site. `SameSite=Strict` cookies are not sent on cross-site requests. The session cookie never reaches the API. Every authenticated request fails with 401. The entire session architecture in ADR-002 is predicated on frontend and API sharing an apex domain.
- WebAuthn rpId: a passkey registered to one apex domain cannot be used from the other. There is no cross-domain passkey inheritance.

This option requires redesigning the session architecture before it can work. It is not a trade-off — it is a constraint violation.

---

## Downstream Impact by System

### 1. CORS (`ALLOWED_ORIGINS`) — Blocks Phase 1

**Source:** ADR-002, CORS Policy section; Hanuman Item 8

The `ALLOWED_ORIGINS` environment variable in the FastAPI application must contain the exact production frontend origin. "Exact" means protocol + hostname + optional port — no wildcards, no trailing slash, no path.

| URL structure | `ALLOWED_ORIGINS` (production) |
|---|---|
| Subdomain split (Option A) | `https://app.{apex-domain}` |
| Path-based split (Option B) | `https://{apex-domain}` |

This value is set in AWS Secrets Manager (Nakula's responsibility) as part of environment configuration. It cannot be `*` with credentials enabled — ADR-002 explicitly prohibits this. It cannot include `localhost` in production.

**Consequence of getting this wrong:** CORS preflight requests from the browser to the API fail. Every POST, PUT, PATCH, DELETE request from the frontend is blocked. The application does not function.

**Consequence of changing it after launch:** The old value must be removed and the new value added atomically. During the transition window, users on cached frontend builds hitting the old origin get CORS errors. This is a user-visible outage.

**What this requires from Atharva:** The production frontend URL. If subdomain split: `app.{your-apex-domain}`. If path-based: `{your-apex-domain}`.

---

### 2. Transactional Email Sending Domain — Blocks Phase 1 production-quality email

**Source:** Nakula infrastructure decisions (2026-08-22); ADR-002 Password and Account Security

TradeForge sends security-critical email: registration verification, password reset, account lock notification, and "account already exists" notification. Deliverability is not optional — if a password reset email goes to spam, the user cannot recover their account.

**Phase 1 (development and staging):** Resend's shared sending domain (`@resend.dev` or similar) is used for initial development. This works for test accounts but is not acceptable for production users — shared sending domains have lower deliverability, no brand recognition, and may be filtered by corporate email gateways.

**Phase 1 (production):** Resend requires DNS records on a domain Atharva owns to send production email. The records are:

| DNS record type | Purpose | Typical value |
|---|---|---|
| TXT on apex domain | SPF — authorises Resend to send on behalf of the domain | `v=spf1 include:amazonses.com ~all` (example) |
| CNAME (×2) | DKIM — cryptographic signing of outgoing email | Provided by Resend at configuration time |
| TXT on `_dmarc.` subdomain | DMARC — policy for handling unauthenticated email | `v=DMARC1; p=quarantine; rua=mailto:...` |

DNS propagation takes up to 48 hours. These records cannot be applied at the moment of launch — they must be configured in advance.

**The "from" address** that users see in their inbox is determined by the domain: `noreply@{apex-domain}` or `noreply@mail.{apex-domain}`. This must be set before any production email is sent, because changing the from-address after launch means users receive email from an unfamiliar address and may mark it as spam.

**What this requires from Atharva:** The apex domain, confirmed as owned (or registered before implementation begins). Nakula configures the DNS records; the domain must exist and be under Atharva's DNS control.

---

### 3. WebAuthn rpId (Passkeys) — Blocks Phase 3, but constraint is permanent

**Source:** ADR-002, WebAuthn / Passkeys section; Hanuman Item 13

WebAuthn passkeys (Phase 3) bind to a "relying party ID" (`rpId`). The `rpId` is the apex domain of the deployment.

```
rpId = {apex-domain}  ← permanent, decided now
```

**Why this is permanent:** When a user registers a passkey, the passkey is cryptographically bound to the `rpId` at registration time. If the `rpId` changes (because the domain changes, or a wrong domain was set in testing), all previously registered passkeys stop working. The user must re-register every passkey on every device. There is no migration path.

**Why it must be decided now (even though passkeys are Phase 3):** The risk is not Phase 3 implementation — it is Phase 1 and Phase 2 environments creating a false precedent. Specifically:

- If a staging environment (`staging.{apex-domain}`) ever enables passkey registration under a different rpId than the apex domain, users who test passkeys in staging will register passkeys that do not work in production.
- If the production domain changes between Phase 1 and Phase 3 (e.g., rebranding from `tradeforgeapp.com` to `tradeforge.in`), all passkeys registered in Phase 3 on the old domain are invalidated.

**The rule from ADR-002:** `rpId` must be set to the apex domain. The apex domain must be the final, stable production domain before Phase 3 begins. No passkey-capable endpoint may be deployed to any environment using the production `rpId` before production itself.

**What this requires from Atharva:** A commitment that the apex domain chosen now is the permanent production domain — not a placeholder, not a "we'll rename it later" choice. If a rebrand is possible, the apex domain decision should be deferred until the name is stable.

---

## Constraint Summary

| System | Constraint | Who it binds | Phase | Reversibility |
|---|---|---|---|---|
| CORS | Frontend origin must be in ALLOWED_ORIGINS before first production request | Nakula (env config), Bhima (FastAPI middleware) | 1 | Reversible but causes user-visible outage during change |
| Email DNS | SPF/DKIM/DMARC records must propagate (up to 48h) before production email is sent | Nakula (DNS config) | 1 | Domain change requires re-verifying DKIM; from-address change causes deliverability regression |
| WebAuthn rpId | Must be apex domain; cannot change after first passkey is registered | Bhima (Phase 3 implementation) | 3 (decide now) | Irreversible — passkey re-registration required if changed |
| SameSite=Strict cookies | Frontend and API must share an apex domain | Bhima (cookie config), Nakula (DNS) | 1 | Domain change requires coordinated migration of all sessions |

---

## What Atharva Must Decide

**Decision 1: Apex domain**

What is the apex domain for TradeForge in production?

- This must be a domain you own or will register before Nakula begins environment setup.
- It will appear in the browser, in user emails, and in passkeys.
- If a rebrand is possible before Phase 3, that is acceptable — but the domain change process must include a WebAuthn passkey migration plan.

**Decision 2: URL structure**

How are the frontend and API addressed?

| Option | Frontend URL | API URL | CORS required? |
|---|---|---|---|
| A — Subdomain split (recommended) | `https://app.{domain}` | `https://api.{domain}` | Yes |
| B — Path-based split | `https://{domain}/` | `https://{domain}/api/` | No (same origin) |

Option C (separate apex domains) is ruled out — it is incompatible with ADR-002's session cookie architecture.

Mayasura's note: Option A is architecturally preferable for independent deployability and future extensibility, but Option B is simpler to operate and is not wrong for a Phase 1 monolith. This is a product and operational preference call, not a pure architecture question — Atharva decides.

---

## What Happens After the Decision

Once Atharva provides the apex domain and URL structure:

1. **Nakula:** registers/confirms domain ownership, provisions DNS, configures CORS env vars in Secrets Manager, configures Resend sending domain with DKIM/SPF/DMARC records, provisions TLS certificates.
2. **Bhima:** sets `ALLOWED_ORIGINS` in application configuration; ensures cookie `Domain` attribute is correct for chosen URL structure.
3. **Arjun:** sets the production API base URL in the frontend build configuration.
4. **ADR-002:** the WebAuthn rpId field can be filled in once the apex domain is confirmed.

None of these actions can begin until the decision is made. The dependency chain runs: domain decision → DNS provisioning → TLS certificates → CORS configuration → Phase 1 deployment.

---

*Mayasura — Senior Software Architect*
*Pending: Atharva's response to the two decisions above*
