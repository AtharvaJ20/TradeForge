import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ExpectancyCard } from '../ExpectancyCard'
import { ANALYTICS_SUMMARY_FIXTURE as F } from '@/__tests__/msw/handlers'

describe('ExpectancyCard', () => {
  it('renders positive expectancy R with coverage info when sufficient data', () => {
    render(<ExpectancyCard expectancy={F.expectancy} />)
    expect(screen.getByText('+1.25')).toBeInTheDocument()
    expect(screen.getByText(/R coverage: 100\.0%/i)).toBeInTheDocument()
  })

  it('renders avg win and avg loss R values', () => {
    render(<ExpectancyCard expectancy={F.expectancy} />)
    expect(screen.getByText('+2.00')).toBeInTheDocument()
    expect(screen.getByText('-1.50')).toBeInTheDocument()
  })

  it('shows insufficient data note and em-dash when insufficient_sample is true', () => {
    const insufficient = {
      ...F.expectancy,
      expectancy_r: null,
      insufficient_sample: true,
      r_coverage_count: 5,
    }
    render(<ExpectancyCard expectancy={insufficient} />)
    const notes = screen.getAllByRole('note')
    expect(notes.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/insufficient data/i)).toBeInTheDocument()
  })
})
