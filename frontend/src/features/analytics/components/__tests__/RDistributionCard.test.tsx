import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { RDistributionCard } from '../RDistributionCard'
import {
  R_DISTRIBUTION_FIXTURE,
  R_DISTRIBUTION_INSUFFICIENT_FIXTURE,
} from '@/__tests__/msw/handlers'
import type { useRDistribution } from '../../hooks/useRDistribution'

vi.mock('../../hooks/useRDistribution', () => ({
  useRDistribution: vi.fn(),
}))

import { useRDistribution as _useRDistribution } from '../../hooks/useRDistribution'

const mockUseRDistribution = vi.mocked(_useRDistribution)

function withData(data: typeof R_DISTRIBUTION_FIXTURE) {
  mockUseRDistribution.mockReturnValue({
    data,
    isLoading: false,
    isError: false,
  } as ReturnType<typeof useRDistribution>)
}

// ---------------------------------------------------------------------------
// TC-RDIST-FE-001: renders section landmark and heading
// ---------------------------------------------------------------------------

describe('RDistributionCard — structure', () => {
  it('renders section landmark with heading', () => {
    withData(R_DISTRIBUTION_FIXTURE)
    render(<RDistributionCard />)
    expect(screen.getByRole('region', { name: /r-multiple distribution/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /r-multiple distribution/i })).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// TC-RDIST-FE-002: renders all 6 bucket labels
// ---------------------------------------------------------------------------

describe('RDistributionCard — bucket bars', () => {
  it('renders all 6 bucket labels from fixture', () => {
    withData(R_DISTRIBUTION_FIXTURE)
    render(<RDistributionCard />)

    expect(screen.getByText('< −2R')).toBeInTheDocument()
    expect(screen.getByText('−2R to −1R')).toBeInTheDocument()
    expect(screen.getByText('−1R to 0')).toBeInTheDocument()
    expect(screen.getByText('0 to +1R')).toBeInTheDocument()
    expect(screen.getByText('+1R to +2R')).toBeInTheDocument()
    expect(screen.getByText('> +2R')).toBeInTheDocument()
  })

  it('renders summary stats: coverage count and mean/median', () => {
    withData(R_DISTRIBUTION_FIXTURE)
    render(<RDistributionCard />)

    // coverage_count=20, total_count=22
    expect(screen.getByText('20/22')).toBeInTheDocument()
    // mean_r='0.45' → '+0.45R'
    expect(screen.getByText('+0.45R')).toBeInTheDocument()
    // median_r='0.50' → '+0.50R'
    expect(screen.getByText('+0.50R')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// TC-RDIST-FE-003: insufficient sample guard
// ---------------------------------------------------------------------------

describe('RDistributionCard — insufficient sample', () => {
  it('shows empty state note when insufficient_sample is true', () => {
    withData(R_DISTRIBUTION_INSUFFICIENT_FIXTURE)
    render(<RDistributionCard />)

    expect(
      screen.getByRole('note'),
    ).toHaveTextContent(/need at least 5 trades with a planned stop/i)
  })

  it('does not render bars when insufficient_sample is true', () => {
    withData(R_DISTRIBUTION_INSUFFICIENT_FIXTURE)
    render(<RDistributionCard />)

    // bucket labels should not be visible when showing empty state
    expect(screen.queryByText('< −2R')).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// TC-RDIST-FE-004: loading and error states
// ---------------------------------------------------------------------------

describe('RDistributionCard — loading / error', () => {
  it('shows loading skeleton while data is loading', () => {
    mockUseRDistribution.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as ReturnType<typeof useRDistribution>)
    render(<RDistributionCard />)

    expect(
      screen.getByRole('status', { name: /loading r-multiple distribution/i }),
    ).toBeInTheDocument()
  })

  it('shows error message on fetch failure', () => {
    mockUseRDistribution.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as ReturnType<typeof useRDistribution>)
    render(<RDistributionCard />)

    expect(screen.getByText(/failed to load r-multiple distribution/i)).toBeInTheDocument()
  })
})
