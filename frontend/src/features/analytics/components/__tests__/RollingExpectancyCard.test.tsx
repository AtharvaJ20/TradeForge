import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { RollingExpectancyCard } from '../RollingExpectancyCard'
import {
  ROLLING_EXPECTANCY_FIXTURE,
  ROLLING_EXPECTANCY_INSUFFICIENT_FIXTURE,
} from '@/__tests__/msw/handlers'
import type { useRollingExpectancy } from '../../hooks/useRollingExpectancy'

vi.mock('../../hooks/useRollingExpectancy', () => ({
  useRollingExpectancy: vi.fn(),
}))

import { useRollingExpectancy as _useRollingExpectancy } from '../../hooks/useRollingExpectancy'

const mockUseRollingExpectancy = vi.mocked(_useRollingExpectancy)

function withData(
  data: typeof ROLLING_EXPECTANCY_FIXTURE | typeof ROLLING_EXPECTANCY_INSUFFICIENT_FIXTURE,
) {
  mockUseRollingExpectancy.mockReturnValue({
    data,
    isLoading: false,
    isError: false,
  } as ReturnType<typeof useRollingExpectancy>)
}

// ---------------------------------------------------------------------------
// F-N1-01: renders last 20 rows; sign-and-colour applied to rolling_exp_r
// ---------------------------------------------------------------------------

describe('RollingExpectancyCard — happy path', () => {
  it('renders section landmark with heading', () => {
    withData(ROLLING_EXPECTANCY_FIXTURE)
    render(<RollingExpectancyCard />)
    expect(
      screen.getByRole('region', { name: /rolling expectancy/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: /rolling expectancy/i }),
    ).toBeInTheDocument()
  })

  it('renders exactly the last 20 data rows when fixture has 22 points', () => {
    withData(ROLLING_EXPECTANCY_FIXTURE)
    render(<RollingExpectancyCard />)
    const rows = screen.getAllByRole('row')
    // 1 header + 20 data rows = 21 total
    expect(rows).toHaveLength(21)
  })

  it('renders positive rolling_exp_r with + prefix', () => {
    withData(ROLLING_EXPECTANCY_FIXTURE)
    render(<RollingExpectancyCard />)
    // Fixture: index 2 (i=2, even, not divisible by 3) → rolling_exp_r='0.42' → '+0.42R'
    const positiveValues = screen.getAllByText('+0.42R')
    expect(positiveValues.length).toBeGreaterThan(0)
  })

  it('renders negative rolling_exp_r with − prefix', () => {
    withData(ROLLING_EXPECTANCY_FIXTURE)
    render(<RollingExpectancyCard />)
    // Fixture: odd index → rolling_exp_r='-0.18' → '-0.18R'
    const negativeValues = screen.getAllByText('-0.18R')
    expect(negativeValues.length).toBeGreaterThan(0)
  })
})

// ---------------------------------------------------------------------------
// F-N1-02: insufficient-sample state renders guidance message
// ---------------------------------------------------------------------------

describe('RollingExpectancyCard — insufficient sample', () => {
  it('renders guidance note when insufficient_sample is true', () => {
    withData(ROLLING_EXPECTANCY_INSUFFICIENT_FIXTURE)
    render(<RollingExpectancyCard />)
    expect(screen.getByRole('note')).toHaveTextContent(
      /needs 20\+ closed trades to compute rolling expectancy/i,
    )
  })

  it('does not render a table when insufficient', () => {
    withData(ROLLING_EXPECTANCY_INSUFFICIENT_FIXTURE)
    render(<RollingExpectancyCard />)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-N1-03: null rolling_exp_r renders "—" without crashing
// ---------------------------------------------------------------------------

describe('RollingExpectancyCard — null rolling_exp_r', () => {
  it('renders "—" for null rolling_exp_r without throwing', () => {
    withData(ROLLING_EXPECTANCY_FIXTURE)
    render(<RollingExpectancyCard />)
    // Fixture: trade_index divisible by 3 (i % 3 === 0) → null rolling_exp_r
    // At least one "—" should appear in the last 20 rows
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBeGreaterThan(0)
  })
})

// ---------------------------------------------------------------------------
// Loading and error states
// ---------------------------------------------------------------------------

describe('RollingExpectancyCard — loading / error', () => {
  it('shows loading skeleton while data is loading', () => {
    mockUseRollingExpectancy.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as ReturnType<typeof useRollingExpectancy>)
    render(<RollingExpectancyCard />)
    expect(
      screen.getByRole('status', { name: /loading rolling expectancy/i }),
    ).toBeInTheDocument()
  })

  it('shows error message on fetch failure', () => {
    mockUseRollingExpectancy.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as ReturnType<typeof useRollingExpectancy>)
    render(<RollingExpectancyCard />)
    expect(screen.getByText(/failed to load rolling expectancy/i)).toBeInTheDocument()
  })
})
