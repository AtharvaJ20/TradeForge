import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { TimeOfDayCard } from '../TimeOfDayCard'
import { TIME_OF_DAY_FIXTURE } from '@/__tests__/msw/handlers'
import type { useTimeOfDay } from '../../hooks/useTimeOfDay'

vi.mock('../../hooks/useTimeOfDay', () => ({
  useTimeOfDay: vi.fn(),
}))

import { useTimeOfDay as _useTimeOfDay } from '../../hooks/useTimeOfDay'

const mockUseTimeOfDay = vi.mocked(_useTimeOfDay)

function withData(data: typeof TIME_OF_DAY_FIXTURE) {
  mockUseTimeOfDay.mockReturnValue({
    data,
    isLoading: false,
    isError: false,
  } as ReturnType<typeof useTimeOfDay>)
}

// ---------------------------------------------------------------------------
// F-N2-01: all 6 buckets render in session-time order
// ---------------------------------------------------------------------------

describe('TimeOfDayCard — all 6 buckets render', () => {
  it('renders section landmark with heading', () => {
    withData(TIME_OF_DAY_FIXTURE)
    render(<TimeOfDayCard />)
    expect(
      screen.getByRole('region', { name: /time-of-day performance/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: /time-of-day performance/i }),
    ).toBeInTheDocument()
  })

  it('renders all 6 session band labels', () => {
    withData(TIME_OF_DAY_FIXTURE)
    render(<TimeOfDayCard />)

    const labels = ['Pre-Open', 'Open Volatility', 'Mid-Morning', 'Lunch', 'Afternoon', 'Close']
    for (const label of labels) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
  })

  it('renders buckets in session-time order (Pre-Open first, Close last)', () => {
    withData(TIME_OF_DAY_FIXTURE)
    render(<TimeOfDayCard />)

    const rows = screen.getAllByRole('row')
    // rows[0] = header, rows[1..6] = data rows
    const rowTexts = rows.slice(1).map(r => r.textContent ?? '')
    expect(rowTexts[0]).toMatch(/Pre-Open/)
    expect(rowTexts[5]).toMatch(/Close/)
  })
})

// ---------------------------------------------------------------------------
// F-N2-02: zero-count bucket renders "—" for win rate and expectancy, not "0%"
// ---------------------------------------------------------------------------

describe('TimeOfDayCard — zero-count bucket', () => {
  it('renders "—" for win rate and expectancy in zero-count row, not 0%', () => {
    withData(TIME_OF_DAY_FIXTURE)
    render(<TimeOfDayCard />)

    // Mid-Morning has trade_count=0
    const rows = screen.getAllByRole('row')
    const midMorningRow = rows.find(r => r.textContent?.includes('Mid-Morning'))!
    expect(midMorningRow).toBeDefined()

    const cells = within(midMorningRow).getAllByRole('cell')
    // cells: [Session, Trades, Win Rate, Exp(₹), Total P&L]
    expect(cells[2].textContent).toBe('—') // win rate
    expect(cells[3].textContent).toBe('—') // expectancy
  })

  it('does not render "0%" in zero-count row', () => {
    withData(TIME_OF_DAY_FIXTURE)
    render(<TimeOfDayCard />)

    const rows = screen.getAllByRole('row')
    const midMorningRow = rows.find(r => r.textContent?.includes('Mid-Morning'))!
    expect(midMorningRow.textContent).not.toContain('0%')
  })
})

// ---------------------------------------------------------------------------
// Best-performing bucket is visually distinguished
// ---------------------------------------------------------------------------

describe('TimeOfDayCard — best-performing bucket highlight', () => {
  it('marks best total-net-pnl bucket with aria-label', () => {
    withData(TIME_OF_DAY_FIXTURE)
    render(<TimeOfDayCard />)
    // Open Volatility has highest total_net_pnl: 5400
    const rows = screen.getAllByRole('row')
    const bestRow = rows.find(r => r.getAttribute('aria-label')?.includes('best session'))
    expect(bestRow).toBeDefined()
    expect(bestRow!.textContent).toContain('Open Volatility')
  })
})

// ---------------------------------------------------------------------------
// Loading and error states
// ---------------------------------------------------------------------------

describe('TimeOfDayCard — loading / error', () => {
  it('shows loading skeleton while data is loading', () => {
    mockUseTimeOfDay.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as ReturnType<typeof useTimeOfDay>)
    render(<TimeOfDayCard />)
    expect(
      screen.getByRole('status', { name: /loading time-of-day performance/i }),
    ).toBeInTheDocument()
  })

  it('shows error message on fetch failure', () => {
    mockUseTimeOfDay.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as ReturnType<typeof useTimeOfDay>)
    render(<TimeOfDayCard />)
    expect(screen.getByText(/failed to load time-of-day performance/i)).toBeInTheDocument()
  })
})
