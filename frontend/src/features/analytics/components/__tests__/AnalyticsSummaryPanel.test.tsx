import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AnalyticsSummaryPanel } from '../AnalyticsSummaryPanel'
import {
  ANALYTICS_SUMMARY_FIXTURE,
  ANALYTICS_SUMMARY_INSUFFICIENT_FIXTURE,
  STREAKS_FIXTURE,
  HOLD_DURATION_FIXTURE,
  EXIT_TYPES_FIXTURE,
} from '@/__tests__/msw/handlers'

// ---------------------------------------------------------------------------
// Mock hooks — isolate container behaviour from network and QueryClient
// ---------------------------------------------------------------------------

vi.mock('../../hooks/useAnalyticsSummary', () => ({
  useAnalyticsSummary: vi.fn(),
}))

vi.mock('../../hooks/useStreaks', () => ({
  useStreaks: vi.fn(),
}))

vi.mock('../../hooks/useHoldDuration', () => ({
  useHoldDuration: vi.fn(),
}))

vi.mock('../../hooks/useExitTypes', () => ({
  useExitTypes: vi.fn(),
}))

import { useAnalyticsSummary } from '../../hooks/useAnalyticsSummary'
import { useStreaks } from '../../hooks/useStreaks'
import { useHoldDuration } from '../../hooks/useHoldDuration'
import { useExitTypes } from '../../hooks/useExitTypes'

const mockUseAnalyticsSummary = vi.mocked(useAnalyticsSummary)
const mockUseStreaks = vi.mocked(useStreaks)
const mockUseHoldDuration = vi.mocked(useHoldDuration)
const mockUseExitTypes = vi.mocked(useExitTypes)

function mockBehavioralDataReady() {
  mockUseStreaks.mockReturnValue({
    data: STREAKS_FIXTURE,
    isLoading: false,
    isError: false,
  } as ReturnType<typeof useStreaks>)
  mockUseHoldDuration.mockReturnValue({
    data: HOLD_DURATION_FIXTURE,
    isLoading: false,
    isError: false,
  } as ReturnType<typeof useHoldDuration>)
  mockUseExitTypes.mockReturnValue({
    data: EXIT_TYPES_FIXTURE,
    isLoading: false,
    isError: false,
  } as ReturnType<typeof useExitTypes>)
}

function mockBehavioralLoading() {
  const loading = { data: undefined, isLoading: true, isError: false }
  mockUseStreaks.mockReturnValue(loading as ReturnType<typeof useStreaks>)
  mockUseHoldDuration.mockReturnValue(loading as ReturnType<typeof useHoldDuration>)
  mockUseExitTypes.mockReturnValue(loading as ReturnType<typeof useExitTypes>)
}

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
    mockBehavioralLoading()

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
    mockBehavioralLoading()

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
    mockBehavioralLoading()

    const { container } = render(<AnalyticsSummaryPanel />)
    expect(container.firstChild).toBeNull()
  })

  it('renders all expected section landmarks when summary data is available', () => {
    mockUseAnalyticsSummary.mockReturnValue({
      data: ANALYTICS_SUMMARY_FIXTURE as ReturnType<typeof useAnalyticsSummary>['data'],
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useAnalyticsSummary>)
    mockBehavioralDataReady()

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
    mockBehavioralLoading()

    render(<AnalyticsSummaryPanel />)

    expect(screen.getAllByText(/insufficient data/i).length).toBeGreaterThanOrEqual(1)
  })

  it('renders all three behavioral analytics card headings (Step 12.5)', () => {
    mockUseAnalyticsSummary.mockReturnValue({
      data: ANALYTICS_SUMMARY_FIXTURE as ReturnType<typeof useAnalyticsSummary>['data'],
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useAnalyticsSummary>)
    mockBehavioralDataReady()

    render(<AnalyticsSummaryPanel />)

    expect(screen.getByRole('region', { name: /consecutive streaks/i })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: /hold duration distribution/i })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: /exit type analysis/i })).toBeInTheDocument()
  })
})
