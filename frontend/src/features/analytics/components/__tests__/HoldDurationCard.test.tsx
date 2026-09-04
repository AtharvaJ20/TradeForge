import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { HoldDurationCard } from '../HoldDurationCard'
import {
  HOLD_DURATION_FIXTURE,
  HOLD_DURATION_EMPTY_FIXTURE,
} from '@/__tests__/msw/handlers'
import type { useHoldDuration } from '../../hooks/useHoldDuration'

vi.mock('../../hooks/useHoldDuration', () => ({
  useHoldDuration: vi.fn(),
}))

import { useHoldDuration as _useHoldDuration } from '../../hooks/useHoldDuration'

const mockUseHoldDuration = vi.mocked(_useHoldDuration)

function withData(data: typeof HOLD_DURATION_FIXTURE | typeof HOLD_DURATION_EMPTY_FIXTURE) {
  mockUseHoldDuration.mockReturnValue({
    data,
    isLoading: false,
    isError: false,
  } as ReturnType<typeof useHoldDuration>)
}

describe('HoldDurationCard', () => {
  it('renders section landmark and heading', () => {
    withData(HOLD_DURATION_FIXTURE)
    render(<HoldDurationCard />)
    expect(screen.getByRole('region', { name: /hold duration distribution/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /hold duration/i })).toBeInTheDocument()
  })

  it('renders a table with all 5 bucket rows from fixture', () => {
    withData(HOLD_DURATION_FIXTURE)
    render(<HoldDurationCard />)
    const table = screen.getByRole('table')
    const rows = within(table).getAllByRole('row')
    // 1 header row + 5 data rows
    expect(rows.length).toBe(6)
    expect(screen.getByText('< 15 min')).toBeInTheDocument()
    expect(screen.getByText('15 min – 1 hr')).toBeInTheDocument()
    expect(screen.getByText('1 – 4 hr')).toBeInTheDocument()
  })

  it('renders buckets in ascending bucket_order', () => {
    withData(HOLD_DURATION_FIXTURE)
    render(<HoldDurationCard />)
    const cells = screen.getAllByRole('cell')
    const bucketLabelCells = cells.filter(c =>
      ['< 15 min', '15 min – 1 hr', '1 – 4 hr', '4 – 24 hr', '> 7 days'].includes(
        c.textContent ?? '',
      ),
    )
    const labels = bucketLabelCells.map(c => c.textContent ?? '')
    expect(labels[0]).toBe('< 15 min')
    expect(labels[1]).toBe('15 min – 1 hr')
    expect(labels[2]).toBe('1 – 4 hr')
  })

  it('shows "No closed trades yet" for empty state', () => {
    withData(HOLD_DURATION_EMPTY_FIXTURE)
    render(<HoldDurationCard />)
    expect(screen.getByText(/no closed trades yet/i)).toBeInTheDocument()
  })

  it('shows avg/median duration summary when data is present', () => {
    withData(HOLD_DURATION_FIXTURE)
    render(<HoldDurationCard />)
    expect(screen.getByText(/avg hold/i)).toBeInTheDocument()
    expect(screen.getByText(/median/i)).toBeInTheDocument()
  })

  it('shows loading skeleton while data is loading', () => {
    mockUseHoldDuration.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as ReturnType<typeof useHoldDuration>)
    render(<HoldDurationCard />)
    expect(screen.getByRole('status', { name: /loading hold duration/i })).toBeInTheDocument()
  })

  it('shows error message on fetch failure', () => {
    mockUseHoldDuration.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as ReturnType<typeof useHoldDuration>)
    render(<HoldDurationCard />)
    expect(screen.getByText(/failed to load hold duration/i)).toBeInTheDocument()
  })
})
