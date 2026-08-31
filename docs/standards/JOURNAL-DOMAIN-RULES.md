# Journal Domain Rules

**Status:** Authoritative — binding on all TradeForge implementation
**Author:** Ganesha (Trading Domain Analyst)
**Date:** 2026-08-23
**Binding on:** Bhima (backend implementation), Arjun (frontend implementation), Karna (analytics — R-multiple input), Sahadeva (QA)
**Reviewed by:** Hanuman (security requirements — JOURNAL-SECURITY-REQUIREMENTS.md), Usha (UX spec — JOURNAL-UX-SPEC.md)

---

## Purpose

This document contains every trading-domain rule for the journal annotation layer of TradeForge. The journal annotation layer is the set of pre-trade analysis, post-trade reflection, behavioral capture, and attachment fields that are layered onto a reconstructed trade.

Any rule not covered here is **unresolved** and must be brought to Ganesha before implementation touches the affected domain.

This document governs only the journal annotation layer. Trade identity, fill reconstruction, product type classification, P&L calculation, and charge calculation are governed by `TRADE-DOMAIN-RULES.md`, `DECIMAL-USAGE-STANDARD.md`, and Kubera's charge specification respectively. Those rules take precedence where they overlap with this document.

---

## Scope

The journal annotation layer consists of three tables:

| Table | Purpose |
|---|---|
| `journal_entries` | One annotation record per trade — pre-trade plan, behavioral reflection |
| `journal_attachments` | Screenshot and image attachments linked to a trade |
| `journal_audit_log` | Field-level audit trail on every write to `journal_entries` |

---

## Part 1 — Journal Entry Identity and Cardinality

### Rule 1.1 — A Journal Entry Is an Annotation, Not a Trade

A **journal entry** is a user-authored annotation attached to a reconstructed trade. It adds subjective, analytical, and behavioral context to an objective execution record.

A journal entry is NOT:
- A trade record. The journal entry contains zero fill data, zero P&L, and zero charge information. It reads from the trade domain; it does not write to it.
- A free-form note. Each field has a defined semantic role. The `notes` field is the only free-form text field. Other fields capture specific, structured domain concepts.
- An alternative execution record. Every journal entry requires a matching `trades` row. There is no standalone journal entry.

A journal entry belongs to **exactly one trade**. A trade has **at most one journal entry**. This is a 1:1 relationship enforced by `UNIQUE(trade_id)` on `journal_entries`.

### Rule 1.2 — Journal Entry Creation Is Non-Blocking

A journal entry may be created at any point during or after a trade's lifecycle — while the trade is open, partially closed, or fully closed. The journal entry creation does not depend on the trade's `status`.

A journal entry may also be created as a side effect of an attachment presign request. When a user uploads an attachment for a trade that has no journal entry yet, the system creates a blank journal entry to own the attachment. This blank entry has all optional fields set to `NULL`. The user may later populate it via `upsert_entry`.

### Rule 1.3 — Journal Entry Ownership

A journal entry is owned by the user who owns the trade. `journal_entries.user_id` must equal `trades.user_id` for the linked trade. The journal service verifies trade ownership in the SQL WHERE clause before any read or write:

```sql
SELECT * FROM trades WHERE id = $trade_id AND user_id = $session_user_id
```

`user_id` is always sourced from the verified session. It is never accepted from the request body, URL parameters, or query strings. This rule is also stated as SR-JOUR-001 in `JOURNAL-SECURITY-REQUIREMENTS.md`.

---

## Part 2 — Journal Entry Fields

### Rule 2.1 — Field Table

Every field in `journal_entries` has exactly one of two statuses: **Optional** (may be NULL) or **Conditionally Required** (required when a specific condition is true).

There are no unconditionally required fields beyond the relational keys (`id`, `trade_id`, `user_id`). A blank journal entry with all optional fields NULL is valid.

| Field | Type | Status | Domain Rule |
|---|---|---|---|
| `id` | UUID | Required | Server-generated. Client never supplies. |
| `trade_id` | UUID | Required | FK → `trades.id`. Immutable after creation. |
| `user_id` | UUID | Required | FK → `users.id`. Must equal the owning trade's `user_id`. Immutable after creation. |
| `planned_entry` | NUMERIC(18,4) | Optional | Intended entry price before the trade was placed. Must be > 0 if supplied. Unit: INR. See Rule 2.2. |
| `planned_stop` | NUMERIC(18,4) | Optional | Intended stop loss price before the trade was placed. Must be > 0 if supplied. Unit: INR. Triggers `planned_risk_amount` computation. See Rule 2.2 and Rule 2.4. |
| `planned_target` | NUMERIC(18,4) | Optional | Intended target price before the trade was placed. Must be > 0 if supplied. Unit: INR. See Rule 2.2. |
| `planned_risk_amount` | NUMERIC(18,4) | Derived | Computed from `planned_stop` and trade snapshot. Never user-supplied. See Rule 2.4. |
| `setup_name` | VARCHAR(100) | Optional | Short label from the user's personal setup library. No fixed enum — user-defined. Example: "VWAP Reclaim", "Opening Range Breakout". |
| `notes` | TEXT | Optional | Free-form post-trade reflection or pre-trade thesis. No length limit enforced in domain (UI caps at a reasonable display length). |
| `discipline_score` | SMALLINT | Optional | Self-assessed score of how well the trader followed their plan. Range: [1, 10] inclusive. NULL means not yet assessed. See Rule 2.5. |
| `mistakes` | VARCHAR(30)[] | Optional | Array of mistake types from the `MistakeType` enum. Empty array and NULL are treated equivalently by the application. See Rule 2.6. |
| `emotion_before` | VARCHAR(30) | Optional | Emotional state immediately before the trade was entered. Must be a value from `EmotionType` enum if supplied. See Rule 2.7. |
| `emotion_during` | VARCHAR(30) | Optional | Emotional state during trade management. Must be a value from `EmotionType` enum if supplied. See Rule 2.7. |
| `emotion_after` | VARCHAR(30) | Optional | Emotional state after the trade closed (or after reflection). Must be a value from `EmotionType` enum if supplied. See Rule 2.7. |
| `deleted_at` | TIMESTAMPTZ | System | NULL = active. Set to `now()` on soft delete. Rows are never hard-deleted. Soft-deleted entries are excluded from all read queries. |
| `created_at` | TIMESTAMPTZ | System | Set by the database at insert. Never user-supplied. |
| `updated_at` | TIMESTAMPTZ | System | Updated by the database on every write via `onupdate`. Never user-supplied. |

---

### Rule 2.2 — Planned Price Fields: Domain Meaning and Validation

`planned_entry`, `planned_stop`, and `planned_target` represent the **intended** prices at the time the trader decided to place the trade. They reflect the pre-trade plan, not the actual execution.

**What they are:**
- `planned_entry`: the price at which the trader intended to enter. It captures the plan precision — whether the trader was targeting a specific level or entering at market.
- `planned_stop`: the price at which the trader planned to exit if the trade moved against them. This is the most analytically important planned field — it is the basis for R-multiple computation.
- `planned_target`: the price at which the trader planned to take profit. Used for planned R:R calculation.

**What they are NOT:**
- They are not the actual fill prices. The actual entry price is `trades.average_entry`, which is computed from execution fills by the reconstruction engine. Planned prices live in the journal; actual prices live in the trade.
- They are not constraints on the trade. Setting a `planned_stop` does not trigger any automatic action. It is a reflection field — the trader records what they planned.

**Validation:**
- Any supplied price must be `> 0` (positive, non-zero Decimal).
- Zero and negative values are rejected with HTTP 422.
- These fields accept values at 4 decimal places per DECIMAL-USAGE-STANDARD.md Rule 7.

**Cross-field constraints (advisory, not enforced in DB):**
For a LONG trade:
```
planned_stop < planned_entry < planned_target   (for a valid long setup)
```
For a SHORT trade:
```
planned_target < planned_entry < planned_stop   (for a valid short setup)
```
These are domain observations, not hard-validated constraints. A trader may record a stop above their entry for documentation purposes. The system stores whatever the user provides, subject only to the `> 0` constraint.

---

### Rule 2.3 — `setup_name` Is User-Defined

`setup_name` is a free-text label sourced from the user's personal setup library. TradeForge does not maintain a global enum of setup names. The user defines their own setup vocabulary.

`setup_name` has a maximum length of 100 characters. Values exceeding 100 characters are rejected with HTTP 422.

Karna's analytics will group trades by `setup_name` to compute per-setup performance. To make this useful, the user should apply consistent naming. Ganesha does not enforce consistency — that is a user discipline, not a system constraint.

---

### Rule 2.4 — `planned_risk_amount` Computation

`planned_risk_amount` is a derived field. It is computed by the journal service on every `upsert_entry` call and stored in `journal_entries`. It is never accepted from the client.

**Computation formula:**

```
planned_risk_amount = abs(trades.average_entry − planned_stop) × trades.total_entry_quantity
```

This represents the maximum loss in INR if the trade hits the planned stop, based on the actual average entry price (not the planned entry price).

**Preconditions for computation:**
- `planned_stop` is not NULL.
- `trades.average_entry` is not NULL (the trade has at least one confirmed entry fill with an average price).

If either precondition is absent, `planned_risk_amount` is stored as NULL.

**Why `trades.average_entry` and not `planned_entry`:**
The planned entry may differ from the actual entry due to slippage or a market order. Risk is measured against where the trader actually is, not where they planned to be. Using `trades.average_entry` produces an accurate INR risk figure that Karna can use for R-multiple computation.

**Downstream use:**
Karna computes `r_multiple = net_pnl / planned_risk_amount` for closed trades where both values are non-NULL. `planned_risk_amount` is Karna's input — do not change the computation formula without notifying Karna.

---

### Rule 2.5 — `discipline_score` Range and Semantics

`discipline_score` is an integer in the range [1, 10] inclusive, representing the trader's self-assessment of how faithfully they followed their trading plan during this trade.

| Score | Meaning |
|---|---|
| 1–3 | Poor — significant deviation from plan (moved stop, sized up impulsively, entered without confirmation) |
| 4–6 | Acceptable — minor deviations, or plan had gaps that required in-flight decisions |
| 7–9 | Good — followed the plan with only small, justified adjustments |
| 10 | Perfect — followed the plan exactly as written |

**Validation:**
- Any supplied value must be an integer in [1, 10] inclusive.
- Values of 0, negative values, and values above 10 are rejected with HTTP 422.
- NULL is valid and means "not yet self-assessed."

**Enforcement layers:**
1. API input validation rejects out-of-range values with HTTP 422.
2. DB CHECK constraint: `discipline_score IS NULL OR (discipline_score >= 1 AND discipline_score <= 10)`.

Karna uses `discipline_score` to correlate plan adherence with P&L outcomes. Score distribution over time is a behavioral metric, not a grade.

---

### Rule 2.6 — `MistakeType` Enum

`mistakes` is an array of `MistakeType` values. Multiple mistakes may apply to a single trade. The application stores them as `VARCHAR(30)[]`.

The authoritative `MistakeType` enum:

| Value | Trading-domain meaning |
|---|---|
| `FOMO_ENTRY` | Entered the trade out of fear of missing the move, without full setup confirmation |
| `FOMO_EXIT` | Exited early due to fear the trade would reverse, before the target or stop was reached |
| `OVERSIZED_POSITION` | Took a position larger than the plan's risk rules permitted |
| `NO_STOP_DEFINED` | Entered the trade without a defined stop loss price |
| `MOVED_STOP_WIDER` | Moved the stop loss further from the entry after entry, increasing risk |
| `CUT_WINNER_EARLY` | Exited a profitable trade before the planned target was reached, without a strategic reason |
| `HELD_THROUGH_STOP` | Did not exit when the planned stop was hit; held the trade hoping for a reversal |
| `REVENGE_TRADE` | Took a trade primarily to recover a previous loss, outside the normal setup criteria |
| `AVERAGING_DOWN` | Added to a losing position rather than honouring the stop; see TRADE-DOMAIN-RULES.md |
| `ENTRY_TOO_EARLY` | Entered before the setup was fully confirmed |
| `ENTRY_TOO_LATE` | Entered after the ideal entry point had passed, significantly worsening the R:R |
| `IGNORED_SIGNAL` | Saw a valid exit or entry signal and did not act on it |
| `DISTRACTED` | Was not fully focused on the trade during active management |

**Validation:**
- Each element of the array must be a member of `MistakeType`.
- Unknown values are rejected with HTTP 422.
- An empty array and NULL are semantically equivalent (no mistakes recorded).

**Note to Arjun:** The UI should present `MistakeType` values as a multi-select checklist with human-readable labels, not raw enum strings.

---

### Rule 2.7 — `EmotionType` Enum

`emotion_before`, `emotion_during`, and `emotion_after` each accept a single value from `EmotionType`. Only one emotional state is captured per moment. If the trader felt multiple emotions, they should record the dominant one.

The authoritative `EmotionType` enum:

| Value | Trading-domain meaning |
|---|---|
| `CALM` | Composed, not influenced by the market's short-term noise |
| `CONFIDENT` | Strong belief in the trade's thesis, based on setup quality |
| `ANXIOUS` | Worried about potential loss; second-guessing the entry |
| `FEARFUL` | Significant fear — either of losing or of missing a move |
| `GREEDY` | Focused on maximising gain to a degree that overrides plan adherence |
| `FRUSTRATED` | Carrying emotional residue from a prior loss or missed opportunity |
| `EUPHORIC` | Excessive optimism following a winning trade; may lead to oversizing |
| `BORED` | Low engagement; risk of impulsive trade to create action |
| `DISTRACTED` | Not mentally present; external factors are competing for attention |
| `NEUTRAL` | No notable emotional state; baseline |

**Validation:**
- The value must be a member of `EmotionType` if supplied.
- Unknown values are rejected with HTTP 422.
- NULL is valid and means "not yet recorded."

**Enforcement layers:**
1. API validates against the enum before writing.
2. DB CHECK constraints on each column: `emotion_before IS NULL OR emotion_before IN (...)`.

Vidura (psychology specialist) uses these fields for behavioral P&L correlation analysis. Consistent recording is essential for the analysis to be meaningful.

---

### Rule 2.8 — `change_reason` Is an Audit Metadata Field

`change_reason` is not stored in `journal_entries`. It is accepted on every PUT request and written to each affected row in `journal_audit_log` alongside the changed field values.

`change_reason` captures why a field was changed. Example: "Corrected stop price — originally entered wrong level from my notes."

**Validation:**
- Maximum 500 characters.
- Values exceeding 500 characters are rejected with HTTP 422.
- NULL is valid — the user is not required to explain every change.

---

## Part 3 — P&L Status (PnlStatus)

### Rule 3.1 — PnlStatus Is a Computed, Three-State Indicator

`PnlStatus` is never stored in a database column. It is computed at query time by the journal service using a LEFT JOIN to `trade_pnl` and the value of `planned_stop`. It is returned in the `JournalEntryView` read model as a read-only field.

The three states:

| State | Condition | Meaning |
|---|---|---|
| `PENDING_STOP` | `journal_entries.planned_stop IS NULL` | The trader has not yet recorded a planned stop. R-multiple cannot be computed because 1R is not defined. |
| `PENDING_CALCULATION` | `planned_stop IS NOT NULL` AND no row exists in `trade_pnl` for this `trade_id` | The stop is defined. The Step 10 P&L engine has not yet run for this trade (trade may still be open, or engine has not processed it). |
| `AVAILABLE` | A row exists in `trade_pnl` for this `trade_id` | Full P&L data (gross, net, charges, R-multiple) is available from the Step 10 P&L engine. |

**State transition precedence rule:**
`AVAILABLE` always takes precedence. If a `trade_pnl` row exists, the status is `AVAILABLE` regardless of whether `planned_stop` is set.

**Why this is computed at read time:**
`PnlStatus` is a function of two pieces of state that can change independently — the trader updating `planned_stop`, and the Step 10 engine inserting a `trade_pnl` row. Storing it would require keeping it in sync across two update paths. Computing it at read time is simpler, cheaper, and always accurate.

**Computation pseudocode:**
```python
def compute_pnl_status(planned_stop, has_pnl_row):
    if has_pnl_row:
        return AVAILABLE
    if planned_stop is not None:
        return PENDING_CALCULATION
    return PENDING_STOP
```

---

### Rule 3.2 — Journal Service Never Writes to `trade_pnl`

The journal service owns `journal_entries`, `journal_attachments`, and `journal_audit_log`. It reads from `trades` and `trade_pnl` for display purposes. It **never** writes to `trade_pnl`.

Zero INSERT, UPDATE, or DELETE operations targeting `trade_pnl` are permitted in `JournalService` or `JournalRepository`. `trade_pnl` is owned exclusively by the Step 10 P&L engine.

This boundary is a hard domain ownership rule. Violating it would corrupt Kubera's P&L data.

---

## Part 4 — Audit Trail

### Rule 4.1 — Which Fields Are Audited

Every PUT to an existing journal entry produces one row in `journal_audit_log` per field that changed. The auditable fields are:

```
planned_entry
planned_stop
planned_target
setup_name
notes
discipline_score
mistakes
emotion_before
emotion_during
emotion_after
```

Fields that are not audited: `planned_risk_amount` (derived — its change is implied by a change to `planned_stop`), `deleted_at` (system field), `created_at`, `updated_at`.

**"Changed" definition:** a field is considered changed when `str(old_value) != str(new_value)`. This includes: value → NULL, NULL → value, or one non-NULL value to a different non-NULL value. An update that sends the same value as the current value does NOT generate an audit row for that field.

### Rule 4.2 — Audit Log Row Structure

Each `journal_audit_log` row records:

| Field | Content |
|---|---|
| `journal_entry_id` | FK to the journal entry that was updated |
| `user_id` | The user who made the change (from session — never from request) |
| `field_name` | The name of the field that changed (e.g., `"planned_stop"`) |
| `previous_value` | The old value serialized to text; NULL if the field was previously unset |
| `new_value` | The new value serialized to text; NULL if the field was cleared |
| `change_reason` | The `change_reason` from the request, or NULL |
| `changed_at` | UTC timestamp of the write |

**Serialization rules:**
- Decimal values serialize to their full string representation (e.g., `"252.5000"`).
- Integer values serialize to their string representation (e.g., `"7"`).
- Array values serialize as comma-separated strings (e.g., `"FOMO_ENTRY,HELD_THROUGH_STOP"`).
- NULL serializes as the SQL NULL value (stored as NULL in the column, not as the string `"None"` or `"null"`).

### Rule 4.3 — `journal_audit_log` Is Immutable

`journal_audit_log` rows are append-only. Once written, they cannot be modified or deleted.

Enforcement:
1. `JournalRepository` exposes only `append_audit_entries(...)`. No update or delete method exists for `journal_audit_log` rows.
2. A PostgreSQL trigger raises an exception on any UPDATE or DELETE targeting `journal_audit_log`. (SR-JOUR-011 in JOURNAL-SECURITY-REQUIREMENTS.md.)

The audit log is the forensic record of every change to every journal entry. Its integrity is non-negotiable.

### Rule 4.4 — First Write Does Not Generate Audit Rows

When a journal entry is created for the first time (`INSERT`), no audit log rows are generated. The audit log records changes to an existing entry, not the initial population.

---

## Part 5 — Attachments

### Rule 5.1 — Attachment Is an Image Capture, Not a Document Store

A journal attachment is a screenshot, chart capture, or image taken at a specific moment during the trade lifecycle. It provides visual evidence of the trade setup, entry, or exit conditions.

Attachments are NOT:
- A general document store. PDF reports, broker statements, and trade summaries belong elsewhere. Only image files are accepted.
- A permanent URL store. Download URLs are pre-signed S3 URLs that expire after 1 hour. The client must call the download endpoint to obtain a fresh URL.
- Unlimited storage. Quota limits apply per file, per trade, and per user. See Rule 5.3.

### Rule 5.2 — Content Type Allowlist

The authoritative allowed content types for attachments:

| Content Type | Allowed Extensions |
|---|---|
| `image/jpeg` | `.jpg`, `.jpeg` |
| `image/png` | `.png` |
| `image/webp` | `.webp` |
| `image/gif` | `.gif` |

**SVG (`image/svg+xml`) is explicitly excluded.** SVG files can contain embedded JavaScript and constitute an XSS vector when rendered in a browser. This exclusion is permanent and not subject to relaxation without a formal Hanuman security review.

**Enforcement is server-side.** The UI may use `<input accept="image/jpeg,image/png,image/webp,image/gif">` as a convenience, but this is a UX affordance only. The server validates the declared `content_type` against the allowlist before issuing a presign URL. A mismatch causes HTTP 422.

**File extension must match content type.** A file named `screenshot.png` with `content_type: image/jpeg` is rejected with HTTP 422. The extension-to-content-type mapping is enforced at presign time.

### Rule 5.3 — Storage Quotas

Three quota limits are enforced before every presign request, in this order:

| Limit | Value | Scope |
|---|---|---|
| Per-file maximum | 15 MB | Applies to the declared `byte_size` of the single file being uploaded |
| Per-trade quota | 75 MB | Sum of `byte_size` for all `CONFIRMED` attachments on the trade + the new file |
| Per-user quota | 2 GB | Sum of `byte_size` for all `CONFIRMED` attachments owned by the user + the new file |

**Zero and negative `byte_size` values are rejected** with HTTP 422. The client declares the byte size at presign time; this declared size is checked against the quotas. The actual uploaded size is not re-verified by the application layer (S3 enforces the maximum via the presign URL's `content-length-range` condition).

**Quota computation uses CONFIRMED bytes only.** PENDING, EXPIRED, and REJECTED attachments are excluded from quota calculations. Soft-deleted attachments (`deleted_at IS NOT NULL`) are also excluded.

### Rule 5.4 — Attachment Lifecycle State Machine

A journal attachment transitions through the following states:

```
[presign request] → PENDING
        ↓
[confirm endpoint — HeadObject success] → CONFIRMED
        ↓ (soft delete)
     [deleted]

PENDING → EXPIRED   (if more than 30 minutes elapse before confirm)
PENDING → REJECTED  (if HeadObject shows the object does not exist)
```

| State | Meaning | Transitions allowed |
|---|---|---|
| `PENDING` | Presign URL issued; upload not yet confirmed | → CONFIRMED, → EXPIRED, → REJECTED |
| `CONFIRMED` | Upload verified via HeadObject; attachment is active | → soft deleted (deleted_at set) |
| `EXPIRED` | 30 minutes elapsed from creation; window closed | Terminal |
| `REJECTED` | HeadObject returned no object at confirm time | Terminal |

**Only one non-terminal transition per attachment.** An EXPIRED or REJECTED attachment cannot be re-activated. The user must initiate a new presign request for a new attachment.

**PENDING expiry is application-enforced at 30 minutes.** S3 lifecycle rules delete the underlying object at 1 hour as a safety net. If an object arrives in S3 but the confirm call never arrives (client crash), the application marks the row EXPIRED at the next read; S3 cleans up the object independently.

### Rule 5.5 — `capture_moment` Enum

`capture_moment` records at what point in the trade lifecycle the screenshot was taken. It is required on every attachment presign request.

| Value | Meaning |
|---|---|
| `AT_ENTRY` | Taken at or immediately before the entry execution — shows the setup context |
| `DURING_TRADE` | Taken while the trade was open and being managed |
| `AT_EXIT` | Taken at or immediately after the final exit — shows the trade result |
| `POST_REVIEW` | Taken during a later review session; may show the full trade on a chart |

**Validation:** Value must be a member of the `capture_moment` enum. Unknown values are rejected with HTTP 422.

### Rule 5.6 — S3 Key Structure

The S3 key for every attachment is:

```
{user_id}/{trade_id}/{attachment_id}
```

All three components are server-generated UUIDs. The client never supplies any component of the S3 key. The filename is stored in `journal_attachments.filename` as display metadata and is never embedded in the S3 key.

**Why user_id is the root prefix:** S3 bucket policies and prefix-level permissions can be scoped per user without complex key parsing. It also makes storage auditing straightforward.

### Rule 5.7 — Filename Sanitization

The client-supplied filename is sanitized before storage. Sanitization rules:

1. Remove path separators: `/`, `\`, `:`.
2. Remove non-word characters except whitespace, hyphens, and periods (Unicode-safe).
3. Collapse multiple consecutive whitespace characters to a single space.
4. Truncate to 255 characters.

The sanitized filename is stored in `journal_attachments.filename` as a display label only. It is used in the `Content-Disposition: attachment; filename=<sanitized_name>` header of the download URL. It has no bearing on the S3 key.

**A filename sanitized to empty string is valid** (result: stored as `""`). The UI should handle empty filenames gracefully by displaying a fallback label.

### Rule 5.8 — Download URL Semantics

Download URLs are pre-signed S3 GET URLs. They:
- Expire after 3600 seconds (1 hour) from generation.
- Include `Content-Disposition: attachment; filename=<sanitized_filename>`, forcing a download rather than inline rendering in the browser. This prevents XSS via served image content.
- Are generated fresh on every read request. The client must not cache or store the URL beyond its TTL.

A fresh download URL is generated for each CONFIRMED attachment on every call to `get_entry` and `confirm_attachment`.

### Rule 5.9 — Attachment Deletion Is Soft Delete

Soft deleting an attachment sets `journal_attachments.deleted_at = now()`. The `journal_attachments` row is retained permanently for audit trail purposes. The underlying S3 object is NOT deleted by the application layer on soft delete; S3 bucket versioning and lifecycle rules manage object retention.

Only CONFIRMED attachments may be soft-deleted. PENDING, EXPIRED, and REJECTED attachments are excluded from the delete endpoint.

---

## Part 6 — Audit and Security Events

### Rule 6.1 — Security Audit Log for Attachment Events

In addition to the field-level `journal_audit_log`, attachment lifecycle events are written to the `security_audit_log` table (shared with the auth layer, owned by the auth infrastructure).

The following attachment events must be logged to `security_audit_log`:

| Event type | When written |
|---|---|
| `ATTACHMENT_PRESIGN_REQUESTED` | After a presign URL is successfully issued |
| `ATTACHMENT_REJECTED_TYPE` | When content type fails the allowlist check |
| `ATTACHMENT_REJECTED_SIZE` | When file size fails the per-file limit check |
| `ATTACHMENT_REJECTED_QUOTA` | When per-trade or per-user quota would be exceeded |
| `ATTACHMENT_CONFIRMED` | After HeadObject succeeds and status transitions to CONFIRMED |
| `ATTACHMENT_CONFIRM_FAILED` | After HeadObject finds no object and status transitions to REJECTED |
| `ATTACHMENT_DELETED` | After a soft delete is executed |

**Minimum payload per event:**
```
user_id, ip_address, declared_content_type, declared_byte_size, trade_id
attachment_id     (included when available — not available on REJECTED_TYPE/SIZE/QUOTA before create)
```

### Rule 6.2 — `user_id` in Audit Logs Comes from Session

`user_id` in every `journal_audit_log` row and every `security_audit_log` event must come from the verified server session. It is never accepted from the request body. This is a restatement of SR-JOUR-001 for the audit context.

---

## Part 7 — Mutation Rules

### Rule 7.1 — What Can Be Updated

The following fields in `journal_entries` may be updated via the `upsert_entry` endpoint on any call after creation:

```
planned_entry, planned_stop, planned_target,
setup_name, notes,
discipline_score, mistakes,
emotion_before, emotion_during, emotion_after
```

`planned_risk_amount` is re-derived on every upsert and updated automatically. It is not a directly updatable field.

### Rule 7.2 — What Cannot Be Updated

The following fields in `journal_entries` are immutable after creation:

```
id, trade_id, user_id, created_at
```

Attempts to change these values are ignored (the service layer does not pass them to the update query). No error is raised for the client.

### Rule 7.3 — Upsert Semantics

The `upsert_entry` endpoint applies create-or-update semantics:
- If no journal entry exists for `(trade_id, user_id)`: create a new entry with the supplied fields.
- If an entry already exists: update the existing entry with the supplied fields.

A field supplied as `null` in the request body clears the existing value (sets it to NULL in the database). A field **absent from the request body** (not supplied) is treated as `null` — all fields default to NULL on each upsert call. Clients must re-submit all fields they wish to retain on each update.

**Why full-replacement semantics (not patch):** Patch semantics require distinguishing "field not supplied" from "field supplied as null." Full-replacement semantics are simpler to implement, test, and reason about. The client owns the current state and submits it in full.

### Rule 7.4 — Soft Delete

A journal entry may be soft-deleted by setting `deleted_at`. The entry row is retained for audit trail purposes and to preserve the linked `journal_audit_log` history. Soft-deleted entries are excluded from all read queries. The entry may not be restored via the API.

---

## Part 8 — Relationship to the Trade Domain

### Rule 8.1 — Journal Reads From Trade; Trade Does Not Read From Journal

The relationship between the journal layer and the trade domain is one-directional:

```
trade domain → journal layer (provides: trades.average_entry, trades.total_entry_quantity)
journal layer → trade domain (never writes)
```

The journal service calls `get_trade_snapshot(trade_id, user_id)` to fetch the trade fields it needs for computation (`average_entry`, `total_entry_quantity`). It never writes to `trades`, `execution_fills`, `management_events`, `tax_lots`, or `trade_pnl`.

### Rule 8.2 — `planned_entry` vs. `trades.average_entry`

These two fields are frequently confused. Their domain roles are entirely distinct:

| Field | Lives in | Set by | Meaning |
|---|---|---|---|
| `trades.average_entry` | `trades` | Reconstruction engine | Actual weighted average fill price — the objective entry price |
| `journal_entries.planned_entry` | `journal_entries` | User, via journal | Intended entry price from the pre-trade plan |

Slippage (difference between planned entry and actual entry) is a derived metric: `trades.average_entry − journal_entries.planned_entry`. Neither field exists to substitute for the other.

Karna uses `trades.average_entry` for P&L. Karna uses `journal_entries.planned_entry` for slippage analysis. Both must be recorded independently.

### Rule 8.3 — `planned_stop` vs. `management_events` Stops

`journal_entries.planned_stop` is the **original intended stop at trade inception** — the stop the trader planned before entry.

`management_events` of types `STOP_MOVED_BREAKEVEN`, `STOP_TIGHTENED`, or `STOP_WIDENED` record subsequent changes to the stop during trade management.

These are different data points serving different analytical purposes:

| Field | Captures |
|---|---|
| `planned_stop` | Where did you plan to be wrong before you entered? |
| `management_events.price_level` (stop type) | Where did you actually move the stop to, and when? |

Both should be recorded. The difference between `planned_stop` and the final stop level reveals the trader's in-trade management quality.

---

## Part 9 — Unresolved Domain Questions

### Unresolved 1 — Multiple-Journal-Entry Versions for Long-Running Swing Trades

**Question:** A swing trade held for 8 days may warrant journal updates at multiple points — initial setup, mid-trade reflection, final review. The current model allows a single `journal_entries` row updated over time, with the `journal_audit_log` recording each change. Is the audit log an adequate representation of the evolving journal, or should there be explicit versioned snapshots?

**Blocked:** Any "journal version history" UI feature. The current model supports showing the change log but not reconstructing the journal as it was at a specific point in time. Ganesha's view: the audit log is sufficient for Phase 1. Versioned snapshots are deferred to a future phase if analytics show they are needed.

### Unresolved 2 — Pre-Trade Journal Entry Before the Trade Exists

**Question:** A trader may want to record a pre-trade plan (setup, entry level, stop, target, thesis) before a trade is ever executed — as a watchlist entry or a hypothesis. Currently, a `journal_entries` row requires a `trades` row. Should there be a separate pre-trade plan entity that is promoted to a journal entry when a matching trade is reconstructed?

**Blocked:** Any "trading plan" or "watchlist" feature that predates trade execution. Ganesha recommends deferring this to Phase 2.

### Unresolved 3 — Attachment Re-upload

**Question:** If a user uploads an image and then wants to replace it with a corrected version, the current model requires soft-deleting the old attachment and uploading a new one. Should there be an explicit "replace attachment" workflow that links the old and new attachment for audit trail purposes?

**Blocked:** Any "re-upload" or "replace" UI. Current workaround: delete the old attachment, upload a new one. This leaves a gap in the visual audit trail. Ganesha recommends deferring replacement semantics to Phase 2.

---

## Handoff Notes for Bhima

The following database-layer rules follow directly from the domain rules in this document:

1. **`journal_entries.UNIQUE(trade_id)`** — enforces 1:1 cardinality. Rule 1.1.

2. **`journal_entries` CHECK constraints** — must enforce:
   - `discipline_score IS NULL OR (discipline_score >= 1 AND discipline_score <= 10)` — Rule 2.5
   - `emotion_before IS NULL OR emotion_before IN (...)` — Rule 2.7
   - `emotion_during IS NULL OR emotion_during IN (...)` — Rule 2.7
   - `emotion_after IS NULL OR emotion_after IN (...)` — Rule 2.7

3. **`journal_audit_log` immutability trigger** — a PostgreSQL BEFORE UPDATE and BEFORE DELETE trigger must raise an exception unconditionally. Rule 4.3 / SR-JOUR-011.

4. **`journal_attachments` CHECK constraints** — must enforce:
   - `byte_size > 0` — Rule 5.3
   - `capture_moment IN (...)` — Rule 5.5
   - `status IN ('PENDING', 'CONFIRMED', 'EXPIRED', 'REJECTED')` — Rule 5.4

5. **`JournalRepository.get_trade_snapshot`** — must include `user_id` in the WHERE clause. Rule 1.3 / SR-JOUR-002.

6. **Quota queries** — must count only CONFIRMED bytes (`status = 'CONFIRMED'`) and exclude soft-deleted rows (`deleted_at IS NULL`). Rule 5.3.

7. **Audit log writes** — one row per changed field, written in the same transaction as the `journal_entries` update. Rule 4.1.

8. **No cross-table writes to `trade_pnl`** — zero references to `trade_pnl` in `JournalService` or `JournalRepository` writes. Rule 3.2.

---

## Handoff Notes for Arjun

1. **`PnlStatus` display** — show all three states distinctly. `PENDING_STOP` prompts the user to add a stop. `PENDING_CALCULATION` shows a "calculating" indicator. `AVAILABLE` shows the P&L values. Rule 3.1.

2. **Download URLs expire in 1 hour** — never cache the URL from a prior response. Fetch it fresh on each view. Rule 5.8.

3. **`setup_name` is user-defined text** — no dropdown with a fixed list. A free-text input with autocomplete from the user's own prior entries is the appropriate UX. Rule 2.3.

4. **Full-replacement upsert** — include all fields the user wants to keep in every save request. Fields not included are set to NULL. Rule 7.3.

5. **`mistakes` is a multi-select** — present `MistakeType` values as a checklist, not a text input. See Rule 2.6 for the full enum and human-readable meanings.

6. **`emotion_*` is a single-select per moment** — one value per field. If the trader felt multiple emotions, they record the dominant one. Rule 2.7.

---

*Ganesha — Trading Domain Analyst*
*This document supersedes any informal domain discussions preceding it. All rules herein are binding unless formally revised by Ganesha.*
