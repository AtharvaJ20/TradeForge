# Journal Security Requirements — G4

**Author:** Hanuman (Security)  
**Status:** Finalised — binding on Bhima (backend), Arjun (frontend), Nakula (infrastructure), Sahadeva (QA)  
**Scope:** Step 9 — Journal annotation layer and attachment handling  
**References:** ADR-002 (journal architecture), SR-AUTH-001–021 (auth security requirements)  
**Date:** 2026-08-23

---

## Overview

The journal feature introduces two attack surfaces that do not exist in prior steps:

1. **User-controlled text annotations** stored against trade records — IDOR risk, injection risk, audit tampering risk.
2. **User-uploaded binary files (attachments)** stored in object storage — content-type spoofing, path traversal, XSS via inline rendering, storage exhaustion, unauthorised download.

This document defines the security requirements for both surfaces. Requirements are numbered **SR-JOUR-xxx** (journal entry and access control) and **SR-ATT-xxx** (attachment handling). Both series are binding.

Acceptance criteria in every requirement are written so that Sahadeva can test them without reading production code.

---

## Part 1 — Authorization and Access Control

---

### SR-JOUR-001 — user_id is always sourced from the verified session

**Component:** All journal API endpoints  
**Threat:** Elevation of Privilege (STRIDE) — a user crafts a request that operates on another user's data by supplying a foreign `user_id`  
**Priority:** Critical  
**Owner:** Bhima

**Requirement:**  
`user_id` must be extracted exclusively from the server-side session context (Redis session lookup keyed by the session cookie). It must never be read from the request body, URL path parameters, or query string. This extends SR-AUTH-008 to the journal domain.

**Acceptance Criteria:**
- [ ] A PUT `/v1/journal/trades/{trade_id}` request whose JSON body includes a `user_id` field is processed using the session `user_id`, not the body value. The body `user_id` is ignored silently (or rejected by `extra: "forbid"` schema validation).
- [ ] A GET `/v1/journal/trades/{trade_id}` request with a `?user_id=<other_id>` query param returns data for the session user, not the injected ID.
- [ ] Code review confirms zero instances of `request.body["user_id"]` or equivalent in journal route handlers.

---

### SR-JOUR-002 — Trade ownership verified before any journal write

**Component:** `JournalService.upsert_entry`, `JournalService.presign_attachment`  
**Threat:** Elevation of Privilege — a user creates a journal entry against a trade they do not own  
**Priority:** Critical  
**Owner:** Bhima

**Requirement:**  
Before creating or updating a journal entry (and before issuing any attachment pre-signed URL), the service must verify that the `trade_id` in the request belongs to the requesting `user_id`. Verification must use a SQL `WHERE trade_id = :tid AND user_id = :uid` query — not a post-fetch ownership check in application code.

**Acceptance Criteria:**
- [ ] A PUT `/v1/journal/trades/{trade_id}` where `trade_id` belongs to User B, authenticated as User A, returns HTTP 404 (not 200, not 403).
- [ ] POST `/v1/journal/trades/{trade_id}/attachments/presign` where `trade_id` belongs to User B, authenticated as User A, returns HTTP 404.
- [ ] The `get_trade_snapshot` repository method includes `user_id` in its WHERE clause (verified by code review).
- [ ] Swapping a valid `trade_id` from User A's account into a request authenticated as User B does not produce a successful write.

---

### SR-JOUR-003 — Unauthorized journal entry access returns 404, not 403

**Component:** All journal GET and PUT endpoints  
**Threat:** Information Disclosure — a 403 confirms that the resource exists; a 404 does not  
**Priority:** High  
**Owner:** Bhima

**Requirement:**  
When a user requests a journal entry for a trade they do not own (trade not found in their account), the response must be HTTP 404 with a generic body. HTTP 403 must not be returned at any point in the journal entry access path.

**Acceptance Criteria:**
- [ ] GET `/v1/journal/trades/{trade_id}` for a `trade_id` that exists but belongs to another user returns `404 Not Found`.
- [ ] PUT `/v1/journal/trades/{trade_id}` for another user's trade returns `404 Not Found`.
- [ ] GET `/v1/journal/trades/{trade_id}/audit` for another user's trade returns `404 Not Found`.
- [ ] No journal endpoint returns `403 Forbidden` in any scenario.

---

### SR-JOUR-004 — Unauthorized attachment access returns 404, not 403

**Component:** All attachment endpoints (presign, confirm, delete)  
**Threat:** Information Disclosure — confirming attachment existence via 403  
**Priority:** High  
**Owner:** Bhima

**Requirement:**  
Attachment ownership is verified by requiring `user_id = :uid` in every attachment repository query. If the attachment does not exist for the requesting user — whether because the attachment does not exist at all or because it belongs to another user — the response must be HTTP 404. HTTP 403 must never be returned.

**Acceptance Criteria:**
- [ ] POST `/v1/journal/trades/{trade_id}/attachments/{att_id}/confirm` where `att_id` belongs to User B, authenticated as User A, returns 404.
- [ ] DELETE `/v1/journal/trades/{trade_id}/attachments/{att_id}` for another user's attachment returns 404.
- [ ] A brute-force scan of attachment UUIDs by a non-owning user reveals no 200 vs 403 distinction — all non-owned IDs return 404.
- [ ] Repository methods `get_pending_attachment` and `get_confirmed_attachment` include `user_id` in their WHERE clause (code review).

---

### SR-JOUR-005 — Journal entries are scoped to the owning user in all read queries

**Component:** `JournalRepository.get_entry`, `JournalRepository.get_audit_log`, `JournalRepository.list_confirmed_attachments`  
**Threat:** Broken Access Control (OWASP A01) — a horizontal IDOR via missing ownership filter  
**Priority:** Critical  
**Owner:** Bhima

**Requirement:**  
Every SELECT query on `journal_entries`, `journal_attachments`, and `journal_audit_log` that returns per-user data must include a `user_id = :uid` or `trade_id IN (SELECT id FROM trades WHERE user_id = :uid)` filter in the SQL WHERE clause. Post-retrieval ownership checks in application code are insufficient and must not be used as the primary control.

**Acceptance Criteria:**
- [ ] Code review confirms no repository method fetches a row by primary key alone (without `user_id` scope) and returns it to the service layer.
- [ ] A direct SQL query `SELECT * FROM journal_entries WHERE trade_id = :tid` (no user filter) returns a row. The same `trade_id` used in a journal GET request authenticated as the non-owning user returns 404 — demonstrating the application filter is doing the work.
- [ ] `list_confirmed_attachments` is called only after the owning journal entry has been retrieved with user scope — Arjun cannot fetch an attachment list for an arbitrary `journal_entry_id` without owning it.

---

## Part 2 — Journal Entry Input Validation

---

### SR-JOUR-006 — Numeric plan fields are validated server-side

**Component:** `JournalEntryRequest` Pydantic schema, `PUT /v1/journal/trades/{trade_id}`  
**Threat:** Injection, Denial of Service — malformed numeric values causing downstream arithmetic errors  
**Priority:** Medium  
**Owner:** Bhima

**Requirement:**  
`planned_entry`, `planned_stop`, and `planned_target` must be validated as positive decimal values by the API schema before any database write. Zero and negative values must be rejected with HTTP 422.

**Acceptance Criteria:**
- [ ] PUT with `planned_stop: -100` returns 422.
- [ ] PUT with `planned_stop: 0` returns 422.
- [ ] PUT with `planned_stop: "abc"` returns 422.
- [ ] PUT with `planned_stop: null` is accepted (field is optional).
- [ ] `planned_risk_amount` is never accepted from the client; it is always computed server-side and cannot be overridden via the request body.

---

### SR-JOUR-007 — Discipline score is bounded server-side

**Component:** `JournalEntryRequest` Pydantic schema  
**Threat:** Data integrity — out-of-range scores corrupting analytics  
**Priority:** Low  
**Owner:** Bhima

**Requirement:**  
`discipline_score` must be rejected unless it is an integer in the range [1, 10]. Values of 0, negative integers, integers above 10, floats, and strings must all return 422.

**Acceptance Criteria:**
- [ ] PUT with `discipline_score: 0` returns 422.
- [ ] PUT with `discipline_score: 11` returns 422.
- [ ] PUT with `discipline_score: 5.5` returns 422.
- [ ] PUT with `discipline_score: 7` returns 200.
- [ ] Database constraint `ck_journal_discipline_score` independently enforces the same range (verified by attempting a direct INSERT with score 11 — the DB rejects it).

---

### SR-JOUR-008 — Emotion and mistake fields only accept defined enum values

**Component:** `JournalEntry` DB model CHECK constraints, `PUT /v1/journal/trades/{trade_id}`  
**Threat:** Injection, Data Integrity  
**Priority:** Medium  
**Owner:** Bhima

**Requirement:**  
`emotion_before`, `emotion_during`, and `emotion_after` must only accept values from the `EmotionType` enum (10 values). `mistakes` array elements must only contain values from the `MistakeType` enum (13 values). Any other string value must be rejected.

**Acceptance Criteria:**
- [ ] PUT with `emotion_before: "EXCITED"` (not in enum) returns 422.
- [ ] PUT with `mistakes: ["FOMO_ENTRY", "INVALID_VALUE"]` returns 422.
- [ ] PUT with `emotion_before: "<script>alert(1)</script>"` returns 422.
- [ ] Database CHECK constraints on `emotion_before`, `emotion_during`, `emotion_after` reject invalid values independently of the API layer (verified by direct SQL INSERT).

---

### SR-JOUR-009 — change_reason has a bounded maximum length

**Component:** `JournalEntryRequest` Pydantic schema  
**Threat:** Denial of Service — unbounded text stored in the audit log  
**Priority:** Low  
**Owner:** Bhima

**Requirement:**  
`change_reason` must be limited to 500 characters. Requests supplying a longer value must be rejected with 422.

**Acceptance Criteria:**
- [ ] PUT with `change_reason` of 501 characters returns 422.
- [ ] PUT with `change_reason` of 500 characters returns 200 and the reason is stored.

---

## Part 3 — Audit Trail

---

### SR-JOUR-010 — All journal entry changes produce a field-level audit record

**Component:** `JournalService._diff_for_audit`, `JournalRepository.append_audit_entries`  
**Threat:** Repudiation — a user edits their journal post-trade to fabricate a better narrative; no record of the change survives  
**Priority:** High  
**Owner:** Bhima

**Requirement:**  
Every PUT to an *existing* journal entry must produce an audit log row in `journal_audit_log` for each field whose value changed. The audit row must capture `previous_value`, `new_value`, and `field_name`. Fields that did not change must not generate an audit row. First-time creates (no prior entry) do not require audit rows.

**Auditable fields:** `planned_entry`, `planned_stop`, `planned_target`, `setup_name`, `notes`, `discipline_score`, `mistakes`, `emotion_before`, `emotion_during`, `emotion_after`.

**Acceptance Criteria:**
- [ ] PUT that changes `setup_name` and `notes` (two fields) produces exactly two audit rows for that edit.
- [ ] PUT that submits the same values as the current entry (no actual change) produces zero audit rows.
- [ ] First-time PUT (entry does not exist yet) produces zero audit rows.
- [ ] Audit rows contain the correct `previous_value` and `new_value` (verified by reading `GET /v1/journal/trades/{trade_id}/audit` after each edit).
- [ ] `planned_risk_amount` is NOT audited (it is a derived field, not a user-supplied value).

---

### SR-JOUR-011 — The journal audit log is immutable at the database level

**Component:** `journal_audit_log` table, trigger `trg_audit_log_immutable`  
**Threat:** Tampering — application code or a compromised DB connection attempts to rewrite audit history  
**Priority:** Critical  
**Owner:** Bhima (trigger implementation), Nakula (DB user permissions)

**Requirement:**  
A PostgreSQL trigger on `journal_audit_log` must raise an exception on any `UPDATE` or `DELETE` statement targeting that table, regardless of which database role issues the command. The `tradeforge_app` database role must not be granted `DELETE` permission on `journal_audit_log` (the broad `GRANT` in the migration is intentional — the trigger is the enforcement layer, but Nakula must verify the role cannot `DELETE` in practice).

**Acceptance Criteria:**
- [ ] Direct SQL `UPDATE journal_audit_log SET new_value = 'tampered' WHERE id = :id` executed by any DB role raises a PostgreSQL exception containing the trigger's message.
- [ ] Direct SQL `DELETE FROM journal_audit_log WHERE id = :id` raises a PostgreSQL exception.
- [ ] The trigger fires for both `UPDATE` and `DELETE` — verified by testing each operation independently.
- [ ] Rows inserted via the application (`append_audit_entries`) succeed and are readable (INSERT is not blocked).
- [ ] Sahadeva confirms there is no API endpoint that can DELETE or UPDATE an audit row.

---

### SR-JOUR-012 — Attachment events are written to security_audit_log

**Component:** `JournalService._log_attachment_event`, `AuditLogRepository.log`  
**Threat:** Repudiation — no record of file upload, confirmation, or deletion  
**Priority:** High  
**Owner:** Bhima

**Requirement:**  
The following attachment lifecycle events must each produce a row in `security_audit_log`: presign requested, presign rejected (type), presign rejected (size/quota), upload confirmed, attachment deleted. Each row must record the `user_id`, `ip_address`, declared `content_type`, declared `byte_size`, and `attachment_id` (where available). These rows must be written by the application service layer, not by DB triggers, and must be visible to the security audit query interface.

**Acceptance Criteria:**
- [ ] After a successful presign, a `security_audit_log` row with `event_type = ATTACHMENT_PRESIGN_REQUESTED` exists and contains `trade_id`, `content_type`, and `byte_size`.
- [ ] After a rejected presign (disallowed type), a row with `event_type = ATTACHMENT_REJECTED_TYPE` exists.
- [ ] After a rejected presign (size exceeded), a row with `event_type = ATTACHMENT_REJECTED_SIZE` exists.
- [ ] After a successful confirm, a row with `event_type = ATTACHMENT_CONFIRMED` exists and contains `attachment_id`.
- [ ] After a successful delete, a row with `event_type = ATTACHMENT_DELETED` exists and contains `attachment_id`.
- [ ] `security_audit_log` rows for attachment events are never modifiable by the `tradeforge_app` role (this table is governed by SR-AUTH-018 immutability requirements).

---

## Part 4 — Attachment Security

---

### SR-ATT-001 — Content type allowlist

**Component:** `JournalService.presign_attachment`  
**Threat:** Information Disclosure, XSS — an attacker uploads an HTML, SVG, or script file that executes when served  
**Priority:** Critical  
**Owner:** Bhima (enforcement), Arjun (client-side accept filter, non-authoritative)

**Requirement:**  
Only four content types are permitted: `image/jpeg`, `image/png`, `image/webp`, `image/gif`. All other content types must be rejected with HTTP 422 before any presign URL is issued. SVG (`image/svg+xml`) is explicitly excluded because browsers execute SVG as HTML when served inline — it is an XSS vector regardless of file extension.

The allowlist check is enforced server-side. The frontend `<input accept>` attribute is UX guidance only and must not be treated as a security control.

**Acceptance Criteria:**
- [ ] POST presign with `content_type: "image/svg+xml"` returns 422 with a descriptive error.
- [ ] POST presign with `content_type: "text/html"` returns 422.
- [ ] POST presign with `content_type: "application/pdf"` returns 422.
- [ ] POST presign with `content_type: "image/jpeg"` proceeds to presign (returns 201 with `upload_url`).
- [ ] POST presign with `content_type: "image/png"` proceeds.
- [ ] POST presign with `content_type: "image/webp"` proceeds.
- [ ] POST presign with `content_type: "image/gif"` proceeds.
- [ ] A security audit log row is written for every rejected type attempt.

---

### SR-ATT-002 — Storage quotas enforced before presign

**Component:** `JournalService.presign_attachment`, `JournalRepository.sum_confirmed_bytes_for_trade`, `JournalRepository.sum_confirmed_bytes_for_user`  
**Threat:** Denial of Service — storage exhaustion via unlimited uploads  
**Priority:** High  
**Owner:** Bhima

**Requirement:**  
Three independent quota checks must all pass before a presign URL is issued:

| Scope | Limit |
|---|---|
| Per file (`byte_size` declared by client) | 15 MB |
| Per trade (sum of CONFIRMED bytes for this trade + new `byte_size`) | 75 MB |
| Per user (sum of CONFIRMED bytes across all trades + new `byte_size`) | 2 GB |

A `byte_size` of zero or negative must also be rejected (no empty-file uploads).

Quota sums count only **CONFIRMED** attachments — PENDING and EXPIRED attachments do not count toward quota.

**Acceptance Criteria:**
- [ ] POST presign with `byte_size: 15728641` (15 MB + 1 byte) returns 422.
- [ ] POST presign with `byte_size: 0` returns 422.
- [ ] POST presign with `byte_size: -1` returns 422.
- [ ] With 74 MB of confirmed attachments on a trade, a presign for a 2 MB file returns 422 (would exceed 75 MB trade limit).
- [ ] With exactly 75 MB of confirmed attachments, a presign for 1 byte returns 422.
- [ ] PENDING attachments do not count toward per-trade quota (a failed previous upload does not block future uploads).

---

### SR-ATT-003 — Filename sanitized; path traversal characters stripped

**Component:** `sanitize_filename()` in `domain/journal/types.py`  
**Threat:** Path Traversal (OWASP A05) — a crafted filename containing `../` could traverse directories if the filename were used in any storage path  
**Priority:** High  
**Owner:** Bhima

**Requirement:**  
The client-supplied filename must be sanitized before storage. The sanitized result is stored as display metadata only — it is never used in the S3 object key (see SR-ATT-005). Sanitization must strip: `/`, `\`, `:`, and any character outside word characters, whitespace, hyphens, and dots. Maximum stored length is 255 characters.

**Acceptance Criteria:**
- [ ] POST presign with `filename: "../../etc/passwd"` does not result in a stored filename containing `/`. The stored `filename` is `..etcpasswd` or equivalent — path separators removed.
- [ ] POST presign with `filename: "chart<script>.png"` stores `chartscript.png` — angle brackets stripped.
- [ ] POST presign with `filename` of 300 characters stores only the first 255.
- [ ] The S3 key stored in `journal_attachments.s3_key` is always `{user_id}/{trade_id}/{attachment_id}` — never contains any part of the client-supplied filename.

---

### SR-ATT-004 — S3 bucket is hardened; no public access

**Component:** S3 bucket configuration (Nakula owns implementation)  
**Threat:** Information Disclosure — public access to uploaded files bypasses all authorization controls  
**Priority:** Critical  
**Owner:** Nakula

**Requirement:**  
The S3 bucket storing journal attachments must be configured with:
1. **Block Public Access** — all four Block Public Access settings enabled at the bucket level.
2. **Server-Side Encryption** — SSE-KMS using a dedicated KMS key. Not SSE-S3.
3. **Server Access Logging** — enabled, logging to a separate audit bucket.
4. **No bucket policy granting public `s3:GetObject`** — objects must only be accessible via pre-signed URLs issued by the application.
5. **Versioning** — enabled (supports recovery if objects are overwritten, though the application never overwrites — new attachment_id per upload).

**Acceptance Criteria:**
- [ ] Attempting to `curl` a direct S3 object URL (without pre-signed params) returns `403 AccessDenied`.
- [ ] The bucket's Block Public Access settings are all set to `true` (verified via AWS Console or `aws s3api get-public-access-block`).
- [ ] The bucket's default encryption is SSE-KMS (verified via `aws s3api get-bucket-encryption`).
- [ ] Server access logs are being written to the audit bucket (verified by presence of log objects after a test upload).
- [ ] No bucket policy exists that grants `s3:GetObject` to `*` or `Principal: "*"`.

---

### SR-ATT-005 — S3 key is server-generated; client supplies only display metadata

**Component:** `build_s3_key()`, `JournalService.presign_attachment`  
**Threat:** Path Traversal, Spoofing — a client that can supply any part of the S3 key can overwrite another user's objects  
**Priority:** Critical  
**Owner:** Bhima

**Requirement:**  
The S3 object key must be composed entirely of server-controlled values: `{user_id}/{trade_id}/{attachment_id}`, where `attachment_id` is a UUID generated by the server. The client never supplies any component of this key. The client-supplied `filename` is stored in `journal_attachments.filename` as display metadata only and must not appear anywhere in the S3 key.

Additionally, the file extension in `filename` must match the declared `content_type` before the presign is issued (e.g., a file named `chart.png` with `content_type: image/jpeg` must be rejected).

**Acceptance Criteria:**
- [ ] POST presign with `filename: "chart.png"` and `content_type: "image/jpeg"` returns 422 — extension `.png` does not match JPEG allowed extensions (`.jpg`, `.jpeg`).
- [ ] POST presign with `filename: "chart.jpeg"` and `content_type: "image/jpeg"` succeeds.
- [ ] The `s3_key` returned in the presign response is of the format `{uuid}/{uuid}/{uuid}` — no filename, no user-supplied path.
- [ ] Two users uploading files with identical filenames get distinct S3 keys (UUID-based, no collision possible).
- [ ] Direct inspection of `journal_attachments.s3_key` confirms no row contains the client filename in the key value.

---

### SR-ATT-006 — Attachment ownership enforced in the repository WHERE clause; 404 returned on failure

**Component:** `JournalRepository.get_pending_attachment`, `JournalRepository.get_confirmed_attachment`  
**Threat:** Broken Access Control — horizontal IDOR on attachment records  
**Priority:** Critical  
**Owner:** Bhima

**Requirement:**  
All attachment repository reads must include `user_id = :uid` in the WHERE clause. If no row is returned (either the attachment does not exist or belongs to another user), the service must raise `AttachmentNotFoundError`, and the API must return HTTP 404. HTTP 403 must never be returned for attachment access failures.

**Acceptance Criteria:**
- [ ] User A presigns and confirms an attachment. User B's attempt to GET, confirm, or delete that `attachment_id` returns 404.
- [ ] The fact that an `attachment_id` exists in the database is not revealed to User B through any response code or timing difference.
- [ ] Code review confirms that no attachment query uses only `id = :att_id` without also filtering `user_id = :uid`.

---

### SR-ATT-007 — Pre-signed URLs enforce safe download and expire promptly

**Component:** `StubStorage` / production S3 implementation (Nakula), `service.py` TTL constants  
**Threat:** Information Disclosure — a long-lived or publicly cacheable URL leaks attachment content  
**Priority:** High  
**Owner:** Nakula (real S3 implementation), Bhima (TTL constants and condition requirements)

**Requirement:**  
Two distinct pre-signed URL types are issued:

**Upload URL (PUT):**
- TTL: 900 seconds (15 minutes)
- Must include a `Content-Type` condition matching the declared content type — S3 rejects uploads that do not match
- Must include a `content-length-range` condition: min 1 byte, max 15,728,640 bytes (15 MB) — S3 rejects uploads outside this range

**Download URL (GET):**
- TTL: 3600 seconds (1 hour)
- Must include `response-content-disposition=attachment; filename=<sanitized_filename>` — forces browser download, prevents inline rendering
- Must NOT include `response-content-type` that would cause browsers to render the content inline (no `text/html`, no `image/svg+xml`)

**Acceptance Criteria:**
- [ ] An upload URL that has been held for 901 seconds is rejected by S3 with `RequestExpired`.
- [ ] A download URL used after 3601 seconds is rejected by S3.
- [ ] A PUT to the upload URL with a `Content-Type` header that differs from the one used to generate the URL is rejected by S3 with a `SignatureDoesNotMatch` or condition-failure error.
- [ ] A PUT to the upload URL with a body larger than 15 MB is rejected by S3.
- [ ] Following a download URL in a browser triggers a file download dialog — the browser does not render the image inline at the pre-signed URL directly (i.e., `Content-Disposition: attachment` is in effect).
- [ ] The `download_url` response field is present only in CONFIRMED attachment responses — never in PENDING or EXPIRED states.

---

### SR-ATT-008 — HeadObject verifies upload before CONFIRM transitions to CONFIRMED

**Component:** `JournalService.confirm_attachment`, `StoragePort.head_object`  
**Threat:** Spoofing — a client calls the confirm endpoint without actually uploading to S3, gaining a CONFIRMED attachment record for a non-existent object  
**Priority:** High  
**Owner:** Bhima

**Requirement:**  
Before transitioning an attachment from `PENDING` to `CONFIRMED`, the application must call `head_object` on the S3 key. If `head_object` returns `None` (object does not exist), the attachment must be transitioned to `REJECTED` and the API must return 422. The server reads only the object's existence and metadata — it must never read the object body (no `get_object`, no streaming the content through the server).

**Acceptance Criteria:**
- [ ] POST confirm for an `attachment_id` whose S3 key does not exist returns 422 with an appropriate error. (In production; stub always returns success — this must be verified against the real S3 implementation.)
- [ ] After a failed HeadObject confirm, the `journal_attachments` row has `status = REJECTED` (not PENDING or CONFIRMED).
- [ ] Code review confirms that no application code calls `get_object` or reads S3 object content at any point in the attachment lifecycle.

---

### SR-ATT-009 — All attachment events are logged to security_audit_log

See **SR-JOUR-012** above. The same requirement is anchored here for the attachment surface.

**Additional attachment-specific criteria:**
- [ ] `ip_address` is present in every attachment audit event row.
- [ ] `user_id` is present in every attachment audit event row.
- [ ] The `attachment_id` is present in CONFIRMED and DELETED event rows (it is not available for REJECTED_TYPE events, since no attachment record is created).
- [ ] Audit events for attachment actions are not visible to the end user through any API response — they are internal security records only.

---

### SR-ATT-010 — PENDING attachments expire at 30 minutes (application) and 1 hour (S3 lifecycle)

**Component:** `JournalService.confirm_attachment` (application expiry); S3 bucket lifecycle rule (Nakula)  
**Threat:** Denial of Service via storage exhaustion from abandoned PENDING records; also information persistence beyond intent  
**Priority:** Medium  
**Owner:** Bhima (application check), Nakula (S3 lifecycle rule)

**Requirement:**  
**Application layer:** A PENDING attachment whose `created_at` is older than 30 minutes must be transitioned to `EXPIRED` by the confirm endpoint when the user attempts to confirm it. The application must not confirm an expired PENDING row; it must return 422.

**S3 layer:** An S3 lifecycle rule must delete objects tagged with `status=PENDING` (or objects under the journal prefix) that are older than 1 hour. This ensures that even if an application-layer expiry is missed, the S3 object itself is eventually cleaned up. The lifecycle rule TTL is intentionally longer than the application TTL to avoid racing with in-progress uploads.

**Acceptance Criteria:**
- [ ] POST confirm for an `attachment_id` whose `journal_attachments.created_at` is more than 30 minutes ago returns 422 with an expiry error.
- [ ] The `journal_attachments` row is transitioned to `EXPIRED` (not left as PENDING) when the 30-minute expiry triggers.
- [ ] The S3 lifecycle rule is present on the bucket (verified via `aws s3api get-bucket-lifecycle-configuration`).
- [ ] EXPIRED attachments do not appear in the journal entry GET response's attachment list.
- [ ] Calling confirm on an EXPIRED attachment (not just a timed-out PENDING) returns 404 (the row's status is EXPIRED, so `get_pending_attachment` returns None).

---

## Part 5 — P&L Data Boundary

---

### SR-JOUR-013 — The journal service must never write to trade_pnl

**Component:** `JournalService`, `JournalRepository`  
**Threat:** Data Integrity — the journal service inadvertently corrupts the P&L engine's outputs, which are owned exclusively by Step 10  
**Priority:** High  
**Owner:** Bhima

**Requirement:**  
`JournalService` and `JournalRepository` must contain no INSERT, UPDATE, or DELETE statements targeting the `trade_pnl` table. The journal reads `trade_pnl` via a LEFT JOIN (to determine `pnl_status`) but must never write to it. This boundary must be enforced by convention, code review, and — once Step 10 is built — by a separate database role with SELECT-only access to `trade_pnl` for the journal application path.

**Acceptance Criteria:**
- [ ] Code review of `JournalRepository` confirms zero occurrences of `trade_pnl` in INSERT, UPDATE, or DELETE statements.
- [ ] Code review of `JournalService` confirms it calls no repository method that would write to `trade_pnl`.
- [ ] The `trade_pnl` table is described in the migration as "owned by Step 10 P&L engine only" — this architectural note remains in the migration file and is not removed.
- [ ] After running all Step 9 journal tests (unit + integration), the `trade_pnl` table contains zero rows (the table was created empty and nothing wrote to it).

---

## Part 6 — Sahadeva Acceptance Gate

Before the journal feature may be released, Sahadeva must confirm:

- [ ] **Authorization:** Cross-user IDOR tests pass for journal entries (SR-JOUR-002, SR-JOUR-003) and attachments (SR-JOUR-004, SR-JOUR-006) — both GET and PUT paths.
- [ ] **Audit log:** Journal edits produce correct audit rows (SR-JOUR-010); the immutability trigger blocks UPDATE and DELETE (SR-JOUR-011).
- [ ] **Content type:** SVG and all non-image types are rejected at presign (SR-ATT-001).
- [ ] **Quotas:** Per-file 15 MB limit enforced (SR-ATT-002); zero-byte files rejected.
- [ ] **Filename safety:** Path traversal characters stripped from stored filename; S3 key contains no filename component (SR-ATT-003, SR-ATT-005).
- [ ] **Extension mismatch:** `.png` file with `image/jpeg` content_type rejected (SR-ATT-005).
- [ ] **PENDING expiry:** Confirm on a 31-minute-old PENDING returns 422 and sets status to EXPIRED (SR-ATT-010).
- [ ] **P&L boundary:** After all tests, `trade_pnl` table is empty (SR-JOUR-013).
- [ ] **Attachment events:** `security_audit_log` contains events for each presign, confirm, and delete action (SR-JOUR-012 / SR-ATT-009).
- [ ] **No 403 responses:** A grep of the journal API routes and service confirms zero `403` status codes are ever returned (SR-JOUR-003, SR-JOUR-004, SR-ATT-006).

Hanuman will review Sahadeva's test report before release approval.

---

## Appendix — Requirement to Implementation Map

| Requirement | Where enforced |
|---|---|
| SR-JOUR-001 | `api/v1/deps.py:get_current_user_id` |
| SR-JOUR-002 | `application/journal/service.py:upsert_entry`, `presign_attachment` |
| SR-JOUR-003 | `domain/journal/errors.py:TradeNotFoundError`, `api/v1/journal.py` |
| SR-JOUR-004 | `domain/journal/errors.py:AttachmentNotFoundError`, `api/v1/journal.py` |
| SR-JOUR-005 | `infrastructure/repositories/journal_repo.py` (all SELECT methods) |
| SR-JOUR-006 | `api/v1/journal.py:JournalEntryRequest` (Pydantic `gt=0`) |
| SR-JOUR-007 | `api/v1/journal.py:JournalEntryRequest` (`ge=1, le=10`) |
| SR-JOUR-008 | `infrastructure/models/journal.py` CHECK constraints |
| SR-JOUR-009 | `api/v1/journal.py:JournalEntryRequest` (`max_length=500`) |
| SR-JOUR-010 | `application/journal/service.py:_diff_for_audit` |
| SR-JOUR-011 | `alembic/versions/0004_journal_tables.py` (trigger) |
| SR-JOUR-012 | `application/journal/service.py:_log_attachment_event` |
| SR-JOUR-013 | Convention + code review; DB role restriction in Step 10 |
| SR-ATT-001 | `domain/journal/types.py:ALLOWED_CONTENT_TYPES`, `service.py:presign_attachment` |
| SR-ATT-002 | `domain/journal/types.py` constants, `service.py:presign_attachment` |
| SR-ATT-003 | `domain/journal/types.py:sanitize_filename` |
| SR-ATT-004 | S3 bucket configuration (Nakula) |
| SR-ATT-005 | `domain/journal/types.py:build_s3_key`, `filename_extension_matches` |
| SR-ATT-006 | `infrastructure/repositories/journal_repo.py` (WHERE user_id) |
| SR-ATT-007 | `application/journal/storage.py:StoragePort` (production implementation by Nakula) |
| SR-ATT-008 | `application/journal/service.py:confirm_attachment` |
| SR-ATT-009 | `application/journal/service.py:_log_attachment_event` |
| SR-ATT-010 | `service.py:confirm_attachment` (app check); S3 lifecycle rule (Nakula) |
