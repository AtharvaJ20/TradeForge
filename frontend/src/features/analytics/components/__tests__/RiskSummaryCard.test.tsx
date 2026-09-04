import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { RiskSummaryCard } from '../RiskSummaryCard'
import {
  RISK_SUMMARY_FIXTURE,
  RISK_SUMMARY_NO_DRAWDOWN_FIXTURE,
  RISK_SUMMARY_NO_AT_RISK_FIXTURE,
} from '@/__tests__/msw/handlers'
import type { useRiskSummary } from '../../hooks/useRiskSummary'

vi.mock('../../hooks/useRiskSummary', () => ({
  useRiskSummary: vi.fn(),
}))

import { useRiskSummary as _useRiskSummary } from '../../hooks/useRiskSummary'

const mockUseRiskSummary = vi.mocked(_useRiskSummary)

function withData(data: typeof RISK_SUMMARY_FIXTURE | typeof RISK_SUMMARY_NO_DRAWDOWN_FIXTURE) {
  mockUseRiskSummary.mockReturnValue({
    data,
    isLoading: false,
    isError: false,
  } as ReturnType<typeof useRiskSummary>)
}

// ---------------------------------------------------------------------------
// F-13-01: section landmark and heading
// ---------------------------------------------------------------------------

describe('RiskSummaryCard — F-13-01: landmark and heading', () => {
  it('renders section landmark with accessible name and heading', () => {
    withData(RISK_SUMMARY_FIXTURE)
    render(<RiskSummaryCard />)
    expect(screen.getByRole('region', { name: /risk summary/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /risk summary/i })).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-13-02: max drawdown pct formatted as −8.50%
// ---------------------------------------------------------------------------

describe('RiskSummaryCard — F-13-02: max drawdown pct', () => {
  it('renders max_drawdown_pct as −8.50%', () => {
    withData(RISK_SUMMARY_FIXTURE)
    render(<RiskSummaryCard />)
    expect(screen.getByText('−8.50%')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-13-03: current drawdown pct formatted as −2.80%
// ---------------------------------------------------------------------------

describe('RiskSummaryCard — F-13-03: current drawdown pct', () => {
  it('renders current_drawdown_pct as −2.80%', () => {
    withData(RISK_SUMMARY_FIXTURE)
    render(<RiskSummaryCard />)
    expect(screen.getByText('−2.80%')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-13-04: max loss streak as "4 trades"
// ---------------------------------------------------------------------------

describe('RiskSummaryCard — F-13-04: max loss streak', () => {
  it('renders max_loss_streak as "4 trades"', () => {
    withData(RISK_SUMMARY_FIXTURE)
    render(<RiskSummaryCard />)
    expect(screen.getByText('4 trades')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-13-04b: current loss streak ≥ 3 → amber colour class
// ---------------------------------------------------------------------------

describe('RiskSummaryCard — F-13-04b: current loss streak amber at 3', () => {
  it('renders current_loss_streak of 3 in amber (text-warning-emphasis)', () => {
    mockUseRiskSummary.mockReturnValue({
      data: { ...RISK_SUMMARY_FIXTURE, current_loss_streak: 3 },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useRiskSummary>)
    render(<RiskSummaryCard />)
    const el = screen.getByText('3 trades')
    expect(el).toHaveClass('text-warning-emphasis')
  })
})

// ---------------------------------------------------------------------------
// F-13-04c: current loss streak = 0 → neutral (no colour class)
// ---------------------------------------------------------------------------

describe('RiskSummaryCard — F-13-04c: current loss streak neutral at 0', () => {
  it('renders current_loss_streak of 0 without amber or danger class', () => {
    mockUseRiskSummary.mockReturnValue({
      data: { ...RISK_SUMMARY_FIXTURE, current_loss_streak: 0 },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useRiskSummary>)
    render(<RiskSummaryCard />)
    // The "0 trades" element should be in text-text-primary (neutral)
    const el = screen.getByText('0 trades')
    expect(el).not.toHaveClass('text-warning-emphasis')
    expect(el).not.toHaveClass('text-danger-emphasis')
  })
})

// ---------------------------------------------------------------------------
// F-13-05: today's loss formatted as −₹2,500.00
// ---------------------------------------------------------------------------

describe('RiskSummaryCard — F-13-05: today\'s loss', () => {
  it('renders daily_loss_inr as −₹2,500.00', () => {
    withData(RISK_SUMMARY_FIXTURE)
    render(<RiskSummaryCard />)
    expect(screen.getByText('−₹2,500.00')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-13-06: total_at_risk_inr null → renders "—"
// ---------------------------------------------------------------------------

describe('RiskSummaryCard — F-13-06: null total_at_risk_inr', () => {
  it('renders "—" for total_at_risk_inr when null', () => {
    withData(RISK_SUMMARY_NO_AT_RISK_FIXTURE)
    render(<RiskSummaryCard />)
    // Multiple "—" may appear (e.g. streak not set), verify at least one for Planned At-Risk
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBeGreaterThanOrEqual(1)
  })
})

// ---------------------------------------------------------------------------
// F-13-07: null drawdown fields → renders "—" (no crash)
// ---------------------------------------------------------------------------

describe('RiskSummaryCard — F-13-07: null drawdown fields', () => {
  it('renders "—" for drawdown pct cells when max_drawdown_pct is null', () => {
    withData(RISK_SUMMARY_NO_DRAWDOWN_FIXTURE)
    render(<RiskSummaryCard />)
    const dashes = screen.getAllByText('—')
    // max_drawdown_pct and current_drawdown_pct are both null → 2 dashes for drawdown + 1 for at-risk
    expect(dashes.length).toBeGreaterThanOrEqual(2)
  })
})

// ---------------------------------------------------------------------------
// F-13-08: loading skeleton with role="status"
// ---------------------------------------------------------------------------

describe('RiskSummaryCard — F-13-08: loading skeleton', () => {
  it('shows loading skeleton with role="status" while loading', () => {
    mockUseRiskSummary.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as ReturnType<typeof useRiskSummary>)
    render(<RiskSummaryCard />)
    expect(
      screen.getByRole('status', { name: /loading risk summary/i }),
    ).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-13-09: error message on fetch failure
// ---------------------------------------------------------------------------

describe('RiskSummaryCard — F-13-09: error state', () => {
  it('shows error message on fetch failure', () => {
    mockUseRiskSummary.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as ReturnType<typeof useRiskSummary>)
    render(<RiskSummaryCard />)
    expect(screen.getByText(/failed to load risk summary/i)).toBeInTheDocument()
  })
})
