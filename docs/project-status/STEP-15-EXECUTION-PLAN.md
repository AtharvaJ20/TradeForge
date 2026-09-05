# Step 15 — User Profile + Account/Broker Management Screen

**Document:** `docs/project-status/STEP-15-EXECUTION-PLAN.md`  
**Author:** Krishna (Project Manager)  
**Date:** 2026-09-05  
**Parent plan:** `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`  
**Branch:** `feat/step-15-profile-account-management` (base: `main` after Step 14 merged)  
**Status:** READY TO IMPLEMENT — no external sign-off required before work begins

---

## Goal

Let users set up their profile (display name, time zone, base currency) and manage their trading accounts (create, edit, deactivate) in the UI. Account selection is persisted in app state and drives all downstream analytics and journal queries.

Done means: Settings screen is navigable from the sidebar, profile fields update against `PATCH /v1/users/me`, account list loads from `GET /v1/accounts`, adding/editing/deactivating accounts works end-to-end, account selection drives analytics — Sahadeva GO, Nakula CI GREEN, Yudhishthira ACCEPT.

---

## What "Done" Looks Like

A logged-in user visiting `/settings` can:

1. **View profile** — see their current display name, time zone, and base currency pre-filled.
2. **Update profile** — change display name, time zone, base currency → PATCH persists → success toast appears.
3. **View accounts** — see a list of all their trading accounts with status, broker, and type.
4. **Create account** — fill in name, broker, account type, currency → POST creates → account appears in list.
5. **Edit account** — change display name or account type → PATCH updates → list reflects change.
6. **Deactivate account** — click deactivate → confirmation dialog → DELETE soft-deletes (status → INACTIVE) → account shown as inactive in the list (or removed, Arjun decides).
7. **Select active account** — pick the account that all analytics and journal queries run against. Selection persists across page navigations within the session (localStorage for cross-refresh persistence).

The Settings nav link in the sidebar is no longer a placeholder — it routes to the real SettingsPage.

---

## Opening Obligations

No external specialist sign-off required before implementation starts.

Step 14 must be merged to `main` before this branch is created. It is merged: branch `feat/step-15-profile-account-management` is based on `main` post-Step-14.

Bhima's backend work (migration + new endpoints) can start immediately in parallel with Arjun's frontend scaffolding. Arjun's form wiring depends on the API contract — that contract is fully specified below.

---

## What Already Exists (Do Not Rebuild)

| Concern | What exists | Location |
|---------|-------------|----------|
| Account creation | `POST /v1/accounts` | `backend/src/tradeforge/api/v1/accounts.py:123` |
| Account list | `GET /v1/accounts` | `backend/src/tradeforge/api/v1/accounts.py:145` |
| Account get | `GET /v1/accounts/{id}` | `backend/src/tradeforge/api/v1/accounts.py:155` |
| CSV import | `POST /v1/accounts/{id}/import` | `backend/src/tradeforge/api/v1/accounts.py:169` |
| Auth me | `GET /v1/auth/me` | `backend/src/tradeforge/api/v1/auth.py` |
| User ORM model | `users` table | `backend/src/tradeforge/infrastructure/models/user.py` |
| Trading account service | `create`, `list`, `get`, `get_active` | `backend/src/tradeforge/application/trading_account_service.py` |
| Account repo | `create`, `get_for_user`, `list_for_user` | `backend/src/tradeforge/infrastructure/repositories/trading_account_repo.py` |
| User repo | `find_by_id`, `update_password`, `set_email_verified` | `backend/src/tradeforge/infrastructure/repositories/user_repo.py` |
| AppShell + sidebar | Nav renders Settings as placeholder | `frontend/src/layout/AppShell.tsx` |
| Router | `/settings` → `PlaceholderPage` | `frontend/src/app.tsx` or `router.tsx` |

---

## Backend Scope (Owner: Bhima)

### Task B-15-A — Migration 0014: User Profile Fields

**File:** `backend/alembic/versions/0014_user_profile_fields.py`

Add three nullable columns to the `users` table:

```sql
ALTER TABLE users
  ADD COLUMN display_name  VARCHAR(100),
  ADD COLUMN time_zone     VARCHAR(60)  NOT NULL DEFAULT 'Asia/Kolkata',
  ADD COLUMN base_currency CHAR(3)      NOT NULL DEFAULT 'INR';
```

- `display_name`: nullable; users who have never set one fall back to their email prefix on the frontend.
- `time_zone`: defaults to `'Asia/Kolkata'` — the overwhelming majority of Phase 1 users are Indian retail traders. Stored as an IANA timezone string. Backend validates against `zoneinfo.available_timezones()`.
- `base_currency`: defaults to `'INR'`. Phase 1 only accepts `INR` at the API level (Phase 2 expands this). Backend validates as ISO-4217 three-letter code; reject anything not `INR` for Phase 1 to keep P&L calculations consistent.

**Downgrade:** reverse the `ALTER TABLE` (drop the three columns).

**Grant:** add a `GRANT UPDATE (display_name, time_zone, base_currency) ON users TO tradeforge_app;` statement consistent with the grant pattern in `0013_grant_trading_accounts.py`.

---

### Task B-15-B — New Router: `GET /v1/users/me` and `PATCH /v1/users/me`

**File (new):** `backend/src/tradeforge/api/v1/users.py`

Register under `prefix="/users"`, tag `"users"`.

#### `GET /v1/users/me`

Returns the authenticated user's full profile including the new fields.

Response schema `UserProfileOut`:

```python
class UserProfileOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    display_name: str | None
    time_zone: str
    base_currency: str
    is_email_verified: bool
    is_admin: bool
    created_at: datetime
```

Security: `user_id` from session only. Never from request body or path.

#### `PATCH /v1/users/me`

Partial update — all fields optional (omitted fields are not changed).

Request schema `UpdateProfileRequest`:

```python
class UpdateProfileRequest(BaseModel):
    model_config = {"extra": "forbid"}

    display_name: str | None = Field(default=None, max_length=100)
    time_zone: str | None = Field(default=None)
    base_currency: str | None = Field(default=None)
```

Validation rules:
- `display_name`: strip whitespace; if provided and blank after strip → 422 `DISPLAY_NAME_BLANK`
- `time_zone`: validate against `zoneinfo.available_timezones()` → 422 `INVALID_TIMEZONE` if not found
- `base_currency`: Phase 1 only accepts `"INR"` → 422 `UNSUPPORTED_CURRENCY` for anything else

Returns `UserProfileOut` of the updated user.

**Add `update_profile` to `UserRepository`:**

```python
async def update_profile(
    self,
    user_id: uuid.UUID,
    *,
    display_name: str | None = UNSET,
    time_zone: str | None = UNSET,
    base_currency: str | None = UNSET,
) -> User:
    ...
```

Use a sentinel `UNSET` pattern so that passing `display_name=None` explicitly sets the field to `NULL`, while omitting the argument leaves it unchanged. Return the updated `User` ORM object (after `refresh`).

**Wire the new router into the main FastAPI app** wherever existing routers (`auth`, `analytics`, `accounts`, `risk`) are registered.

---

### Task B-15-C — Extend Accounts Router: PATCH + DELETE

**File:** `backend/src/tradeforge/api/v1/accounts.py`

Two new routes, appended to the existing router.

#### `PATCH /v1/accounts/{account_id}`

Request schema `UpdateAccountRequest`:

```python
class UpdateAccountRequest(BaseModel):
    model_config = {"extra": "forbid"}

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    account_type: str | None = Field(default=None)
```

- Validates `account_type` against `_VALID_ACCOUNT_TYPES` if provided.
- Returns `AccountOut` of the updated account.
- 404 if account not found or not owned by user.
- 422 if `display_name` is blank after strip.

Add `update` method to `TradingAccountService` and `TradingAccountRepository`:

```python
# TradingAccountRepository
async def update(
    self,
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    display_name: str | None = None,
    account_type: str | None = None,
) -> TradingAccountDomain | None:
    ...
```

Only set the columns that are non-`None` in the `values()` call. Return `None` if the account doesn't exist or isn't owned by the user.

#### `DELETE /v1/accounts/{account_id}`

Soft-delete: sets `status = 'INACTIVE'` on the account. No hard delete.

- 404 if account not found or not owned by user.
- 204 No Content on success.
- Idempotent: calling DELETE on an already-inactive account returns 204 (no error).

Add `deactivate` method to `TradingAccountService` and `TradingAccountRepository`:

```python
async def deactivate(
    self,
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
) -> bool:
    ...  # returns True if found, False if not found
```

---

### Backend Tests (Bhima)

All new tests go in `backend/tests/`. Follow the existing conftest fixtures and `AsyncClient` pattern.

| Test ID | File | Description |
|---------|------|-------------|
| B-15-01 | `tests/api/test_users_api.py` | `GET /v1/users/me` returns `UserProfileOut` with `display_name`, `time_zone`, `base_currency` for authenticated user |
| B-15-02 | `tests/api/test_users_api.py` | `GET /v1/users/me` returns 401 when unauthenticated |
| B-15-03 | `tests/api/test_users_api.py` | `PATCH /v1/users/me` with `display_name` updates and returns updated profile |
| B-15-04 | `tests/api/test_users_api.py` | `PATCH /v1/users/me` with blank `display_name` returns 422 `DISPLAY_NAME_BLANK` |
| B-15-05 | `tests/api/test_users_api.py` | `PATCH /v1/users/me` with invalid `time_zone` returns 422 `INVALID_TIMEZONE` |
| B-15-06 | `tests/api/test_users_api.py` | `PATCH /v1/users/me` with `base_currency="USD"` returns 422 `UNSUPPORTED_CURRENCY` |
| B-15-07 | `tests/api/test_users_api.py` | `PATCH /v1/users/me` with no body fields is a no-op — returns unchanged profile |
| B-15-08 | `tests/api/test_users_api.py` | `PATCH /v1/users/me` with `display_name=null` clears the field (returns `null`) |
| B-15-09 | `tests/api/test_accounts_api.py` | `PATCH /v1/accounts/{id}` updates `display_name` — returns updated `AccountOut` |
| B-15-10 | `tests/api/test_accounts_api.py` | `PATCH /v1/accounts/{id}` with invalid `account_type` returns 422 |
| B-15-11 | `tests/api/test_accounts_api.py` | `PATCH /v1/accounts/{id}` for another user's account returns 404 |
| B-15-12 | `tests/api/test_accounts_api.py` | `DELETE /v1/accounts/{id}` sets status to INACTIVE — subsequent GET returns `status: INACTIVE` |
| B-15-13 | `tests/api/test_accounts_api.py` | `DELETE /v1/accounts/{id}` is idempotent — second DELETE returns 204 |
| B-15-14 | `tests/api/test_accounts_api.py` | `DELETE /v1/accounts/{id}` for another user's account returns 404 |
| B-15-15 | `tests/unit/application/test_trading_account_service.py` | `update()` with only `display_name` — only that column changes |
| B-15-16 | `tests/unit/application/test_trading_account_service.py` | `deactivate()` returns True for existing account, False for missing account |

---

## Frontend Scope (Owner: Arjun)

### Task F-15-A — Account Context: `src/features/accounts/context/AccountContext.tsx`

Global account selection state, analogous to `AuthContext`.

**Responsibilities:**
- On mount (after `AuthContext` confirms user is authenticated): call `GET /v1/accounts` to load the user's accounts.
- Expose `accounts: Account[]`, `selectedAccount: Account | null`, `selectAccount(id: string): void`, `isLoading: boolean`.
- Persist `selectedAccountId` in `localStorage` under key `'tf_selected_account_id'`. On load, if the stored ID is present in the fetched accounts list, pre-select it. Otherwise, auto-select the first active account (status `ACTIVE`).
- Expose `refetchAccounts(): void` — called after create/edit/deactivate to refresh the list.

`AccountContext` must be rendered inside `AuthProvider` and inside `<RequireAuth>` — it should not fetch until the user is confirmed authenticated.

Export `useAccount()` hook — throws if called outside `AccountProvider`.

**API client additions** (`src/features/accounts/api.ts` — new file):

```typescript
export const accountsApi = {
  list: () => apiClient.get<Account[]>('/v1/accounts'),
  create: (body: CreateAccountBody) => apiClient.post<Account>('/v1/accounts', body),
  update: (id: string, body: UpdateAccountBody) =>
    apiClient.patch<Account>(`/v1/accounts/${id}`, body),
  deactivate: (id: string) => apiClient.delete<void>(`/v1/accounts/${id}`),
}
```

**Types** (`src/features/accounts/types.ts`):

```typescript
export interface Account {
  id: string
  user_id: string
  broker: string
  display_name: string
  account_type: string
  base_currency: string
  status: 'ACTIVE' | 'INACTIVE'
  created_at: string
  updated_at: string
}

export interface CreateAccountBody {
  broker: string
  display_name: string
  account_type: string
  base_currency: string
}

export interface UpdateAccountBody {
  display_name?: string
  account_type?: string
}
```

---

### Task F-15-B — Profile API Client: Extend `src/features/auth/api.ts`

Add two calls to the existing `authApi` object:

```typescript
getProfile: () => apiClient.get<UserProfile>('/v1/users/me'),
updateProfile: (body: UpdateProfileBody) =>
  apiClient.patch<UserProfile>('/v1/users/me', body),
```

**Update `src/features/auth/types.ts`** — extend the `User` type:

```typescript
export interface User {
  id: string
  email: string
  display_name: string | null
  time_zone: string
  base_currency: string
  is_email_verified: boolean
  is_admin: boolean
  created_at: string
}

export interface UpdateProfileBody {
  display_name?: string | null
  time_zone?: string
  base_currency?: string
}
```

> `AuthContext` already calls `GET /v1/auth/me` on mount. That endpoint returns the old `UserResponse` shape (no profile fields). **Do not change `GET /v1/auth/me`** — it is used purely for session presence. The Settings page calls `GET /v1/users/me` directly to load the richer profile.

---

### Task F-15-C — Settings Page: `src/features/settings/`

#### `src/features/settings/SettingsPage.tsx`

Two-section layout (tabs or vertical scroll with anchored headings — Arjun's call):

1. **Profile** section
2. **Accounts** section

This is the real implementation of the `/settings` route — the `PlaceholderPage` for Settings is replaced.

---

#### Profile Section: `src/features/settings/components/ProfileSection.tsx`

Loads `GET /v1/users/me` on mount via a `useQuery`.

**Form fields:**

| Field | Type | Notes |
|-------|------|-------|
| Display Name | text input | optional; shows placeholder "Your name" |
| Time Zone | select / searchable dropdown | options are a curated list of IANA zones (not the full 500+ — show the ~30 most relevant to Indian traders + a search input). Default: `Asia/Kolkata`. |
| Base Currency | select | Phase 1: only `INR` in the dropdown. Disabled select or read-only field is acceptable. |

On submit: `PATCH /v1/users/me` → on success show a success toast/notice; on error show inline error.

**Validation (client-side, before submit):**
- `display_name`: if provided, must not be blank after trim.

**Time zone options (curated — not dynamic):** Include at minimum: `Asia/Kolkata`, `Asia/Dubai`, `Asia/Singapore`, `Asia/Tokyo`, `Europe/London`, `Europe/Berlin`, `America/New_York`, `America/Chicago`, `America/Los_Angeles`, `UTC`. Arjun may expand this list. These are hardcoded in the component — no API call for timezone list.

---

#### Accounts Section: `src/features/settings/components/AccountsSection.tsx`

Uses `useAccount()` from `AccountContext`.

**Account list:** table or card list showing each account:
- Display name
- Broker badge (ZERODHA, UPSTOX, ANGEL\_ONE, MANUAL)
- Account type (INDIVIDUAL, HUF)
- Status badge (ACTIVE green, INACTIVE grey)
- Edit button (opens `EditAccountModal`)
- Deactivate button (opens confirmation dialog) — hidden for already-inactive accounts

**Add account button** → opens `CreateAccountModal`.

**Account selector:** For each ACTIVE account, a "Select" or radio-style indicator that sets it as the active account in `AccountContext`. The currently selected account is highlighted.

---

#### `src/features/settings/components/CreateAccountModal.tsx`

Modal (or slide-over panel — Arjun's call). Form fields:

| Field | Type | Options |
|-------|------|---------|
| Display Name | text | required, 1–100 chars |
| Broker | select | ZERODHA, UPSTOX, ANGEL\_ONE, MANUAL |
| Account Type | select | INDIVIDUAL, HUF |
| Base Currency | select | INR (Phase 1 only) |

On submit: calls `accountsApi.create()` → on success: calls `refetchAccounts()`, closes modal.

Client-side: all fields required. Display name must not be blank.

---

#### `src/features/settings/components/EditAccountModal.tsx`

Pre-populated with the account being edited. Only `display_name` and `account_type` are editable (broker and currency are immutable post-creation — Phase 1).

On submit: calls `accountsApi.update(id, body)` → on success: `refetchAccounts()`, closes modal.

---

#### Deactivate Confirmation Dialog

Inline (not a modal-stack) confirmation: "Are you sure you want to deactivate [Account Name]? It will no longer appear in analytics or trade imports."

Confirm → `accountsApi.deactivate(id)` → `refetchAccounts()`.

---

### Task F-15-D — Router + AppShell Updates

**`src/app.tsx` (or router file):** Replace the `PlaceholderPage` for `/settings` with the real `SettingsPage`.

**`src/layout/AppShell.tsx`:** No change needed to the link itself — it already links to `/settings`. The route replacement handles the rest.

**`AccountProvider` placement:** Wrap the protected route content in `AccountProvider`:

```tsx
<RequireAuth>
  <AccountProvider>
    <AppShell>
      <Outlet />
    </AppShell>
  </AccountProvider>
</RequireAuth>
```

This ensures `useAccount()` is available to all protected pages from Step 15 onwards.

---

### Frontend Tests (Arjun)

All tests follow the existing MSW + Vitest + Testing Library pattern.

**Add MSW handlers to `src/__tests__/msw/handlers.ts`:**

| Handler | Fixture |
|---------|---------|
| `GET /v1/users/me` | `USER_PROFILE_FIXTURE` (with display_name, time_zone, base_currency) |
| `PATCH /v1/users/me` | `UPDATE_PROFILE_SUCCESS`, `UPDATE_PROFILE_INVALID_TZ`, `UPDATE_PROFILE_BLANK_NAME` |
| `GET /v1/accounts` | `ACCOUNTS_LIST_FIXTURE` (2 accounts: 1 ACTIVE, 1 INACTIVE), `ACCOUNTS_EMPTY_FIXTURE` |
| `POST /v1/accounts` | `CREATE_ACCOUNT_SUCCESS`, `CREATE_ACCOUNT_INVALID` |
| `PATCH /v1/accounts/:id` | `UPDATE_ACCOUNT_SUCCESS` |
| `DELETE /v1/accounts/:id` | `DEACTIVATE_ACCOUNT_SUCCESS` (204) |

**AccountContext tests (`F-15-01` to `F-15-05`):**

| Test ID | Description |
|---------|-------------|
| F-15-01 | On mount, fetches `/v1/accounts` and populates `accounts` list |
| F-15-02 | Auto-selects first ACTIVE account when no stored selection in localStorage |
| F-15-03 | Restores stored `selectedAccountId` from localStorage if present in fetched accounts |
| F-15-04 | Falls back to first ACTIVE account if stored ID is not in fetched list |
| F-15-05 | `selectAccount()` updates `selectedAccount` and writes to localStorage |

**ProfileSection tests (`F-15-06` to `F-15-11`):**

| Test ID | Description |
|---------|-------------|
| F-15-06 | Renders pre-populated display name, time zone, base currency from `GET /v1/users/me` |
| F-15-07 | Submit with valid `display_name` change calls `PATCH /v1/users/me` and shows success notice |
| F-15-08 | Submit with blank `display_name` shows client-side error before API call |
| F-15-09 | Shows inline error message when PATCH returns 422 `INVALID_TIMEZONE` |
| F-15-10 | Shows inline error message when PATCH returns 422 `DISPLAY_NAME_BLANK` |
| F-15-11 | Submit button is disabled while PATCH is in flight |

**AccountsSection tests (`F-15-12` to `F-15-18`):**

| Test ID | Description |
|---------|-------------|
| F-15-12 | Renders account list with display name, broker, status for each account |
| F-15-13 | INACTIVE account does not show a Deactivate button |
| F-15-14 | Clicking "Add Account" opens `CreateAccountModal` |
| F-15-15 | `CreateAccountModal` submit with valid data calls `POST /v1/accounts` and closes modal |
| F-15-16 | `CreateAccountModal` submit with blank display name shows validation error (no API call) |
| F-15-17 | Clicking Edit opens `EditAccountModal` pre-populated with account data |
| F-15-18 | Deactivate confirmation confirms then calls `DELETE /v1/accounts/{id}` |

---

## Explicitly NOT in Step 15

| Deferred to | What |
|-------------|------|
| Step 16 | Manual trade entry screen |
| Step 17 | Import trades screen |
| Step 18 | Dashboard screen (real content) |
| Step 19 | Trade list and detail screens |
| Phase 2 | Deposits/withdrawals tracking per account |
| Phase 2 | Per-account fee configuration UI (charge schedules exist in backend) |
| Phase 2 | Account-level P&L reports with capital return calculations |
| Phase 2 | Expanding `base_currency` beyond INR |
| Phase 3 | OAuth account linking |

---

## Order of Work

### Bhima (backend — can start immediately)

1. Write migration `0014_user_profile_fields.py` — run locally, verify `alembic upgrade head` clean
2. Add `update_profile` to `UserRepository` (user_repo.py)
3. Create `backend/src/tradeforge/api/v1/users.py` — GET + PATCH `/v1/users/me`
4. Register the new users router in the FastAPI app
5. Add `update` and `deactivate` to `TradingAccountRepository` and `TradingAccountService`
6. Add PATCH and DELETE routes to `accounts.py`
7. Write backend tests B-15-01 through B-15-16

### Arjun (frontend — steps 1–2 can start in parallel with Bhima)

1. Create `src/features/accounts/types.ts`, `src/features/accounts/api.ts`, MSW fixtures
2. Create `AccountContext.tsx` + `useAccount()` hook + `AccountProvider`
3. Extend `src/features/auth/types.ts` and `api.ts` with profile types and calls
4. Create `SettingsPage.tsx` scaffold (two sections, no wiring yet)
5. Implement `ProfileSection.tsx` with useQuery + mutation (wire to MSW in tests)
6. Implement `AccountsSection.tsx`, `CreateAccountModal.tsx`, `EditAccountModal.tsx`
7. Wire `AccountProvider` into the protected route tree (`app.tsx` / router)
8. Replace `/settings` placeholder with real `SettingsPage` in router
9. Write frontend tests F-15-01 through F-15-18
10. **Arjun dependency on Bhima:** Profile form and account mutations can be developed against MSW fixtures. No blocker. Integration against the real backend happens once Bhima's task B-15-B and B-15-C are up on the branch.

---

## Risk Register (Step 15)

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|-----------|
| R-15-1 | `AccountContext` fetches before session is confirmed → 401 on mount → race with `AuthContext` | Medium | Medium | `AccountProvider` is rendered inside `<RequireAuth>` which only renders when `AuthContext` has confirmed the user. No fetch fires until `isLoading` is `false` and `user` is set. |
| R-15-2 | `selectedAccountId` in localStorage from a previous session belongs to an account now deleted/inactive → stale selection | Low | Medium | On load, validate the stored ID against the fetched accounts list. If missing or inactive, fall back to the first ACTIVE account. Write this fallback as an explicit test (F-15-04). |
| R-15-3 | `PATCH /v1/users/me` and `GET /v1/auth/me` return different shapes — `AuthContext` user state and Settings profile state diverge | Low | Low | `AuthContext` uses `GET /v1/auth/me` (existing, unchanged shape) for session presence only. Settings uses `GET /v1/users/me` (richer shape) for profile display. These are intentionally separate concerns — no single source of truth conflict because AuthContext does not hold display_name/timezone. |
| R-15-4 | Time zone dropdown with 500+ options is unusable | Medium | Medium | Arjun renders a curated list of ~10 common zones (specified above). This list is hardcoded, not fetched. No external library needed. |
| R-15-5 | Deactivating the currently selected account leaves `selectedAccount` pointing to an INACTIVE account | Medium | Medium | `refetchAccounts()` after deactivate re-runs the selection logic. If the previously selected account is now INACTIVE, fallback to first ACTIVE. Arjun must confirm this path in `AccountContext` implementation. |
| R-15-6 | Migration 0014 column defaults conflict with existing `users` rows if the CI database has pre-existing test users | Low | Low | `time_zone` and `base_currency` have server-side defaults (`'Asia/Kolkata'`, `'INR'`). `display_name` is nullable. Existing rows receive the defaults on `ALTER TABLE`. Verify in migration dry-run. |

---

## Gate Criteria

| Gate | Owner | Criteria |
|------|-------|---------|
| Sahadeva QA | Sahadeva | All 34 new tests pass (B-15-01 through B-15-16, F-15-01 through F-15-18); no regressions in Step 14 auth tests or analytics tests; Settings screen manually verified for keyboard navigation and tab order |
| Nakula CI | Nakula | `pytest` coverage thresholds pass; `npm run coverage` passes thresholds (lines ≥ 70, functions ≥ 45, branches ≥ 79); `tsc --noEmit` clean; ESLint 0 warnings; `alembic upgrade head` applies cleanly from prior head |
| Yudhishthira accept | Yudhishthira | Profile update persists and reloads correctly; account creation appears in list; deactivate confirmation flow works; account selector in Settings drives account context (observable in subsequent Steps 16–18 via `useAccount()`) |

---

## Effort Estimate

| Owner | Work | Estimate |
|-------|------|----------|
| Bhima | Migration + UserRepo update + users router (GET/PATCH) | ~0.25 session |
| Bhima | Account PATCH/DELETE + service/repo updates | ~0.25 session |
| Bhima | Backend tests B-15-01 through B-15-16 | ~0.25 session |
| Arjun | AccountContext + API clients + types | ~0.25 session |
| Arjun | SettingsPage: ProfileSection + AccountsSection + modals | ~0.5 session |
| Arjun | Router wiring + AppShell AccountProvider wrap | ~0.1 session |
| Arjun | Frontend tests F-15-01 through F-15-18 | ~0.4 session |
| **Total** | | **~1.5–2 sessions** |

This is within the Phase 1 plan estimate of 1 session, with a modest overrun risk driven by the account context and modal interaction complexity. No scope is at risk — all items above are Phase 1 required.

---

*Krishna — Senior Project Manager*  
*Source: `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`, `backend/src/tradeforge/api/v1/accounts.py`, `backend/src/tradeforge/infrastructure/models/user.py`, `backend/src/tradeforge/infrastructure/repositories/user_repo.py`, `frontend/src/features/auth/`, `frontend/src/layout/AppShell.tsx`*
