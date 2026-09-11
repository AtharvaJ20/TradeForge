# TradeForge — Railway Infrastructure Topology

**Document:** `docs/infrastructure/RAILWAY-TOPOLOGY.md`  
**Owner:** Nakula (DevOps)  
**Date:** 2026-09-10  
**Platform:** Railway (railway.app)

---

## Service Topology

### Staging Environment

| Service | Type | Build source | Railway service name (display) | Railway service ID (CLI) |
|---------|------|-------------|-------------------------------|--------------------------|
| Backend API | Dockerfile (Python 3.12 / uvicorn) | `backend/Dockerfile` | (see Railway dashboard) | `intuitive-education` |
| Frontend | Dockerfile (Node 20 / nginx 1.27) | `frontend/Dockerfile` | (see Railway dashboard) | `distinguished-creativity` |
| PostgreSQL | Railway managed plugin | — | (see Railway dashboard) | — |
| Redis | Railway managed plugin | — | (see Railway dashboard) | — |

> **Service IDs** (`intuitive-education`, `distinguished-creativity`) are Railway's auto-generated identifiers used by the CLI (`railway redeploy --service`). The **display name** is what you set in the Railway dashboard UI.

**Staging URLs — find from Railway dashboard:**

Railway auto-generates a domain when "Public Networking" is enabled for a service. The URL is **not** known until Atharva opens the Railway dashboard:

1. Railway dashboard → staging project → select **intuitive-education** service → **Settings** → **Networking** → copy the auto-generated domain (e.g. `https://intuitive-education-production-xxxx.up.railway.app`)
2. Set that URL as the **`RAILWAY_BACKEND_URL`** GitHub secret (repo → Settings → Secrets → Actions)
3. The CI `deploy-staging` job will then verify the backend is healthy after each deploy

> **Note:** `tradeforge-backend-staging.up.railway.app` was the _planned_ URL documented before provisioning. If Railway generated a different domain, that URL will return `{"status":"error","code":404,"message":"Application not found"}` (Railway CDN 404). Use the URL from the Railway dashboard.

### Production Environment (Step I-3 — not yet provisioned)

Separate Railway project (or separate environments within the same project). Provisioning blocked on Step QA-1 manual walkthrough sign-off.

---

## External Services (free tier)

| Service | Purpose | Provider | Status |
|---------|---------|----------|--------|
| Attachment storage (S3-compatible) | Trade journal image attachments | Cloudflare R2 (10 GB free, zero egress) | ⚠️ Needs provisioning |
| Transactional email | Registration, password-reset, email-verify | Resend (3,000 emails/month free) | ⚠️ Needs provisioning |

---

## Environment Variables

### Backend service (set in Railway dashboard — never in code)

| Variable | Source | Notes |
|----------|--------|-------|
| `DATABASE_URL` | Railway injects automatically (PostgreSQL plugin) | asyncpg format: `postgresql+asyncpg://...` |
| `REDIS_URL` | Railway injects automatically (Redis plugin) | `redis://...` |
| `SECRET_KEY` | Generate: `openssl rand -hex 32` | Session signing key |
| `ALLOWED_ORIGINS` | Manual | `https://tradeforge-frontend-staging.up.railway.app` |
| `SECURE_COOKIES` | Manual | `true` in staging/production |
| `ENVIRONMENT` | Manual | `staging` or `production` |
| `S3_BUCKET` | Cloudflare R2 | Bucket name |
| `S3_ENDPOINT` | Cloudflare R2 | `https://<account-id>.r2.cloudflarestorage.com` |
| `S3_ACCESS_KEY` | Cloudflare R2 | R2 API token — Access Key ID |
| `S3_SECRET_KEY` | Cloudflare R2 | R2 API token — Secret Access Key |
| `EMAIL_TRANSPORT` | Manual | `resend` (when Bhima wires Resend into EmailService) |
| `RESEND_API_KEY` | Resend dashboard | Resend API key |
| `FROM_ADDRESS` | Manual | Verified sender address (e.g. `noreply@yourdomain.com` — must be a domain verified in Resend dashboard) |
| `KMS_KEY_ARN` | Manual | Leave empty (`""`) — deferred to Phase 2 per Krishna/Hanuman ruling |

### Frontend service (set as Railway build variables)

| Variable | Value | Notes |
|----------|-------|-------|
| `VITE_API_BASE_URL` | `https://tradeforge-backend-staging.up.railway.app` | Embedded into JS bundle at build time |

### GitHub Actions secrets (set in repo Settings → Secrets → Actions)

| Secret | Value |
|--------|-------|
| `RAILWAY_STAGING_BACKEND_WEBHOOK` | Railway → backend service → Settings → Deploy Hooks → Generate |
| `RAILWAY_STAGING_FRONTEND_WEBHOOK` | Railway → frontend service → Settings → Deploy Hooks → Generate |

---

## What Was Done (Nakula — 2026-09-10)

All infrastructure-as-code deliverables are committed to `main`:

| File | Purpose |
|------|---------|
| `backend/Dockerfile` | Multi-stage Python 3.12 build + uvicorn runtime; runs `alembic upgrade head` on start |
| `backend/.dockerignore` | Excludes tests, docs, caches from image |
| `backend/railway.toml` | Railway service config: Dockerfile builder, `/health` healthcheck, ON_FAILURE restart |
| `frontend/Dockerfile` | Multi-stage Node 20 build + nginx 1.27 runtime; SPA routing via `try_files` |
| `frontend/nginx.conf` | SPA routing, asset caching, `/health` endpoint |
| `frontend/.dockerignore` | Excludes node_modules, dist, coverage |
| `frontend/railway.toml` | Railway service config: Dockerfile builder, `/health` healthcheck |
| `.github/workflows/ci.yml` | Added `deploy-staging` job: triggers both deploy hooks on push to `main` after CI passes |

---

## What Atharva Must Do (Manual — Blocked on Cloud Credentials)

These steps cannot be automated without Railway and Cloudflare credentials. Complete them in order.

### 1. Railway — Create project and services

1. Go to [railway.app](https://railway.app) → New Project → "Deploy from GitHub repo"
2. Select the `TradeForge` repo; **do not** enable Railway's auto-deploy (CI controls deploys)
3. Create a **Staging** environment
4. Add services:
   - **Backend service:** root directory = `backend/`, Dockerfile path = `Dockerfile`
   - **Frontend service:** root directory = `frontend/`, Dockerfile path = `Dockerfile`
   - **PostgreSQL plugin:** attach to the backend service
   - **Redis plugin:** attach to the backend service

### 2. Railway — Set environment variables

In the Railway dashboard, for the **backend service** in the Staging environment, set all variables from the Backend table above. `DATABASE_URL` and `REDIS_URL` are auto-injected by the plugins.

For the **frontend service**, set `VITE_API_BASE_URL` as a **build variable** (not a runtime variable — Vite embeds it at build time).

### 3. Railway — Generate deploy hooks

- Backend service → Settings → Deploy Hooks → Generate URL → copy
- Frontend service → Settings → Deploy Hooks → Generate URL → copy

### 4. GitHub — Add secrets

Go to GitHub → repo → Settings → Secrets and variables → Actions → New repository secret:
- `RAILWAY_STAGING_BACKEND_WEBHOOK` = backend deploy hook URL from step 3
- `RAILWAY_STAGING_FRONTEND_WEBHOOK` = frontend deploy hook URL from step 3

### 5. Cloudflare R2 — Create bucket

1. [Cloudflare dashboard](https://dash.cloudflare.com) → R2 Object Storage → Create bucket
2. Bucket name: `tradeforge-staging-attachments`
3. Create an API token: R2 API Token → Create → "Object Read & Write" → scope to this bucket
4. Note the **Access Key ID**, **Secret Access Key**, and **Endpoint URL**
5. Set the R2 env vars in the Railway backend service (S3_BUCKET, S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY)

### 6. Resend — Create account and API key

1. [resend.com](https://resend.com) → Sign up (free tier)
2. Create an API key with "Sending access"
3. Set `EMAIL_API_KEY` in Railway backend service
4. **Note:** Bhima must update `EmailService` to use Resend's API before email flows work. The current implementation uses SMTP; coordinate with Bhima on the transport change.

### 7. Trigger the first deploy

After completing steps 1–6, push a commit to `main` (or manually hit the deploy hooks):
```
curl -X POST $RAILWAY_STAGING_BACKEND_WEBHOOK
curl -X POST $RAILWAY_STAGING_FRONTEND_WEBHOOK
```

### 7a. Find and record the actual staging URLs

After the Railway deploy completes, the service domains may differ from what was originally planned:

1. Railway dashboard → staging project → **intuitive-education** (backend) → **Settings** → **Networking** — copy the public domain
2. Railway dashboard → staging project → **distinguished-creativity** (frontend) → **Settings** → **Networking** — copy the public domain
3. Update this document with the confirmed URLs (replace the placeholder lines below)
4. Set `RAILWAY_BACKEND_URL` as a GitHub secret: repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

**Confirmed staging URLs** *(update once verified from Railway dashboard)*:
- Backend: `[to be confirmed from Railway dashboard — intuitive-education service]`
- Frontend: `[to be confirmed from Railway dashboard — distinguished-creativity service]`

### 8. Verify the staging environment

After the Railway deploy completes (check Railway dashboard logs — select service → Deployments → latest → View Logs):
- `<BACKEND_URL>/health` → `{"status": "ok"}`
- `<FRONTEND_URL>` → TradeForge login page loads
- Railway logs should show `alembic upgrade head` completing cleanly (migrations applied)

Report the confirmed staging URLs to Sahadeva to begin the QA-1 manual walkthrough.

---

## Rollback Procedure

Railway retains the full deploy history per service. To roll back:
1. Railway dashboard → service → Deployments → select a prior deployment → Redeploy
2. Time to rollback: < 2 minutes (Railway restarts from the existing built image)

Database migrations run on every deploy. Forward-only migrations mean rollback does **not** undo schema changes — only the application binary rolls back. This is acceptable for Phase 1 (no destructive migrations since Step 1).

---

## Cost Estimate (Railway free tier)

| Resource | Free allowance | Expected Phase 1 usage |
|----------|---------------|----------------------|
| Railway compute | $5 credit/month | Backend + frontend: ~$3–4/month (light traffic) |
| PostgreSQL (Railway) | 1 GB storage, 100 MB RAM | Well within free tier |
| Redis (Railway) | 25 MB RAM | Well within free tier |
| Cloudflare R2 | 10 GB storage, 10M Class A ops | Well within free tier |
| Resend email | 3,000 emails/month | Well within free tier |

**Total estimated cost:** $0 under Railway's free credit for Phase 1 with a solo developer.
