import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ProfitFactorCard } from '../ProfitFactorCard'
import { ANALYTICS_SUMMARY_FIXTURE as F } from '@/__tests__/msw/handlers'

describe('ProfitFactorCard', () => {
  it('renders profit factor value and gross profit/loss from fixture', () => {
    render(<ProfitFactorCard profitFactor={F.profit_factor} />)
    expect(screen.getByText('3.14')).toBeInTheDocument()
    expect(screen.getByText('₹19,000')).toBeInTheDocument()
    expect(screen.getByText('-₹6,050')).toBeInTheDocument()
  })

  it('shows em-dash and "No losing trades" note when profit_factor is null', () => {
    const noLoss = { ...F.profit_factor, profit_factor: null }
    render(<ProfitFactorCard profitFactor={noLoss} />)
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent(/no losing trades/i)
  })
})
