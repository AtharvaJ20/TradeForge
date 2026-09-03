import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ChargesCard } from '../ChargesCard'
import { ANALYTICS_SUMMARY_FIXTURE as F } from '@/__tests__/msw/handlers'

describe('ChargesCard', () => {
  it('renders total charges and all charge line items from fixture', () => {
    render(<ChargesCard charges={F.charges} />)
    // Total charges appears twice (line item + total row) — use getAllByText
    const totalEntries = screen.getAllByText('₹1,500')
    expect(totalEntries.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('₹600')).toBeInTheDocument()
    expect(screen.getByText('₹300')).toBeInTheDocument()
  })

  it('shows charge drag % when charge_drag_pct is non-null', () => {
    render(<ChargesCard charges={F.charges} />)
    expect(screen.getByText(/charge drag/i)).toBeInTheDocument()
    expect(screen.getByText('5.17%')).toBeInTheDocument()
  })

  it('shows charges_added_to_loss when charge_drag_pct is null', () => {
    const lossCharges = {
      ...F.charges,
      charge_drag_pct: null,
      charges_added_to_loss: '1500.00',
    }
    render(<ChargesCard charges={lossCharges} />)
    expect(screen.getByText(/charges added to loss/i)).toBeInTheDocument()
  })
})
