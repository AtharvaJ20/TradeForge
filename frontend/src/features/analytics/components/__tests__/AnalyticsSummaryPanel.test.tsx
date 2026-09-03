import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AnalyticsSummaryPanel } from '../AnalyticsSummaryPanel'
import {
  ANALYTICS_SUMMARY_FIXTURE,
  ANALYTICS_SUMMARY_INSUFFICIENT_FIXTURE,
} from '@/__tests__/msw/handlers'

// ---------------------------------------------------------------------------
// Mock hook — isolate container behaviour from network and QueryClient
// ---------------------------------------------------------------------------

vi.mock('../../hooks/useAnalyticsSummary', () => ({
  useAnalyticsSummary: vi.fn(),
}))

import { useAnalyticsSummary } from '../../hooks/useAnalyticsSummary'

const mockUseAnalyticsSummary = vi.mocked(useAnalyticsSummary)

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AnalyticsSummaryPanel — container states', () => {
  it('shows a loading skeleton with aria-busy when data is loading', () => {
    mockUseAnalyticsSummary.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as ReturnType<typeof useAnalyticsSummary>)

    render(<AnalyticsSummaryPanel />)

    const skeleton = screen.getByRole('status', { name: /loading analytics/i })
    expect(skeleton).toBeInTheDocument()
    expect(skeleton).toHaveAttribute('aria-busy', 'true')
  })

  it('shows an error alert when the request fails', () => {
    mockUseAnalyticsSummary.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as ReturnType<typeof useAnalyticsSummary>)

    render(<AnalyticsSummaryPanel />)

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText(/failed to load analytics/i)).toBeInTheDocument()
  })

  it('renders nothing when data is absent and not loading or errored', () => {
    mockUseAnalyticsSummary.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useAnalyticsSummary>)

    const { container } = render(<AnalyticsSummaryPanel />)
    expect(container.firstChild).toBeNull()
  })

  it('renders all expected section landmarks when summary data is available', () => {
    mockUseAnalyticsSummary.mockReturnValue({
      data: ANALYTICS_SUMMARY_FIXTURE as ReturnType<typeof useAnalyticsSummary>['data'],
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useAnalyticsSummary>)

    render(<AnalyticsSummaryPanel />)

    expect(screen.getByRole('region', { name: /risk-adjusted returns/i })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: /p&l summary/i })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: /outcome distribution/i })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: /charges breakdown/i })).toBeInTheDocument()
  })

  it('renders risk-adjusted section with insufficient_sample data', () => {
    mockUseAnalyticsSummary.mockReturnValue({
      data: ANALYTICS_SUMMARY_INSUFFICIENT_FIXTURE as ReturnType<typeof useAnalyticsSummary>['data'],
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useAnalyticsSummary>)

    render(<AnalyticsSummaryPanel />)

    expect(screen.getAllByText(/insufficient data/i).length).toBeGreaterThanOrEqual(1)
  })
})
