import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DrawdownCard } from '../DrawdownCard'
import { ANALYTICS_SUMMARY_FIXTURE as F } from '@/__tests__/msw/handlers'

describe('DrawdownCard', () => {
  it('shows "no drawdown data" note when all fields are null (fixture default)', () => {
    render(<DrawdownCard drawdown={F.drawdown} />)
    expect(screen.getByRole('note')).toHaveTextContent(/no drawdown data/i)
  })

  it('renders max drawdown values when non-null', () => {
    const withDrawdown = {
      max_drawdown_pct: '-15.00',
      max_drawdown_inr: '-45000.00',
      avg_drawdown_pct: '-8.00',
      current_drawdown_pct: '-3.00',
    }
    render(<DrawdownCard drawdown={withDrawdown} />)
    expect(screen.getByText('-15.00%')).toBeInTheDocument()
    expect(screen.getByText('-₹45,000')).toBeInTheDocument()
  })
})
