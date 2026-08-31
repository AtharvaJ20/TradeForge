# Local Development Infrastructure

**Status:** Active — governs all development environments until production deployment
**Author:** Mayasura / Nakula
**Date:** 2026-08-22
**Constraint:** Zero-cost / local-first development. No paid cloud infrastructure during development.
**Relationship to production decisions:** This document defines local equivalents. It does not change the production architecture. Nakula's five production infrastructure decisions (2026-08-22) remain the deployment target.

---

## Constraint Statement

TradeForge will be developed under a zero-cost, local-first infrastructure constraint for the foreseeable future. No paid cloud services, no production domain, no managed cloud infrastructure are required during development.

**What this changes:** the environment each service runs in during development.
**What this does not change:** any ADR, any security requirement, any production deployment target, any data model, any calculation standard.

When TradeForge is ready to deploy, the production infrastructure decisions (AWS, RDS, ElastiCache, AWS KMS, Resend) are applied. The application code does not change — only environment variables.

---

## Service Mapping

| Production target | Local equivalent | Code path change? |
|---|---|---|
| RDS PostgreSQL (Multi-AZ, db.t4g.small) | Docker: `postgres:16-alpine` | None — same asyncpg driver, same SQLAlchemy config |
| ElastiCache Redis (Multi-AZ, cache.t4g.small) | Docker: `redis:7-alpine` | None — same redis-py client, same key schema |
| AWS KMS CMK (HSM-backed, ap-south-1) | LocalStack KMS (Docker) | None — boto3 pointed at localhost instead of AWS |
| AWS Secrets Manager | `.env` file (gitignored) | None — env vars are env vars regardless of source |
| Resend (transactional email) | Mailpit (Docker, local SMTP capture) | Minimal — SMTP transport locally, HTTP API in production |

**The design principle:** every service is accessed through an environment variable. Switching from local to production is a config change, not a code change. No `if ENV == 'development'` branches in application logic.

---

## Local Service Definitions

### PostgreSQL

- **Image:** `postgres:16-alpine`
- **Port:** `5432` (local only — not exposed beyond localhost)
- **Version rationale:** matches the PostgreSQL 16 engine on RDS production target. Schema, index syntax, and behaviour are identical.
- **Local configuration:**
  - Username: `postgres`, Password: `postgres` (local only, never in production)
  - Database: `tradeforge_dev`
  - No TLS required locally (TLS is enforced by `sslmode=require` in production via RDS parameter group)
- **Persistence:** Docker named volume (`tradeforge_postgres_data`) so data survives container restarts
- **Migrations:** Alembic runs as `tradeforge_app` (via `DATABASE_URL` in `.env`). Same migration files run against local PostgreSQL and production RDS — same connection string pattern, same driver.

#### What `docker compose up` provisions automatically

`docker/postgres/init.sql` runs once on first container start, executed as the `postgres` superuser by the Docker entrypoint. It handles everything that requires superuser and must be in place before Alembic migrations run:

| What | Why | Who can do it |
|---|---|---|
| `CREATE USER tradeforge_app` | Application DB user | superuser only |
| `CREATE USER tradeforge_audit` | Read-only audit log user | superuser only |
| `GRANT CREATE ON SCHEMA public TO tradeforge_app` | PG 15+ revoked this from PUBLIC — Alembic needs it to create tables | superuser only |
| `ALTER DEFAULT PRIVILEGES FOR ROLE postgres … GRANT REFERENCES ON TABLES TO tradeforge_app` | Allows tradeforge_app to declare FK constraints against any table created by the postgres superuser | superuser only |
| `CREATE EXTENSION IF NOT EXISTS btree_gist` | Required by migration 0002's EXCLUSION constraint on `lot_size_history`. **Must be installed before `alembic upgrade head` runs.** | superuser only |

None of these require any manual step. They are idempotent (`IF NOT EXISTS`) and apply on every clean-volume start.

#### PostgreSQL extensions required by migrations

| Extension | Required by | Installed by | Failure mode if absent |
|---|---|---|---|
| `btree_gist` | Migration `0002` — `EXCLUDE USING gist` on `lot_size_history` | `init.sql` (automatic) | `ERROR: data type uuid has no default operator class for access method "gist"` |

In production (RDS), Nakula provisions this extension as a one-time DBA step before the first migration run, not via the application user. The RDS parameter group does not affect extension installation; it requires a superuser `psql` session against the database.

#### First-time setup sequence

```bash
# 1. Start PostgreSQL (init.sql runs automatically — users, privileges, btree_gist)
docker compose up -d postgres

# 2. Run all migrations as tradeforge_app (DATABASE_URL must be set in .env)
cd backend
python -m alembic upgrade head

# 3. Apply post-migration table grants (auth tables from migration 0001 need
#    DML grants; the trade domain tables in migration 0002 grant themselves).
#    Run as the postgres superuser:
docker exec tradeforge-postgres psql -U postgres -d tradeforge_dev -c "
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO tradeforge_app;
REVOKE DELETE, UPDATE, TRUNCATE ON security_audit_log FROM tradeforge_app;
GRANT INSERT ON security_audit_log TO tradeforge_app;
GRANT SELECT ON security_audit_log TO tradeforge_audit;
"
```

Step 3 enforces ADR-002's INSERT-only audit log requirement in local development — not just in production. A local environment that skips this would allow tests to pass that would fail the permission constraint in production.

> **Why step 3 is manual, not automatic:** the `GRANT … ON ALL TABLES` statement is point-in-time — it only grants on tables that exist when the statement runs. At init time, no tables exist. Migration 0002 grants itself on the six new trade domain tables; migration 0001 does not self-grant. The post-migration step covers migration 0001's auth tables.

#### Verifying the provisioned state

After `docker compose up -d postgres` (before running migrations), verify init.sql ran correctly:

```bash
docker exec tradeforge-postgres psql -U postgres -d tradeforge_dev -c "
SELECT extname FROM pg_extension WHERE extname = 'btree_gist';
SELECT has_schema_privilege('tradeforge_app', 'public', 'CREATE') AS can_create_tables;
"
```

Expected output: `btree_gist` row present, `can_create_tables = true`.

---

### Redis

- **Image:** `redis:7-alpine`
- **Port:** `6379` (local only)
- **Version rationale:** matches Redis 7.x on ElastiCache production target.
- **Local configuration:**
  - No AUTH token required locally
  - No TLS required locally
  - No persistence (`--save ""`) — Redis is a session/cache store; local sessions do not need to survive container restarts
- **Fail-closed behaviour preserved locally:** ADR-002 specifies that if Redis is unavailable, all authenticated requests return 503. This behaviour must not be disabled in local development. If `docker compose stop redis` is run, the FastAPI application must return 503 — not fall back to a permissive mode.

---

### KMS (LocalStack)

This is the most important local equivalent to get right. ADR-002 mandates that broker credential encryption uses envelope encryption via a managed KMS. The boto3 SDK calls (`kms.generate_data_key`, `kms.decrypt`) must be exercised in local development — not stubbed, not skipped, not replaced with a different encryption path.

- **Image:** `localstack/localstack:latest`
- **Port:** `4566` (LocalStack gateway — all AWS services on one port)
- **Services enabled:** `KMS` only (no other LocalStack services needed)
- **What LocalStack KMS provides:** A local AWS KMS API that accepts the same boto3 calls as real AWS KMS. The local key is not HSM-backed (obviously), but the code path — `generate_data_key` → encrypt → store encrypted DEK → `decrypt` → decrypt credential — runs identically.

**Local KMS initialisation** (must run once after LocalStack starts, before the application starts):

```bash
# Create the local CMK (run via docker exec or init script)
aws --endpoint-url=http://localhost:4566 \
    --region ap-south-1 \
    kms create-key \
    --description "TradeForge broker credentials key (local dev)" \
    --key-usage ENCRYPT_DECRYPT \
    --key-spec SYMMETRIC_DEFAULT

# The Key ARN from this output goes into .env as KMS_KEY_ARN
```

This initialisation step must be documented in the project README and automated in the Docker Compose setup via a one-time init container or a `docker compose up --profile init` profile. Bhima must not manually create keys on each dev environment setup.

**Environment variable that switches KMS between local and production:**

```
KMS_ENDPOINT_URL=http://localhost:4566   # local (LocalStack)
KMS_ENDPOINT_URL=                        # production (omit; boto3 uses AWS default endpoint)

KMS_KEY_ARN=arn:aws:kms:ap-south-1:000000000000:key/{local-key-id}  # local
KMS_KEY_ARN=arn:aws:kms:ap-south-1:{real-account}:key/{real-key-id}  # production
```

The boto3 client is initialised with `endpoint_url=os.environ.get('KMS_ENDPOINT_URL')`. When `KMS_ENDPOINT_URL` is empty, boto3 uses the real AWS endpoint. No code branch.

**Security note for local development:** The LocalStack KMS key is not secret, not HSM-backed, and must never be used to encrypt real broker credentials. Local development must use test/dummy broker API keys only. This is an operational constraint, not a code constraint.

---

### Transactional Email (Mailpit)

- **Image:** `axllent/mailpit:latest`
- **SMTP port:** `1025` (application sends to this)
- **Web UI port:** `8025` (browse captured emails at `http://localhost:8025`)
- **What Mailpit does:** catches all outgoing email and displays it in a web inbox. No email is actually sent. Verification links, password reset links, and account lock notifications appear in the Mailpit UI for testing.

**Environment variable that switches email between local and production:**

```
# Local (Mailpit SMTP)
EMAIL_TRANSPORT=smtp
SMTP_HOST=localhost
SMTP_PORT=1025

# Production (Resend HTTP API)
EMAIL_TRANSPORT=resend
RESEND_API_KEY={secret-from-secrets-manager}
FROM_ADDRESS=noreply@{production-domain}
```

Bhima implements a thin `EmailSender` interface with two concrete implementations: `SMTPEmailSender` (local) and `ResendEmailSender` (production). The `EMAIL_TRANSPORT` env var selects the implementation. The rest of the application (auth service, password reset service) calls `EmailSender.send(...)` and does not know which transport is in use.

---

### Secrets (`.env` file)

Production uses AWS Secrets Manager, with secrets injected as environment variables at runtime. Locally, the same pattern is replicated with a `.env` file:

```
# .env (gitignored — never committed)
DATABASE_URL=postgresql+asyncpg://tradeforge_app:dev_password@localhost:5432/tradeforge_dev
REDIS_URL=redis://localhost:6379
KMS_ENDPOINT_URL=http://localhost:4566
KMS_KEY_ARN=arn:aws:kms:ap-south-1:000000000000:key/{local-key-id}
EMAIL_TRANSPORT=smtp
SMTP_HOST=localhost
SMTP_PORT=1025
ALLOWED_ORIGINS=http://localhost:5173
SECRET_KEY={random-local-value}
```

A `.env.example` file (committed to version control) lists every required variable with placeholder values and a comment explaining each. A new developer clones the repo, copies `.env.example` to `.env`, runs `docker compose up`, and the local environment starts.

**`.env` must be in `.gitignore` from the first commit.** A `.env` file committed to version control — even with dummy local values — trains developers to treat secrets as code. This habit causes production secrets to be committed. The `.env.example` pattern enforces the correct discipline from day one.

---

## CORS in Local Development

ADR-002 requires `ALLOWED_ORIGINS` to be an environment variable containing the exact production frontend origin. Locally:

```
ALLOWED_ORIGINS=http://localhost:5173
```

The Vite dev server runs at `http://localhost:5173` by default. The FastAPI application runs at `http://localhost:8000`. These are different origins, so CORS applies even locally — the configuration is exercised and tested in development, not bypassed.

This is intentional. A local CORS configuration that disables CORS entirely (e.g., `allow_all_origins=True`) would mask CORS bugs that only appear in production. The local `ALLOWED_ORIGINS` value mirrors the production pattern exactly — just pointing at localhost instead of the production frontend URL.

---

## Environment Variable Reference

Full mapping of environment-variable-controlled behaviour between local and production:

| Variable | Local value | Production value | Who sets it |
|---|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://tradeforge_app:dev_password@localhost:5432/tradeforge_dev` | From AWS Secrets Manager | Nakula (prod), Bhima (local) |
| `REDIS_URL` | `redis://localhost:6379` | TLS ElastiCache URL from Secrets Manager | Nakula (prod), Bhima (local) |
| `KMS_ENDPOINT_URL` | `http://localhost:4566` | _(omit — boto3 uses AWS default)_ | Nakula (prod), Bhima (local) |
| `KMS_KEY_ARN` | LocalStack key ARN | Real CMK ARN | Nakula (prod), Bhima (local) |
| `EMAIL_TRANSPORT` | `smtp` | `resend` | Nakula (prod), Bhima (local) |
| `SMTP_HOST` | `localhost` | _(not used in prod)_ | Bhima (local) |
| `SMTP_PORT` | `1025` | _(not used in prod)_ | Bhima (local) |
| `RESEND_API_KEY` | _(not used locally)_ | From AWS Secrets Manager | Nakula (prod) |
| `FROM_ADDRESS` | _(not used locally)_ | `noreply@{production-domain}` | Nakula (prod) |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | `https://app.{domain}` or `https://{domain}` | Nakula (prod), Bhima (local) |
| `SECRET_KEY` | Any random local string | From AWS Secrets Manager | Nakula (prod), Bhima (local) |

---

## What Is Explicitly Not Changed

The following remain in full effect during local development:

| Item | Status |
|---|---|
| ADR-001 (Python + FastAPI) | Unchanged |
| ADR-002 (Authentication and Authorization Architecture) | Unchanged |
| All 21 SR-AUTH security requirements | Unchanged — must be satisfied in local dev |
| Kubera Decimal Usage Standard | Unchanged |
| Ganesha Domain Rules | Unchanged |
| Nakula production decisions (AWS, RDS, ElastiCache, KMS, Resend) | Unchanged — production deployment targets |
| PROD-DOMAIN-DECISION-BRIEF | Unchanged — decision deferred, not dismissed |

---

## Deferred Until Production Deployment

| Item | Deferred to | Trigger |
|---|---|---|
| AWS account setup and IAM | Production deployment | Atharva initiates deployment |
| Cloud provider (AWS, ap-south-1) | Production deployment | — |
| RDS PostgreSQL provisioning | Production deployment | — |
| ElastiCache Redis provisioning | Production deployment | — |
| Real AWS KMS CMK provisioning | Production deployment | — |
| Resend production email setup | Production deployment | — |
| Production domain (apex domain + URL structure) | Production deployment | See PROD-DOMAIN-DECISION-BRIEF.md |
| DNS record configuration (SPF/DKIM/DMARC) | Production deployment | After domain decision |
| ALLOWED_ORIGINS production value | Production deployment | After domain decision |

---

## Docker Compose Service Summary

The following services are required in `docker-compose.yml` for local development. Nakula writes the actual Compose file when implementation begins; this table defines the required services and their constraints.

| Service | Image | Ports | Persistence | Required for |
|---|---|---|---|---|
| `postgres` | `postgres:16-alpine` | `5432` | Named volume | All features |
| `redis` | `redis:7-alpine` | `6379` | None (ephemeral) | Auth, sessions, rate limiting |
| `localstack` | `localstack/localstack` | `4566` | None (ephemeral KEKs) | Broker credential encryption |
| `mailpit` | `axllent/mailpit` | `1025` (SMTP), `8025` (UI) | None (ephemeral emails) | Auth flows (email verification, password reset) |

The FastAPI application itself is run outside Docker during development (`uvicorn main:app --reload`) so that code changes hot-reload without rebuilding an image. Docker Compose provides only the backing services.

---

*Mayasura — Senior Software Architect*
*Nakula — Senior DevOps / Platform / SRE Engineer*
*This document governs the development phase. Production infrastructure decisions are recorded separately in Nakula's infrastructure decision report (2026-08-22) and remain the deployment target.*
