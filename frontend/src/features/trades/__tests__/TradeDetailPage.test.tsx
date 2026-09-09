import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { TradeDetailPage } from '../TradeDetailPage'
import {
  TRADE_DETAIL_CLOSED,
  TRADE_DETAIL_OPEN,
  TRADE_DETAIL_PARTIAL,
  TRADE_DETAIL_SCALP,
} from '@/__tests__/msw/handlers'
import type { TradeDetailOut } from '../types'

// ---------------------------------------------------------------------------
// Mock dependencies
// ---------------------------------------------------------------------------

const mockUseQuery = vi.fn()

vi.mock('@tanstack/react-query', () => ({
  useQuery: (...args: unknown[]) => mockUseQuery(...args),
}))

vi.mock('@/features/journal/components/JournalPanel', () => ({
  JournalPanel: ({ trade }: { trade: { id: string } }) => (
    <div data-testid="journal-panel" data-trade-id={trade.id} />
  ),
}))

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeIdle<T>(data: T) {
  return { data, isLoading: false, isError: false }
}

function makeLoading() {
  return { data: undefined, isLoading: true, isError: false }
}

function makeError() {
  return { data: undefined, isLoading: false, isError: true }
}

function renderDetail(tradeId = 'trade-detail-001') {
  return render(
    <MemoryRouter initialEntries={[`/trades/${tradeId}`]}>
      <Routes>
        <Route path="/trades/:tradeId" element={<TradeDetailPage />} />
        <Route path="/trades" element={<div>Trade List</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockUseQuery.mockReturnValue(makeIdle(TRADE_DETAIL_CLOSED as TradeDetailOut))
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('TradeDetailPage', () => {
  it('F-19-12: renders Trade Summary section with symbol, direction chip, status badge, trade date', () => {
    renderDetail()
    expect(screen.getByText('RELIANCE')).toBeInTheDocument()
    expect(screen.getByText('Long')).toBeInTheDocument()
    expect(screen.getByText('Closed')).toBeInTheDocument()
    expect(screen.getByText('2026-09-01')).toBeInTheDocument()
  })

  it('F-19-13: CLOSED trade hold_duration_seconds renders as formatted duration; OPEN renders as "Open"', () => {
    // CLOSED: hold_duration_seconds: 8100 = 2h 15m
    renderDetail()
    expect(screen.getByText('2h 15m')).toBeInTheDocument()
    expect(screen.getByText('Hold duration')).toBeInTheDocument()

    // OPEN: hold_duration_seconds: null → "Open"
    mockUseQuery.mockReturnValue(makeIdle(TRADE_DETAIL_OPEN as TradeDetailOut))
    renderDetail('trade-detail-002')
    expect(screen.getAllByText('Open').length).toBeGreaterThan(0)
  })

  it('F-19-13b: PARTIAL trade hold_duration_seconds renders with label "Elapsed" not "Hold duration"', () => {
    mockUseQuery.mockReturnValue(makeIdle(TRADE_DETAIL_PARTIAL as TradeDetailOut))
    renderDetail('trade-detail-003')
    // hold_duration_seconds: 6300 = 1h 45m
    expect(screen.getByText('1h 45m')).toBeInTheDocument()
    expect(screen.getByText('Elapsed')).toBeInTheDocument()
    expect(screen.queryByText('Hold duration')).not.toBeInTheDocument()
  })

  it('F-19-14: Execution Timeline renders all fills in order with timestamp, side, role, quantity, price', () => {
    renderDetail()
    expect(screen.getByText(/Execution Timeline/i)).toBeInTheDocument()
    const buyChips = screen.getAllByText('BUY')
    const sellChips = screen.getAllByText('SELL')
    expect(buyChips.length).toBe(2)
    expect(sellChips.length).toBe(1)
    expect(screen.getByText('100')).toBeInTheDocument()
    // Price includes ₹
    expect(screen.getByText('₹2850.00')).toBeInTheDocument()
  })

  it('F-19-15: fill_role null renders as "—" in the Role column', () => {
    const tradeWithNullRole: TradeDetailOut = {
      ...TRADE_DETAIL_CLOSED,
      fills: [
        {
          ...TRADE_DETAIL_CLOSED.fills[0],
          fill_role: null,
        },
        ...TRADE_DETAIL_CLOSED.fills.slice(1),
      ],
    }
    mockUseQuery.mockReturnValue(makeIdle(tradeWithNullRole))
    renderDetail()
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('F-19-16: P&L Breakdown section visible for CLOSED trade; shows gross P&L, all 7 charge rows, net P&L', () => {
    renderDetail()
    expect(screen.getByText('Gross P&L')).toBeInTheDocument()
    expect(screen.getByText('Brokerage')).toBeInTheDocument()
    expect(screen.getByText('STT')).toBeInTheDocument()
    expect(screen.getByText('Exchange charges')).toBeInTheDocument()
    expect(screen.getByText('SEBI charges')).toBeInTheDocument()
    expect(screen.getByText('Stamp duty')).toBeInTheDocument()
    expect(screen.getByText('GST')).toBeInTheDocument()
    expect(screen.getByText('IPFT')).toBeInTheDocument()
    expect(screen.getByText('Net P&L')).toBeInTheDocument()
  })

  it('F-19-17: OPEN trade shows P&L placeholder "No exits yet…" — P&L Breakdown table hidden', () => {
    mockUseQuery.mockReturnValue(makeIdle(TRADE_DETAIL_OPEN as TradeDetailOut))
    renderDetail('trade-detail-002')
    expect(
      screen.getByText('No exits yet — P&L will be available when the trade closes.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Gross P&L')).not.toBeInTheDocument()
  })

  it('F-19-17b: PARTIAL trade shows "Partially closed…" placeholder — different from OPEN placeholder', () => {
    mockUseQuery.mockReturnValue(makeIdle(TRADE_DETAIL_PARTIAL as TradeDetailOut))
    renderDetail('trade-detail-003')
    expect(
      screen.getByText(
        'Partially closed — final P&L will be calculated when all positions are exited.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.queryByText('No exits yet — P&L will be available when the trade closes.'),
    ).not.toBeInTheDocument()
    expect(screen.queryByText('Gross P&L')).not.toBeInTheDocument()
  })

  it('F-19-18: JournalPanel is rendered for both OPEN and CLOSED trades', () => {
    renderDetail()
    expect(screen.getByTestId('journal-panel')).toBeInTheDocument()
    cleanup()

    mockUseQuery.mockReturnValue(makeIdle(TRADE_DETAIL_OPEN as TradeDetailOut))
    renderDetail('trade-detail-002')
    expect(screen.getByTestId('journal-panel')).toBeInTheDocument()
  })

  it('F-19-19: page shows "Back to trades" link navigating to /trades', () => {
    renderDetail()
    const backLink = screen.getByText(/Back to trades/i)
    expect(backLink).toBeInTheDocument()
    expect(backLink.closest('a')).toHaveAttribute('href', '/trades')
  })

  it('F-19-20: TRADE_DETAIL_NOT_FOUND: page renders "Trade not found" error state without crashing', () => {
    mockUseQuery.mockReturnValue(makeError())
    renderDetail()
    expect(screen.getByText(/Trade not found/i)).toBeInTheDocument()
  })

  it('F-19-21: loading state: skeleton renders while trade detail is fetching', () => {
    mockUseQuery.mockReturnValue(makeLoading())
    const { container } = renderDetail()
    const skeletons = container.querySelectorAll('.animate-pulse')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it('F-19-24: Trade Detail header renders exchange_segment as "NSE F&O" not raw "NSE_FO"', () => {
    // TRADE_DETAIL_CLOSED has exchange_segment: 'NSE_FO'
    renderDetail()
    expect(screen.getByText('NSE F&O')).toBeInTheDocument()
    expect(screen.queryByText('NSE_FO')).not.toBeInTheDocument()
  })

  it('F-19-25: Quantity row shows "entered / exited" for CLOSED; only "entered" for OPEN', () => {
    // CLOSED: 150 entered / 150 exited
    renderDetail()
    expect(screen.getByText('150 entered / 150 exited')).toBeInTheDocument()
    expect(screen.queryByText(/×/)).not.toBeInTheDocument()

    // OPEN: 200 entered (total_exit_quantity is '0')
    mockUseQuery.mockReturnValue(makeIdle(TRADE_DETAIL_OPEN as TradeDetailOut))
    renderDetail('trade-detail-002')
    expect(screen.getByText('200 entered')).toBeInTheDocument()
    expect(screen.queryByText(/×/)).not.toBeInTheDocument()
  })

  it('F-19-26: Trade Detail header renders instrument_name alongside symbol', () => {
    renderDetail()
    expect(screen.getByText('RELIANCE')).toBeInTheDocument()
    expect(screen.getByText('RELIANCE INDUSTRIES LTD')).toBeInTheDocument()
  })

  it('F-19-28: hold_duration_seconds: 45 renders as "45s" not "0h 0m"', () => {
    mockUseQuery.mockReturnValue(makeIdle(TRADE_DETAIL_SCALP as TradeDetailOut))
    renderDetail('trade-detail-004')
    expect(screen.getByText('45s')).toBeInTheDocument()
    expect(screen.queryByText('0h 0m')).not.toBeInTheDocument()
  })
})
