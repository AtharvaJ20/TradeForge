import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PnlSummaryCard } from '../PnlSummaryCard'
import { ANALYTICS_SUMMARY_FIXTURE as F } from '@/__tests__/msw/handlers'

describe('PnlSummaryCard', () => {
  it('renders net P&L, gross P&L, and trade count from fixture', () => {
    render(<PnlSummaryCard pnl={F.pnl} />)
    expect(screen.getByText('₹27,500')).toBeInTheDocument()
    expect(screen.getByText('₹29,000')).toBeInTheDocument()
    expect(screen.getByText(/30 trades in period/i)).toBeInTheDocument()
  })

  it('renders total charges', () => {
    render(<PnlSummaryCard pnl={F.pnl} />)
    expect(screen.getByText('₹1,500')).toBeInTheDocument()
  })

  it('renders negative net P&L with a minus prefix', () => {
    const negativePnl = { ...F.pnl, net_pnl: '-5000.00' }
    render(<PnlSummaryCard pnl={negativePnl} />)
    expect(screen.getByText('-₹5,000')).toBeInTheDocument()
  })
})
