import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AnalyticsFilterBar } from '../AnalyticsFilterBar'

describe('AnalyticsFilterBar', () => {
  it('renders the filter region with date inputs, checkbox groups, and Clear All', () => {
    render(<AnalyticsFilterBar value={{}} onChange={vi.fn()} />)

    expect(screen.getByRole('region', { name: /analytics filters/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/date from/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/date to/i)).toBeInTheDocument()
    expect(screen.getByRole('group', { name: /direction/i })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: /trade type/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /clear all/i })).toBeInTheDocument()
  })

  it('calls onChange with directions populated when a direction checkbox is checked', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<AnalyticsFilterBar value={{}} onChange={onChange} />)

    await user.click(screen.getByRole('checkbox', { name: 'LONG' }))

    expect(onChange).toHaveBeenCalledWith({ directions: ['LONG'] })
  })

  it('omits the directions key when the last selected direction is unchecked', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<AnalyticsFilterBar value={{ directions: ['LONG'] }} onChange={onChange} />)

    await user.click(screen.getByRole('checkbox', { name: 'LONG' }))

    expect(onChange).toHaveBeenCalledWith({})
  })

  it('calls onChange with {} when Clear All is clicked', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(
      <AnalyticsFilterBar
        value={{ directions: ['SHORT'], trade_types: ['SWING'] }}
        onChange={onChange}
      />,
    )

    await user.click(screen.getByRole('button', { name: /clear all/i }))

    expect(onChange).toHaveBeenCalledWith({})
  })

  it('calls onChange with date_from when the date-from input changes', () => {
    const onChange = vi.fn()
    render(<AnalyticsFilterBar value={{}} onChange={onChange} />)

    fireEvent.change(screen.getByLabelText(/date from/i), {
      target: { value: '2026-01-01' },
    })

    expect(onChange).toHaveBeenCalledWith({ date_from: '2026-01-01' })
  })

  it('removes date_from from params when the date-from input is cleared', () => {
    const onChange = vi.fn()
    render(<AnalyticsFilterBar value={{ date_from: '2026-01-01' }} onChange={onChange} />)

    fireEvent.change(screen.getByLabelText(/date from/i), {
      target: { value: '' },
    })

    expect(onChange).toHaveBeenCalledWith({})
  })
})
