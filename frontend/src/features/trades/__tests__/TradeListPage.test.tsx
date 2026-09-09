import { render, screen, fireEvent, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import { TradeListPage } from '../TradeListPage'
import {
  TRADES_LIST,
  TRADES_LIST_EMPTY,
} from '@/__tests__/msw/handlers'
import type { TradeListPageOut } from '../types'

// ---------------------------------------------------------------------------
// Mock dependencies
// ---------------------------------------------------------------------------

const mockUseAccount = vi.fn()
const mockUseNavigate = vi.fn()
const mockUseQuery = vi.fn()

vi.mock('@/features/accounts/context/AccountContext', () => ({
  useAccount: () => mockUseAccount(),
}))

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return {
    ...actual,
    useNavigate: () => mockUseNavigate,
  }
})

vi.mock('@tanstack/react-query', () => ({
  useQuery: (...args: unknown[]) => mockUseQuery(...args),
}))

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const MOCK_ACCOUNT = {
  id: '00000000-0000-0000-0000-000000000001',
  display_name: 'Zerodha Main',
  user_id: '00000000-0000-0000-0000-000000000099',
  broker: 'ZERODHA',
  account_type: 'INDIVIDUAL',
  base_currency: 'INR',
  status: 'ACTIVE' as const,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

function makeIdle<T>(data: T) {
  return { data, isLoading: false, isError: false }
}

function makeLoading() {
  return { data: undefined, isLoading: true, isError: false }
}

function renderTradeList() {
  return render(
    <MemoryRouter>
      <TradeListPage />
    </MemoryRouter>,
  )
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockUseAccount.mockReturnValue({
    selectedAccount: MOCK_ACCOUNT,
    accounts: [MOCK_ACCOUNT],
    isLoading: false,
    selectAccount: vi.fn(),
    refetchAccounts: vi.fn(),
  })
  mockUseQuery.mockReturnValue(makeIdle(TRADES_LIST))
  mockUseNavigate.mockReset()
})

afterEach(() => {
  vi.useRealTimers()
})

// ---------------------------------------------------------------------------
// Helpers to read the last queryKey passed to useQuery
// ---------------------------------------------------------------------------

function lastQueryParams(): Record<string, unknown> {
  const calls = mockUseQuery.mock.calls
  const last = calls[calls.length - 1]
  // queryKey is [identifier, params] — params is at index 1 or nested
  const queryKey = last[0].queryKey as unknown[]
  return queryKey.find((k) => typeof k === 'object' && k !== null) as Record<string, unknown>
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('TradeListPage', () => {
  it('F-19-01: renders table with items from TRADES_LIST fixture showing symbol, direction, status, P&L', () => {
    renderTradeList()
    // items[0]: SYM1, LONG, CLOSED, net_pnl=-100 (i=0, 0%3===0 → -(0+1)*100)
    expect(screen.getByText('SYM1')).toBeInTheDocument()
    expect(screen.getAllByText('Long').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Closed').length).toBeGreaterThan(0)
    // items[1]: SYM2, SHORT, CLOSED, net_pnl=400 (i=1, 1%3!==0 → (1+1)*200)
    expect(screen.getByText('+₹400')).toBeInTheDocument()
  })

  it('F-19-02: total field drives "Showing X–Y of Z trades" text', () => {
    renderTradeList()
    expect(screen.getByText('Showing 1–10 of 10 trades')).toBeInTheDocument()
  })

  it('F-19-03: "Next" button is disabled when total <= limit', () => {
    renderTradeList()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
  })

  it('F-19-04: clicking "Next" increments offset and triggers a new fetch', () => {
    const bigList: TradeListPageOut = { ...TRADES_LIST, total: 50 }
    mockUseQuery.mockReturnValue(makeIdle(bigList))
    renderTradeList()

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    const params = lastQueryParams()
    expect(params).toMatchObject({ offset: 25 })
  })

  it('F-19-05: Status tab "Closed" applies status=CLOSED param to the API call', () => {
    renderTradeList()
    fireEvent.click(screen.getByRole('button', { name: 'Closed' }))

    const params = lastQueryParams()
    expect(params).toMatchObject({ status: 'CLOSED' })
  })

  it('F-19-06: Direction filter "Long" applies direction=LONG param', () => {
    renderTradeList()
    fireEvent.change(screen.getByRole('combobox', { name: 'Direction filter' }), {
      target: { value: 'LONG' },
    })

    const params = lastQueryParams()
    expect(params).toMatchObject({ direction: 'LONG' })
  })

  it('F-19-07: Instrument text input (after 300ms debounce) applies instrument= param', () => {
    vi.useFakeTimers()
    renderTradeList()

    const input = screen.getByRole('textbox', { name: 'Instrument search' })
    fireEvent.change(input, { target: { value: 'RELIANCE' } })

    act(() => {
      vi.advanceTimersByTime(300)
    })

    const params = lastQueryParams()
    expect(params).toMatchObject({ instrument: 'RELIANCE' })
  })

  it('F-19-08: "Clear filters" button resets all filter params to defaults', () => {
    renderTradeList()

    // Apply a filter
    fireEvent.change(screen.getByRole('combobox', { name: 'Direction filter' }), {
      target: { value: 'LONG' },
    })

    // "Clear filters" should appear
    const clearBtn = screen.getByRole('button', { name: 'Clear filters' })
    expect(clearBtn).toBeInTheDocument()

    fireEvent.click(clearBtn)

    // After clearing, button should be gone
    expect(screen.queryByRole('button', { name: 'Clear filters' })).not.toBeInTheDocument()

    // Params should be reset (no direction)
    const params = lastQueryParams()
    expect(params).not.toMatchObject({ direction: 'LONG' })
  })

  it('F-19-09: empty state "No trades found…" renders when items is empty', () => {
    mockUseQuery.mockReturnValue(makeIdle(TRADES_LIST_EMPTY))
    renderTradeList()
    expect(screen.getByText(/No trades found/i)).toBeInTheDocument()
  })

  it('F-19-10: clicking a row navigates to /trades/<id>', () => {
    renderTradeList()
    const firstRow = screen.getByText('SYM1').closest('tr')!
    fireEvent.click(firstRow)
    expect(mockUseNavigate).toHaveBeenCalledWith('/trades/trade-001')
  })

  it('F-19-11: loading state shows skeleton rows while fixture resolves', () => {
    mockUseQuery.mockReturnValue(makeLoading())
    const { container } = renderTradeList()
    const skeletonCells = container.querySelectorAll('.animate-pulse')
    expect(skeletonCells.length).toBeGreaterThan(0)
  })

  it('F-19-23: clicking "Date" column header fires API call with sort_by=trade_date; clicking again cycles sort_dir; only one column shows active sort', () => {
    renderTradeList()

    // Initial click → desc
    fireEvent.click(screen.getByText('Date'))
    expect(lastQueryParams()).toMatchObject({ sort_by: 'trade_date', sort_dir: 'desc' })

    // Second click → asc
    fireEvent.click(screen.getByText('Date'))
    expect(lastQueryParams()).toMatchObject({ sort_by: 'trade_date', sort_dir: 'asc' })

    // Arrow indicator only on Date header
    const arrows = screen.getAllByLabelText(/ascending|descending/)
    expect(arrows).toHaveLength(1)
  })

  it('F-19-27: "Previous" disabled at offset=0; Next increments; Previous decrements back', () => {
    const bigList: TradeListPageOut = { ...TRADES_LIST, total: 50 }
    mockUseQuery.mockReturnValue(makeIdle(bigList))
    renderTradeList()

    // Initially disabled
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()

    // Click next → offset = 25
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(lastQueryParams()).toMatchObject({ offset: 25 })

    // Previous should now be enabled — click it
    const prevBtn = screen.getByRole('button', { name: 'Previous' })
    expect(prevBtn).not.toBeDisabled()
    fireEvent.click(prevBtn)
    expect(lastQueryParams()).toMatchObject({ offset: 0 })
  })

  it('F-19-22: TradeListPage reads items from TradeListPageOut envelope shape correctly', () => {
    const envelope: TradeListPageOut = {
      items: [TRADES_LIST.items[0]],
      total: 1,
      limit: 25,
      offset: 0,
    }
    mockUseQuery.mockReturnValue(makeIdle(envelope))
    renderTradeList()
    expect(screen.getByText('SYM1')).toBeInTheDocument()
    expect(screen.getByText('Showing 1–1 of 1 trades')).toBeInTheDocument()
  })
})
