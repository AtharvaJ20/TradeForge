import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PlannedRRCard } from '../PlannedRRCard'
import { ANALYTICS_SUMMARY_FIXTURE as F } from '@/__tests__/msw/handlers'

describe('PlannedRRCard', () => {
  it('shows em-dash and null note when avg_planned_rr is null (fixture default)', () => {
    render(<PlannedRRCard plannedRR={F.planned_rr} />)
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent(/no trades with stop \+ target/i)
  })

  it('renders coverage count and total', () => {
    render(<PlannedRRCard plannedRR={F.planned_rr} />)
    expect(screen.getByText(/0 of 30 trades/i)).toBeInTheDocument()
  })

  it('renders avg planned R:R value when non-null', () => {
    const withRR = { ...F.planned_rr, avg_planned_rr: '2.50', trade_count_with_rr: 15 }
    render(<PlannedRRCard plannedRR={withRR} />)
    expect(screen.getByText('2.50')).toBeInTheDocument()
  })
})
