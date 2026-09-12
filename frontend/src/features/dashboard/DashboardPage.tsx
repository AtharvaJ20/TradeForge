import { Link } from 'react-router-dom'
import { useAccount } from '@/features/accounts/context/AccountContext'
import { useAnalyticsSummary } from '@/features/analytics/hooks/useAnalyticsSummary'
import { useStreaks } from '@/features/analytics/hooks/useStreaks'
import { useDashboardSummary } from './hooks/useDashboardSummary'
import { useRecentTrades } from './hooks/useRecentTrades'
import { useRecentJournal } from './hooks/useRecentJournal'
import type { DashboardSummaryOut, TradeListItemOut, RecentJournalItemOut } from './types'

// ---------------------------------------------------------------------------
// Local formatting helpers
// ---------------------------------------------------------------------------

function thousands(n: number): string {
  return Math.round(Math.abs(n))
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

function formatPnl(value: number | string): string {
  const n = parseFloat(String(value))
  if (isNaN(n)) return '—'
  const abs = thousands(n)
  if (n > 0) return `+₹${abs}`
  if (n < 0) return `-₹${abs}`
  return '₹0'
}

function pnlClass(value: number | string): string {
  const n = parseFloat(String(value))
  if (n > 0) return 'text-success-emphasis'
  if (n < 0) return 'text-danger-emphasis'
  return 'text-text-primary'
}

function formatCapital(value: number | string): string {
  const n = parseFloat(String(value))
  return isNaN(n) ? '—' : `₹${thousands(n)}`
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return iso.slice(0, 10)
}

function formatR(value: number | string | null): string {
  if (value === null) return '—'
  const n = parseFloat(String(value))
  if (isNaN(n)) return '—'
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toFixed(2)}R`
}

function formatPct(value: string): string {
  const n = parseFloat(value)
  return isNaN(n) ? '—' : `${n.toFixed(2)}%`
}

function formatDecStr(value: string | null): string {
  if (value === null) return '—'
  return value
}

// ---------------------------------------------------------------------------
// Skeleton row
// ---------------------------------------------------------------------------

function SkeletonRow() {
  return (
    <div className="flex items-center gap-3 py-2">
      <div className="h-4 w-16 animate-pulse rounded bg-surface-subtle" />
      <div className="h-4 w-24 animate-pulse rounded bg-surface-subtle" />
      <div className="h-4 w-12 animate-pulse rounded bg-surface-subtle" />
      <div className="h-4 w-16 animate-pulse rounded bg-surface-subtle" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Section 1: Account Overview
// ---------------------------------------------------------------------------

function AccountOverviewContent({ data }: { data: DashboardSummaryOut }) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
      <div>
        <p className="text-xs uppercase tracking-wider text-text-secondary">All-time P&L</p>
        <p className={`text-2xl font-bold tabular-nums ${pnlClass(data.all_time_net_pnl)}`}>
          {formatPnl(data.all_time_net_pnl)}
        </p>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wider text-text-secondary">MTD P&L</p>
        <p className={`text-2xl font-bold tabular-nums ${pnlClass(data.mtd_net_pnl)}`}>
          {formatPnl(data.mtd_net_pnl)}
        </p>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wider text-text-secondary">WTD P&L</p>
        <p className={`text-2xl font-bold tabular-nums ${pnlClass(data.wtd_net_pnl)}`}>
          {formatPnl(data.wtd_net_pnl)}
        </p>
      </div>
      {data.starting_capital !== null && (
        <div>
          <p className="text-xs uppercase tracking-wider text-text-secondary">Starting Capital</p>
          <p className="text-xl font-semibold tabular-nums text-text-primary">
            {formatCapital(data.starting_capital)}
          </p>
        </div>
      )}
      {data.realized_equity !== null && (
        <div>
          <p className="text-xs uppercase tracking-wider text-text-secondary">Realized Equity</p>
          <p className="text-xl font-semibold tabular-nums text-text-primary">
            {formatCapital(data.realized_equity)}
          </p>
        </div>
      )}
      <div>
        <p className="text-xs uppercase tracking-wider text-text-secondary">Open Positions</p>
        <p className="text-xl font-semibold tabular-nums text-text-primary">
          {data.open_trade_count}
        </p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Section 2: Performance
// ---------------------------------------------------------------------------

interface AnalyticsSummary {
  outcome: { win_rate: string }
  expectancy: { expectancy_r: string; insufficient_sample: boolean }
  profit_factor: { profit_factor: string | null }
}

function PerformanceContent({ data }: { data: AnalyticsSummary }) {
  const expectancy =
    data.expectancy.insufficient_sample ? 'N/A' : formatDecStr(data.expectancy.expectancy_r)
  const pf = data.profit_factor.profit_factor ?? 'N/A'

  return (
    <div className="flex gap-6">
      <div>
        <p className="text-xs uppercase tracking-wider text-text-secondary">Win Rate</p>
        <p className="text-2xl font-bold tabular-nums text-text-primary">
          {formatPct(data.outcome.win_rate)}
        </p>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wider text-text-secondary">Expectancy</p>
        <p className="text-2xl font-bold tabular-nums text-text-primary">{expectancy}</p>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wider text-text-secondary">Profit Factor</p>
        <p className="text-2xl font-bold tabular-nums text-text-primary">{pf}</p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Section 3: Streaks
// ---------------------------------------------------------------------------

interface StreakData {
  current_win_streak: number
  current_loss_streak: number
}

function StreaksContent({ data }: { data: StreakData }) {
  const { current_win_streak, current_loss_streak } = data

  if (current_win_streak === 0 && current_loss_streak === 0) {
    return <p className="text-sm text-text-secondary">No active streak.</p>
  }

  if (current_win_streak > 0) {
    return (
      <p className="text-2xl font-bold tabular-nums text-success-emphasis">
        +{current_win_streak} wins
      </p>
    )
  }

  return (
    <p className="text-2xl font-bold tabular-nums text-danger-emphasis">
      -{current_loss_streak} losses
    </p>
  )
}

// ---------------------------------------------------------------------------
// Section 4: Recent Trades
// ---------------------------------------------------------------------------

function TradeRow({ trade }: { trade: TradeListItemOut }) {
  const dirClass =
    trade.direction === 'LONG' ? 'text-success-emphasis' : 'text-danger-emphasis'

  return (
    <tr className="border-b border-border last:border-0">
      <td className="py-2 pr-4 text-sm tabular-nums text-text-secondary">
        {formatDate(trade.last_fill_at)}
      </td>
      <td className="py-2 pr-4 text-sm font-medium text-text-primary">
        <Link to={`/trades/${trade.id}`} className="hover:underline">
          {trade.symbol}
        </Link>
      </td>
      <td className={`py-2 pr-4 text-sm font-medium ${dirClass}`}>{trade.direction}</td>
      <td
        className={`py-2 pr-4 text-sm tabular-nums ${trade.net_pnl !== null ? pnlClass(trade.net_pnl) : 'text-text-secondary'}`}
      >
        {trade.net_pnl !== null ? formatPnl(trade.net_pnl) : '—'}
      </td>
      <td className="py-2 text-sm tabular-nums text-text-secondary">{formatR(trade.r_multiple)}</td>
    </tr>
  )
}

// ---------------------------------------------------------------------------
// Section 5: Recent Journal
// ---------------------------------------------------------------------------

function JournalRow({ entry }: { entry: RecentJournalItemOut }) {
  const emotion = entry.emotion_before ?? entry.emotion_during ?? entry.emotion_after

  return (
    <tr className="border-b border-border last:border-0">
      <td className="py-2 pr-4 text-sm tabular-nums text-text-secondary">
        {formatDate(entry.trade_date)}
      </td>
      <td className="py-2 pr-4 text-sm font-medium text-text-primary">
        <Link to={`/journal/${entry.trade_id}`} className="hover:underline">
          {entry.symbol}
        </Link>
      </td>
      <td className="py-2 pr-4 text-sm tabular-nums text-text-primary">
        {entry.discipline_score ?? '—'}
      </td>
      {emotion && (
        <td className="py-2 text-sm text-text-secondary">{emotion}</td>
      )}
      {!emotion && <td className="py-2 text-sm text-text-secondary">—</td>}
    </tr>
  )
}

// ---------------------------------------------------------------------------
// Dashboard page
// ---------------------------------------------------------------------------

export function DashboardPage() {
  const { selectedAccount, isLoading: accountLoading } = useAccount()
  const accountId = selectedAccount?.id ?? ''
  const filterParams = accountId ? { account_ids: [accountId] } : {}

  const { data: summary, isLoading: summaryLoading, isError: summaryError } = useDashboardSummary(accountId)
  const { data: analytics, isError: analyticsError } = useAnalyticsSummary(filterParams)
  const { data: streakData, isError: streaksError } = useStreaks(filterParams)
  const { data: trades, isLoading: tradesLoading, isError: tradesError } = useRecentTrades(accountId)
  const { data: journal, isLoading: journalLoading, isError: journalError } = useRecentJournal(accountId)

  return (
    <div className="flex flex-col gap-6 p-6">
      <h1 className="text-xl font-semibold text-text-primary">
        {selectedAccount?.display_name ?? 'Dashboard'}
      </h1>

      {/* Section 1 — Account Overview */}
      <section
        aria-label="Account Overview"
        className="rounded-xl border border-border bg-surface-base p-5"
      >
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
          Account Overview
        </h2>
        {(summaryLoading || accountLoading) && (
          <div
            role="status"
            aria-label="Loading dashboard"
            className="space-y-2"
          >
            <div className="h-5 w-1/2 animate-pulse rounded bg-surface-subtle" />
            <div className="h-5 w-1/3 animate-pulse rounded bg-surface-subtle" />
            <div className="h-5 w-2/5 animate-pulse rounded bg-surface-subtle" />
          </div>
        )}
        {!accountLoading && !selectedAccount && (
          <p className="text-sm text-text-secondary">No account selected.</p>
        )}
        {summaryError && !summaryLoading && !accountLoading && selectedAccount && (
          <p role="alert" className="text-sm text-danger-emphasis">
            Failed to load account overview.
          </p>
        )}
        {summary && !summaryLoading && !accountLoading && selectedAccount && (
          <AccountOverviewContent data={summary} />
        )}
      </section>

      {/* Section 2 — Performance */}
      <section
        aria-label="Performance"
        className="rounded-xl border border-border bg-surface-base p-5"
      >
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
          Performance
        </h2>
        {analytics && <PerformanceContent data={analytics as AnalyticsSummary} />}
        {analyticsError && !analytics && (
          <p role="alert" className="text-sm text-danger-emphasis">
            Failed to load performance data.
          </p>
        )}
        {!analytics && !analyticsError && (
          <div className="h-10 w-2/3 animate-pulse rounded bg-surface-subtle" />
        )}
      </section>

      {/* Section 3 — Streaks */}
      <section
        aria-label="Streaks"
        className="rounded-xl border border-border bg-surface-base p-5"
      >
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
          Streaks
        </h2>
        {streakData && <StreaksContent data={streakData} />}
        {streaksError && !streakData && (
          <p role="alert" className="text-sm text-danger-emphasis">
            Failed to load streak data.
          </p>
        )}
        {!streakData && !streaksError && (
          <div className="h-8 w-1/4 animate-pulse rounded bg-surface-subtle" />
        )}
      </section>

      {/* Section 4 — Recent Trades */}
      <section
        aria-label="Recent Trades"
        className="rounded-xl border border-border bg-surface-base p-5"
      >
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
          Recent Trades
        </h2>
        {(tradesLoading || accountLoading) && (
          <div aria-busy="true" className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <SkeletonRow key={i} />
            ))}
          </div>
        )}
        {!accountLoading && !selectedAccount && (
          <p className="text-sm text-text-secondary">No account selected.</p>
        )}
        {tradesError && !tradesLoading && !accountLoading && selectedAccount && (
          <p role="alert" className="text-sm text-danger-emphasis">
            Failed to load recent trades.
          </p>
        )}
        {!tradesLoading && !tradesError && !accountLoading && selectedAccount && trades !== undefined && trades.length === 0 && (
          <p className="text-sm text-text-secondary">No closed trades yet.</p>
        )}
        {!tradesLoading && !tradesError && !accountLoading && selectedAccount && trades && trades.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-border">
                  <th className="pb-2 pr-4 text-xs uppercase tracking-wider text-text-secondary">
                    Date
                  </th>
                  <th className="pb-2 pr-4 text-xs uppercase tracking-wider text-text-secondary">
                    Symbol
                  </th>
                  <th className="pb-2 pr-4 text-xs uppercase tracking-wider text-text-secondary">
                    Dir
                  </th>
                  <th className="pb-2 pr-4 text-xs uppercase tracking-wider text-text-secondary">
                    P&L
                  </th>
                  <th className="pb-2 text-xs uppercase tracking-wider text-text-secondary">R</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((trade) => (
                  <TradeRow key={trade.id} trade={trade} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Section 5 — Recent Journal */}
      <section
        aria-label="Recent Journal"
        className="rounded-xl border border-border bg-surface-base p-5"
      >
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
          Recent Journal
        </h2>
        {(journalLoading || accountLoading) && (
          <div aria-busy="true" className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <SkeletonRow key={i} />
            ))}
          </div>
        )}
        {!accountLoading && !selectedAccount && (
          <p className="text-sm text-text-secondary">No account selected.</p>
        )}
        {journalError && !journalLoading && !accountLoading && selectedAccount && (
          <p role="alert" className="text-sm text-danger-emphasis">
            Failed to load recent journal entries.
          </p>
        )}
        {!journalLoading && !journalError && !accountLoading && selectedAccount && journal !== undefined && journal.length === 0 && (
          <p className="text-sm text-text-secondary">No journal entries yet.</p>
        )}
        {!journalLoading && !journalError && !accountLoading && selectedAccount && journal && journal.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-border">
                  <th className="pb-2 pr-4 text-xs uppercase tracking-wider text-text-secondary">
                    Date
                  </th>
                  <th className="pb-2 pr-4 text-xs uppercase tracking-wider text-text-secondary">
                    Symbol
                  </th>
                  <th className="pb-2 pr-4 text-xs uppercase tracking-wider text-text-secondary">
                    Score
                  </th>
                  <th className="pb-2 text-xs uppercase tracking-wider text-text-secondary">
                    Emotion
                  </th>
                </tr>
              </thead>
              <tbody>
                {journal.map((entry) => (
                  <JournalRow key={entry.trade_id} entry={entry} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
