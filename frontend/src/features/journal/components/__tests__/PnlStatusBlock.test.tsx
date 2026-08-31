import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PnlStatusBlock } from '../PnlStatusBlock'

describe('PnlStatusBlock', () => {
  it('renders PENDING_STOP state with CTA', () => {
    const onAddStop = vi.fn()
    render(
      <PnlStatusBlock
        status="PENDING_STOP"
        netPnl={null}
        grossPnl={null}
        totalCharges={null}
        rMultiple={null}
        onAddStop={onAddStop}
      />,
    )
    expect(screen.getByText(/set a stop to unlock r-multiple/i)).toBeInTheDocument()
    const btn = screen.getByRole('button', { name: /add stop/i })
    expect(btn).toBeInTheDocument()
  })

  it('calls onAddStop when CTA clicked', async () => {
    const onAddStop = vi.fn()
    render(
      <PnlStatusBlock
        status="PENDING_STOP"
        netPnl={null}
        grossPnl={null}
        totalCharges={null}
        rMultiple={null}
        onAddStop={onAddStop}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: /add stop/i }))
    expect(onAddStop).toHaveBeenCalledOnce()
  })

  it('renders PENDING_CALCULATION state', () => {
    render(
      <PnlStatusBlock
        status="PENDING_CALCULATION"
        netPnl={null}
        grossPnl={null}
        totalCharges={null}
        rMultiple={null}
      />,
    )
    expect(screen.getByText(/p&l calculating/i)).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('renders AVAILABLE state with net P&L', () => {
    render(
      <PnlStatusBlock
        status="AVAILABLE"
        netPnl="2150.00"
        grossPnl="2300.00"
        totalCharges="150.00"
        rMultiple="2.15"
      />,
    )
    expect(screen.getByText(/p&l available/i)).toBeInTheDocument()
    // Net P&L should show a + prefix for profit
    expect(screen.getByLabelText(/net p&l/i)).toHaveTextContent('+')
  })
})
