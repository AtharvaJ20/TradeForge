import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { KellyCard } from '../KellyCard'
import { KELLY_FIXTURE, KELLY_INSUFFICIENT_FIXTURE } from '@/__tests__/msw/handlers'
import type { useKelly } from '../../hooks/useKelly'

vi.mock('../../hooks/useKelly', () => ({
  useKelly: vi.fn(),
}))

import { useKelly as _useKelly } from '../../hooks/useKelly'

const mockUseKelly = vi.mocked(_useKelly)

function withData(data: typeof KELLY_FIXTURE | typeof KELLY_INSUFFICIENT_FIXTURE) {
  mockUseKelly.mockReturnValue({
    data,
    isLoading: false,
    isError: false,
  } as ReturnType<typeof useKelly>)
}

// ---------------------------------------------------------------------------
// F-N4-01: happy path renders Full Kelly % and Half-Kelly %
// ---------------------------------------------------------------------------

describe('KellyCard — happy path', () => {
  it('renders section landmark with heading', () => {
    withData(KELLY_FIXTURE)
    render(<KellyCard />)
    expect(screen.getByRole('region', { name: /kelly fraction/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /kelly fraction/i })).toBeInTheDocument()
  })

  it('renders Full Kelly and Half-Kelly percentage values', () => {
    withData(KELLY_FIXTURE)
    render(<KellyCard />)
    // 0.3142 * 100 = 31.4%
    expect(screen.getByText('31.4%')).toBeInTheDocument()
    // 0.1571 * 100 = 15.7%
    expect(screen.getByText('15.7%')).toBeInTheDocument()
  })

  it('renders contextual guidance text', () => {
    withData(KELLY_FIXTURE)
    render(<KellyCard />)
    expect(screen.getByText(/half-kelly is the recommended starting point/i)).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-N4-02: insufficient-sample state renders guidance, no numeric values
// ---------------------------------------------------------------------------

describe('KellyCard — insufficient sample', () => {
  it('renders guidance note when insufficient_sample is true', () => {
    withData(KELLY_INSUFFICIENT_FIXTURE)
    render(<KellyCard />)
    expect(screen.getByRole('note')).toHaveTextContent(/needs 30\+ trades with a planned stop/i)
  })

  it('does not render percentage values when insufficient', () => {
    withData(KELLY_INSUFFICIENT_FIXTURE)
    render(<KellyCard />)
    expect(screen.queryByText('31.4%')).not.toBeInTheDocument()
    expect(screen.queryByText('15.7%')).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Null kelly_pct guard: renders "—" rather than 0 or NaN
// ---------------------------------------------------------------------------

describe('KellyCard — null kelly_pct guard', () => {
  it('renders "—" for null kelly_pct when insufficient_sample is false', () => {
    mockUseKelly.mockReturnValue({
      data: {
        kelly_pct: null,
        half_kelly_pct: null,
        trades_with_r: 35,
        insufficient_sample: false,
        min_n: 30,
      },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useKelly>)
    render(<KellyCard />)
    // Both stat cells should show "—"
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBeGreaterThanOrEqual(2)
  })
})

// ---------------------------------------------------------------------------
// Loading and error states
// ---------------------------------------------------------------------------

describe('KellyCard — loading / error', () => {
  it('shows loading skeleton while data is loading', () => {
    mockUseKelly.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as ReturnType<typeof useKelly>)
    render(<KellyCard />)
    expect(
      screen.getByRole('status', { name: /loading kelly fraction/i }),
    ).toBeInTheDocument()
  })

  it('shows error message on fetch failure', () => {
    mockUseKelly.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as ReturnType<typeof useKelly>)
    render(<KellyCard />)
    expect(screen.getByText(/failed to load kelly fraction/i)).toBeInTheDocument()
  })
})
