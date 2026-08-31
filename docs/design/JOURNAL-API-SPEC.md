# Journal API Specification

**Status:** Authoritative — binding on Arjun (frontend) and Bhima (backend)
**Author:** Bhima (Backend Engineer) · reviewed by Mayasura (ADR-003)
**Domain authority:** Ganesha (JOURNAL-DOMAIN-RULES.md — G1)
**Security authority:** Hanuman (JOURNAL-SECURITY-REQUIREMENTS.md — G4)
**Date:** 2026-08-23
**Base URL:** `/v1/journal`
**OpenAPI tag:** `journal`

---

## Overview

The Journal API is a REST API over the journal annotation layer. It provides six endpoints covering: reading a journal entry, writing (upsert) a journal entry, reading the audit history, and the three-step attachment lifecycle (presign, confirm, delete).

**Authentication:** Every endpoint requires an authenticated session cookie (`session_token`, HttpOnly, Secure, SameSite=Strict). Unauthenticated requests receive `401 Unauthorized`. The session is verified against Redis per ADR-002. If Redis is unavailable, all endpoints return `503 Service Unavailable`.

**Authorization model:** `user_id` is extracted from the session by `get_current_user_id()`. It is never accepted from the request body, URL parameters, or query strings. All database queries include `user_id` in the WHERE clause. Requests for resources that do not belong to the authenticated user return `404 Not Found` (not `403 Forbidden`) to prevent resource existence disclosure.

**Error envelope:** All error responses use the standard FastAPI error envelope:
```json
{
  "detail": "Human-readable error message"
}
```
Validation errors from Pydantic use FastAPI's default 422 structure with a `detail` array.

**Decimal serialization:** All `Decimal` fields are serialized as JSON strings (not numbers) to preserve precision. Clients must parse these as Decimal or BigDecimal types — never as IEEE 754 floats.

**Timestamp format:** All timestamps are ISO 8601 with UTC timezone suffix, e.g. `"2026-08-23T04:15:00.000000+00:00"`.

---

## Shared Types

These types appear in multiple endpoint contracts.

### `PnlSnapshotOut`

Returned nested inside `JournalEntryOut`. `PnlStatus` is computed at read time — never stored.

| Field | Type | Always present | Notes |
|---|---|---|---|
| `status` | `string` | Yes | `PENDING_STOP` \| `PENDING_CALCULATION` \| `AVAILABLE` |
| `net_pnl` | `string` (Decimal) \| `null` | Yes | Non-null only when `status = AVAILABLE` |
| `gross_pnl` | `string` (Decimal) \| `null` | Yes | Non-null only when `status = AVAILABLE` |
| `total_charges` | `string` (Decimal) \| `null` | Yes | Non-null only when `status = AVAILABLE` |
| `r_multiple` | `string` (Decimal) \| `null` | Yes | Non-null only when `status = AVAILABLE` and `planned_stop` was set |

**PnlStatus semantics:**

| Status | Condition |
|---|---|
| `PENDING_STOP` | `planned_stop` is null — 1R cannot be defined |
| `PENDING_CALCULATION` | `planned_stop` is set, but no `trade_pnl` row exists yet |
| `AVAILABLE` | A `trade_pnl` row exists for this trade |

### `AttachmentOut`

Represents a confirmed attachment returned inside `JournalEntryOut.attachments`.

| Field | Type | Always present | Notes |
|---|---|---|---|
| `id` | `string` (UUID) | Yes | |
| `filename` | `string` | Yes | Sanitized display name. May be empty string. |
| `content_type` | `string` | Yes | One of the four allowed types |
| `byte_size` | `integer` | Yes | Bytes |
| `capture_moment` | `string` | Yes | `AT_ENTRY` \| `DURING_TRADE` \| `AT_EXIT` \| `POST_REVIEW` |
| `caption` | `string` \| `null` | Yes | |
| `status` | `string` | Yes | Always `CONFIRMED` in this response |
| `download_url` | `string` \| `null` | Yes | Pre-signed S3 GET URL, valid for 3600 seconds. Null when StubStorage is active in development. |
| `confirmed_at` | `string` (ISO 8601) \| `null` | Yes | |
| `created_at` | `string` (ISO 8601) | Yes | |

### `JournalEntryOut`

The full journal entry response shape, returned by `GET` and `PUT`.

| Field | Type | Always present | Notes |
|---|---|---|---|
| `id` | `string` (UUID) | Yes | Journal entry ID |
| `trade_id` | `string` (UUID) | Yes | Parent trade ID |
| `planned_entry` | `string` (Decimal) \| `null` | Yes | |
| `planned_stop` | `string` (Decimal) \| `null` | Yes | |
| `planned_target` | `string` (Decimal) \| `null` | Yes | |
| `planned_risk_amount` | `string` (Decimal) \| `null` | Yes | Derived — see G1 Rule 2.4 |
| `setup_name` | `string` \| `null` | Yes | Max 100 chars |
| `notes` | `string` \| `null` | Yes | Free text |
| `discipline_score` | `integer` \| `null` | Yes | [1, 10] or null |
| `mistakes` | `string[]` | Yes | Array of `MistakeType` values; empty array when none |
| `emotion_before` | `string` \| `null` | Yes | `EmotionType` value or null |
| `emotion_during` | `string` \| `null` | Yes | `EmotionType` value or null |
| `emotion_after` | `string` \| `null` | Yes | `EmotionType` value or null |
| `pnl` | `PnlSnapshotOut` | Yes | Nested P&L snapshot |
| `attachments` | `AttachmentOut[]` | Yes | CONFIRMED, non-deleted attachments only. Empty array when none. |
| `created_at` | `string` (ISO 8601) | Yes | |
| `updated_at` | `string` (ISO 8601) | Yes | |

---

## Enum Reference

### `EmotionType`

Allowed values for `emotion_before`, `emotion_during`, `emotion_after`:

`CALM` · `CONFIDENT` · `ANXIOUS` · `FEARFUL` · `GREEDY` · `FRUSTRATED` · `EUPHORIC` · `BORED` · `DISTRACTED` · `NEUTRAL`

### `MistakeType`

Allowed values for elements of the `mistakes` array:

`FOMO_ENTRY` · `FOMO_EXIT` · `OVERSIZED_POSITION` · `NO_STOP_DEFINED` · `MOVED_STOP_WIDER` · `CUT_WINNER_EARLY` · `HELD_THROUGH_STOP` · `REVENGE_TRADE` · `AVERAGING_DOWN` · `ENTRY_TOO_EARLY` · `ENTRY_TOO_LATE` · `IGNORED_SIGNAL` · `DISTRACTED`

### `CaptureMoment`

Allowed values for `capture_moment` in attachment requests:

`AT_ENTRY` · `DURING_TRADE` · `AT_EXIT` · `POST_REVIEW`

### Allowed Content Types

Allowed values for `content_type` in attachment presign requests:

`image/jpeg` · `image/png` · `image/webp` · `image/gif`

SVG (`image/svg+xml`) is permanently excluded (XSS vector per SR-ATT-001).

---

## Endpoints

---

### 1. Get Journal Entry

Retrieves the journal entry for a trade. If no entry exists for this trade, returns `404`.

```
GET /v1/journal/trades/{trade_id}
```

#### Path Parameters

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `trade_id` | UUID | Yes | The trade whose journal entry to retrieve |

#### Request Body

None.

#### Response — `200 OK`

Returns `JournalEntryOut`.

```json
{
  "id": "a1b2c3d4-0000-0000-0000-000000000001",
  "trade_id": "a1b2c3d4-0000-0000-0000-000000000002",
  "planned_entry": "251.5000",
  "planned_stop": "248.0000",
  "planned_target": "260.0000",
  "planned_risk_amount": "1400.0000",
  "setup_name": "VWAP Reclaim",
  "notes": "Strong opening gap with volume confirmation. Entry on VWAP reclaim after 10-min consolidation.",
  "discipline_score": 8,
  "mistakes": [],
  "emotion_before": "CONFIDENT",
  "emotion_during": "CALM",
  "emotion_after": "CALM",
  "pnl": {
    "status": "PENDING_CALCULATION",
    "net_pnl": null,
    "gross_pnl": null,
    "total_charges": null,
    "r_multiple": null
  },
  "attachments": [
    {
      "id": "a1b2c3d4-0000-0000-0000-000000000003",
      "filename": "entry_screenshot.png",
      "content_type": "image/png",
      "byte_size": 245760,
      "capture_moment": "AT_ENTRY",
      "caption": "5-min chart at entry",
      "status": "CONFIRMED",
      "download_url": "https://s3.amazonaws.com/...?X-Amz-Expires=3600&...",
      "confirmed_at": "2026-08-23T04:15:00.000000+00:00",
      "created_at": "2026-08-23T04:14:30.000000+00:00"
    }
  ],
  "created_at": "2026-08-23T04:10:00.000000+00:00",
  "updated_at": "2026-08-23T04:15:00.000000+00:00"
}
```

#### Error Responses

| Status | Condition |
|---|---|
| `401` | No valid session cookie |
| `404` | No journal entry exists for this `trade_id`, or the trade does not exist / is not owned by the authenticated user |
| `503` | Redis unavailable |

#### Security Notes

- SR-JOUR-001: `user_id` from session only
- SR-JOUR-003: unauthorized or non-existent returns `404`, not `403`
- SR-JOUR-005: `JournalRepository.get_entry()` includes `user_id` in WHERE

---

### 2. Upsert Journal Entry

Creates or updates the journal entry for a trade. If no entry exists, creates one. If an entry exists, replaces its fields with the request body values. Uses **full-replacement semantics**: every field not present in the request body is stored as `null`.

```
PUT /v1/journal/trades/{trade_id}
Content-Type: application/json
```

#### Path Parameters

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `trade_id` | UUID | Yes | The trade whose journal entry to create or update |

#### Request Body

`JournalEntryRequest` — all fields are optional.

| Field | Type | Required | Validation | Notes |
|---|---|---|---|---|
| `planned_entry` | `number` (Decimal) \| `null` | No | `> 0` if supplied | Intended entry price. See G1 Rule 2.2. |
| `planned_stop` | `number` (Decimal) \| `null` | No | `> 0` if supplied | Intended stop loss. Triggers `planned_risk_amount` computation. |
| `planned_target` | `number` (Decimal) \| `null` | No | `> 0` if supplied | Intended target price. |
| `setup_name` | `string` \| `null` | No | Max 100 chars | User-defined setup label. |
| `notes` | `string` \| `null` | No | No length limit | Free-form post-trade reflection. |
| `discipline_score` | `integer` \| `null` | No | [1, 10] inclusive | See G1 Rule 2.5. |
| `mistakes` | `string[]` \| `null` | No | Each element must be a `MistakeType` value | See G1 Rule 2.6. |
| `emotion_before` | `string` \| `null` | No | Must be an `EmotionType` value if supplied | See G1 Rule 2.7. |
| `emotion_during` | `string` \| `null` | No | Must be an `EmotionType` value if supplied | See G1 Rule 2.7. |
| `emotion_after` | `string` \| `null` | No | Must be an `EmotionType` value if supplied | See G1 Rule 2.7. |
| `change_reason` | `string` \| `null` | No | Max 500 chars | Recorded in audit log for each changed field. Not stored in the entry. See G1 Rule 2.8. |

Unknown fields in the request body are rejected (`extra = "forbid"` in Pydantic model config).

**Example request:**
```json
{
  "planned_entry": "251.5000",
  "planned_stop": "248.0000",
  "planned_target": "260.0000",
  "setup_name": "VWAP Reclaim",
  "notes": "Strong opening gap with volume confirmation.",
  "discipline_score": 8,
  "mistakes": [],
  "emotion_before": "CONFIDENT",
  "emotion_during": "CALM",
  "emotion_after": "CALM",
  "change_reason": null
}
```

#### Response — `200 OK`

Returns `JournalEntryOut` (same shape as GET). The response reflects the state of the entry immediately after the write, including the freshly computed `planned_risk_amount` and `PnlStatus`.

#### Upsert Semantics

- If no entry exists for `(trade_id, authenticated_user_id)`: creates a new entry with the supplied fields; no audit log rows are generated.
- If an entry already exists: updates it. Generates one `journal_audit_log` row per field that changed (old value → new value). Fields that did not change produce no audit row.

#### Error Responses

| Status | Condition |
|---|---|
| `401` | No valid session cookie |
| `404` | The `trade_id` does not exist or is not owned by the authenticated user (SR-JOUR-002) |
| `422` | Validation failure — `planned_entry/stop/target` ≤ 0; `discipline_score` out of [1,10]; unknown `emotion_*` value; unknown `mistakes` element; `setup_name` > 100 chars; `change_reason` > 500 chars; extra fields in body |
| `503` | Redis unavailable |

#### Security Notes

- SR-JOUR-001: `user_id` from session only
- SR-JOUR-002: trade ownership verified via `get_trade_snapshot(trade_id, user_id)` in WHERE clause
- SR-JOUR-006: `planned_entry/stop/target` must be `> 0` (positive, non-zero)
- SR-JOUR-007: `discipline_score` [1, 10]
- SR-JOUR-008: emotion values and mistake values validated against enums
- SR-JOUR-009: `change_reason` ≤ 500 chars
- SR-JOUR-010: per-field audit rows written for changed fields only

---

### 3. Get Audit History

Returns the complete audit history for the journal entry attached to a trade, ordered chronologically (oldest first). Each row represents one field change on one specific update call.

```
GET /v1/journal/trades/{trade_id}/audit
```

#### Path Parameters

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `trade_id` | UUID | Yes | |

#### Request Body

None.

#### Response — `200 OK`

Returns an array of audit entries, ordered by `changed_at` ascending. Empty array if the entry was created but never updated, or if no entry exists.

```json
[
  {
    "id": "a1b2c3d4-0000-0000-0000-000000000010",
    "field_name": "planned_stop",
    "previous_value": "245.0000",
    "new_value": "248.0000",
    "change_reason": "Adjusted stop to below the morning low",
    "changed_at": "2026-08-23T05:30:00.000000+00:00"
  },
  {
    "id": "a1b2c3d4-0000-0000-0000-000000000011",
    "field_name": "discipline_score",
    "previous_value": null,
    "new_value": "8",
    "change_reason": null,
    "changed_at": "2026-08-23T06:00:00.000000+00:00"
  }
]
```

#### Audit Entry Fields

| Field | Type | Notes |
|---|---|---|
| `id` | `string` (UUID) | Audit row ID |
| `field_name` | `string` | Name of the changed field (e.g. `"planned_stop"`) |
| `previous_value` | `string` \| `null` | Old value serialized to string; null if field was previously unset |
| `new_value` | `string` \| `null` | New value serialized to string; null if field was cleared |
| `change_reason` | `string` \| `null` | The `change_reason` from the request that caused this change |
| `changed_at` | `string` (ISO 8601) | UTC timestamp of the write |

**Auditable fields:** `planned_entry`, `planned_stop`, `planned_target`, `setup_name`, `notes`, `discipline_score`, `mistakes`, `emotion_before`, `emotion_during`, `emotion_after`.

**Array serialization in audit:** `mistakes` values are serialized as comma-separated strings, e.g. `"FOMO_ENTRY,HELD_THROUGH_STOP"`. An empty array serializes as `""` (empty string). Null serializes as SQL NULL (shown as `null` in JSON).

#### Error Responses

| Status | Condition |
|---|---|
| `401` | No valid session cookie |
| `404` | No journal entry exists for this `trade_id` / not owned by the authenticated user |
| `503` | Redis unavailable |

#### Security Notes

- SR-JOUR-001: `user_id` from session only
- SR-JOUR-011: `journal_audit_log` rows are immutable — this endpoint is read-only

---

### 4. Presign Attachment Upload

Step 1 of the two-step attachment upload flow. Validates the attachment metadata, creates a PENDING attachment row, and returns a pre-signed S3 PUT URL for the client to upload directly to S3.

The application server never receives or handles file bytes.

```
POST /v1/journal/trades/{trade_id}/attachments/presign
Content-Type: application/json
```

#### Path Parameters

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `trade_id` | UUID | Yes | |

#### Request Body

`PresignRequest` — all fields except `caption` are required.

| Field | Type | Required | Validation | Notes |
|---|---|---|---|---|
| `filename` | `string` | Yes | 1–255 chars | Client-supplied display name. Sanitized server-side (path separators and unsafe chars stripped). |
| `content_type` | `string` | Yes | Must be one of the four allowed types | `image/jpeg`, `image/png`, `image/webp`, `image/gif` only. SVG rejected. |
| `byte_size` | `integer` | Yes | `> 0`, `≤ 15,728,640` (15 MB) | Declared file size in bytes. |
| `capture_moment` | `string` | Yes | Must be a `CaptureMoment` value | `AT_ENTRY` \| `DURING_TRADE` \| `AT_EXIT` \| `POST_REVIEW` |
| `caption` | `string` \| `null` | No | Max 500 chars | Optional short label for the attachment. |

Unknown fields in the request body are rejected.

**Example request:**
```json
{
  "filename": "entry_screenshot.png",
  "content_type": "image/png",
  "byte_size": 245760,
  "capture_moment": "AT_ENTRY",
  "caption": "5-min chart at entry"
}
```

#### Server-Side Validation Sequence (in order)

1. Content type check against allowlist (SR-ATT-001)
2. `byte_size > 0` and `byte_size ≤ 15 MB` (SR-ATT-002)
3. Filename extension matches declared `content_type` (SR-ATT-005)
4. Trade ownership check — `SELECT ... WHERE id = trade_id AND user_id = session_user_id` (SR-ATT-006)
5. Per-trade quota: sum of CONFIRMED bytes for this trade + `byte_size` ≤ 75 MB (SR-ATT-002)
6. Per-user quota: sum of CONFIRMED bytes for this user + `byte_size` ≤ 2 GB (SR-ATT-002)

The server creates the PENDING attachment row and the presign URL only after all six checks pass.

**Side effect:** If no journal entry exists for this trade, a blank journal entry (all fields null) is created as a side effect. This ensures the attachment has a valid `journal_entry_id` foreign key.

#### Response — `201 Created`

```json
{
  "attachment_id": "a1b2c3d4-0000-0000-0000-000000000020",
  "upload_url": "https://s3.amazonaws.com/bucket/{user_id}/{trade_id}/{attachment_id}?X-Amz-Signature=...&X-Amz-Expires=900&...",
  "s3_key": "{user_id}/{trade_id}/{attachment_id}",
  "expires_in_seconds": 900
}
```

| Field | Type | Notes |
|---|---|---|
| `attachment_id` | `string` (UUID) | Server-generated. Use this as `attachment_id` in the confirm endpoint. |
| `upload_url` | `string` | Pre-signed S3 PUT URL. Valid for 900 seconds (15 minutes). |
| `s3_key` | `string` | The S3 object key. Included for client logging/debugging; the client does not need to use it for the upload or confirm call. |
| `expires_in_seconds` | `integer` | Always 900. |

#### Upload Instructions for the Client

After receiving this response, the client must PUT the raw file bytes to `upload_url`:

```
PUT {upload_url}
Content-Type: {the content_type declared in the presign request}
Body: raw file bytes
```

The `Content-Type` header on the S3 PUT **must match** the `content_type` declared in the presign request. S3's presign URL includes a `Content-Type` condition; a mismatch causes S3 to reject the upload with `403 Forbidden`.

The maximum body size is `byte_size` as declared. S3's `content-length-range` condition rejects uploads smaller than 1 byte or larger than 15 MB.

After the S3 PUT succeeds (S3 returns `200 OK`), the client calls the confirm endpoint.

#### Error Responses

| Status | Condition |
|---|---|
| `401` | No valid session cookie |
| `404` | `trade_id` not found or not owned by the authenticated user |
| `422` | Content type not in allowlist; `byte_size` ≤ 0 or > 15 MB; filename extension does not match `content_type`; per-trade or per-user storage quota would be exceeded; unknown `capture_moment`; `caption` > 500 chars; extra fields in body |
| `503` | Redis unavailable |

#### Security Notes

- SR-ATT-001: Content type allowlist enforced before presign; rejected content types logged to `security_audit_log`
- SR-ATT-002: File size and storage quota enforced before presign; quota violations logged
- SR-ATT-003: `filename` sanitized server-side; stored as display metadata only
- SR-ATT-005: S3 key is `{user_id}/{trade_id}/{attachment_id}` — server-generated, client never supplies
- SR-ATT-006: Trade ownership verified in SQL WHERE clause; missing/unauthorized → 404
- SR-ATT-007: Upload URL TTL is 900 seconds with `Content-Type` condition + `content-length-range(1, 15728640)` condition
- SR-ATT-009: `ATTACHMENT_PRESIGN_REQUESTED` and rejection events logged to `security_audit_log`

---

### 5. Confirm Attachment Upload

Step 3 of the two-step attachment upload flow (step 2 is the direct S3 upload by the client). Verifies the upload completed, transitions the attachment from PENDING to CONFIRMED, and returns the confirmed attachment with a download URL.

```
POST /v1/journal/trades/{trade_id}/attachments/{attachment_id}/confirm
```

#### Path Parameters

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `trade_id` | UUID | Yes | Used for routing clarity but attachment ownership is verified via `attachment_id` + `user_id` |
| `attachment_id` | UUID | Yes | The `attachment_id` returned by the presign endpoint |

#### Request Body

None.

#### Server-Side Processing

1. Load the PENDING attachment by `(attachment_id, user_id)`. Returns `404` if not found, already confirmed, expired, or rejected.
2. Check age: if the attachment was created more than 30 minutes ago, mark it EXPIRED and return `422`. (SR-ATT-010)
3. Call `StoragePort.head_object(s3_key)`. Returns object metadata dict, or `None` if the object does not exist.
4. If `head_object` returns `None`: mark attachment REJECTED, log `ATTACHMENT_CONFIRM_FAILED` to `security_audit_log`, return `404`.
5. If `head_object` succeeds: mark attachment CONFIRMED, set `confirmed_at = now()`, log `ATTACHMENT_CONFIRMED` to `security_audit_log`.
6. Generate and return a pre-signed download URL (TTL 3600 seconds, `Content-Disposition: attachment`).

#### Response — `200 OK`

```json
{
  "id": "a1b2c3d4-0000-0000-0000-000000000020",
  "filename": "entry_screenshot.png",
  "content_type": "image/png",
  "byte_size": 245760,
  "status": "CONFIRMED",
  "download_url": "https://s3.amazonaws.com/...?X-Amz-Expires=3600&response-content-disposition=attachment%3Bfilename%3Dentry_screenshot.png&...",
  "confirmed_at": "2026-08-23T04:15:00.000000+00:00"
}
```

| Field | Type | Notes |
|---|---|---|
| `id` | `string` (UUID) | Attachment ID |
| `filename` | `string` | Sanitized display filename |
| `content_type` | `string` | |
| `byte_size` | `integer` | |
| `status` | `string` | Always `CONFIRMED` in this response |
| `download_url` | `string` \| `null` | Pre-signed S3 GET URL, valid for 3600 seconds. Null in development with StubStorage. |
| `confirmed_at` | `string` (ISO 8601) \| `null` | UTC timestamp of confirmation |

#### Error Responses

| Status | Condition |
|---|---|
| `401` | No valid session cookie |
| `404` | Attachment not found, not in PENDING status, not owned by the authenticated user, or S3 HeadObject returned no object (upload did not complete) |
| `422` | Attachment is PENDING but was created more than 30 minutes ago (expired upload window) |
| `503` | Redis unavailable |

**Note on 404 vs. 422 for expired:** A PENDING attachment older than 30 minutes returns `422` (not `404`) because the resource exists and the specific issue is a time constraint violation, not missing ownership. This gives the client a recoverable error — it can tell the user "the upload window expired, please try again" rather than "attachment not found."

#### Security Notes

- SR-ATT-006: Attachment lookup includes `user_id` in WHERE clause; missing/unauthorized → 404
- SR-ATT-008: `HeadObject` called; if object absent → status set to REJECTED, return 404 (server never reads object body)
- SR-ATT-009: `ATTACHMENT_CONFIRMED` or `ATTACHMENT_CONFIRM_FAILED` logged to `security_audit_log`
- SR-ATT-010: PENDING expiry checked at 30 minutes; PENDING window enforced application-side; S3 lifecycle rule cleans orphaned objects at 1 hour

---

### 6. Delete Attachment

Soft-deletes a confirmed attachment. The attachment row is retained permanently in the database (audit trail). The underlying S3 object is not deleted by this endpoint; S3 object retention is governed by bucket policy and versioning (Nakula responsibility).

```
DELETE /v1/journal/trades/{trade_id}/attachments/{attachment_id}
```

#### Path Parameters

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `trade_id` | UUID | Yes | |
| `attachment_id` | UUID | Yes | Must be a CONFIRMED, non-deleted attachment |

#### Request Body

None.

#### Response — `204 No Content`

No response body. The attachment is now excluded from all future `GET /v1/journal/trades/{trade_id}` responses.

#### Error Responses

| Status | Condition |
|---|---|
| `401` | No valid session cookie |
| `404` | Attachment not found, not in CONFIRMED status, already soft-deleted, or not owned by the authenticated user |
| `503` | Redis unavailable |

#### Security Notes

- SR-ATT-006: Attachment lookup includes `user_id` in WHERE clause; missing/unauthorized → 404
- SR-ATT-009: `ATTACHMENT_DELETED` event logged to `security_audit_log` with `user_id`, `ip_address`, `content_type`, `byte_size`, `attachment_id`

---

## Error Response Reference

### Validation error format (422)

```json
{
  "detail": [
    {
      "type": "greater_than",
      "loc": ["body", "planned_stop"],
      "msg": "Input should be greater than 0",
      "input": "-5",
      "ctx": {"gt": 0}
    }
  ]
}
```

### Domain error format (404, 422 from service layer)

```json
{
  "detail": "Attachment a1b2c3d4-... not found or has expired"
}
```

### Session / auth errors

| Status | Body |
|---|---|
| `401` | `{"detail": "Not authenticated"}` |
| `503` | `{"detail": "Service temporarily unavailable"}` |

---

## Complete Endpoint Summary

| Method | Path | Auth | Status codes | Description |
|---|---|---|---|---|
| `GET` | `/v1/journal/trades/{trade_id}` | Session | 200, 401, 404, 503 | Get journal entry |
| `PUT` | `/v1/journal/trades/{trade_id}` | Session | 200, 401, 404, 422, 503 | Upsert journal entry (full replace) |
| `GET` | `/v1/journal/trades/{trade_id}/audit` | Session | 200, 401, 404, 503 | Get audit history |
| `POST` | `/v1/journal/trades/{trade_id}/attachments/presign` | Session | 201, 401, 404, 422, 503 | Request upload URL |
| `POST` | `/v1/journal/trades/{trade_id}/attachments/{attachment_id}/confirm` | Session | 200, 401, 404, 422, 503 | Confirm upload |
| `DELETE` | `/v1/journal/trades/{trade_id}/attachments/{attachment_id}` | Session | 204, 401, 404, 503 | Soft-delete attachment |

---

## Implementation Notes for Bhima

1. **`extra = "forbid"` on all request models.** Unknown fields in the request body must return 422, not be silently ignored. This is already set on `JournalEntryRequest` and `PresignRequest`.

2. **Commit responsibility.** The `PUT`, `POST .../presign`, `POST .../confirm`, and `DELETE` routes call `await db.commit()` after the service call. The `GET` routes do not commit (read-only). Do not commit inside the service or repository — commit in the route handler.

3. **IP extraction.** Use `get_client_ip(request)` (defined in `api/v1/deps.py`) to extract the client IP for `security_audit_log` events. This dependency reads the `X-Forwarded-For` header or falls back to `request.client.host`.

4. **Pydantic model for Decimal fields.** `planned_entry`, `planned_stop`, `planned_target`, and `planned_risk_amount` are `Decimal | None` in the Pydantic models. FastAPI serializes Decimal as a string in JSON by default when `model_config = {"json_encoders": {Decimal: str}}` is set, or when using Pydantic v2 with `Decimal` as the field type. Verify the serialized output is a string, not a float.

5. **Timestamp serialization.** Datetime objects must serialize with timezone suffix. Use `dt.isoformat()` — not `str(dt)`. All datetimes stored in PostgreSQL are `TIMESTAMPTZ` in UTC.

---

## Implementation Notes for Arjun

1. **Full-replacement semantics.** On every `PUT /v1/journal/trades/{trade_id}`, send all fields the user wants retained. Fields omitted from the request body are stored as `null`. Initialize the form from the `GET` response before showing it to the user. See ADR-003 Decision 3.

2. **Download URLs expire.** The `download_url` in `AttachmentOut` is valid for 3600 seconds from when the response was received. Do not cache or store it between navigation events. Re-fetch the journal entry to get fresh URLs.

3. **Three-request upload flow.** Every attachment upload requires:
   a. POST to `/presign` → receive `upload_url` and `attachment_id`
   b. PUT directly to S3 at `upload_url` with the raw file bytes
   c. POST to `/{attachment_id}/confirm` → receive confirmed attachment with download URL
   The presign URL expires in 900 seconds. Initiate the S3 PUT immediately after step (a). If the S3 PUT fails, do not call confirm — the upload window will expire and the PENDING row will be cleaned up automatically.

4. **`PnlStatus` display states.** The `pnl.status` field has three states that require distinct UI treatment:
   - `PENDING_STOP`: show a prompt asking the user to set a planned stop to enable R-multiple tracking.
   - `PENDING_CALCULATION`: show a neutral indicator that P&L is being calculated (trade may still be open).
   - `AVAILABLE`: show `net_pnl`, `gross_pnl`, `total_charges`, `r_multiple` (all will be non-null).

5. **Decimal parsing.** `planned_entry`, `planned_stop`, `planned_target`, `planned_risk_amount`, and all `pnl.*` fields are JSON strings, not numbers. Parse them as `Decimal` (or use a Decimal-aware JSON parser). Do not parse them as JavaScript `number` — floating-point precision loss will corrupt the displayed values.

6. **Empty `mistakes` array.** The `mistakes` field in the response is always an array, never `null`. An empty array means no mistakes recorded. Initialize the mistakes multi-select to the current value from `GET` before displaying the edit form.

---

## Field Validation Quick Reference

For frontend validation (mirrors server-side):

| Field | Rule | Error message |
|---|---|---|
| `planned_entry`, `planned_stop`, `planned_target` | Must be `> 0` if supplied | "Price must be greater than 0" |
| `discipline_score` | Integer [1, 10] if supplied | "Score must be between 1 and 10" |
| `setup_name` | Max 100 characters | "Setup name must be 100 characters or fewer" |
| `change_reason` | Max 500 characters | "Reason must be 500 characters or fewer" |
| `emotion_before/during/after` | Must be a valid EmotionType if supplied | |
| `mistakes` (each element) | Must be a valid MistakeType | |
| Attachment `filename` | 1–255 characters | "Filename is required" / "Filename too long" |
| Attachment `content_type` | One of 4 allowed types | "Only JPEG, PNG, WebP, and GIF are accepted" |
| Attachment `byte_size` | 1 byte to 15 MB (15,728,640 bytes) | "File must be between 1 byte and 15 MB" |
| Attachment `capture_moment` | Must be a valid CaptureMoment | |
| Attachment `caption` | Max 500 characters | "Caption must be 500 characters or fewer" |

---

*Bhima — Senior Backend Engineer*
*Reviewed by: Mayasura (architecture alignment with ADR-003)*
*Domain reference: Ganesha (JOURNAL-DOMAIN-RULES.md — G1)*
*Security reference: Hanuman (JOURNAL-SECURITY-REQUIREMENTS.md — G4)*
