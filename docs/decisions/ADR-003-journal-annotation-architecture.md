# ADR-003: Journal Annotation Layer Architecture

**Status:** Accepted
**Author:** Mayasura (Senior Software Architect)
**Domain authority:** Ganesha (JOURNAL-DOMAIN-RULES.md — G1)
**Security authority:** Hanuman (JOURNAL-SECURITY-REQUIREMENTS.md — G4)
**Decision authority:** Atharva
**Date:** 2026-08-23
**Depends on:** ADR-001 (Python + FastAPI), ADR-002 (Authentication and Authorization Architecture)
**Binding inputs:** JOURNAL-DOMAIN-RULES.md Rules 1.1–9.3, JOURNAL-SECURITY-REQUIREMENTS.md SR-JOUR-001 through SR-JOUR-013, SR-ATT-001 through SR-ATT-010

---

## Context

The journal annotation layer is Step 9 of the TradeForge build sequence. It layers subjective, behavioral, and analytical context onto the objective execution records produced by the trade reconstruction engine (Steps 1–8).

The key tension this layer must resolve is between two competing requirements that pull in opposite directions:

1. **Authoritative record separation.** The trade domain (fills, reconstructed trades, P&L) must remain immutable and authoritative. The journal layer must never corrupt it. Any design that allows the journal service to write to trade domain tables is architecturally incorrect.

2. **Tight coupling to trade data.** The journal reads from the trade domain (`trades.average_entry`, `trades.total_entry_quantity`) to compute derived values (`planned_risk_amount`). It also reads from the P&L layer (`trade_pnl`) to compute `PnlStatus`. It cannot operate in complete isolation.

A secondary tension exists within the journal layer itself: the attachment subsystem must allow users to attach screenshots to trade records without the application server ever handling raw file bytes, because handling file bytes at the application layer creates a DoS surface and introduces storage infrastructure concerns that belong outside the application process.

The architectural decisions below resolve these tensions explicitly. Each decision records the constraint it satisfies and what it costs.

---

## Decisions

### Decision 1 — Journal Layer Is a Read Subscriber of the Trade Domain

The journal annotation layer is a **one-directional read subscriber** of the trade domain. It reads from `trades` and `trade_pnl`; it never writes to them.

**Permitted reads:**
- `trades`: `id`, `user_id`, `average_entry`, `total_entry_quantity` (trade snapshot for `planned_risk_amount` computation)
- `trade_pnl`: existence check only (for `PnlStatus` determination)

**Writes the journal layer owns:**
- `journal_entries` — all reads and writes
- `journal_attachments` — all reads and writes
- `journal_audit_log` — append-only writes, reads for audit history display

**Writes the journal layer is prohibited from making:**
- `trades` — zero writes. No UPDATE to `trades.planned_entry`, `trades.planned_stop`, `trades.planned_target`, or any other column.
- `trade_pnl` — zero writes. P&L is produced by the Step 10 engine (Kubera), not the journal service.
- `execution_fills`, `management_events`, `tax_lots` — out of scope entirely.

**Why this decision:** The trade domain tables are authoritative financial records. Giving the journal service write access to them would allow a journal operation (an upsert, an audit log write) to accidentally corrupt an execution record. Defense in depth requires that the journal service's repository has no `INSERT`, `UPDATE`, or `DELETE` method targeting any trade domain table. This is a code boundary, not just a policy statement.

**Code enforcement:** `JournalRepository` imports no ORM models from the trade domain layer except for `SELECT` queries. A code review that introduces a write import from `trade_domain.py` is rejected.

**Consequence:** `planned_entry`, `planned_stop`, and `planned_target` exist in `journal_entries`, not in `trades`. This duplicates columns that also exist in `trades` (as planning fields added in the trade domain design). The `trades` planning fields are populated by the trade reconstruction engine from broker pre-trade data where available; the `journal_entries` planning fields are populated by the user via the journal API. These are not the same values — one is sourced from the broker, the other is user-entered reflection. Both are retained. See JOURNAL-DOMAIN-RULES.md Rule 8.2.

---

### Decision 2 — 1:1 Cardinality Enforced by Unique Constraint

One trade has at most one journal entry. This cardinality is enforced by:

1. A `UNIQUE(trade_id)` constraint on `journal_entries`.
2. The `upsert_entry` service method, which checks for an existing entry before deciding to INSERT or UPDATE.

**Why 1:1 and not 1:N:** Multiple journal entries per trade would require a version or timestamp concept, UI for navigating between versions, and analytics complexity for Karna (which version of the planned stop is the "canonical" 1R value?). The audit log already provides a full history of every field change. A "journal version" is the audit log — not a separate row. Phase 1 records one active snapshot; the audit log reconstructs the history. See JOURNAL-DOMAIN-RULES.md Unresolved 1 for the deferred case of versioned snapshots.

**Consequence:** A blank journal entry is created as a side effect of the first attachment presign request, if no entry exists yet. This ensures the attachment always has a parent `journal_entry_id` foreign key to reference. The blank entry has all optional fields as NULL; the user populates it later via `PUT /v1/journal/trades/{trade_id}`.

---

### Decision 3 — Full-Replacement PUT Semantics (Not PATCH)

The `PUT /v1/journal/trades/{trade_id}` endpoint uses **full-replacement semantics**: every field in the request body is written to the database. Fields absent from the request body are treated as `null` and stored as NULL.

This is deliberately not `PATCH` (partial update) semantics.

**Why full-replacement:**

Patch semantics require the server to distinguish between three states per field: "field present with a value", "field present as null (explicit clear)", and "field absent (leave unchanged)". In JSON, `{"planned_stop": null}` and an object with no `planned_stop` key are genuinely different intentions under PATCH. Pydantic v2 can model this with `Optional` + `model_fields_set`, but it introduces complexity throughout the serialization and service layers.

Full-replacement is simpler: the client is the authority on the current complete state of the journal entry. It always sends all fields it wants kept, and nulls the rest. This is consistent with how browser form submits work. The service layer has one code path per field: write what you received.

**Consequence:** The client must re-send all fields it wants to retain on every save, even if only one field changed. This is a client-side concern. The UX spec (JOURNAL-UX-SPEC.md) must account for this: the edit form initializes from the `GET` response and sends all current values on save. Arjun must not send a partial object.

---

### Decision 4 — `PnlStatus` Is Computed at Read Time, Never Stored

`PnlStatus` is a three-state indicator (`PENDING_STOP`, `PENDING_CALCULATION`, `AVAILABLE`) returned in every `GET` and `PUT` response. It is computed at read time from two conditions:

1. Is `journal_entries.planned_stop` non-null?
2. Does a `trade_pnl` row exist for this `trade_id`?

It is never stored in a database column.

**Why computed, not stored:**

`PnlStatus` is a function of two independently-changing pieces of state. If it were stored, two update paths would need to maintain it in sync: the journal upsert path (when `planned_stop` changes) and the Step 10 P&L engine path (when it inserts a `trade_pnl` row). A stored status that drifts from the underlying conditions it reflects is a source of display bugs.

The computation is cheap: one EXISTS subquery on `trade_pnl` (indexed on `trade_id`). The read path already runs this query to populate the `pnl` object in the response.

**Consequence:** Every `GET /v1/journal/trades/{trade_id}` call issues a query to `trade_pnl`. At Phase 1 scale (low user count, low trade volume) this is negligible. At higher scale, a Redis cache keyed on `trade_id` could cache the EXISTS result with a short TTL. This optimization is deferred.

---

### Decision 5 — Audit Log Written by the Service Layer, Not Database Triggers

Field-level audit log rows in `journal_audit_log` are written by `JournalService._diff_for_audit()` in the application service layer, not by a PostgreSQL trigger on the `journal_entries` table.

**Why service layer:**

The audit log requires business logic that a database trigger cannot cleanly express:

- **Selective field tracking.** Only 10 of 14 writeable fields are audited. The trigger would need to know which columns are in the audit scope — leaking domain knowledge into the database layer.
- **Serialization rules.** Arrays (e.g., `mistakes`) are serialized as comma-separated strings. Decimal values serialize as strings with 4 decimal places. A trigger can produce these but the formatting logic belongs in application code, where it can be tested without a live database.
- **`change_reason` correlation.** Each audit row for a single PUT must carry the same `change_reason` from that request. Triggers do not have access to the HTTP request body. The service passes `change_reason` explicitly to each audit row.
- **Testability.** The diff-and-audit logic is tested as a pure unit test in the application layer without starting the database.

**PostgreSQL trigger responsibility is narrower:** the `journal_audit_log` immutability trigger (which raises an exception on UPDATE or DELETE) is a database-level control. It enforces append-only behavior as a defense against application bugs or direct database access. This trigger is appropriate because it requires no business logic — it is a blanket rejection of all mutations.

**Consequence:** The service layer is responsible for running the audit diff on every update path. A code path that updates `journal_entries` without calling `_diff_for_audit` is a bug. This risk is mitigated by the single `upsert_entry` entry point — there is no secondary update path.

---

### Decision 6 — StoragePort Protocol Abstraction for S3

Attachment storage is accessed through a `StoragePort` Protocol (Python structural typing). The `JournalService` holds a `StoragePort` instance injected at construction. Two implementations exist:

| Implementation | Used in |
|---|---|
| `StubStorage` | Local development, unit tests, integration tests (no real S3 required) |
| Real S3 implementation (Nakula) | Production and staging |

`JournalService` imports only `StoragePort` — never `boto3`, `aioboto3`, or any AWS SDK class. The real S3 implementation is provided at application startup via dependency injection. The service layer has zero knowledge of which implementation it is using.

**Why Protocol-based, not an abstract base class:**

Python Protocols (structural typing) allow the `StubStorage` to satisfy the interface without inheriting from a base class. This means the stub can be used in unit tests without any import of the real infrastructure code. The Protocol is defined in the application layer (`application/journal/storage.py`), satisfying the dependency direction rule from ADR-001 (application layer does not import infrastructure).

**Nakula's responsibility:** Implement a production `S3Storage` class satisfying `StoragePort`. This class lives in the infrastructure layer. It must implement `presign_put`, `presign_get`, and `head_object` per the interface contract. The production wire-up replaces `StubStorage()` in the FastAPI dependency at startup. See `JOURNAL-SECURITY-REQUIREMENTS.md SR-ATT-004` and `SR-ATT-007` for the S3 bucket configuration and presign URL conditions the real implementation must satisfy.

**Consequence:** Phase 1 attachment uploads work end-to-end against `StubStorage`, but the upload URL returned is a stub URL that cannot receive real files. The feature is architecturally complete but storage is non-functional until Nakula wires the real implementation.

---

### Decision 7 — Two-Step Attachment Upload (Presign → Direct-to-S3 → Confirm)

Attachment uploads follow a two-step protocol. The application server never handles file bytes.

```
Step 1 — Presign:
  Client → POST /v1/journal/trades/{trade_id}/attachments/presign
    body: {filename, content_type, byte_size, capture_moment, caption}
  Server validates: content type, file size, quota, trade ownership
  Server creates: attachment row (status=PENDING), S3 presign PUT URL
  Server returns: {attachment_id, upload_url, expires_in_seconds}

Step 2 — Direct upload:
  Client → PUT {upload_url} (direct to S3, not via the application server)
    body: raw file bytes
    headers: Content-Type: {declared_content_type}
  S3 enforces: Content-Type condition, content-length-range condition

Step 3 — Confirm:
  Client → POST /v1/journal/trades/{trade_id}/attachments/{attachment_id}/confirm
  Server: HeadObject to verify the object exists
  Server: transitions attachment status PENDING → CONFIRMED
  Server returns: {id, filename, content_type, byte_size, status, download_url, confirmed_at}
```

**Why two-step and not direct-to-server upload:**

Direct server upload (multipart/form-data to the FastAPI endpoint) requires the application server to:
- Buffer or stream file bytes in memory or temp storage
- Enforce file size limits before the upload is complete (partial reads)
- Handle upload interruptions and partial writes
- Then copy the bytes to S3 or object storage

This makes the application server a file transfer proxy, adding memory pressure, increasing request duration, and creating a DoS surface (an attacker can open many upload connections that each consume server memory). The presign-direct approach pushes all file-handling load to S3, which is designed for it.

**Why HeadObject and not trusting the client's confirm:**

Without the HeadObject verification, the confirm endpoint would trust the client's claim that an upload completed. A client could call confirm immediately after presign without uploading anything, leaving a CONFIRMED attachment row pointing to a non-existent S3 object. Subsequent download URL generation would produce presign URLs for missing objects. HeadObject is a cheap metadata check that verifies object presence without reading the object body (SR-ATT-008).

**Consequence:** The frontend must implement a three-request flow for every attachment upload. The UX must handle the intermediate PENDING state and the confirm step. See JOURNAL-UX-SPEC.md for the attachment upload component spec (C-07).

---

### Decision 8 — Ephemeral Pre-Signed Download URLs (1-Hour TTL, No Permanent URLs)

Download URLs for confirmed attachments are pre-signed S3 GET URLs with a 1-hour TTL. They are generated fresh on every call to `GET /v1/journal/trades/{trade_id}` and `POST .../confirm`. They are never stored in the database.

**Pre-sign parameters enforced:**
- `Content-Disposition: attachment; filename={sanitized_filename}` — forces a download, prevents inline rendering (prevents XSS via served image content)
- TTL: 3600 seconds (1 hour)
- HTTPS only

**Why ephemeral and not permanent:**

If the attachment were served via a permanent public URL, any person or system with the URL could access the file indefinitely — even after the user deletes the attachment, the account is suspended, or the S3 object is deleted by lifecycle policy. Pre-signed URLs expire. A deleted attachment's download URL stops working when its TTL passes (at most 1 hour). This is the correct security posture for private financial screenshots.

Storing the download URL would require invalidating it on every attachment deletion and re-generating it on expiry, which is more complex than regenerating it on every read.

**Consequence:** The frontend must not cache the download URL between page loads. Each `GET /v1/journal/trades/{trade_id}` call produces fresh URLs for all attachments. This is documented in JOURNAL-DOMAIN-RULES.md Rule 5.8 and in the handoff notes to Arjun.

---

### Decision 9 — Ownership Failures Return 404, Not 403

When a user attempts to access a journal entry or attachment they do not own, the API returns `404 Not Found`, not `403 Forbidden`.

**Why 404:** A `403 Forbidden` response confirms that the resource exists — only the requestor lacks access. For a trading journal, confirming that a given `trade_id` is a real trade in another user's account is information disclosure. By returning `404`, the API is indistinguishable from a request for a non-existent resource. An attacker who enumerates UUIDs learns nothing about whether those UUIDs are valid trade IDs in other accounts.

This rule applies to: journal entry reads, journal entry writes, audit history reads, attachment presign (trade ownership check), attachment confirm, and attachment delete. All of these use the pattern:

```sql
SELECT ... WHERE resource.user_id = :session_user_id AND resource.id = :requested_id
```

The result `None` means either "doesn't exist" or "owned by someone else." The application never distinguishes these cases.

**Consequence:** This makes debugging authorization failures harder for developers — a 404 on a resource that you know exists but don't own is confusing without context. Development-mode debug logging (disabled in production) can include the ownership mismatch reason.

---

### Decision 10 — `planned_risk_amount` Is Derived and Service-Computed

`planned_risk_amount` is not a field the user supplies. It is computed by `JournalService.upsert_entry()` from the trade snapshot and stored in `journal_entries`. It is re-computed on every upsert.

**Formula:**
```
planned_risk_amount = abs(trades.average_entry − planned_stop) × trades.total_entry_quantity
```

**Why derived, not user-entered:**

If the user could enter `planned_risk_amount` directly, they could supply a value inconsistent with their actual `planned_stop` and the trade's `average_entry`. This would corrupt Karna's R-multiple calculation (R = net_pnl / planned_risk_amount). Deriving it from authoritative trade data (actual average entry) and the user's declared stop ensures internal consistency.

**Why `trades.average_entry` and not `planned_entry`:**

Risk is measured from where the trader actually entered, not where they planned to enter. Using the actual average entry produces a risk figure that reflects real dollars-at-risk from the actual position, not a hypothetical.

**Consequence:** `planned_risk_amount` is NULL until two conditions are true: (1) `planned_stop` is set, and (2) `trades.average_entry` is non-NULL (the trade has completed entry fill reconstruction). For very fresh trades imported with no average entry yet computed, the risk amount is unavailable. The UI should display a "calculating" state for this field.

---

## Component Map

```
┌──────────────────────────────────────────────────────────────────┐
│  API Layer  (FastAPI)                                            │
│  /v1/journal/trades/{trade_id}               [journal.py]        │
│  /v1/journal/trades/{trade_id}/audit                             │
│  /v1/journal/trades/{trade_id}/attachments/presign               │
│  /v1/journal/trades/{trade_id}/attachments/{id}/confirm          │
│  /v1/journal/trades/{trade_id}/attachments/{id}  DELETE          │
└─────────────────────────┬────────────────────────────────────────┘
                          │ calls
┌─────────────────────────▼────────────────────────────────────────┐
│  Application Layer                                               │
│  JournalService                          [application/journal/]   │
│    ├── upsert_entry()      ← diff + audit + compute risk amount  │
│    ├── get_entry()         ← PnlStatus computed here             │
│    ├── get_audit_history()                                       │
│    ├── presign_attachment()   ← validates type/size/quota        │
│    ├── confirm_attachment()   ← HeadObject verify               │
│    └── delete_attachment()   ← soft delete + audit log          │
│  StoragePort (Protocol)  [application/journal/storage.py]        │
│    ├── StubStorage        (dev / test)                           │
│    └── S3Storage          (prod — Nakula implements)             │
└─────────────────────────┬────────────────────────────────────────┘
                          │ calls
┌─────────────────────────▼────────────────────────────────────────┐
│  Infrastructure Layer                                            │
│  JournalRepository       [infrastructure/repositories/]          │
│    ├── Reads:  trades (snapshot), trade_pnl (EXISTS only)        │
│    └── Writes: journal_entries, journal_attachments,             │
│                journal_audit_log                                 │
│  ORM models:  JournalEntry, JournalAttachment, JournalAuditLog   │
│               [infrastructure/models/journal.py]                 │
└─────────────────────────┬────────────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────────────┐
│  Database (PostgreSQL)                                           │
│  journal_entries         — UNIQUE(trade_id), immutability rules  │
│  journal_attachments     — status machine, quota enforcement     │
│  journal_audit_log       — append-only, UPDATE/DELETE trigger    │
│  trades                  — READ ONLY from this layer             │
│  trade_pnl               — EXISTS check only                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Security Architecture

All security requirements for this layer are defined in `JOURNAL-SECURITY-REQUIREMENTS.md` (Hanuman G4). The architectural decisions above satisfy:

| SR | Satisfied by |
|---|---|
| SR-JOUR-001 | `user_id` sourced from `get_current_user_id()` dependency in every route; never from request body |
| SR-JOUR-002 | `JournalRepository.get_trade_snapshot()` includes `user_id` in WHERE clause |
| SR-JOUR-003 | `JournalEntryNotFoundError` → 404 (not 403). Decision 9. |
| SR-JOUR-004 | `AttachmentNotFoundError` → 404 (not 403). Decision 9. |
| SR-JOUR-005 | All SELECT queries in `JournalRepository` include `user_id` in WHERE |
| SR-JOUR-006 | API layer: `planned_entry/stop/target` validated `> 0` via Pydantic; service rejects zero/negative |
| SR-JOUR-007 | `discipline_score`: Pydantic `Field(ge=1, le=10)` + DB CHECK constraint |
| SR-JOUR-008 | `emotion_*` and `mistakes` validated against enums at API layer; DB CHECK constraints |
| SR-JOUR-009 | `change_reason`: Pydantic `Field(max_length=500)` |
| SR-JOUR-010 | `_diff_for_audit()` in `JournalService` produces per-field audit rows on every PUT |
| SR-JOUR-011 | PostgreSQL BEFORE UPDATE/DELETE trigger on `journal_audit_log` (Bhima to implement in migration) |
| SR-JOUR-012 | `_log_attachment_event()` writes to `security_audit_log` for all attachment lifecycle events |
| SR-JOUR-013 | `JournalRepository` has no INSERT/UPDATE/DELETE methods targeting `trade_pnl` |
| SR-ATT-001 | Content type checked against `ALLOWED_CONTENT_TYPES` frozenset before presign |
| SR-ATT-002 | `byte_size` > 0, ≤ 15 MB, trade quota, user quota — all checked before presign |
| SR-ATT-003 | `sanitize_filename()` strips unsafe characters; stored as display metadata |
| SR-ATT-004 | S3 bucket configuration — Nakula responsibility |
| SR-ATT-005 | `build_s3_key()` is server-generated; extension-content-type match enforced at presign |
| SR-ATT-006 | Attachment ownership in repository WHERE clause; 404 on failure |
| SR-ATT-007 | Upload TTL 900s, download TTL 3600s; `Content-Disposition: attachment` on GET |
| SR-ATT-008 | `head_object()` called before CONFIRM transition; missing object → REJECTED |
| SR-ATT-009 | Seven attachment events written to `security_audit_log` with required payload |
| SR-ATT-010 | PENDING expiry checked at confirm time; S3 lifecycle rule (Nakula) cleans objects at 1 hr |

---

## Layer Allocation: What Goes Where

| Concern | Owner | Location |
|---|---|---|
| Request/response schema | Bhima | `api/v1/journal.py` (Pydantic models) |
| Business rules and orchestration | Bhima | `application/journal/service.py` |
| Storage interface | Bhima | `application/journal/storage.py` |
| Production S3 implementation | Nakula | `infrastructure/storage/s3_storage.py` (to be created) |
| Domain types, enums, constants | Bhima | `domain/journal/types.py` |
| Domain errors | Bhima | `domain/journal/errors.py` |
| ORM models | Bhima | `infrastructure/models/journal.py` |
| Repository queries | Bhima | `infrastructure/repositories/journal_repo.py` |
| Alembic migration (journal tables) | Bhima | `alembic/versions/0004_…` (already created) |
| Alembic migration (audit triggers) | Bhima | Next migration after 0004 |
| Frontend components | Arjun | Per JOURNAL-UX-SPEC.md C-01 through C-10 |

---

## Consequences

### What Becomes Easier

- **Authoritative record integrity:** The journal service cannot corrupt trade records. The boundary is enforced by code structure, not discipline.
- **Testability:** `StoragePort` means the entire journal service — including attachment presign, confirm, delete — can be tested with no real S3. `StubStorage.head_object()` always returns a non-None dict, simulating a successful upload in tests.
- **P&L decoupling:** Karna's R-multiple calculation only needs `planned_risk_amount` from `journal_entries` and `net_pnl` from `trade_pnl`. Neither depends on the journal service's update path.
- **Audit completeness:** Every field change is traceable. `journal_audit_log` captures the old and new value, the timestamp, and the user's stated reason. No change to a journal entry is anonymous.

### What Becomes Harder

- **Three-request attachment flow:** Every attachment upload requires presign → upload → confirm. The frontend complexity is higher than a simple `<input type="file">` submission. The UX spec must accommodate the intermediate PENDING state.
- **No PATCH semantics:** The full-replacement PUT means the client must maintain the complete current state of the journal entry and re-send it on every update. If the client loses state (e.g., page reload between reads), it must `GET` first.
- **Stub storage is non-functional for real files:** Phase 1 integration tests for the attachment upload path must use `StubStorage`. End-to-end attachment testing requires Nakula to wire the real S3 implementation first.
- **`planned_risk_amount` depends on trade reconstruction:** If `trades.average_entry` is NULL (trade not yet reconstructed), `planned_risk_amount` is NULL even if `planned_stop` is set. The UI must handle this gracefully.

### Technical Debt Accepted

- **S3 implementation is a stub in Phase 1.** The production attachment upload path is non-functional until Nakula delivers the real `S3Storage` implementation and bucket configuration. The feature is architecturally complete; the storage backend is not.
- **Attachment PENDING expiry is not pro-actively enforced.** PENDING rows expire at confirm time (application check) and their S3 objects expire via S3 lifecycle (Nakula). There is no background job that sweeps expired PENDING rows and marks them EXPIRED. A PENDING row that is never confirmed stays PENDING in the database until the next confirm attempt. This means `sum_confirmed_bytes_for_trade` (quota check) does not include never-confirmed rows — which is correct behavior, since they're not consuming real user storage quota. The only gap is cosmetic: the database has PENDING rows that are past their window but not yet marked EXPIRED. A Phase 2 cleanup job (Celery task, per ADR-001 async architecture) can sweep and expire stale PENDING rows.

---

## Open Items — Must Be Resolved Before Full Production

| Item | Owner | Blocks |
|---|---|---|
| `S3Storage` implementation | Nakula | Real attachment upload in production |
| S3 bucket configuration (SR-ATT-004) | Nakula | SR compliance for attachments |
| S3 lifecycle rule for PENDING objects (SR-ATT-010) | Nakula | PENDING object cleanup |
| `journal_audit_log` immutability trigger migration | Bhima | SR-JOUR-011 compliance |
| Sahadeva acceptance gate (10-item checklist in SR doc) | Sahadeva | QA sign-off |

---

## Assumptions

1. `trade_pnl` table exists with at minimum a `trade_id` column, indexed, before the journal's `has_pnl_row()` query runs in production.
2. The `security_audit_log` table from ADR-002 is available in the same database and the application role has `INSERT` privilege.
3. Nakula's S3 bucket will use `{user_id}/{trade_id}/{attachment_id}` as the key prefix structure, per SR-ATT-005, and will block public access, per SR-ATT-004.
4. All journal API routes are behind the `get_current_user_id` FastAPI dependency, which itself depends on the Redis session store per ADR-002. Redis unavailability returns 503 on all journal routes (fail-closed, per ADR-002 session architecture).

---

*Mayasura — Senior Software Architect*
*ADR-003 status: Accepted 2026-08-23*
*Approved by: Atharva*
*Security review: Hanuman (JOURNAL-SECURITY-REQUIREMENTS.md — G4)*
*Domain review: Ganesha (JOURNAL-DOMAIN-RULES.md — G1)*
