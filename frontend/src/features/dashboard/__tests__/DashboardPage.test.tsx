import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, Navigate } from 'react-router-dom'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { DashboardPage } from '../DashboardPage'
import {
  DASHBOARD_SUMMARY,
  DASHBOARD_SUMMARY_EMPTY,
  TRADES_LIST,
  TRADES_LIST_EMPTY,
  JOURNAL_RECENT,
  JOURNAL_RECENT_EMPTY,
  ANALYTICS_SUMMARY_FIXTURE,
  STREAKS_FIXTURE,
} from '@/__tests__/msw/handlers'

// ---------------------------------------------------------------------------
// Mock all hooks
// ---------------------------------------------------------------------------

const mockUseDashboardSummary = vi.fn()
const mockUseRecentTrades = vi.fn()
const mockUseRecentJournal = vi.fn()
const mockUseAnalyticsSummary = vi.fn()
const mockUseStreaks = vi.fn()
const mockUseAccount = vi.fn()
const mockUseAuth = vi.fn()

vi.mock('../hooks/useDashboardSummary', () => ({
  useDashboardSummary: (...args: unknown[]) => mockUseDashboardSummary(...args),
}))
vi.mock('../hooks/useRecentTrades', () => ({
  useRecentTrades: (...args: unknown[]) => mockUseRecentTrades(...args),
}))
vi.mock('../hooks/useRecentJournal', () => ({
  useRecentJournal: (...args: unknown[]) => mockUseRecentJournal(...args),
}))
vi.mock('@/features/analytics/hooks/useAnalyticsSummary', () => ({
  useAnalyticsSummary: (...args: unknown[]) => mockUseAnalyticsSummary(...args),
}))
vi.mock('@/features/analytics/hooks/useStreaks', () => ({
  useStreaks: (...args: unknown[]) => mockUseStreaks(...args),
}))
vi.mock('@/features/accounts/context/AccountContext', () => ({
  useAccount: () => mockUseAccount(),
}))
vi.mock('@/features/auth/context/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}))

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const ACCOUNT_ID = '00000000-0000-0000-0000-000000000001'

const MOCK_ACCOUNT = {
  id: ACCOUNT_ID,
  display_name: 'Main Account',
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

function makeError() {
  return { data: undefined, isLoading: false, isError: true }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderDashboard() {
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  )
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockUseAccount.mockReturnValue({
    selectedAccount: MOCK_ACCOUNT,
    accounts: [MOCK_ACCOUNT],
    isLoading: false,
    selectAccount: vi.fn(),
    refetchAccounts: vi.fn(),
  })
  mockUseDashboardSummary.mockReturnValue(makeIdle(DASHBOARD_SUMMARY))
  mockUseRecentTrades.mockReturnValue(makeIdle(TRADES_LIST.items))
  mockUseRecentJournal.mockReturnValue(makeIdle(JOURNAL_RECENT))
  mockUseAnalyticsSummary.mockReturnValue(makeIdle(ANALYTICS_SUMMARY_FIXTURE))
  mockUseStreaks.mockReturnValue(makeIdle(STREAKS_FIXTURE))
  mockUseAuth.mockReturnValue({
    user: { id: '99', email: 'trader@example.com' },
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
  })
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('DashboardPage', () => {
  it('F-18-01: renders the account display name from context', () => {
    renderDashboard()
    expect(screen.getByText('Main Account')).toBeInTheDocument()
  })

  it('F-18-02: renders all-time, MTD, and WTD P&L values', () => {
    renderDashboard()
    expect(screen.getByText('+₹27,500')).toBeInTheDocument()
    expect(screen.getByText('+₹5,000')).toBeInTheDocument()
    expect(screen.getByText('+₹1,500')).toBeInTheDocument()
  })

  it('F-18-03: renders Realized Equity label and formatted capital values', () => {
    renderDashboard()
    expect(screen.getByText('Realized Equity')).toBeInTheDocument()
    expect(screen.getByText('₹500,000')).toBeInTheDocument()
    expect(screen.getByText('₹527,500')).toBeInTheDocument()
  })

  it('F-18-04: hides Starting Capital and Realized Equity rows when values are null', () => {
    mockUseDashboardSummary.mockReturnValue(makeIdle(DASHBOARD_SUMMARY_EMPTY))
    renderDashboard()
    expect(screen.queryByText('Starting Capital')).not.toBeInTheDocument()
    expect(screen.queryByText('Realized Equity')).not.toBeInTheDocument()
  })

  it('F-18-05: renders win rate, expectancy, and profit factor from analytics summary', () => {
    renderDashboard()
    // win_rate: '0.67' → 67.0%
    expect(screen.getByText('67.0%')).toBeInTheDocument()
    // expectancy_r: '1.25'
    expect(screen.getByText('1.25')).toBeInTheDocument()
    // profit_factor: '3.14'
    expect(screen.getByText('3.14')).toBeInTheDocument()
  })

  it('F-18-06: renders the active loss streak value', () => {
    // STREAKS_FIXTURE: current_win_streak: 0, current_loss_streak: 2
    renderDashboard()
    expect(screen.getByText(/-2 losses/i)).toBeInTheDocument()
  })

  it('F-18-07: renders 10 trade rows in the Recent Trades section', () => {
    renderDashboard()
    const tradesSection = screen.getByRole('region', { name: 'Recent Trades' })
    const rows = tradesSection.querySelectorAll('tbody tr')
    expect(rows).toHaveLength(10)
  })

  it('F-18-08: each trade row contains a link to the trade detail page', () => {
    renderDashboard()
    const tradesSection = screen.getByRole('region', { name: 'Recent Trades' })
    const links = Array.from(tradesSection.querySelectorAll('tbody a'))
    expect(links).toHaveLength(10)
    links.forEach((link, i) => {
      expect(link).toHaveAttribute('href', `/trades/trade-${String(i + 1).padStart(3, '0')}`)
    })
  })

  it('F-18-09: shows empty state when trades list is empty', () => {
    mockUseRecentTrades.mockReturnValue(makeIdle(TRADES_LIST_EMPTY.items))
    renderDashboard()
    expect(screen.getByText('No closed trades yet.')).toBeInTheDocument()
  })

  it('F-18-10: renders 5 journal rows with discipline score and emotion', () => {
    renderDashboard()
    // discipline scores 7, 8, 9, 7, 8 (7 + i%3 for i=0..4)
    const scoreSection = screen.getByRole('region', { name: 'Recent Journal' })
    expect(scoreSection).toBeInTheDocument()
    const rows = scoreSection.querySelectorAll('tbody tr')
    expect(rows).toHaveLength(5)
    // first row: discipline_score: 7, emotion_before: 'CALM'
    expect(rows[0]).toHaveTextContent('7')
    expect(rows[0]).toHaveTextContent('CALM')
  })

  it('F-18-11: shows empty state when journal list is empty', () => {
    mockUseRecentJournal.mockReturnValue(makeIdle(JOURNAL_RECENT_EMPTY))
    renderDashboard()
    expect(screen.getByText('No journal entries yet.')).toBeInTheDocument()
  })

  it('F-18-12: calls useDashboardSummary with new account id after context update', () => {
    const { rerender } = renderDashboard()

    const NEW_ID = '00000000-0000-0000-0000-000000000002'
    mockUseAccount.mockReturnValue({
      selectedAccount: { ...MOCK_ACCOUNT, id: NEW_ID, display_name: 'Other Account' },
      accounts: [MOCK_ACCOUNT],
      isLoading: false,
      selectAccount: vi.fn(),
      refetchAccounts: vi.fn(),
    })

    rerender(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    )

    const calls = mockUseDashboardSummary.mock.calls
    const lastCall = calls[calls.length - 1]
    expect(lastCall[0]).toBe(NEW_ID)
  })

  it('F-18-13: Dashboard nav link has href /dashboard in AppShell', async () => {
    const { AppShell } = await import('@/layout/AppShell')

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route
            element={<AppShell />}
          >
            <Route path="/dashboard" element={<DashboardPage />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    const dashboardLink = screen.getByRole('link', { name: 'Dashboard' })
    expect(dashboardLink).toHaveAttribute('href', '/dashboard')
  })

  it('F-18-14: root path / redirects to /dashboard and renders DashboardPage', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
        </Routes>
      </MemoryRouter>,
    )

    // DashboardPage renders — account name is visible
    expect(screen.getByText('Main Account')).toBeInTheDocument()
  })

  it('F-18-15: renders loading skeleton with role=status while data is loading', () => {
    mockUseDashboardSummary.mockReturnValue(makeLoading())
    renderDashboard()
    expect(screen.getByRole('status', { name: 'Loading dashboard' })).toBeInTheDocument()
  })

  it('F-18-16: shows error alert in Account Overview when summary fetch fails', () => {
    mockUseDashboardSummary.mockReturnValue(makeError())
    renderDashboard()
    const overviewSection = screen.getByRole('region', { name: 'Account Overview' })
    expect(overviewSection.querySelector('[role="alert"]')).toBeInTheDocument()
    expect(overviewSection).toHaveTextContent('Failed to load account overview.')
  })

  it('F-18-17: shows error alert in Performance when analytics fetch fails', () => {
    mockUseAnalyticsSummary.mockReturnValue(makeError())
    renderDashboard()
    const perfSection = screen.getByRole('region', { name: 'Performance' })
    expect(perfSection.querySelector('[role="alert"]')).toBeInTheDocument()
    expect(perfSection).toHaveTextContent('Failed to load performance data.')
  })

  it('F-18-18: shows error alert in Streaks when streaks fetch fails', () => {
    mockUseStreaks.mockReturnValue(makeError())
    renderDashboard()
    const streaksSection = screen.getByRole('region', { name: 'Streaks' })
    expect(streaksSection.querySelector('[role="alert"]')).toBeInTheDocument()
    expect(streaksSection).toHaveTextContent('Failed to load streak data.')
  })

  it('F-18-19: shows error alert in Recent Trades when trades fetch fails', () => {
    mockUseRecentTrades.mockReturnValue(makeError())
    renderDashboard()
    const tradesSection = screen.getByRole('region', { name: 'Recent Trades' })
    expect(tradesSection.querySelector('[role="alert"]')).toBeInTheDocument()
    expect(tradesSection).toHaveTextContent('Failed to load recent trades.')
  })

  it('F-18-20: shows error alert in Recent Journal when journal fetch fails', () => {
    mockUseRecentJournal.mockReturnValue(makeError())
    renderDashboard()
    const journalSection = screen.getByRole('region', { name: 'Recent Journal' })
    expect(journalSection.querySelector('[role="alert"]')).toBeInTheDocument()
    expect(journalSection).toHaveTextContent('Failed to load recent journal entries.')
  })

  it('F-18-22: shows "No account selected" in all three sections when account loaded but selectedAccount is null', () => {
    mockUseAccount.mockReturnValue({
      selectedAccount: null,
      accounts: [],
      isLoading: false,
      selectAccount: vi.fn(),
      refetchAccounts: vi.fn(),
    })
    mockUseDashboardSummary.mockReturnValue({ data: undefined, isLoading: false, isError: false })
    mockUseRecentTrades.mockReturnValue({ data: undefined, isLoading: false, isError: false })
    mockUseRecentJournal.mockReturnValue({ data: undefined, isLoading: false, isError: false })

    renderDashboard()

    const overviewSection = screen.getByRole('region', { name: 'Account Overview' })
    const tradesSection = screen.getByRole('region', { name: 'Recent Trades' })
    const journalSection = screen.getByRole('region', { name: 'Recent Journal' })

    expect(overviewSection).toHaveTextContent('No account selected.')
    expect(tradesSection).toHaveTextContent('No account selected.')
    expect(journalSection).toHaveTextContent('No account selected.')
  })

  it('F-18-23: formatR does not throw when r_multiple is a Decimal string from the API', () => {
    const stringRMultiple = TRADES_LIST.items.map(t => ({ ...t, r_multiple: '1.50' }))
    mockUseRecentTrades.mockReturnValue({ data: stringRMultiple, isLoading: false, isError: false })

    expect(() => renderDashboard()).not.toThrow()

    const tradesSection = screen.getByRole('region', { name: 'Recent Trades' })
    expect(tradesSection).toHaveTextContent('+1.50R')
  })

  it('F-18-24: dashboard renders without crash when all summary fields are Decimal strings', () => {
    expect(() => renderDashboard()).not.toThrow()
    expect(screen.getByText('+₹27,500')).toBeInTheDocument()
  })

  it('F-18-21: shows loading skeletons in all three data sections while accounts are loading', () => {
    // Simulate AccountContext mid-load: no account selected yet
    mockUseAccount.mockReturnValue({
      selectedAccount: null,
      accounts: [],
      isLoading: true,
      selectAccount: vi.fn(),
      refetchAccounts: vi.fn(),
    })
    // Hooks return idle-with-no-data (queries disabled when accountId is '')
    mockUseDashboardSummary.mockReturnValue(makeLoading())
    mockUseRecentTrades.mockReturnValue(makeLoading())
    mockUseRecentJournal.mockReturnValue(makeLoading())

    renderDashboard()

    // Account Overview: role=status skeleton
    expect(screen.getByRole('status', { name: 'Loading dashboard' })).toBeInTheDocument()

    // Recent Trades: aria-busy skeleton
    const tradesSection = screen.getByRole('region', { name: 'Recent Trades' })
    expect(tradesSection.querySelector('[aria-busy="true"]')).toBeInTheDocument()

    // Recent Journal: aria-busy skeleton
    const journalSection = screen.getByRole('region', { name: 'Recent Journal' })
    expect(journalSection.querySelector('[aria-busy="true"]')).toBeInTheDocument()
  })
})
