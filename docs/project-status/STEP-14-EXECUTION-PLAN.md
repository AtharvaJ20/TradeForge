# Step 14 — Frontend Navigation Shell + Auth Screens

**Document:** `docs/project-status/STEP-14-EXECUTION-PLAN.md`  
**Author:** Krishna (Project Manager)  
**Date:** 2026-09-05  
**Parent plan:** `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`  
**Branch base:** `main` (after `feat/step-13-basic-risk-metrics` is merged via PR)  
**Status:** READY TO IMPLEMENT — no external sign-off required before Arjun begins

---

## Goal

Give the application a navigable structure that a real user can open in a browser, sign up, verify their email, and land on a working analytics page — without any developer assistance.

Done means: React Router wired, auth screens fully functional against the existing backend, navigation sidebar renders on all protected pages, session-expired redirect works, all component tests pass, Sahadeva GO, Nakula CI GREEN, Yudhishthira ACCEPT.

---

## What "Done" Looks Like

A new user visiting the app can:

1. **Register** — fill in email, password, confirm password → POST to `/v1/auth/register` → see a "check your email" screen.
2. **Verify email** — click the link in their email → land on `/verify-email?token=...` → token is automatically submitted → redirect to `/login` with a success notice.
3. **Log in** — enter credentials → POST to `/v1/auth/login` → land on the analytics page (existing content).
4. **Navigate** — sidebar links to Dashboard, Analytics, Risk, Import, Settings. Analytics is functional. All others show a clear "Coming soon" placeholder.
5. **Session expires** — any 401 from the API redirects to `/login` with a "session expired" notice.
6. **Log out** — sidebar logout button clears session and redirects to `/login`.
7. **Request password reset** — enter email → POST to `/v1/auth/password-reset/request` → "check your email" screen.
8. **Confirm password reset** — click email link → land on `/reset-password?token=...` → enter new password → POST to `/v1/auth/password-reset/confirm` → redirect to `/login`.

A returning user visiting any protected route while unauthenticated is redirected to `/login?next=<original-path>` and lands on their intended page after logging in.

---

## Opening Obligations

No specialist sign-off is required before implementation begins. All backend auth endpoints are already built and tested (Steps 2–5). This is a pure-frontend step.

Step 13 PR must be merged to `main` before this branch is created.

---

## Confirmed Backend Endpoints (Already Built — Do Not Modify)

All auth endpoints are registered under `/v1/auth`:

| Method | Path | Body | Success | Key Error Codes |
|--------|------|------|---------|-----------------|
| POST | `/v1/auth/register` | `{email, password}` | 200 `{message}` | `RATE_LIMITED` (429), `PasswordPolicyViolationError` (422) |
| POST | `/v1/auth/login` | `{email, password}` | 200 `UserResponse` + sets `HttpOnly` cookie | `INVALID_CREDENTIALS` (401), `ACCOUNT_LOCKED` (423), `EMAIL_NOT_VERIFIED` (403), `RATE_LIMITED` (429) |
| POST | `/v1/auth/logout` | — | 200 `{message}` + clears cookie | — |
| GET | `/v1/auth/me` | — | 200 `UserResponse` | 401 (not authenticated) |
| POST | `/v1/auth/verify-email` | `{token}` | 200 `{message}` | `INVALID_OR_EXPIRED_TOKEN` (400), `RATE_LIMITED` (429) |
| POST | `/v1/auth/password-reset/request` | `{email}` | 200 `{message}` (enumeration-safe) | `RATE_LIMITED` (429) |
| POST | `/v1/auth/password-reset/confirm` | `{token, new_password}` | 200 `{message}` | `INVALID_OR_EXPIRED_TOKEN` (400), `PasswordPolicyViolationError` (422) |

`UserResponse` shape: `{ id: string, email: string, is_email_verified: boolean, is_admin: boolean }`

Session is cookie-based (`HttpOnly`, `SameSite=Strict`). The frontend never touches the session token directly.

---

## Scope — Frontend Only (Owner: Arjun)

### New Dependency

Install `react-router-dom` v6. Do not install v7 — it introduces breaking API changes. Pin to `6.x`.

```bash
npm install react-router-dom@^6.26.0
npm install --save-dev @types/react-router-dom
```

(`@types/react-router-dom` is included in the package itself from v6.4+; the `--save-dev` install is a no-op safety net. Verify after install.)

---

### Auth Feature Module: `src/features/auth/`

#### `src/features/auth/types.ts`

```typescript
export interface User {
  id: string
  email: string
  is_email_verified: boolean
  is_admin: boolean
}
```

#### `src/features/auth/schemas.ts`

Zod schemas for all auth API responses:

```typescript
import { z } from 'zod'

export const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  is_email_verified: z.boolean(),
  is_admin: z.boolean(),
})

export const MessageSchema = z.object({ message: z.string() })
```

#### `src/features/auth/api.ts`

Thin wrappers over `apiClient`. No business logic.

```typescript
import { apiClient } from '@/lib/api-client'
import type { User } from './types'

export const authApi = {
  me: () => apiClient.get<User>('/v1/auth/me'),
  login: (email: string, password: string) =>
    apiClient.post<User>('/v1/auth/login', { email, password }),
  logout: () => apiClient.post<{ message: string }>('/v1/auth/logout'),
  register: (email: string, password: string) =>
    apiClient.post<{ message: string }>('/v1/auth/register', { email, password }),
  verifyEmail: (token: string) =>
    apiClient.post<{ message: string }>('/v1/auth/verify-email', { token }),
  requestPasswordReset: (email: string) =>
    apiClient.post<{ message: string }>('/v1/auth/password-reset/request', { email }),
  confirmPasswordReset: (token: string, new_password: string) =>
    apiClient.post<{ message: string }>('/v1/auth/password-reset/confirm', {
      token,
      new_password,
    }),
}
```

#### `src/features/auth/context/AuthContext.tsx`

Provides `user`, `isLoading`, `login()`, `logout()` to the component tree. Must be rendered inside `<BrowserRouter>` so it can call `useNavigate`.

**Session-expired pattern:** `api-client.ts` dispatches `new CustomEvent('auth:session-expired')` on any 401 response. `AuthContext` listens for this event and navigates to `/login?expired=1`, clearing local user state. This keeps the API client free of router dependencies.

**Update `api-client.ts`:** In the `request()` function, when `res.status === 401`, dispatch the event before throwing:

```typescript
if (res.status === 401) {
  window.dispatchEvent(new CustomEvent('auth:session-expired'))
}
```

`AuthContext` responsibilities:
- On mount: call `GET /v1/auth/me` to hydrate `user`. Set `isLoading: true` during this check; set to `false` whether authenticated or not. Never render protected content until `isLoading` is `false`.
- `login(email, password)`: call `authApi.login()` → set `user` in state → navigate to `next` param or `/analytics`.
- `logout()`: call `authApi.logout()` → clear `user` → navigate to `/login`.
- Session-expired listener: on `auth:session-expired` event → clear `user` → navigate to `/login?expired=1`.
- Clean up the event listener on unmount.

Export `useAuth()` hook — throws if called outside `AuthProvider` (development guard).

---

#### `src/features/auth/hooks/useLogin.ts`
#### `src/features/auth/hooks/useRegister.ts`
#### `src/features/auth/hooks/usePasswordReset.ts`

TanStack Query `useMutation` wrappers for the form submissions. Error state is surfaced to form components via `mutation.error`. These are not TanStack Query cached queries — they are fire-once mutations.

---

### Auth Screen Components: `src/features/auth/components/`

All auth screens share a full-page centered card layout (`max-w-sm`, centred vertically and horizontally). No sidebar on auth screens — sidebar is only on protected pages.

#### `LoginPage.tsx`

Fields: Email (type=email), Password (type=password).

On submit: call `login(email, password)` from `AuthContext`.

Error states (map backend detail codes):
- `INVALID_CREDENTIALS` → inline: "Incorrect email or password."
- `ACCOUNT_LOCKED` → inline: "Account locked due to too many failed attempts. Contact support."
- `EMAIL_NOT_VERIFIED` → inline: "Please verify your email before logging in." with a "Resend verification" link (Phase 2 — render the message only, not the link, for Phase 1).
- `RATE_LIMITED` → inline: "Too many attempts. Please wait before trying again."
- Network / 5xx → inline: "Something went wrong. Please try again."

URL param: if `?expired=1` is in the URL, show a banner above the form: "Your session expired. Please log in again."  
URL param: if `?verified=1`, show a banner: "Email verified. You can now log in."  
URL param: if `?reset=1`, show a banner: "Password reset successful. Please log in."

Link to: `/register` (no account?), `/forgot-password` (forgot password?).

#### `RegisterPage.tsx`

Fields: Email (type=email), Password (type=password, with strength indicator), Confirm Password (type=password).

Confirm password is client-side only: if passwords don't match, show inline error before submitting.

Password strength indicator: a 4-segment colour bar (red → amber → amber → green) based on client-side scoring. Score increases for: length ≥ 8, length ≥ 12, contains uppercase + lowercase, contains digit or symbol. This is a UX hint — do not block submission; backend is authoritative on policy.

On submit (after client confirm-password check): call `authApi.register()`.

On success: navigate to `/register-success` (a static screen — see below).

Error states:
- `RATE_LIMITED` → "Too many registration attempts. Please wait."
- 422 with `detail` string → show `detail` verbatim (backend password policy message).
- Network / 5xx → "Something went wrong. Please try again."

Link to `/login` (already have an account?).

#### `RegisterSuccessPage.tsx`

Static informational screen. No form, no API call. Text: "Registration successful — check your email for a verification link." Link back to `/login`.

#### `VerifyEmailPage.tsx`

Reads `?token=` from the URL query string on mount. Automatically calls `authApi.verifyEmail(token)` — no user action required.

States:
- Loading: "Verifying your email…"
- Success: "Email verified successfully." → after 2 seconds, navigate to `/login?verified=1`.
- Error (`INVALID_OR_EXPIRED_TOKEN`): "This verification link is invalid or has expired. Request a new one from the login page."
- Missing token (no `?token=` in URL): "Invalid verification link."

Do not auto-navigate on error. Let the user read the message.

#### `ForgotPasswordPage.tsx`

Field: Email (type=email).

On submit: call `authApi.requestPasswordReset(email)`.

On success (always — backend is enumeration-safe): show "If this email is registered, a password reset link has been sent. Check your inbox." Do not re-enable the form.

Error:
- `RATE_LIMITED` → "Too many requests. Please wait before trying again."
- Network / 5xx → "Something went wrong. Please try again."

Link to `/login`.

#### `ResetPasswordPage.tsx`

Reads `?token=` from the URL query string.

Fields: New Password (type=password, with strength indicator), Confirm Password.

Client-side confirm check before submitting.

On submit: call `authApi.confirmPasswordReset(token, newPassword)`.

On success: navigate to `/login?reset=1`.

Error states:
- `INVALID_OR_EXPIRED_TOKEN` → "This reset link is invalid or has expired. Request a new one."
- 422 with `detail` → show `detail` verbatim.
- `RATE_LIMITED` → "Too many attempts. Please wait."

If `?token=` is absent in URL: show "Invalid reset link." with a link to `/forgot-password`.

---

### App Shell: `src/layout/AppShell.tsx`

Rendered as the layout wrapper for all protected routes via React Router's nested route `<Outlet>`.

Structure:
- Sidebar (fixed, left): TradeForge logo/wordmark, nav links, logout button at the bottom.
- Main content area: `<Outlet />` renders the current page.

Nav links (use `<NavLink>` from react-router-dom for active-link highlighting):

| Label | Path | Phase 1 status |
|-------|------|----------------|
| Dashboard | `/` | Placeholder ("Coming soon — Step 18") |
| Analytics | `/analytics` | Functional (existing AnalyticsPage) |
| Risk | `/risk` | Placeholder ("Coming soon — Step 13 metrics will appear here") |
| Trades | `/trades` | Placeholder ("Coming soon — Step 19") |
| Import | `/import` | Placeholder ("Coming soon — Step 17") |
| Settings | `/settings` | Placeholder ("Coming soon — Step 15") |

Logout: clicking the logout button in the sidebar calls `logout()` from `useAuth()`.

Active link: use `NavLink`'s `isActive` prop to apply a distinct background/text colour to the current route. Exact match for `/`; prefix match for all others.

Accessibility: `<nav aria-label="Main navigation">`, each link has meaningful text, sidebar has a visible focus ring.

---

### Protected Route: `src/components/RequireAuth.tsx`

```typescript
// Renders <Outlet /> when authenticated; redirects to /login?next=<pathname> when not.
// Renders null while isLoading (initial auth check) to avoid flash of login screen.
```

Uses `useAuth()` to read `user` and `isLoading`. If `isLoading`, render nothing (or a spinner). If not `user`, `<Navigate to={`/login?next=${location.pathname}`} replace />`. Otherwise render `<Outlet />`.

---

### Route Structure: `src/router.tsx`

```
/login                 LoginPage           (public)
/register              RegisterPage        (public)
/register-success      RegisterSuccessPage (public)
/verify-email          VerifyEmailPage     (public)
/forgot-password       ForgotPasswordPage  (public)
/reset-password        ResetPasswordPage   (public)

<RequireAuth>
  <AppShell>
    /                  → <Navigate to="/analytics" replace />
    /analytics         AnalyticsPage
    /risk              PlaceholderPage ("Risk — Coming soon")
    /trades            PlaceholderPage ("Trades — Coming soon")
    /import            PlaceholderPage ("Import — Coming soon")
    /settings          PlaceholderPage ("Settings — Coming soon")
  </AppShell>
</RequireAuth>
```

`PlaceholderPage` is a single reusable component that accepts a `title` prop and renders a centred "Coming soon" message.

---

### Analytics Page: `src/features/analytics/AnalyticsPage.tsx`

Move the existing content of `src/app.tsx` (filter bar, all analytics cards) into this new file. Remove the hardcoded `DEMO_TRADE` constant and the `JournalPanel` — it was a development scaffold; Step 19 will wire the real trade detail. The analytics page should render analytics cards only.

`src/app.tsx` becomes the router entry point — it renders `<RouterProvider router={...}>` (or wraps `Routes`) as its sole content.

---

### Modified Files

| File | Change |
|------|--------|
| `src/main.tsx` | Add `<BrowserRouter>` wrapping `<QueryClientProvider>`, then `<AuthProvider>` inside that |
| `src/app.tsx` | Replace analytics scaffold with `<Routes>` from `src/router.tsx`; remove `DEMO_TRADE` + `JournalPanel` |
| `src/lib/api-client.ts` | Add `window.dispatchEvent(new CustomEvent('auth:session-expired'))` before throwing on `res.status === 401` |
| `vite.config.ts` | Add `app.tsx` and `main.tsx` coverage exclusions are already present — no change needed |

---

### Tests (Arjun)

All component tests live in `src/features/auth/components/__tests__/` and `src/components/__tests__/`. Use the existing hook-mock + MSW pattern established in Steps 12–13.

**Add MSW handlers to `src/__tests__/msw/handlers.ts`:**

| Handler | Fixture |
|---------|---------|
| `POST /v1/auth/me` (GET) | `AUTH_ME_FIXTURE` (authenticated user), `AUTH_ME_401` (not authenticated) |
| `POST /v1/auth/login` | `LOGIN_SUCCESS_FIXTURE`, `LOGIN_INVALID_CREDENTIALS`, `LOGIN_ACCOUNT_LOCKED`, `LOGIN_EMAIL_NOT_VERIFIED`, `LOGIN_RATE_LIMITED` |
| `POST /v1/auth/register` | `REGISTER_SUCCESS_FIXTURE`, `REGISTER_RATE_LIMITED` |
| `POST /v1/auth/verify-email` | `VERIFY_EMAIL_SUCCESS`, `VERIFY_EMAIL_INVALID_TOKEN` |
| `POST /v1/auth/password-reset/request` | `PASSWORD_RESET_REQUEST_SUCCESS` |
| `POST /v1/auth/password-reset/confirm` | `PASSWORD_RESET_CONFIRM_SUCCESS`, `PASSWORD_RESET_INVALID_TOKEN` |
| `POST /v1/auth/logout` | `LOGOUT_SUCCESS` |

**LoginPage tests (`F-14-01` to `F-14-08`):**

| Test ID | Description |
|---------|-------------|
| F-14-01 | Renders email field, password field, and submit button |
| F-14-02 | Shows `INVALID_CREDENTIALS` error message on 401 response |
| F-14-03 | Shows `ACCOUNT_LOCKED` error message on 423 response |
| F-14-04 | Shows `EMAIL_NOT_VERIFIED` error message on 403 response |
| F-14-05 | Shows `RATE_LIMITED` error message on 429 response |
| F-14-06 | Shows "session expired" banner when `?expired=1` is in URL |
| F-14-07 | Shows "email verified" banner when `?verified=1` is in URL |
| F-14-08 | Disables submit button while request is in flight (prevents double-submit) |

**RegisterPage tests (`F-14-09` to `F-14-14`):**

| Test ID | Description |
|---------|-------------|
| F-14-09 | Renders email, password, confirm password fields |
| F-14-10 | Shows client-side error when passwords do not match (does not call API) |
| F-14-11 | Renders password strength indicator (4-segment bar present in DOM) |
| F-14-12 | Shows rate-limited error on 429 response |
| F-14-13 | Shows backend policy message verbatim on 422 response |
| F-14-14 | On success, navigates to `/register-success` |

**VerifyEmailPage tests (`F-14-15` to `F-14-18`):**

| Test ID | Description |
|---------|-------------|
| F-14-15 | Shows loading state on mount |
| F-14-16 | Shows success message and navigates to `/login?verified=1` after 2 seconds |
| F-14-17 | Shows error message on `INVALID_OR_EXPIRED_TOKEN` response |
| F-14-18 | Shows "invalid verification link" when `?token` is absent from URL |

**ForgotPasswordPage tests (`F-14-19` to `F-14-21`):**

| Test ID | Description |
|---------|-------------|
| F-14-19 | Shows "check your email" confirmation on success (regardless of whether email exists) |
| F-14-20 | Shows rate-limited error on 429 response |
| F-14-21 | Disables form after successful submission (prevent re-submit) |

**ResetPasswordPage tests (`F-14-22` to `F-14-26`):**

| Test ID | Description |
|---------|-------------|
| F-14-22 | Shows client-side error when passwords do not match |
| F-14-23 | Shows error on `INVALID_OR_EXPIRED_TOKEN` response |
| F-14-24 | Navigates to `/login?reset=1` on success |
| F-14-25 | Shows policy message verbatim on 422 response |
| F-14-26 | Shows "invalid reset link" when `?token` is absent from URL |

**RequireAuth tests (`F-14-27` to `F-14-29`):**

| Test ID | Description |
|---------|-------------|
| F-14-27 | Renders outlet content when user is authenticated |
| F-14-28 | Redirects to `/login?next=/analytics` when unauthenticated |
| F-14-29 | Renders nothing (null / loading state) while auth check is in flight |

**AppShell tests (`F-14-30` to `F-14-33`):**

| Test ID | Description |
|---------|-------------|
| F-14-30 | Renders nav landmark with all six nav links |
| F-14-31 | Analytics link is marked active when on `/analytics` |
| F-14-32 | Logout button calls `logout()` from `useAuth` |
| F-14-33 | Renders `<main>` landmark for the outlet content area |

---

## Explicitly NOT in Step 14

| Deferred to | What |
|-------------|------|
| Step 15 | User profile page, display name, timezone, base currency |
| Step 15 | Trading account management screen |
| Step 16 | Manual trade entry screen |
| Step 17 | Import trades screen |
| Step 18 | Dashboard screen (real content — not a placeholder) |
| Step 19 | Trade list and trade detail screens |
| Step 19 | JournalPanel wired to a real trade (DEMO_TRADE removed from app) |
| Phase 2 | "Resend verification email" link on EMAIL_NOT_VERIFIED login error |
| Phase 3 | OAuth / social login (Google, etc.) |
| Phase 3 | Passkeys (WebAuthn) |
| Never | Top bar as alternative to sidebar — sidebar is the nav pattern for Phase 1 |

---

## Order of Work

1. **Arjun** — install `react-router-dom@^6.26.0`; confirm TypeScript types resolve
2. **Arjun** — `api-client.ts` session-expired dispatch; update MSW handlers for all auth endpoints
3. **Arjun** — `AuthContext.tsx` + `useAuth` hook; `RequireAuth.tsx`
4. **Arjun** — move analytics content from `app.tsx` to `AnalyticsPage.tsx` (remove `JournalPanel` demo); create `PlaceholderPage`
5. **Arjun** — auth screen components (LoginPage, RegisterPage, RegisterSuccessPage, VerifyEmailPage, ForgotPasswordPage, ResetPasswordPage)
6. **Arjun** — `AppShell.tsx` with sidebar nav
7. **Arjun** — `router.tsx` + wire into `app.tsx` + update `main.tsx`
8. **Arjun** — component tests (F-14-01 through F-14-33)
9. **Sahadeva** — QA gate
10. **Nakula** — CI gate
11. **Yudhishthira** — acceptance

Steps 3 and 4 are independent and can be done in parallel. Auth screens (step 5) depend on `AuthContext` (step 3). `AppShell` (step 6) depends on `AnalyticsPage` (step 4). Router (step 7) depends on all of the above.

---

## Risk Register (Step 14)

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|-----------|
| R-14-1 | BrowserRouter in `main.tsx` conflicts with test setup — tests use `MemoryRouter` internally; double-router wrapper causes navigation failures | Medium | Medium | All component tests that need routing must render their component inside `<MemoryRouter>` explicitly. Do not wrap `App` in tests — test individual page components. Establish this pattern in the first test written. |
| R-14-2 | `auth:session-expired` event fired during test runs (MSW returns 401) → test navigates unexpectedly | Medium | Low | In test setup (`src/__tests__/setup.ts`), suppress the session-expired event listener or mock it. AuthContext tests should explicitly control the event dispatch. |
| R-14-3 | AnalyticsPage loses test coverage when content moves from `app.tsx` to `AnalyticsPage.tsx` — vite.config.ts currently excludes `app.tsx` from coverage | Low | Low | `AnalyticsPage.tsx` is NOT excluded from coverage. Verify coverage thresholds pass after the move. Existing analytics component tests still cover the cards; the page itself needs a smoke render test. |
| R-14-4 | Password strength indicator implemented as a library import rather than inline logic — adds a dep for cosmetic UX only | Low | Low | Arjun implements inline (no library). Scoring: length ≥ 8 (+1), length ≥ 12 (+1), uppercase + lowercase present (+1), digit or symbol present (+1). 4 segments, no external package. |
| R-14-5 | `?next=` redirect loop — if `/analytics` also returns 401 (e.g. during backend outage), `RequireAuth` redirects to `/login?next=/analytics`, login succeeds, navigates to `/analytics`, which 401s again | Low | Medium | The `?next=` param is consumed once on login. The session-expired event clears user state and navigates to `/login?expired=1` (no `?next=` — do not re-use next on session expiry). This breaks the loop. |

---

## Open Items Before Implementation

None. All backend endpoints are built and tested. No external sign-off is required.

---

## Gate Criteria

| Gate | Owner | Criteria |
|------|-------|---------|
| Sahadeva QA | Sahadeva | All 33 frontend component tests pass (F-14-01 through F-14-33); no regressions in existing analytics/journal test suite; auth screens manually verified for keyboard navigation (tab order, form submission on Enter) |
| Nakula CI | Nakula | `npm run coverage` passes thresholds (lines ≥ 70, functions ≥ 45, branches ≥ 79); `tsc --noEmit` clean; ESLint 0 warnings; backend CI unaffected |
| Yudhishthira accept | Yudhishthira | Register → verify email → login → analytics page flow completes end-to-end; session-expired redirect works; all six nav links present; logout clears session |

---

## Effort Estimate

| Owner | Work | Estimate |
|-------|------|----------|
| Arjun | Router install, AuthContext, RequireAuth, api-client update, AnalyticsPage move | ~0.5 session |
| Arjun | Six auth screen components + AppShell + router wiring | ~0.5 session |
| Arjun | 33 component tests + MSW fixture expansion | ~0.5 session |
| **Total** | | **~1.5 sessions** |

This matches the Phase 1 plan estimate of 1 session, with a 0.5 session buffer for the test suite which is larger than previous steps (auth flows have more error states to cover).

---

*Krishna — Senior Project Manager*  
*Source: `docs/project-status/PHASE-1-MVP-EXECUTION-PLAN.md`, `backend/src/tradeforge/api/v1/auth.py`, `frontend/src/lib/api-client.ts`, `frontend/package.json`*
