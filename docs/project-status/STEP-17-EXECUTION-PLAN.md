# Step 17 — Import Trades Screen

**Document:** `docs/project-status/STEP-17-EXECUTION-PLAN.md`  
**Author:** Krishna (Project Manager)  
**Date:** 2026-09-08  
**Parent plan:** `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`  
**Branch:** `feat/step-17-import-trades` (base: `main` after Step 16 merged as PR #10)  
**Status:** READY TO IMPLEMENT

---

## Goal

Give users a UI for the CSV broker import pipeline that already exists in the backend. A logged-in user picks a trading account, uploads a broker CSV file, and sees a summary of what was imported. Past imports are listed on the same screen.

Done means: `POST /v1/imports` and `GET /v1/imports` are live; the Import Trades screen at `/import` lets a user complete a full import flow and see their import history — Sahadeva GO, Nakula CI GREEN, Yudhishthira ACCEPT.

---

## What "Done" Looks Like

A logged-in user with an active trading account can:

1. **Upload a CSV:** Navigate to `/import`, select their trading account, drop in a Zerodha / Upstox / Angel One CSV, and click Import.
2. **See the result immediately:** Status (COMPLETE / PARTIAL / EMPTY / FAILED), fills imported, fills skipped (duplicates), and row errors.
3. **Receive a clear error for duplicate imports:** If the same file has already been imported to the same account, the UI shows "This file has already been imported."
4. **Provide a product type hint for ambiguous F&O rows:** An optional dropdown lets users specify MIS, CNC, or NRML when the CSV lacks a product column.
5. **Review import history:** A history list shows all past imports for the selected account — date, broker, file name, fills imported, errors, status.

---

## What Already Exists (Do Not Rebuild)

The entire import pipeline is already built. Step 17 is a thin HTTP + UI layer over it.

| Concern | What exists | Location |
|---------|-------------|----------|
| Import orchestration | `ImportService.import_fills()` — full pipeline (account verify, file hash, adapter dispatch, fill insertion, reconstruction, P&L backfill, import record write) | `backend/src/tradeforge/application/import_service.py` |
| Import record model | `ImportRecord` ORM + `import_records` table (migration in Step 11) | `backend/src/tradeforge/infrastructure/models/import_record.py` |
| Import record repo | `ImportRecordRepository.exists()` and `.create()` | `backend/src/tradeforge/infrastructure/repositories/import_record_repo.py` |
| Broker adapters | Zerodha, Upstox, Angel One — all three registered and working | `backend/src/tradeforge/infrastructure/adapters/` |
| Domain errors | `DuplicateImportError`, `UnrecognizedFileError`, `EmptyFileError`, `MissingProductTypeError` | `backend/src/tradeforge/domain/import_domain/errors.py` |
| Account auth | `TradingAccountService.get_active()` — verifies ownership + ACTIVE status | `backend/src/tradeforge/application/trading_account_service.py` |
| Account context | `AccountContext`, `useAccount()` — active account in frontend state | `frontend/src/features/accounts/context/AccountContext.tsx` |
| App router | `/import` placeholder route (or nav link) | `frontend/src/app.tsx` |

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

### Task B-17-B — New Router: `POST /v1/imports`, `GET /v1/imports`

**File (new):** `backend/src/tradeforge/api/v1/imports.py`

Register under `prefix="/imports"`, tag `"imports"`. Wire into `main.py` alongside existing routers.

---

#### API Types

**`ImportOut`** — response from `POST /v1/imports`:

```python
class ImportOut(BaseModel):
    import_record_id: uuid.UUID
    account_id: uuid.UUID
    broker: str
    file_name: str | None
    fills_ingested: int
    fills_skipped: int
    row_errors: int
    trades_created: int
    trades_closed: int
    status: str  # COMPLETE | PARTIAL | EMPTY | FAILED
    imported_at: datetime
```

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

---

#### `POST /v1/imports`

Accepts a multipart form upload. Runs the full `ImportService.import_fills()` pipeline and returns an `ImportOut`.

**Form fields:**
- `file: UploadFile` — the CSV file. Validate that the content-type is `text/csv` or filename ends in `.csv` — return 422 `INVALID_FILE_TYPE` if neither.
- `account_id: uuid.UUID` — the target trading account.
- `product_type_hint: str | None = None` — optional; must be one of `"MIS"`, `"CNC"`, `"NRML"` if provided — return 422 `INVALID_PRODUCT_TYPE_HINT` otherwise.

**Implementation sequence:**

1. Validate form fields (content type, product_type_hint enum).
2. Read `file.read()` into `file_content: bytes`. Reject if empty (0 bytes) with 422 `EMPTY_FILE`.
3. Call `ImportService.import_fills(session, user_id, account_id, file_content, product_type_hint, file_name=file.filename)`.
4. Commit.
5. Query `import_records` for the returned `import_record_id` and return `ImportOut`.

**Error mapping:**

| Exception | HTTP status | Error code |
|-----------|------------|------------|
| `AccountNotFoundError` / `AccountInactiveError` | 404 | `ACCOUNT_NOT_FOUND` |
| `DuplicateImportError` | 409 | `DUPLICATE_IMPORT` |
| `UnrecognizedFileError` | 422 | `UNRECOGNIZED_FILE` |
| `EmptyFileError` | 422 | `EMPTY_FILE` |
| `MissingProductTypeError` | 422 | `MISSING_PRODUCT_TYPE` |

> **R-16-6 carried forward:** `ImportService.import_fills()` uses `fill_exists()` to deduplicate by `broker_trade_id + account_id`. A manual gap-repair fill from Step 16 (`import_source = 'MANUAL'`, `broker_trade_id` = generated UUID) will **not** be detected as a duplicate by this check when the broker's version of the same fill later arrives in a CSV. Both fills will be inserted, causing double-counting for that position. Phase 1 has no fill-exclusion UI to resolve this. Document this in the router code with a comment referencing R-16-6. The fill-exclusion UI is a Phase 2 requirement and must be built before automated CSV re-import is enabled.

**Response:** `201 Created` with `ImportOut`.

---

#### `GET /v1/imports`

Returns the import history for a trading account owned by the authenticated user.

**Query params:**
- `account_id: uuid.UUID` — required.

**Implementation sequence:**

1. Verify the account belongs to the authenticated user: call `TradingAccountService.get(session, user_id, account_id)`. This method does **not** require ACTIVE status — a user can view import history for a deactivated account. If you need to bypass the ACTIVE check, call the underlying `TradingAccountRepository.get(session, account_id, user_id)` directly (or add a `get_any()` method to `TradingAccountService`). Return 404 `ACCOUNT_NOT_FOUND` if not owned.
2. Call `ImportRecordRepository.list_by_account(session, account_id, limit=20)`.
3. Return `list[ImportRecordOut]`.

> **Note on `TradingAccountService.get()` vs `get_active()`:** Use `get()` (ownership check only, no status check) for this endpoint. A user reviewing import history for a now-deactivated account must still be able to see what was imported. If `TradingAccountService.get()` does not exist (only `get_active()` does), add it as a thin wrapper that omits the ACTIVE status check.

**Response:** `200 OK` with `list[ImportRecordOut]` (may be empty list).

---

### Task B-17-C — Wire Imports Router into `main.py`

Add to `main.py` alongside other v1 routers:

```python
from tradeforge.api.v1 import imports as imports_router
app.include_router(imports_router.router, prefix="/v1")
```

---

### Backend Tests (Bhima)

**New file:** `backend/tests/api/test_imports_api.py`

Use real Zerodha/Upstox/Angel One fixture CSV bytes already present in the test suite from Step 11. Do not re-create fixtures.

| Test ID | Description |
|---------|-------------|
| B-17-01 | `POST /v1/imports` with valid Zerodha CSV → 201; `fills_ingested > 0`, `status = "COMPLETE"`, `import_record_id` is a valid UUID |
| B-17-02 | `POST /v1/imports` with same file for same account again → 409 `DUPLICATE_IMPORT` |
| B-17-03 | `POST /v1/imports` with same file for a different account owned by the same user → 201 (hash+account unique, not hash-only) |
| B-17-04 | `POST /v1/imports` with a non-CSV text file → 422 `UNRECOGNIZED_FILE` |
| B-17-05 | `POST /v1/imports` with header-only CSV (zero data rows) → 422 `EMPTY_FILE` |
| B-17-06 | `POST /v1/imports` with another user's `account_id` → 404 `ACCOUNT_NOT_FOUND` |
| B-17-07 | `POST /v1/imports` with INACTIVE account → 404 `ACCOUNT_NOT_FOUND` |
| B-17-08 | `POST /v1/imports` unauthenticated → 401 |
| B-17-09 | `POST /v1/imports` with invalid `product_type_hint` value → 422 `INVALID_PRODUCT_TYPE_HINT` |
| B-17-10 | `GET /v1/imports?account_id=<uuid>` returns list for owned account; asserts length and first entry fields |
| B-17-11 | `GET /v1/imports?account_id=<uuid>` for another user's account → 404 |
| B-17-12 | `GET /v1/imports?account_id=<uuid>` unauthenticated → 401 |
| B-17-13 | `GET /v1/imports?account_id=<uuid>` for deactivated account owned by user → 200 (not 404) |
| B-17-14 | `POST /v1/imports` with Upstox CSV → 201 (adapter dispatch coverage) |
| B-17-15 | `POST /v1/imports` with Angel One CSV → 201 (adapter dispatch coverage) |

---

## Frontend Scope (Owner: Arjun)

### Task F-17-A — API Client: `src/features/imports/api.ts`

New file. Follows the existing `accountsApi` / `tradesApi` pattern.

```typescript
export const importsApi = {
  upload: (body: FormData) =>
    apiClient.post<ImportOut>('/v1/imports', body, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  list: (accountId: string) =>
    apiClient.get<ImportRecordOut[]>(`/v1/imports?account_id=${accountId}`),
}
```

**Types:** `src/features/imports/types.ts`

```typescript
export interface ImportOut {
  import_record_id: string
  account_id: string
  broker: string
  file_name: string | null
  fills_ingested: number
  fills_skipped: number
  row_errors: number
  trades_created: number
  trades_closed: number
  status: 'COMPLETE' | 'PARTIAL' | 'EMPTY' | 'FAILED'
  imported_at: string
}

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

---

### Task F-17-B — Import Trades Screen: `src/features/imports/ImportTradesPage.tsx`

Routed at `/import`. Linked from the navigation sidebar (add "Import" link to `AppShell`).

#### Layout

**Section 1 — Upload form**

| Field | Notes |
|-------|-------|
| Account selector | Populated from `useAccount()`. Active accounts only. Shows account name + broker chip (e.g. "Main account · ZERODHA"). Defaults to `selectedAccount`. Required. |
| Product type hint | Optional `<select>` labelled "F&O product type (if needed)". Options: "Auto-detect (default)", "MIS — Intraday", "CNC — Delivery", "NRML — Overnight". Default: auto-detect (send `null`). Show a `?` tooltip: "Select only if your file contains F&O rows and the import reports a product type error." |
| File input | Accepts `.csv` only. Drag-and-drop zone or standard file button. Show the selected filename once a file is chosen. |
| Import button | Label: "Import". Disabled until both account and file are selected. Disabled while request is in-flight (show spinner). |

**Client-side validation (before submission):**
- Account must be selected.
- File must have a `.csv` extension — show inline error "Please select a CSV file" if not.
- File size > 5 MB: show inline warning "This file is unusually large for a broker export. Proceed?" (not a block — just a warning; user can still submit).

**Section 2 — Import result** (shown after a successful or error submission)

| State | Display |
|-------|---------|
| COMPLETE | Green success banner: "Import complete — X fills imported." Sub-line: "Y fills skipped (already imported)." |
| PARTIAL | Amber warning banner: "Import partially completed — X fills imported, Z rows could not be read. Check that the file is a valid Zerodha / Upstox / Angel One export." |
| EMPTY | Amber warning banner: "No new fills found. The file may already be fully imported or contain no data rows." |
| FAILED | Red error banner: "Import failed — no fills could be read. Check the file format." |
| 409 DUPLICATE_IMPORT | Red inline error: "This file has already been imported to this account." |
| 422 UNRECOGNIZED_FILE | Red inline error: "File format not recognised. Only Zerodha, Upstox, and Angel One CSV exports are supported." |
| 422 MISSING_PRODUCT_TYPE | Amber inline error: "This file contains F&O rows but no product type column. Select a product type above and try again." (auto-expand the product type hint select) |

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
| `POST /v1/imports` | `IMPORT_SUCCESS` (201, COMPLETE), `IMPORT_DUPLICATE` (409), `IMPORT_UNRECOGNIZED` (422), `IMPORT_MISSING_PRODUCT_TYPE` (422) |
| `GET /v1/imports?account_id=*` | `IMPORT_HISTORY` (list of ImportRecordOut) |

**ImportTradesPage tests (`src/features/imports/__tests__/ImportTradesPage.test.tsx`):**

| Test ID | Description |
|---------|-------------|
| F-17-01 | Renders account selector populated from AccountContext |
| F-17-02 | Import button is disabled when no file is selected |
| F-17-03 | Import button is disabled when no account is selected |
| F-17-04 | Non-CSV file shows inline "Please select a CSV file" error; Import button remains disabled |
| F-17-05 | On successful import (COMPLETE), shows green banner with fills_ingested count |
| F-17-06 | On 409 DUPLICATE_IMPORT, shows inline duplicate error message |
| F-17-07 | On 422 UNRECOGNIZED_FILE, shows inline unrecognised format message |
| F-17-08 | On 422 MISSING_PRODUCT_TYPE, shows amber error and product type hint select is visible |
| F-17-09 | Import button is disabled while request is in-flight |
| F-17-10 | "Import another file" button resets file selection and clears result banner |
| F-17-11 | Import history list renders on mount with account_id from context |
| F-17-12 | Import history list re-fetches after a successful import |
| F-17-13 | Empty import history shows "No imports yet for this account." |

---

## Explicitly NOT in Step 17

| Deferred to | What |
|-------------|------|
| Phase 2 | Real-time import progress bar (requires async Celery job infrastructure) |
| Phase 2 | Column mapping UI for unknown broker CSV formats |
| Phase 2 | Broker API integrations (live trade sync via Zerodha Kite Connect etc.) — Sanjaya |
| Phase 2 | Fill exclusion UI — required before safe re-import after manual gap-repair (R-16-6) |
| Phase 2 | Re-import of a file that has already been imported (file-hash dedup is a hard constraint for Phase 1) |
| Phase 2 | Malware / content scanning of uploaded files |

---

## Key Risk: Mixed-Provenance Double-Count (R-16-6 Carried Forward)

From Step 16 risk register (R-16-6): if a user has added a manual fill to an open position (Step 16 gap-repair use case, D3), and then imports a broker CSV covering the same period, the broker's fill and the user's manual fill will both be inserted — the broker's fill has a real `broker_trade_id`; the user's fill has a generated UUID. `fill_exists()` does not match them. The position is double-counted until the user manually excludes one fill via the fill exclusion mechanism — which has no UI in Phase 1.

**Mitigation for Phase 1:**
- Bhima must add a code comment in `POST /v1/imports` route handler warning future developers about this gap.
- Arjun must add a UI notice on the Import screen: "If you've manually added fills to an open position, review those trades after importing a file that covers the same period. Duplicate fills may require support to resolve."
- This is an accepted known risk for Phase 1. The fill-exclusion UI (Phase 2) resolves it.

---

## Order of Work

### Bhima (backend — can start immediately)

1. Add `list_by_account()` to `ImportRecordRepository`.
2. Verify `TradingAccountService.get()` (ownership only, no ACTIVE check) exists — add it if not.
3. Create `backend/src/tradeforge/api/v1/imports.py` with `POST /v1/imports` and `GET /v1/imports`.
4. Wire `imports` router into `main.py`.
5. Write backend tests B-17-01 through B-17-15.

### Arjun (frontend — steps 1–2 can start in parallel with Bhima)

1. Create `src/features/imports/types.ts` and `src/features/imports/api.ts`.
2. Add MSW fixtures and handlers for imports endpoints.
3. Implement `src/features/imports/ImportTradesPage.tsx` — upload form, result section, history list.
4. Update `frontend/src/app.tsx` to add the `/import` route.
5. Update `AppShell.tsx` to add "Import" sidebar link.
6. Write frontend tests F-17-01 through F-17-13.

**Arjun dependency on Bhima:** All frontend work can be developed against MSW fixtures. No blocker.

---

## Gate Criteria

| Gate | Owner | Criteria |
|------|-------|---------|
| Sahadeva QA | Sahadeva | All 28 new tests pass (B-17-01 through B-17-15, F-17-01 through F-17-13); no regressions in Steps 12–16 tests; duplicate import 409 confirmed by B-17-02; deactivated-account history access confirmed by B-17-13 (ownership-only check) |
| Nakula CI | Nakula | `pytest` coverage thresholds pass; `npm run coverage` passes thresholds; `tsc --noEmit` clean; ESLint 0 warnings; no new migration (import_records table already exists) |
| Yudhishthira accept | Yudhishthira | Import Trades screen accessible from nav; CSV upload produces COMPLETE result with fill count; duplicate file upload shows error; import history list shows past imports |

---

## Effort Estimate

| Owner | Work | Estimate |
|-------|------|----------|
| Bhima | `list_by_account()` method + `get()` ownership check | ~0.1 session |
| Bhima | `imports.py` router — 2 routes + error mapping | ~0.25 session |
| Bhima | Wire into `main.py` | ~0.05 session |
| Bhima | Backend tests B-17-01 through B-17-15 | ~0.35 session |
| Arjun | Types + API client + MSW fixtures | ~0.15 session |
| Arjun | `ImportTradesPage.tsx` — 3 sections | ~0.45 session |
| Arjun | Router + AppShell updates | ~0.05 session |
| Arjun | Frontend tests F-17-01 through F-17-13 | ~0.3 session |
| **Total** | | **~1.7 sessions** |

Well within the Phase 1 plan estimate of 1 session — at the high end due to the result/error UX states. No scope is at risk.

---

## Pre-Conditions Confirmed

- Step 15 (account selection) ✅ merged to main
- Step 16 (manual trade entry) ✅ merged to main as PR #10
- Branch `feat/step-17-import-trades` ✅ created from `main` (head: `43faf38`)
- No new migration required — `import_records` table created in Step 11
- All three broker adapters (Zerodha, Upstox, Angel One) are registered and tested — Sanjaya confirmed correctness in Step 11

---

*Krishna — Senior Project Manager*  
*Source: `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`, `backend/src/tradeforge/application/import_service.py`, `backend/src/tradeforge/infrastructure/models/import_record.py`, `backend/src/tradeforge/infrastructure/repositories/import_record_repo.py`, `docs/project-status/STEP-16-EXECUTION-PLAN.md` (R-16-6)*
