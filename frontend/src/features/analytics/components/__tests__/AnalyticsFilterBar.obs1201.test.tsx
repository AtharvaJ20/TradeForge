/**
 * OBS-12.3-01 — FilterBar renders Instrument and Segment chips
 *
 * This file uses a real QueryClient + MSW (no vi.mock on useFilterDimensions)
 * so the full TanStack Query → fetch → Zod-parse path is exercised for the
 * dynamic dimension groups (accounts, setups, brokers), while the static
 * Instrument and Segment fieldsets are asserted alongside them.
 *
 * MSW server is started/reset/stopped globally via src/__tests__/setup.ts.
 * Default handlers include the 3 filter-dimension endpoints.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { AnalyticsFilterBar } from '../AnalyticsFilterBar'

function createWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}

describe('AnalyticsFilterBar — OBS-12.3-01: Instrument and Segment chips (MSW integration)', () => {
  it('renders the Instrument fieldset with all static instrument type chips', () => {
    render(<AnalyticsFilterBar value={{}} onChange={vi.fn()} />, {
      wrapper: createWrapper(),
    })

    // Instrument is a static fieldset — always present, no async needed
    expect(screen.getByRole('group', { name: /instrument/i })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'FUT' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'OPT' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'EQ' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'CFD' })).toBeInTheDocument()
  })

  it('renders the Segment fieldset with all static exchange segment chips', () => {
    render(<AnalyticsFilterBar value={{}} onChange={vi.fn()} />, {
      wrapper: createWrapper(),
    })

    expect(screen.getByRole('group', { name: /segment/i })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'NSE' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'BSE' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'NFO' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'BFO' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'MCX' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'CDS' })).toBeInTheDocument()
  })

  it('resolves dynamic Account dimension from MSW and renders Account fieldset', async () => {
    render(<AnalyticsFilterBar value={{}} onChange={vi.fn()} />, {
      wrapper: createWrapper(),
    })

    // Account group appears after the real TanStack Query → MSW fetch resolves
    await waitFor(() => {
      expect(screen.getByRole('group', { name: /account/i })).toBeInTheDocument()
    })

    expect(screen.getByRole('checkbox', { name: 'Zerodha Main' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Upstox Secondary' })).toBeInTheDocument()
  })

  it('resolves dynamic Setup dimension from MSW and renders Setup fieldset', async () => {
    render(<AnalyticsFilterBar value={{}} onChange={vi.fn()} />, {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(screen.getByRole('group', { name: /setup/i })).toBeInTheDocument()
    })

    expect(screen.getByRole('checkbox', { name: 'Breakout' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'VWAP Reversion' })).toBeInTheDocument()
  })
})
