import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DimensionBreakdownCard } from '../DimensionBreakdownCard'
import {
  DIMENSION_BREAKDOWN_DIRECTION_FIXTURE,
  DIMENSION_BREAKDOWN_SETUP_FIXTURE,
  DIMENSION_BREAKDOWN_EMPTY_FIXTURE,
} from '@/__tests__/msw/handlers'
import type { useDimensionBreakdown } from '../../hooks/useDimensionBreakdown'

vi.mock('../../hooks/useDimensionBreakdown', () => ({
  useDimensionBreakdown: vi.fn(),
}))

import { useDimensionBreakdown as _useDimensionBreakdown } from '../../hooks/useDimensionBreakdown'

const mockUseDimensionBreakdown = vi.mocked(_useDimensionBreakdown)

function withData(data: typeof DIMENSION_BREAKDOWN_DIRECTION_FIXTURE) {
  mockUseDimensionBreakdown.mockReturnValue({
    data,
    isLoading: false,
    isError: false,
  } as ReturnType<typeof useDimensionBreakdown>)
}

// ---------------------------------------------------------------------------
// TC-BREAK-FE-001: structure
// ---------------------------------------------------------------------------

describe('DimensionBreakdownCard — structure', () => {
  it('renders section landmark and heading', () => {
    withData(DIMENSION_BREAKDOWN_DIRECTION_FIXTURE)
    render(<DimensionBreakdownCard />)

    expect(screen.getByRole('region', { name: /dimension breakdown/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /dimension breakdown/i })).toBeInTheDocument()
  })

  it('renders all 5 dimension tabs', () => {
    withData(DIMENSION_BREAKDOWN_DIRECTION_FIXTURE)
    render(<DimensionBreakdownCard />)

    expect(screen.getByRole('tab', { name: /direction/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /setup/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /instrument/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /trade type/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /segment/i })).toBeInTheDocument()
  })

  it('Direction tab is selected by default', () => {
    withData(DIMENSION_BREAKDOWN_DIRECTION_FIXTURE)
    render(<DimensionBreakdownCard />)

    expect(screen.getByRole('tab', { name: /direction/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
  })
})

// ---------------------------------------------------------------------------
// TC-BREAK-FE-002: renders group rows from fixture
// ---------------------------------------------------------------------------

describe('DimensionBreakdownCard — data rows', () => {
  it('renders group labels from direction fixture (LONG, SHORT)', () => {
    withData(DIMENSION_BREAKDOWN_DIRECTION_FIXTURE)
    render(<DimensionBreakdownCard />)

    expect(screen.getByText('LONG')).toBeInTheDocument()
    expect(screen.getByText('SHORT')).toBeInTheDocument()
  })

  it('renders — for null avg_r_multiple (SHORT row)', () => {
    withData(DIMENSION_BREAKDOWN_DIRECTION_FIXTURE)
    render(<DimensionBreakdownCard />)

    // SHORT row has avg_r_multiple: null → renders '—'
    // There is only one '—' in the avg R column (LONG has +0.85)
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBeGreaterThanOrEqual(1)
  })

  it('renders "(no setup)" label for null-setup group', () => {
    withData(DIMENSION_BREAKDOWN_SETUP_FIXTURE)
    render(<DimensionBreakdownCard />)

    expect(screen.getByText('(no setup)')).toBeInTheDocument()
  })

  it('renders all 8 table column headers', () => {
    withData(DIMENSION_BREAKDOWN_DIRECTION_FIXTURE)
    render(<DimensionBreakdownCard />)

    expect(screen.getByText(/trades/i)).toBeInTheDocument()
    expect(screen.getByText(/wins/i)).toBeInTheDocument()
    expect(screen.getByText(/win rate/i)).toBeInTheDocument()
    expect(screen.getByText(/total p&l/i)).toBeInTheDocument()
    expect(screen.getByText(/avg p&l/i)).toBeInTheDocument()
    expect(screen.getByText(/avg r/i)).toBeInTheDocument()
    expect(screen.getByText(/avg hold/i)).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// TC-BREAK-FE-003: dimension selector triggers re-fetch
// ---------------------------------------------------------------------------

describe('DimensionBreakdownCard — dimension switching', () => {
  it('calls useDimensionBreakdown with the new dimension after clicking a tab', async () => {
    withData(DIMENSION_BREAKDOWN_DIRECTION_FIXTURE)
    const user = userEvent.setup()
    render(<DimensionBreakdownCard />)

    // Setup tab — mock returns setup fixture on next call
    mockUseDimensionBreakdown.mockReturnValue({
      data: DIMENSION_BREAKDOWN_SETUP_FIXTURE,
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useDimensionBreakdown>)

    await user.click(screen.getByRole('tab', { name: /setup/i }))

    // After clicking Setup, the hook should have been called with dimension='setup'
    const calls = mockUseDimensionBreakdown.mock.calls
    const lastCall = calls[calls.length - 1]
    expect(lastCall[1]).toBe('setup')
  })

  it('marks the clicked tab as selected', async () => {
    withData(DIMENSION_BREAKDOWN_DIRECTION_FIXTURE)
    const user = userEvent.setup()
    render(<DimensionBreakdownCard />)

    await user.click(screen.getByRole('tab', { name: /instrument/i }))

    expect(screen.getByRole('tab', { name: /instrument/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByRole('tab', { name: /direction/i })).toHaveAttribute(
      'aria-selected',
      'false',
    )
  })
})

// ---------------------------------------------------------------------------
// TC-BREAK-FE-004: empty state
// ---------------------------------------------------------------------------

describe('DimensionBreakdownCard — empty state', () => {
  it('shows empty state note when groups is empty', () => {
    withData(DIMENSION_BREAKDOWN_EMPTY_FIXTURE)
    render(<DimensionBreakdownCard />)

    expect(screen.getByRole('note')).toHaveTextContent(/no trades match the current filter/i)
  })

  it('does not render a table when groups is empty', () => {
    withData(DIMENSION_BREAKDOWN_EMPTY_FIXTURE)
    render(<DimensionBreakdownCard />)

    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// TC-BREAK-FE-005: loading and error states
// ---------------------------------------------------------------------------

describe('DimensionBreakdownCard — loading / error', () => {
  it('shows loading skeleton while data is loading', () => {
    mockUseDimensionBreakdown.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as ReturnType<typeof useDimensionBreakdown>)
    render(<DimensionBreakdownCard />)

    expect(
      screen.getByRole('status', { name: /loading dimension breakdown/i }),
    ).toBeInTheDocument()
  })

  it('shows error message on fetch failure', () => {
    mockUseDimensionBreakdown.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as ReturnType<typeof useDimensionBreakdown>)
    render(<DimensionBreakdownCard />)

    expect(screen.getByText(/failed to load dimension breakdown/i)).toBeInTheDocument()
  })
})
