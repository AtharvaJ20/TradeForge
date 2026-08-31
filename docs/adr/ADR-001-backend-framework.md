# ADR-001: Backend Framework — Python + FastAPI

**Status:** Accepted
**Author:** Mayasura
**Decision authority:** Atharva
**Accepted:** 2026-08-22

---

## Context

TradeForge is a calculation-heavy, domain-complex, data-intensive
application. The primary non-functional requirement is financial
calculation correctness — deterministic, reproducible P&L, risk,
and trade reconstruction results. Traffic scale is low; domain
complexity is high.

The system must also accommodate:
- Async workflows (CSV import, broker sync, report generation)
- A future AI/ML interpretation layer (Phase 3)
- Broker integrations for Indian markets (Zerodha, Upstox, Angel One)
- Strict separation between authoritative financial records and derived
  analytics or AI interpretation

The backend framework decision is foundational. It governs the language
of every calculation engine, the async processing model, the broker
integration approach, and the testability of the financial domain.

---

## Decision

Python 3.12+ with FastAPI as the web framework.

| Component            | Choice                       | Phase |
|----------------------|------------------------------|-------|
| Web framework        | FastAPI                      | 1     |
| Validation/serial.   | Pydantic v2                  | 1     |
| ORM                  | SQLAlchemy 2.x (async)       | 1     |
| Migrations           | Alembic                      | 1     |
| Financial arithmetic | Python stdlib Decimal        | 1     |
| Async jobs (durable) | Celery + Redis               | 2*    |
| Cache / job broker   | Redis                        | 2*    |
| Type bridge          | FastAPI OpenAPI → openapi-ts | 1     |

\* Celery + Redis is the decided async architecture target. Phase 1 may
use FastAPI BackgroundTasks as a temporary concession where jobs are
short-lived and loss-tolerant. See Consequences — Async Processing.

---

## Architectural Boundary Rule (non-negotiable)

The trading and financial domain layer must contain no imports from
FastAPI, Pydantic, SQLAlchemy, Celery, or any other framework or
infrastructure library.

Dependency directions (arrow = imports / depends on):

```
API Layer ──────────────────→ Application Layer
Infrastructure Layer ────────→ Application Layer
                                      │
                                      ↓
                                Domain Layer
                              (no external deps
                               outside stdlib)
```

Domain models are Python dataclasses or plain classes. Pydantic schemas
exist only in the API layer as request/response contracts — they are not
domain models. SQLAlchemy models exist only in the infrastructure layer
as persistence representations — they are not domain models.

Kubera's P&L engine, Karna's analytics calculators, and Dhanvantari's
risk engine are domain layer components. They must be fully testable
with no database, no HTTP server, and no framework running.

---

## Consequences

### Financial Arithmetic

Python's Decimal type eliminates binary floating-point representation
errors for decimal fractions. Within a correctly configured Decimal
context, arithmetic is exact: `Decimal('0.1') + Decimal('0.2') ==
Decimal('0.3')` is true. This is the primary advantage over
JavaScript's number type.

Decimal does not automatically provide correct financial results. The
following require explicit decisions:

- **Rounding mode.** Python's default is ROUND_HALF_EVEN (banker's
  rounding). Indian brokerage calculations typically require
  ROUND_HALF_UP. The difference produces systematically incorrect
  charge results on .5 values if the mode is not set explicitly per
  calculation context.
- **Precision per output type.** R-multiples, brokerage charges, and
  weighted average prices have different appropriate precision levels.
  One global precision setting is not correct.
- **Initialization discipline.** `Decimal(0.1)` is wrong — it captures
  the float approximation before conversion. `Decimal('0.1')` is
  correct. This cannot be enforced by the type system; it must be
  enforced by code review and linting.

**Kubera must produce a Decimal Usage Standard before any financial
calculation code is written.** It must specify: rounding mode per
calculation type, precision per output type, and initialization rules.
This is a hard prerequisite for Bhima's implementation of any P&L,
charge, or risk calculation. No financial code merges without it.

### Async Processing

The decided async architecture is Celery + Redis.

Phase 1 concession: FastAPI BackgroundTasks may be used only for async
operations that are simultaneously:
- (a) short-lived (seconds, not minutes)
- (b) loss-tolerant (silently dropped on server restart is acceptable)
- (c) not user-observable for progress or completion

BackgroundTasks must not be used for:
- CSV import jobs of any meaningful size
- Broker synchronization
- Report generation
- Any job requiring retry, progress reporting, or auditability

The async job interface must be designed against the Celery task model
from Phase 1, with BackgroundTasks as a drop-in substitute where the
above conditions hold. The migration to Celery must require no redesign
of the job interface — only replacement of the execution layer.

Nakula must provision Redis from Phase 1, even if Celery workers are
not yet active.

### Broker SDK Neutrality

Python's official broker SDKs (KiteConnect, Upstox v2, Angel One)
reduce integration friction for Sanjaya. This is an implementation
advantage, not an architectural dependency.

A BrokerAdapter interface (Python abstract base class or Protocol) must
be defined before any broker SDK is introduced. All broker-specific
code — including SDK imports — is confined to concrete adapter
implementations in the infrastructure layer. The import pipeline, trade
reconstruction engine, and reconciliation system depend only on the
BrokerAdapter interface.

Replacing or adding a broker must not touch any code outside the adapter
implementation.

### AI Interpretation Layer

The AI interpretation layer (Phase 3) is architecturally downstream of
the authoritative domain, P&L, and analytics layers. It receives
computed, validated data as input. It does not participate in producing
authoritative financial records, and must not feed back into them.

This positioning is decided. The execution boundary — whether the AI
layer runs in-process alongside the API, as a separate service, or as
isolated functions — is a Phase 3 architecture decision and is not made
here.

Python's ecosystem (Anthropic/OpenAI SDKs, vector stores, data science
libraries) is an available option that eliminates a language boundary if
in-process execution is chosen. That option is preserved by this
decision; it is not mandated.

### Type Bridge (Frontend)

FastAPI generates an OpenAPI specification automatically from route and
Pydantic type annotations. The TypeScript frontend consumes this spec
via openapi-ts to generate a typed HTTP client and request/response
types.

CI must enforce that the generated TypeScript types are committed and up
to date with the current OpenAPI spec. Drift between the spec and the
frontend types must fail the build.

### Testing Architecture Implication

The domain layer boundary rule has a direct consequence on test
architecture, binding on Sahadeva and all engineering agents:

| Layer          | Test type       | Framework deps                               |
|----------------|-----------------|----------------------------------------------|
| Domain         | Pure unit tests | None. No DB, no HTTP, no app startup. Fast.  |
| Application    | Unit tests      | Domain only. Infrastructure mocked.          |
| Infrastructure | Integration     | Live DB required. Isolated schema.           |
| API            | Integration     | FastAPI test client. Live or in-memory DB.   |
| Full stack     | E2E tests       | All layers live.                             |

P&L engine tests, risk engine tests, and trade reconstruction tests are
domain layer tests. They must run without a database connection and
without starting the application. Any calculation that cannot be tested
this way has leaked into the wrong layer.

### What Becomes Harder

- No native type sharing: the openapi-ts codegen step adds CI complexity
  and a manual trigger on API changes.
- Celery adds an operational surface from Phase 2 that Nakula must
  design and monitor.
- Python async patterns require attention if the developer is new to them.

---

## Assumptions

1. The developer has workable Python familiarity or is prepared to
   invest in it before implementation begins. If Python is genuinely
   unfamiliar, this decision must be revisited before a line of code
   is written.
2. PostgreSQL hosting is managed (not self-hosted). Nakula to confirm
   in infrastructure design.
3. No existing codebase or framework dependency forces a specific
   language choice.

---

## Open Items — Must Be Resolved Before Implementation

- [x] **ADR-002:** Authentication and Authorization Architecture — Accepted 2026-08-22.
- [ ] **Decimal Usage Standard** — Owner: Kubera. Blocker for: any
  financial calculation code.
- [ ] **Trade matching rules** (FIFO vs average cost) — Owner: Ganesha.
  Blocker for: trade reconstruction engine design.
- [ ] **Infrastructure design** (cloud target, Redis, managed PG) —
  Owner: Nakula. Blocker for: environment setup.

---

*Supersedes: ADR-001 draft (2026-08-22)*
