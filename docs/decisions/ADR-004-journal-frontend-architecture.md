# ADR-004 — Journal Frontend Architecture

**Status:** Accepted  
**Date:** 2026-08-23  
**Author:** Arjun (Frontend)  
**Scope:** `frontend/` directory — Step 9 Journal annotation layer

---

## Context

TradeForge had no frontend. Step 9 added a complete backend journal API (see ADR-003). This ADR records the key structural decisions made when bootstrapping the frontend and implementing the Journal feature.

---

## Decisions

### 1. Toolchain: Vite 5 + React 18 + TypeScript strict

- `strict: true`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`
- Vite over Next.js: the app is a fully authenticated SPA — no public pages, no SEO requirement, no need for SSR/SSG overhead at this stage
- `defineConfig` must be imported from `vitest/config` (not `vite`) when a `test` block is present

### 2. Feature-first directory structure

```
src/
  features/
    journal/
      components/     ← all 10+ journal components
      components/__tests__/
      hooks/          ← TanStack Query wrappers
      schemas.ts      ← Zod validation at the API boundary
      types.ts        ← TypeScript types inferred from schemas
      api.ts          ← typed fetch functions
      index.ts        ← public barrel (JournalPanel only)
  shared/
    tokens.css        ← CSS custom properties (design tokens)
  lib/
    api-client.ts     ← base fetch wrapper with credentials: 'include'
    utils.ts          ← formatInr, formatRMultiple, formatBytes, etc.
  __tests__/
    setup.ts          ← Vitest global setup (MSW server lifecycle)
    msw/
      handlers.ts     ← per-endpoint MSW request handlers + fixtures
      server.ts       ← msw/node server instance
```

### 3. API client: credentials: 'include' on every request

All requests include `credentials: 'include'`. `user_id` is **never** sent in any request body or URL — the backend derives it from the session cookie (constraint from ADR-003 and UX spec §13).

### 4. Server state: TanStack Query v5 only

Never copy server state into a global store or `useState`. All API data lives in TanStack Query cache. Key factory pattern:

```ts
export const journalKeys = {
  entry: (tradeId: string) => ['journal', 'entry', tradeId] as const,
  audit: (tradeId: string) => ['journal', 'audit', tradeId] as const,
}
```

### 5. 404 on journal GET = empty state, not an error

The `useJournalEntry` hook catches 404 and returns `null` instead of throwing. This keeps `isError: false` when no journal entry exists yet, and lets `JournalPanel` distinguish "no entry" from "API failure" without the calller checking error types.

### 6. Decimal values from backend are strings

Pydantic v2 serializes `Decimal` fields as JSON strings (e.g. `"500.00"`). All `planned_entry`, `net_pnl`, `r_multiple`, etc. are typed as `z.string().nullable()` in Zod schemas. The utility functions `formatInr` and `formatRMultiple` handle both `string | number | null | undefined`.

### 7. Form stack: React Hook Form + Zod + @hookform/resolvers

`JournalQuickCapture` and `JournalFullForm` use RHF with `zodResolver` for validation. Risk fields (`planned_entry`, `planned_stop`, `planned_target`) are HTML `number` inputs bound as strings; `calcPlannedRisk` and `calcRR` in `lib/utils.ts` derive the computed display values without storing them in form state.

### 8. Optimistic updates

- Attachment delete: `useDeleteAttachment` removes the attachment from the TQ cache immediately and rolls back on non-404 errors (404 = already deleted, no rollback)
- Upsert: updates cache via `setQueryData` in `useUpsertJournalEntry` on success

### 9. XHR for S3 upload progress

`s3Upload` in `api.ts` uses `XMLHttpRequest` rather than `fetch` so `xhr.upload.onprogress` can track bytes sent. The function accepts an injectable `uploadFn` parameter (default `s3Upload`) to allow synchronous test mocking without real XHR.

### 10. Styling: Tailwind v3 with CSS custom properties

All colours are CSS custom property tokens defined in `src/shared/tokens.css`. Tailwind maps token names to `var(--color-*)` in `tailwind.config.ts`. This means dark mode is a single CSS swap with no class-level duplication in component markup. Animations (`shimmer`, `spin-slow`) are defined in Tailwind config keyframes and respect `prefers-reduced-motion`.

### 11. Testing: Vitest + RTL + MSW v2

- Unit tests: `DisciplineScoreInput`, `MistakesCheckboxGroup`, `PnlStatusBlock`, `AuditPromptInline`
- Integration tests: `JournalPanel` with MSW intercepting all 7 API endpoints
- MSW handlers live in `src/__tests__/msw/` and are registered globally in `setup.ts`
- `server.use(overrideHandler)` pattern for per-test handler variations (e.g. 404, 500)

---

## Rejected Alternatives

| Alternative | Reason rejected |
|---|---|
| Next.js App Router | No SSR/SEO requirement; adds significant complexity for a fully-auth'd SPA |
| Zustand for server state | Server state belongs in TanStack Query; Zustand adds a second source of truth |
| SWR instead of TanStack Query | TQ v5 is already established in the project; SWR offers no advantage here |
| inline fetch in components | Breaks the API client layer; leaks credentials config across the codebase |
| CSS Modules instead of Tailwind | Tailwind is already the design system; CSS Modules would create a parallel system |

---

## Consequences

- All journal state flows through TanStack Query — no local state cache to keep in sync
- New API endpoints should follow the key factory pattern in `hooks/useJournalEntry.ts`
- The `JournalPanel` is the single integration root; consumers import only from `features/journal/index.ts`
- Tests are co-located in `components/__tests__/` and rely on the shared MSW server in `src/__tests__/`
