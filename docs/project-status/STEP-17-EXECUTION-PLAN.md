# Step 17 — Import Trades Screen

**Document:** `docs/project-status/STEP-17-EXECUTION-PLAN.md`  
**Author:** Krishna (Project Manager)  
**Date:** 2026-09-08  
**Parent plan:** `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`  
**Branch:** `feat/step-17-import-trades` (base: `main` after Step 16 merged as PR #10)  
**Status:** READY TO IMPLEMENT — Mayasura architectural review (A-17-1/2/3), Ganesha domain review (G-17-1), Dhanvantari risk review (D-17-1/D-17-2), and Sahadeva QA review (QA-17-1/2/3, OBS-QA-3) all applied — 2026-09-08

---

## Architectural Review Decisions (Mayasura, 2026-09-08)

Three blocking issues were identified and resolved before implementation began. These decisions are final for Phase 1.

| Finding | Decision | Effect on plan |
|---------|----------|----------------|
| **A-17-1** — `POST /v1/accounts/{account_id}/import` already exists; plan proposed a duplicate `POST /v1/imports` | **Option A:** Use the existing endpoint as the canonical import route. No new POST endpoint. | B-17-B scope reduced to `GET /v1/imports` + `status` field addition to `ImportSummaryOut` only. Arjun's API client calls the existing URL. |
| **A-17-2** — Only `ZerodhaAdapter` exists on disk; Upstox and Angel One adapters do not exist; pre-conditions were false | **Option A:** Zerodha only for Phase 1. Upstox and Angel One deferred to Phase 2 (Sanjaya). Original Upstox and Angel One adapter tests removed. UI shows Zerodha only. | Scope reduced. Pre-conditions corrected. "Not in Step 17" table updated. (Original B-17-14/B-17-15 slots later repurposed: B-17-14 → file size test per D-17-1; B-17-15 → PARTIAL status test per QA-17-1.) |
| **A-17-3** — Plan mapped `AccountInactiveError` to `404 ACCOUNT_NOT_FOUND`, conflicting with existing endpoint's `422 ACCOUNT_INACTIVE` | **Use `422 ACCOUNT_INACTIVE`** consistently. `AccountNotFoundError` maps to `404 ACCOUNT_NOT_FOUND`; `AccountInactiveError` maps to `422 ACCOUNT_INACTIVE`. | Error mapping table corrected. B-17-07 expected response corrected to 422. |
| **G-17-1** (Ganesha, 2026-09-08) — `EmptyFileError` in `ZerodhaAdapter` raises `422 EMPTY_FILE` for header-only CSVs; `status = "EMPTY"` success-path in `ImportService` is unreachable in Phase 1 (Zerodha adapter has no silent-skip path). Frontend had no `422 EMPTY_FILE` handler; B-17-05 expected wrong outcome. | **Remove `EMPTY` success-path banner from Phase 1 frontend** (dead code for Zerodha-only scope; reserved for Phase 2 adapters). **Add `422 EMPTY_FILE` as an explicit frontend error state.** Correct B-17-05 to assert `422 EMPTY_FILE`. Add `IMPORT_EMPTY_FILE` MSW fixture. Add F-17-16 test. | Frontend result table updated. B-17-05 corrected. MSW and test added. EMPTY banner removed from Phase 1 scope. |
| **D-17-1** (Dhanvantari, 2026-09-08) — No server-side file size limit; `file.read()` in `accounts.py` is unbounded. Client-side warning (>5 MB) is not a block and is bypassed by direct API callers. | **Add server-side size check in `accounts.py` route handler:** files > 10 MB → `413 FILE_TOO_LARGE`. Add frontend handler, `IMPORT_FILE_TOO_LARGE` MSW fixture, B-17-14 backend test, and F-17-17 frontend test. | B-17-B scope extended. Error table updated. MSW, backend test, and frontend test added. |
| **D-17-2** (Dhanvantari, 2026-09-08) — `file.filename` (client-controlled) stored without API-layer length validation; filenames > 255 chars cause unhandled 500s (DB `String(255)` constraint violation is not caught by existing exception handlers). | **Bhima truncates filename at the route handler** before calling `import_fills`: `file_name = (file.filename or "")[:255] or None`. One-liner in `accounts.py`. | B-17-B scope note added. No new test required (browser clients never produce filenames > 255 chars; direct API abuse is a hardening concern, not a feature-correctness test). |
| **QA-17-1** (Sahadeva, 2026-09-08) — Backend tests cover `status = "COMPLETE"` (B-17-01) but not `"PARTIAL"` or `"FAILED"`. Two of three reachable success-path status values have zero backend test coverage despite being the primary deliverable of B-17-B. | **Add B-17-15** (PARTIAL: CSV with valid and invalid rows → 201, `status = "PARTIAL"`, `fills_ingested > 0`, `row_errors > 0`) and **B-17-16** (FAILED: CSV where all data rows are malformed → 201, `status = "FAILED"`, `fills_ingested == 0`, `row_errors > 0`). | Backend test list extended to B-17-16. Test count +2. |
| **QA-17-2** (Sahadeva, 2026-09-08) — `IMPORT_PARTIAL` MSW fixture defined but used by no test. `IMPORT_FAILED` fixture not defined and no test for FAILED banner. PARTIAL and FAILED result banners are specified in the plan with no frontend test coverage. | **Add `IMPORT_FAILED` MSW fixture** (201, `status: "FAILED"`, `fills_ingested: 0`, `row_errors: N`). **Add F-17-18** (PARTIAL banner) and **F-17-19** (FAILED banner). | MSW table updated. Frontend tests extended to F-17-19. Test count +2. |
| **QA-17-3** (Sahadeva, 2026-09-08) — Client-side > 5 MB warning ("This file is unusually large...") is explicitly specified in the upload form section but has no frontend test. It is a distinct code path from the 413 server-side response (F-17-17). | **Add F-17-20** (selecting a file > 5 MB shows the inline size warning; Import button remains enabled — not a block). | Frontend tests extended to F-17-20. Test count +1. |

---

## Goal

Give users a UI for the Zerodha CSV broker import pipeline that already exists in the backend. A logged-in user picks a trading account, uploads a Zerodha CSV file, and sees a summary of what was imported. Past imports are listed on the same screen.

Done means: the existing `POST /v1/accounts/{account_id}/import` is callable from the frontend with a `status` field in the response; `GET /v1/imports` is live for import history; the Import Trades screen at `/import` lets a user complete a full Zerodha import flow and see their import history — Sahadeva GO, Nakula CI GREEN, Yudhishthira ACCEPT.

---

## What "Done" Looks Like

A logged-in user with an active Zerodha trading account can:

1. **Upload a Zerodha CSV:** Navigate to `/import`, select their trading account, drop in a Zerodha CSV, and click Import.
2. **See the result immediately:** Status (COMPLETE / PARTIAL / EMPTY / FAILED), fills imported, fills skipped (duplicates), and row errors.
3. **Receive a clear error for duplicate imports:** If the same file has already been imported to the same account, the UI shows "This file has already been imported."
4. **Provide a product type hint for ambiguous F&O rows:** An optional dropdown lets users specify MIS, CNC, or NRML when the CSV lacks a product column.
5. **Review import history:** A history list shows all past imports for the selected account — date, broker, file name, fills imported, errors, status.

---

## What Already Exists (Do Not Rebuild)

The entire import pipeline and the POST endpoint are already built. Step 17 adds `status` to the existing response, a new GET history endpoint, and the frontend UI.

| Concern | What exists | Location |
|---------|-------------|----------|
| **Import HTTP endpoint (POST)** | `POST /v1/accounts/{account_id}/import` — multipart form, calls `ImportService.import_fills()`, returns `ImportSummaryOut` | `backend/src/tradeforge/api/v1/accounts.py:213` |
| Import orchestration | `ImportService.import_fills()` — full pipeline (account verify, file hash, adapter dispatch, fill insertion, reconstruction, P&L backfill, import record write) | `backend/src/tradeforge/application/import_service.py` |
| Import record model | `ImportRecord` ORM + `import_records` table (migration in Step 11) | `backend/src/tradeforge/infrastructure/models/import_record.py` |
| Import record repo | `ImportRecordRepository.exists()` and `.create()` | `backend/src/tradeforge/infrastructure/repositories/import_record_repo.py` |
| Broker adapter | Zerodha only — `ZerodhaAdapter` registered in `get_import_service()` DI | `backend/src/tradeforge/infrastructure/adapters/zerodha_adapter.py` |
| Domain errors | `DuplicateImportError`, `UnrecognizedFileError`, `EmptyFileError`, `MissingProductTypeError`, `AccountNotFoundError`, `AccountInactiveError` | `backend/src/tradeforge/domain/import_domain/errors.py` |
| Account auth (ownership) | `TradingAccountService.get()` — verifies ownership, no ACTIVE check | `backend/src/tradeforge/application/trading_account_service.py:70` |
| Account auth (active) | `TradingAccountService.get_active()` — verifies ownership + ACTIVE status; used by `import_fills()` | `backend/src/tradeforge/application/trading_account_service.py:86` |
| Account context | `AccountContext`, `useAccount()` — active account in frontend state | `frontend/src/features/accounts/context/AccountContext.tsx` |

**Not built (Upstox and Angel One adapters):** Only `ZerodhaAdapter` exists. Upstox and Angel One CSV import is explicitly deferred to Phase 2 — see "Explicitly NOT in Step 17" below.

---

## Backend Scope (Owner: Bhima)

### Task B-17-A — New Method: `ImportRecordRepository.list_by_account()`

**File:** `backend/src/tradeforge/infrastructure/repositories/import_record_repo.py`

Add alongside the existing `exists()` and `create()` methods:

```python
async def list_by_account(
    self,
    session: AsyncSession,
    account_id: uuid.UUID,
    limit: int = 20,
) -> list[ImportRecord]:
    stmt = (
        select(ImportRecord)
        .where(ImportRecord.account_id == account_id)
        .order_by(ImportRecord.imported_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
```

Returns the most recent `limit` imports for the account, newest first. No cursor pagination for Phase 1 — 20 records is sufficient for the history list.

---

### Task B-17-B — Add `status` Field to `ImportSummary` and `ImportSummaryOut`

**Context:** The existing `POST /v1/accounts/{account_id}/import` returns `ImportSummaryOut`, which does not currently include the import `status` field (COMPLETE / PARTIAL / EMPTY / FAILED). The frontend must show the correct result banner. Bhima must add `status` to both the dataclass and the response schema — this is an additive, backwards-compatible change.

**File 1:** `backend/src/tradeforge/application/import_service.py`

Add `status: str` to the `ImportSummary` dataclass and populate it from the same `status` computation that already writes to `ImportRecord`:

```python
@dataclass(frozen=True)
class ImportSummary:
    import_record_id: uuid.UUID
    fills_ingested: int
    fills_skipped: int
    row_errors: int
    trades_created: int
    trades_closed: int
    pnl_succeeded: int
    pnl_failed: int
    status: str          # NEW: COMPLETE | PARTIAL | EMPTY | FAILED
```

The `status` value is already computed locally inside `import_fills()` before writing to `ImportRecord`. Add it to the `ImportSummary(...)` return at the end of the method.

**File 2:** `backend/src/tradeforge/api/v1/accounts.py`

Add `status: str` to `ImportSummaryOut` and include `status=summary.status` in the construction of the response at `accounts.py:247`:

```python
class ImportSummaryOut(BaseModel):
    import_record_id: uuid.UUID
    fills_ingested: int
    fills_skipped: int
    row_errors: int
    trades_created: int
    trades_closed: int
    pnl_succeeded: int
    pnl_failed: int
    status: str          # NEW
```

**Also in `accounts.py` — route handler hardening (D-17-1, D-17-2):**

In the `import_fills` route handler, immediately after `file_content = await file.read()`, add a server-side file size guard:

```python
file_content = await file.read()
if len(file_content) > 10 * 1024 * 1024:          # D-17-1: 10 MB hard limit
    raise HTTPException(status_code=413, detail="FILE_TOO_LARGE")
```

And truncate `file.filename` before passing it downstream (D-17-2):

```python
safe_file_name = (file.filename or "")[:255] or None   # D-17-2: DB column is String(255)
```

Pass `file_name=safe_file_name` (not `file.filename`) into `svc.import_fills(...)`.

No route signature change. No DI change. The endpoint URL, authentication, and existing error handling in `accounts.py` are otherwise untouched.

---

### Task B-17-C — New Router: `GET /v1/imports`

**File (new):** `backend/src/tradeforge/api/v1/imports.py`

Register under `prefix="/imports"`, tag `"imports"`. Wire into `main.py` alongside existing routers. This file contains **only the GET endpoint** — the POST endpoint lives in `accounts.py` and is not moved.

**`ImportRecordOut`** — one row in the import history list:

```python
class ImportRecordOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    account_id: uuid.UUID
    broker: str
    file_name: str | None
    row_count: int
    error_count: int
    status: str
    imported_at: datetime
    created_at: datetime
```

#### `GET /v1/imports`

Returns the import history for a trading account owned by the authenticated user.

**Query params:**
- `account_id: uuid.UUID` — required.

**Implementation sequence:**

1. Verify the account belongs to the authenticated user: call `TradingAccountService.get(session, user_id, account_id)`. This method does **not** check ACTIVE status — a user can view import history for a deactivated account. Return 404 `ACCOUNT_NOT_FOUND` if the account does not exist or is not owned by the authenticated user.
2. Call `ImportRecordRepository.list_by_account(session, account_id, limit=20)`.
3. Return `list[ImportRecordOut]`.

**Response:** `200 OK` with `list[ImportRecordOut]` (may be empty list).

> **`TradingAccountService.get()` is confirmed to exist** (ownership check only, no ACTIVE filter — `trading_account_service.py:70`). Bhima does not need to add it.

---

### Task B-17-D — Wire Imports Router into `main.py`

```python
from tradeforge.api.v1 import imports as imports_router
app.include_router(imports_router.router, prefix="/v1")
```

---

### Backend Tests (Bhima)

**New file:** `backend/tests/api/test_imports_api.py`

**Note on the existing import endpoint:** `POST /v1/accounts/{account_id}/import` was already tested in Step 11. Do not re-test the full pipeline. These tests target the new `status` field (B-17-01 through B-17-07, B-17-14 through B-17-16) and the new `GET /v1/imports` endpoint (B-17-08 through B-17-13). Use real Zerodha fixture CSV bytes already present from Step 11. B-17-15 and B-17-16 require crafted fixture CSVs: a mixed-row CSV (valid EQ rows + CD-segment rows) for PARTIAL, and an all-malformed CSV (every row has a non-numeric price) for FAILED.

| Test ID | Description |
|---------|-------------|
| B-17-01 | `POST /v1/accounts/{account_id}/import` with valid Zerodha CSV → 201; `status = "COMPLETE"`, `fills_ingested > 0`, `import_record_id` is a valid UUID |
| B-17-02 | `POST /v1/accounts/{account_id}/import` with same file for same account again → 409 `DUPLICATE_IMPORT` |
| B-17-03 | `POST /v1/accounts/{account_id}/import` with same file for a different account owned by the same user → 201 (`file_hash + account_id` unique, not `file_hash`-only) |
| B-17-04 | `POST /v1/accounts/{account_id}/import` with a non-CSV text file → 422 `UNRECOGNIZED_FILE_FORMAT` (existing error code from `accounts.py:241`) |
| B-17-05 | `POST /v1/accounts/{account_id}/import` with header-only CSV (zero data rows) → **422 `EMPTY_FILE`** (G-17-1: `ZerodhaAdapter` raises `EmptyFileError` before `ImportService` is reached; `status = "EMPTY"` success-path is unreachable via Zerodha) |
| B-17-06 | `POST /v1/accounts/{account_id}/import` with another user's `account_id` → 404 `ACCOUNT_NOT_FOUND` |
| B-17-07 | `POST /v1/accounts/{account_id}/import` with INACTIVE account → **422 `ACCOUNT_INACTIVE`** (not 404 — matches existing error mapping in `accounts.py:236`) |
| B-17-08 | `POST /v1/accounts/{account_id}/import` unauthenticated → 401 |
| B-17-09 | `GET /v1/imports?account_id=<uuid>` returns list for owned account; asserts length ≥ 1 and first entry's `status` and `broker` fields |
| B-17-10 | `GET /v1/imports?account_id=<uuid>` for another user's account → 404 |
| B-17-11 | `GET /v1/imports?account_id=<uuid>` unauthenticated → 401 |
| B-17-12 | `GET /v1/imports?account_id=<uuid>` for a deactivated account owned by the user → 200 (ownership-only check; ACTIVE status not required for history) |
| B-17-13 | `GET /v1/imports?account_id=<uuid>` returns empty list for account with no import history |

| B-17-14 | `POST /v1/accounts/{account_id}/import` with file content > 10 MB → **413 `FILE_TOO_LARGE`** (D-17-1: server-side size guard added to route handler) |
| B-17-15 | `POST /v1/accounts/{account_id}/import` with a CSV containing some valid rows and some invalid rows (e.g., valid EQ rows alongside rows with `segment = "CD"` which the adapter rejects) → 201; `status = "PARTIAL"`, `fills_ingested > 0`, `row_errors > 0` (QA-17-1: PARTIAL is a primary status value with no prior test) |
| B-17-16 | `POST /v1/accounts/{account_id}/import` with a CSV where **all** data rows are malformed (e.g., every row has a non-numeric `price`) → 201; `status = "FAILED"`, `fills_ingested == 0`, `fills_skipped == 0`, `row_errors > 0` (QA-17-1: FAILED is a primary status value with no prior test) |

**Original tests removed (A-17-2) and slots repurposed:**
- ~~Upstox CSV → 201~~ (deferred; adapter does not exist) — original B-17-14 slot **repurposed** → B-17-14: file size > 10 MB → 413 FILE_TOO_LARGE (D-17-1)
- ~~Angel One CSV → 201~~ (deferred; adapter does not exist) — original B-17-15 slot **repurposed** → B-17-15: PARTIAL status CSV → 201 status="PARTIAL" (QA-17-1)
- B-17-16 is a net-new slot added by QA-17-1 for FAILED status coverage

---

## Frontend Scope (Owner: Arjun)

### Task F-17-A — API Client: `src/features/imports/api.ts`

New file. The upload function calls the **existing** `POST /v1/accounts/{account_id}/import` endpoint — `account_id` is a URL path segment, not a form field. The history function calls the new `GET /v1/imports`.

```typescript
export const importsApi = {
  upload: (accountId: string, body: FormData) =>
    apiClient.post<ImportSummaryOut>(`/v1/accounts/${accountId}/import`, body, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  list: (accountId: string) =>
    apiClient.get<ImportRecordOut[]>(`/v1/imports?account_id=${accountId}`),
}
```

**Types:** `src/features/imports/types.ts`

```typescript
// Response from POST /v1/accounts/{account_id}/import
export interface ImportSummaryOut {
  import_record_id: string
  fills_ingested: number
  fills_skipped: number
  row_errors: number
  trades_created: number
  trades_closed: number
  pnl_succeeded: number
  pnl_failed: number
  status: 'COMPLETE' | 'PARTIAL' | 'EMPTY' | 'FAILED'   // NEW field — B-17-B
}

// One row in the import history list
export interface ImportRecordOut {
  id: string
  account_id: string
  broker: string
  file_name: string | null
  row_count: number
  error_count: number
  status: 'COMPLETE' | 'PARTIAL' | 'EMPTY' | 'FAILED'
  imported_at: string
  created_at: string
}
```

> **Frontend note (A-17-1):** `account_id` is passed as a URL path segment to the upload endpoint, not as a form field. `FormData` contains only `file` and (optionally) `product_type_hint`. The `broker` name displayed in the UI comes from `AccountContext` — no need for the server to echo it back.

---

### Task F-17-B — Import Trades Screen: `src/features/imports/ImportTradesPage.tsx`

Routed at `/import`. Linked from the navigation sidebar (add "Import" link to `AppShell`).

#### Layout

**Section 1 — Upload form**

| Field | Notes |
|-------|-------|
| Account selector | Populated from `useAccount()`. Active accounts only. Shows account name + broker chip. Defaults to `selectedAccount`. Required. Only Zerodha accounts are able to import CSV files in Phase 1. If the selected account is not Zerodha, show an inline notice: "CSV import is currently supported for Zerodha accounts only." and disable the Import button. |
| Product type hint | Optional `<select>` labelled "F&O product type (if needed)". Options: "Auto-detect (default)", "MIS — Intraday", "CNC — Delivery", "NRML — Overnight". Default: auto-detect (send `null` / omit field). Show a `?` tooltip: "Select only if your file contains F&O rows and the import reports a product type error." |
| File input | Accepts `.csv` only. Drag-and-drop zone or standard file button. Show the selected filename once a file is chosen. |
| Import button | Label: "Import". Disabled until both account and file are selected. Disabled while request is in-flight (show spinner). Disabled if selected account is not Zerodha. |

**Client-side validation (before submission):**
- Account must be selected.
- Account broker must be `ZERODHA` — show inline notice and disable Import button if not.
- File must have a `.csv` extension — show inline error "Please select a CSV file" if not.
- File size > 5 MB: show inline warning "This file is unusually large for a broker export. Proceed?" (not a block — just a warning).

**Section 2 — Import result** (shown after a successful or error submission)

| State | Display |
|-------|---------|
| COMPLETE | Green success banner: "Import complete — X fills imported." Sub-line: "Y fills skipped (already imported)." |
| PARTIAL | Amber warning banner: "Import partially completed — X fills imported, Z rows could not be read. Check that the file is a valid Zerodha export." |
| FAILED | Red error banner: "Import failed — no fills could be read. Check the file format." |
| 409 DUPLICATE_IMPORT | Red inline error: "This file has already been imported to this account." |
| 413 FILE_TOO_LARGE | Red inline error: "The file is too large. Zerodha tradebook exports are typically under 1 MB." |
| 422 EMPTY_FILE | Amber inline error: "The file contains no data rows. Check that you have exported the correct date range from Zerodha." |
| 422 UNRECOGNIZED_FILE_FORMAT | Red inline error: "File format not recognised. Only Zerodha CSV exports are supported in Phase 1." |
| 422 MISSING_PRODUCT_TYPE | Amber inline error: "This file contains F&O rows but no product type column. Select a product type above and try again." (auto-expand the product type hint select) |
| 422 ACCOUNT_INACTIVE | Red inline error: "This account is inactive. Reactivate it in Settings before importing." |

> **Note on `EMPTY` status (G-17-1):** The `status = "EMPTY"` success-path in `ImportService` is unreachable in Phase 1 — `ZerodhaAdapter` always raises `EmptyFileError` (→ `422 EMPTY_FILE`) before returning an empty fills list. The `EMPTY` success-path banner is **not implemented in Phase 1**. It is reserved for Phase 2 adapters that may return an empty result without raising `EmptyFileError`. Arjun must not wire a handler for `status === "EMPTY"` in Phase 1 — the empty-file scenario is covered by `422 EMPTY_FILE` above.

> **Note on error code (A-17-3):** The existing endpoint returns `422 ACCOUNT_INACTIVE` (not `404`) for inactive accounts. Arjun must handle this as a `422` with `detail === "ACCOUNT_INACTIVE"` in the API client's error handler, not as a `404`.

"Import another file" button resets the form (clears file selection and result) — does not reset the account selector.

**Section 3 — Import history**

Auto-loads on mount (using `GET /v1/imports?account_id=...`) and after each successful import.

Columns: Date (formatted), Broker, File name (or "—"), Fills, Errors, Status badge.

Sort: newest first (matches API response order).

Empty state: "No imports yet for this account."

Loading state: skeleton rows while fetching.

---

### Task F-17-C — Router Update

**File:** `frontend/src/app.tsx`

Add the `/import` route:

```tsx
<Route path="/import" element={<ImportTradesPage />} />
```

**Update `AppShell.tsx`:** Add "Import" nav link pointing to `/import` in the sidebar, between "Trades" and "Settings" (or as Arjun sees fit for visual flow).

---

### Frontend Tests (Arjun)

Add MSW handlers to `src/__tests__/msw/handlers.ts`:

| Handler | Fixture |
|---------|---------|
| `POST /v1/accounts/:accountId/import` | `IMPORT_SUCCESS` (201, status: "COMPLETE", fills_ingested: N, fills_skipped: 0, row_errors: 0), `IMPORT_PARTIAL` (201, status: "PARTIAL", fills_ingested: N, row_errors: M where M > 0), `IMPORT_FAILED` (201, status: "FAILED", fills_ingested: 0, fills_skipped: 0, row_errors: N where N > 0), `IMPORT_DUPLICATE` (409), `IMPORT_FILE_TOO_LARGE` (413, `FILE_TOO_LARGE`), `IMPORT_EMPTY_FILE` (422, `EMPTY_FILE`), `IMPORT_UNRECOGNIZED` (422, `UNRECOGNIZED_FILE_FORMAT`), `IMPORT_MISSING_PRODUCT_TYPE` (422, `MISSING_PRODUCT_TYPE`), `IMPORT_ACCOUNT_INACTIVE` (422, `ACCOUNT_INACTIVE`) |
| `GET /v1/imports?account_id=*` | `IMPORT_HISTORY` (list of ImportRecordOut), `IMPORT_HISTORY_EMPTY` (empty list) |

**ImportTradesPage tests (`src/features/imports/__tests__/ImportTradesPage.test.tsx`):**

| Test ID | Description |
|---------|-------------|
| F-17-01 | Renders account selector populated from AccountContext |
| F-17-02 | Import button is disabled when no file is selected |
| F-17-03 | Import button is disabled when no account is selected |
| F-17-04 | Non-CSV file shows inline "Please select a CSV file" error; Import button remains disabled |
| F-17-05 | Non-Zerodha account (e.g. broker = "MANUAL") shows inline "CSV import is currently supported for Zerodha accounts only" notice; Import button is disabled |
| F-17-06 | On successful import (COMPLETE), shows green banner with fills_ingested count |
| F-17-07 | On 409 DUPLICATE_IMPORT, shows inline duplicate error message |
| F-17-08 | On 422 UNRECOGNIZED_FILE_FORMAT, shows inline unrecognised format message |
| F-17-09 | On 422 MISSING_PRODUCT_TYPE, shows amber error and product type hint select is visible |
| F-17-10 | On 422 ACCOUNT_INACTIVE, shows inline "This account is inactive" error |
| F-17-11 | Import button is disabled while request is in-flight |
| F-17-12 | "Import another file" button resets file selection and clears result banner |
| F-17-13 | Import history list renders on mount with account_id from context |
| F-17-14 | Import history list re-fetches after a successful import |
| F-17-15 | Empty import history shows "No imports yet for this account." |
| F-17-16 | On 422 `EMPTY_FILE`, shows amber inline error "The file contains no data rows. Check that you have exported the correct date range from Zerodha." (G-17-1) |
| F-17-17 | On 413 `FILE_TOO_LARGE`, shows red inline error "The file is too large. Zerodha tradebook exports are typically under 1 MB." (D-17-1) |
| F-17-18 | On 201 `PARTIAL` status, shows amber warning banner "Import partially completed — X fills imported, Z rows could not be read." with correct `fills_ingested` count and `row_errors` count from response (QA-17-2; uses `IMPORT_PARTIAL` fixture) |
| F-17-19 | On 201 `FAILED` status, shows red error banner "Import failed — no fills could be read. Check the file format." (QA-17-2; uses `IMPORT_FAILED` fixture) |
| F-17-20 | Selecting a file with `size > 5 MB` shows inline warning "This file is unusually large for a broker export. Proceed?"; Import button **remains enabled** (warning is not a block — user can proceed) (QA-17-3) |

---

## Explicitly NOT in Step 17

| Deferred to | What |
|-------------|------|
| Phase 2 — Sanjaya | **Upstox and Angel One CSV import** — adapters do not exist; only ZerodhaAdapter is implemented (A-17-2) |
| Phase 2 | Real-time import progress bar (requires async Celery job infrastructure) |
| Phase 2 | Column mapping UI for unknown broker CSV formats |
| Phase 2 | Broker API integrations (live trade sync via Zerodha Kite Connect etc.) — Sanjaya |
| Phase 2 | Fill exclusion UI — required before safe re-import after manual gap-repair (R-16-6) |
| Phase 2 | Re-import of a file that has already been imported (file-hash dedup is a hard constraint for Phase 1) |
| Phase 2 | Malware / content scanning of uploaded files |

---

## Key Risk: Mixed-Provenance Double-Count (R-16-6 Carried Forward)

From Step 16 risk register (R-16-6): if a user has added a manual fill to an open position (Step 16 gap-repair use case, D3), and then imports a Zerodha CSV covering the same period, the broker's fill and the user's manual fill will both be inserted — the broker's fill has a real `broker_trade_id`; the user's fill has a generated UUID. `fill_exists()` does not match them. The position is double-counted until the user manually excludes one fill via the fill exclusion mechanism — which has no UI in Phase 1.

**Mitigation for Phase 1:**
- Bhima must add a code comment in `accounts.py:import_fills` warning future developers about this gap.
- Arjun must add a UI notice on the Import screen: "If you've manually added fills to an open position, review those trades after importing a file that covers the same period. Duplicate fills can be removed from the Trades screen." (D-17-R: "may require support" was incorrect — users can self-resolve via Step 16 delete-fill capability)
- This is an accepted known risk for Phase 1. The fill-exclusion UI (Phase 2) resolves it.

---

## Order of Work

### Bhima (backend — can start immediately)

1. **Pre-implementation check (OBS-QA-3):** Before touching `import_service.py`, grep all Step 11 test files for direct `ImportSummary(` construction. The `ImportSummary` dataclass is `frozen=True`; adding `status: str` as a new field will break any test that constructs it without the new argument (`TypeError: missing required argument 'status'`). Update any such callsites before proceeding.
   ```
   grep -r "ImportSummary(" backend/tests/
   ```
2. Add `status: str` to `ImportSummary` dataclass in `import_service.py` and populate it before the `return`.
3. Add `status: str` to `ImportSummaryOut` in `accounts.py` and include `status=summary.status` in the response construction.
4. Add file size guard and filename truncation to the `import_fills` route handler in `accounts.py` (D-17-1, D-17-2).
5. Add `list_by_account()` to `ImportRecordRepository`.
6. Create `backend/src/tradeforge/api/v1/imports.py` with `GET /v1/imports` only.
7. Wire `imports` router into `main.py`.
8. Write backend tests B-17-01 through B-17-16.

### Arjun (frontend — steps 1–2 can start in parallel with Bhima)

1. Create `src/features/imports/types.ts` and `src/features/imports/api.ts`.
2. Add MSW fixtures and handlers for both endpoints.
3. Implement `src/features/imports/ImportTradesPage.tsx` — upload form (Zerodha-only guard), result section, history list.
4. Update `frontend/src/app.tsx` to add the `/import` route.
5. Update `AppShell.tsx` to add "Import" sidebar link.
6. Write frontend tests F-17-01 through F-17-20.

**Arjun dependency on Bhima:** All frontend work can be developed against MSW fixtures. The `status` field on the upload response is in the fixture, not required from the live server. No blocker.

---

## Gate Criteria

| Gate | Owner | Criteria |
|------|-------|---------|
| Sahadeva QA | Sahadeva | All 36 new tests pass (B-17-01 through B-17-16, F-17-01 through F-17-20); no regressions in Steps 11–16 tests (including Step 11 `ImportSummary(` direct-construction callsites updated per OBS-QA-3); `status` field present in POST response (B-17-01); `status = "PARTIAL"` confirmed by B-17-15; `status = "FAILED"` confirmed by B-17-16; `ACCOUNT_INACTIVE` as 422 confirmed by B-17-07; `EMPTY_FILE` as 422 confirmed by B-17-05; `FILE_TOO_LARGE` as 413 confirmed by B-17-14; deactivated-account history access (200) confirmed by B-17-12; Zerodha-only guard confirmed by F-17-05; PARTIAL banner confirmed by F-17-18; FAILED banner confirmed by F-17-19; `>5 MB` client warning confirmed by F-17-20; `EMPTY_FILE` error display confirmed by F-17-16; `FILE_TOO_LARGE` error display confirmed by F-17-17; `EMPTY` success-path banner absent from Phase 1 frontend (G-17-1) |
| Nakula CI | Nakula | `pytest` coverage thresholds pass; `npm run coverage` passes thresholds; `tsc --noEmit` clean; ESLint 0 warnings; no new migration (import_records table already exists); `ImportSummary.status` field confirmed in dataclass; file size check present in `accounts.py` route handler (D-17-1); filename truncation present in route handler (D-17-2) |
| Yudhishthira accept | Yudhishthira | Import Trades screen accessible from nav; Zerodha CSV upload produces COMPLETE result with fill count and status banner; PARTIAL import shows amber warning banner; oversized file upload shows red inline error; empty-file upload shows amber inline error (not a success banner); duplicate file upload shows error; ACCOUNT_INACTIVE shows correct error; import history list shows past imports |

---

## Effort Estimate

| Owner | Work | Estimate |
|-------|------|----------|
| Bhima | Pre-implementation Step 11 grep check (OBS-QA-3) + `status` field in `ImportSummary` + `ImportSummaryOut`; file size check + filename truncation in `accounts.py` (D-17-1, D-17-2) | ~0.1 session |
| Bhima | `list_by_account()` method | ~0.05 session |
| Bhima | `imports.py` router — GET only | ~0.1 session |
| Bhima | Wire into `main.py` | ~0.05 session |
| Bhima | Backend tests B-17-01 through B-17-16 (PARTIAL + FAILED fixture CSVs included) | ~0.4 session |
| Arjun | Types + API client + MSW fixtures (3 new: `IMPORT_EMPTY_FILE`, `IMPORT_FILE_TOO_LARGE`, `IMPORT_FAILED`; `IMPORT_PARTIAL` fields corrected with `row_errors`) | ~0.2 session |
| Arjun | `ImportTradesPage.tsx` — 3 sections + Zerodha guard + all error/status states | ~0.5 session |
| Arjun | Router + AppShell updates | ~0.05 session |
| Arjun | Frontend tests F-17-01 through F-17-20 | ~0.45 session |
| **Total** | | **~1.9 sessions** |

Increased from 1.8 — Sahadeva QA review added 5 tests (B-17-15, B-17-16, F-17-18, F-17-19, F-17-20), 1 MSW fixture (`IMPORT_FAILED`), and a pre-implementation grep check. Within acceptable range for Phase 1.

---

## Pre-Conditions Confirmed

- Step 15 (account selection) ✅ merged to main
- Step 16 (manual trade entry) ✅ merged to main as PR #10
- Branch `feat/step-17-import-trades` ✅ created from `main` (head: `43faf38`)
- No new migration required — `import_records` table created in Step 11
- `POST /v1/accounts/{account_id}/import` endpoint ✅ exists in `accounts.py` — Step 17 extends its response, does not replace it
- `TradingAccountService.get()` ✅ confirmed to exist at `trading_account_service.py:70`
- **Zerodha adapter only** — `ZerodhaAdapter` registered in `get_import_service()` DI. Upstox and Angel One adapters do not exist. Phase 1 import is Zerodha-only by design (A-17-2 ruling).

---

*Krishna — Senior Project Manager*  
*Architectural review: Mayasura (Senior Software Architect) — 2026-09-08 — A-17-1 (duplicate API surface, resolved: use existing POST endpoint), A-17-2 (missing Upstox/Angel One adapters, resolved: Zerodha-only Phase 1), A-17-3 (AccountInactiveError HTTP code conflict, resolved: 422 ACCOUNT_INACTIVE) applied*  
*Domain review: Ganesha (Trading Domain Analyst) — 2026-09-08 — G-17-1 (422 EMPTY_FILE unhandled; EMPTY success-path unreachable in Phase 1 via Zerodha adapter; B-17-05 corrected; 422 EMPTY_FILE frontend handler + MSW fixture + F-17-16 added; EMPTY success-path banner removed from Phase 1 scope) applied*  
*Risk review: Dhanvantari (Risk Management Engineer) — 2026-09-08 — D-17-1 (no server-side file size limit; 10 MB hard cap added to accounts.py route handler; 413 FILE_TOO_LARGE frontend handler + MSW fixture + B-17-14 + F-17-17 added), D-17-2 (file.filename not length-validated; filename truncated to 255 chars in route handler), R-16-6 notice text corrected ("can be removed from the Trades screen") applied*  
*QA review: Sahadeva (Senior QA/Testing Engineer) — 2026-09-08 — QA-17-1 (PARTIAL and FAILED status values untested; B-17-15 + B-17-16 added), QA-17-2 (IMPORT_PARTIAL fixture unused, IMPORT_FAILED fixture missing; IMPORT_FAILED added, F-17-18 + F-17-19 added), QA-17-3 (>5 MB client-side warning untested; F-17-20 added), OBS-QA-3 (Step 11 ImportSummary frozen dataclass construction regression risk; pre-implementation grep check added to Bhima order of work) applied*  
*Source: `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`, `backend/src/tradeforge/api/v1/accounts.py`, `backend/src/tradeforge/application/import_service.py`, `backend/src/tradeforge/infrastructure/models/import_record.py`, `backend/src/tradeforge/infrastructure/repositories/import_record_repo.py`, `backend/src/tradeforge/application/trading_account_service.py`, `backend/src/tradeforge/infrastructure/adapters/zerodha_adapter.py`, `docs/project-status/STEP-16-EXECUTION-PLAN.md` (R-16-6)*
