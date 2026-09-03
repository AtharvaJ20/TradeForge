import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DirectionBreakdownTable } from '../DirectionBreakdownTable'
import { ANALYTICS_SUMMARY_FIXTURE as F } from '@/__tests__/msw/handlers'

describe('DirectionBreakdownTable', () => {
  it('renders LONG row with win rate and avg net P&L from fixture', () => {
    render(<DirectionBreakdownTable rows={F.direction} />)
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByText('LONG')).toBeInTheDocument()
    expect(screen.getByText('67.0%')).toBeInTheDocument()
    expect(screen.getByText('₹917')).toBeInTheDocument()
  })

  it('shows column headers', () => {
    render(<DirectionBreakdownTable rows={F.direction} />)
    expect(screen.getByRole('columnheader', { name: /direction/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /win rate/i })).toBeInTheDocument()
  })

  it('shows "no direction data" note when rows is empty', () => {
    render(<DirectionBreakdownTable rows={[]} />)
    expect(screen.getByRole('note')).toHaveTextContent(/no direction data/i)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})
