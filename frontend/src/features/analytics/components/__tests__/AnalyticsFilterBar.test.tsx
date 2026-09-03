import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AnalyticsFilterBar } from '../AnalyticsFilterBar'
import type { FilterDimensions } from '../../hooks/useFilterDimensions'

// ---------------------------------------------------------------------------
// Mock useFilterDimensions — isolate FilterBar from network / QueryClient
// ---------------------------------------------------------------------------

vi.mock('../../hooks/useFilterDimensions', () => ({
  useFilterDimensions: vi.fn(),
}))

import { useFilterDimensions } from '../../hooks/useFilterDimensions'

const mockUseFilterDimensions = vi.mocked(useFilterDimensions)

const LOADED_DIMENSIONS: FilterDimensions = {
  accounts: [
    { id: '00000000-0000-0000-0000-000000000011', label: 'Zerodha Main' },
    { id: '00000000-0000-0000-0000-000000000022', label: 'Upstox Secondary' },
  ],
  setups: ['Breakout', 'VWAP Reversion'],
  brokers: ['UPSTOX', 'ZERODHA'],
  isLoading: false,
  accountsError: false,
  setupsError: false,
  brokersError: false,
}

const LOADING_DIMENSIONS: FilterDimensions = {
  accounts: [],
  setups: [],
  brokers: [],
  isLoading: true,
  accountsError: false,
  setupsError: false,
  brokersError: false,
}

const ERROR_DIMENSIONS: FilterDimensions = {
  accounts: [],
  setups: [],
  brokers: [],
  isLoading: false,
  accountsError: true,
  setupsError: true,
  brokersError: true,
}

beforeEach(() => {
  mockUseFilterDimensions.mockReturnValue(LOADED_DIMENSIONS)
})

// ---------------------------------------------------------------------------
// Static structure
// ---------------------------------------------------------------------------

describe('AnalyticsFilterBar — static structure', () => {
  it('renders the filter region with date inputs, static groups, and Clear All', () => {
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

// ---------------------------------------------------------------------------
// Dynamic dimension groups — loaded state
// ---------------------------------------------------------------------------

describe('AnalyticsFilterBar — dynamic dimensions loaded', () => {
  it('renders Account fieldset with fetched account labels', () => {
    render(<AnalyticsFilterBar value={{}} onChange={vi.fn()} />)

    expect(screen.getByRole('group', { name: /account/i })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Zerodha Main' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Upstox Secondary' })).toBeInTheDocument()
  })

  it('renders Setup fieldset with fetched setup names', () => {
    render(<AnalyticsFilterBar value={{}} onChange={vi.fn()} />)

    expect(screen.getByRole('group', { name: /setup/i })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Breakout' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'VWAP Reversion' })).toBeInTheDocument()
  })

  it('renders Broker fieldset with fetched broker values', () => {
    render(<AnalyticsFilterBar value={{}} onChange={vi.fn()} />)

    expect(screen.getByRole('group', { name: /broker/i })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'ZERODHA' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'UPSTOX' })).toBeInTheDocument()
  })

  it('stores the account UUID (not the label) in account_ids when checked', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<AnalyticsFilterBar value={{}} onChange={onChange} />)

    await user.click(screen.getByRole('checkbox', { name: 'Zerodha Main' }))

    expect(onChange).toHaveBeenCalledWith({
      account_ids: ['00000000-0000-0000-0000-000000000011'],
    })
  })

  it('stores the setup name string in setup_names when checked', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<AnalyticsFilterBar value={{}} onChange={onChange} />)

    await user.click(screen.getByRole('checkbox', { name: 'Breakout' }))

    expect(onChange).toHaveBeenCalledWith({ setup_names: ['Breakout'] })
  })

  it('stores the broker string in brokers when checked', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<AnalyticsFilterBar value={{}} onChange={onChange} />)

    await user.click(screen.getByRole('checkbox', { name: 'ZERODHA' }))

    expect(onChange).toHaveBeenCalledWith({ brokers: ['ZERODHA'] })
  })

  it('unchecking removes the value from account_ids and drops the key when empty', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(
      <AnalyticsFilterBar
        value={{ account_ids: ['00000000-0000-0000-0000-000000000011'] }}
        onChange={onChange}
      />,
    )

    await user.click(screen.getByRole('checkbox', { name: 'Zerodha Main' }))

    expect(onChange).toHaveBeenCalledWith({})
  })

  it('hides dynamic groups when all lists are empty (no user data)', () => {
    mockUseFilterDimensions.mockReturnValue({
      ...LOADED_DIMENSIONS,
      accounts: [],
      setups: [],
      brokers: [],
    })
    render(<AnalyticsFilterBar value={{}} onChange={vi.fn()} />)

    expect(screen.queryByRole('group', { name: /account/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('group', { name: /setup/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('group', { name: /broker/i })).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-5: Loading skeleton state
// ---------------------------------------------------------------------------

describe('AnalyticsFilterBar — loading skeleton (F-5)', () => {
  it('shows aria-busy skeletons while dimensions are loading', () => {
    mockUseFilterDimensions.mockReturnValue(LOADING_DIMENSIONS)
    render(<AnalyticsFilterBar value={{}} onChange={vi.fn()} />)

    const skeletons = screen.getAllByRole('generic', { hidden: false }).filter(
      el => el.getAttribute('aria-busy') === 'true',
    )
    expect(skeletons.length).toBeGreaterThanOrEqual(3)
  })

  it('still renders all static groups while loading', () => {
    mockUseFilterDimensions.mockReturnValue(LOADING_DIMENSIONS)
    render(<AnalyticsFilterBar value={{}} onChange={vi.fn()} />)

    expect(screen.getByRole('group', { name: /direction/i })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: /trade type/i })).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Error degradation state
// ---------------------------------------------------------------------------

describe('AnalyticsFilterBar — dimension error degradation', () => {
  it('shows "Unable to load options" notes when all dimensions error', () => {
    mockUseFilterDimensions.mockReturnValue(ERROR_DIMENSIONS)
    render(<AnalyticsFilterBar value={{}} onChange={vi.fn()} />)

    const notes = screen.getAllByRole('note')
    expect(notes.length).toBe(3)
    notes.forEach(n => expect(n).toHaveTextContent(/unable to load options/i))
  })

  it('still renders static groups when dynamic dimensions error', () => {
    mockUseFilterDimensions.mockReturnValue(ERROR_DIMENSIONS)
    render(<AnalyticsFilterBar value={{}} onChange={vi.fn()} />)

    expect(screen.getByRole('group', { name: /direction/i })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'LONG' })).toBeInTheDocument()
  })
})
