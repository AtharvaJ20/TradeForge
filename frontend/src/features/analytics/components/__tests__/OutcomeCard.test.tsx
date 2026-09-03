import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { OutcomeCard } from '../OutcomeCard'
import { ANALYTICS_SUMMARY_FIXTURE as F } from '@/__tests__/msw/handlers'

describe('OutcomeCard', () => {
  it('renders win rate, loss rate, and total count from fixture', () => {
    render(<OutcomeCard outcome={F.outcome} />)
    expect(screen.getByText('67.0%')).toBeInTheDocument()
    expect(screen.getByText('33.0%')).toBeInTheDocument()
    expect(screen.getByText(/30 total trades/i)).toBeInTheDocument()
  })

  it('renders win and loss counts', () => {
    render(<OutcomeCard outcome={F.outcome} />)
    expect(screen.getByText(/20 wins/i)).toBeInTheDocument()
    expect(screen.getByText(/10 losses/i)).toBeInTheDocument()
  })

  it('renders breakeven rate and count', () => {
    render(<OutcomeCard outcome={F.outcome} />)
    expect(screen.getByText('0.0%')).toBeInTheDocument()
    expect(screen.getByText(/0 trades/i)).toBeInTheDocument()
  })
})
