/**
 * QO-1 (Step 12.4 obligation, gate item for Step 12.5)
 *
 * Integration test: renderHook + QueryClientWrapper + MSW.
 * Verifies the full TanStack Query → fetch → Zod-parse path for
 * useFilterDimensions WITHOUT mocking the hook itself.
 * A wiring bug (wrong queryFn import, wrong URL, wrong query key)
 * that component-level tests would not catch IS caught here.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import {
  FILTER_ACCOUNTS_FIXTURE,
  FILTER_BROKERS_FIXTURE,
  FILTER_SETUPS_FIXTURE,
} from '@/__tests__/msw/handlers'
import { useFilterDimensions } from '../useFilterDimensions'

// MSW server is started/reset/stopped globally via src/__tests__/setup.ts.
// Default handlers include the 3 filter-dimension endpoints.

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}

describe('useFilterDimensions — renderHook + MSW (QO-1)', () => {
  it('resolves accounts from the /filters/accounts endpoint', async () => {
    const { result } = renderHook(() => useFilterDimensions(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.accountsError).toBe(false)
    expect(result.current.accounts).toEqual(FILTER_ACCOUNTS_FIXTURE)
  })

  it('resolves setups from the /filters/setups endpoint', async () => {
    const { result } = renderHook(() => useFilterDimensions(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.setupsError).toBe(false)
    expect(result.current.setups).toEqual(FILTER_SETUPS_FIXTURE)
  })

  it('resolves brokers from the /filters/brokers endpoint', async () => {
    const { result } = renderHook(() => useFilterDimensions(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.brokersError).toBe(false)
    expect(result.current.brokers).toEqual(FILTER_BROKERS_FIXTURE)
  })

  it('reports isLoading=true before all three queries resolve', () => {
    const { result } = renderHook(() => useFilterDimensions(), {
      wrapper: createWrapper(),
    })

    // Immediately after mount, at least one query should be loading.
    expect(result.current.isLoading).toBe(true)
  })

  it('defaults to empty arrays when data is not yet fetched', () => {
    const { result } = renderHook(() => useFilterDimensions(), {
      wrapper: createWrapper(),
    })

    // Before any query resolves, the hook returns [] defaults — not undefined.
    expect(result.current.accounts).toEqual([])
    expect(result.current.setups).toEqual([])
    expect(result.current.brokers).toEqual([])
  })
})
