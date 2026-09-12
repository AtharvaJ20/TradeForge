import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAccount } from '@/features/accounts/context/AccountContext'
import { tradesApi } from './api'
import type { TradeListItemOut } from './types'

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' })
}

function formatPnl(value: number | string): string {
  const n = parseFloat(String(value))
  if (isNaN(n)) return '—'
  const abs = Math.round(Math.abs(n)).toLocaleString('en-IN')
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

// ---------------------------------------------------------------------------
// Sort types
// ---------------------------------------------------------------------------

type SortColumn = 'trade_date' | 'net_pnl' | 'r_multiple'
type SortDir = 'asc' | 'desc'

// ---------------------------------------------------------------------------
// Skeleton row
// ---------------------------------------------------------------------------

function SkeletonTableRow() {
  return (
    <tr>
      {Array.from({ length: 7 }).map((_, i) => (
        <td key={i} className="px-3 py-3">
          <div className="h-4 animate-pulse rounded bg-surface-subtle" />
        </td>
      ))}
    </tr>
  )
}

// ---------------------------------------------------------------------------
// Chip components
// ---------------------------------------------------------------------------

function DirectionChip({ direction }: { direction: string }) {
  const cls =
    direction === 'LONG'
      ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
      : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${cls}`}>
      {direction === 'LONG' ? 'Long' : 'Short'}
    </span>
  )
}

function StatusChip({ status }: { status: string }) {
  const map: Record<string, string> = {
    OPEN: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
    PARTIAL: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
    CLOSED: 'bg-surface-subtle text-text-secondary',
  }
  const cls = map[status] ?? 'bg-surface-subtle text-text-secondary'
  const label = status.charAt(0) + status.slice(1).toLowerCase()
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${cls}`}>
      {label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Trade row
// ---------------------------------------------------------------------------

function TradeRow({ trade, onClick }: { trade: TradeListItemOut; onClick: () => void }) {
  return (
    <tr
      className="cursor-pointer border-b border-border hover:bg-surface-subtle"
      onClick={onClick}
    >
      <td className="px-3 py-3 text-sm tabular-nums text-text-secondary">
        {formatDate(trade.trade_date)}
      </td>
      <td className="px-3 py-3 text-sm font-medium text-text-primary">{trade.symbol}</td>
      <td className="px-3 py-3 text-sm text-text-secondary">{trade.instrument_type}</td>
      <td className="px-3 py-3">
        <DirectionChip direction={trade.direction} />
      </td>
      <td className="px-3 py-3">
        <StatusChip status={trade.status} />
      </td>
      <td
        className={`px-3 py-3 text-sm tabular-nums ${trade.net_pnl !== null ? pnlClass(trade.net_pnl) : 'text-text-secondary'}`}
      >
        {trade.net_pnl !== null ? formatPnl(trade.net_pnl) : '—'}
      </td>
      <td className="px-3 py-3 text-sm tabular-nums text-text-secondary">
        {trade.r_multiple !== null ? `${parseFloat(String(trade.r_multiple)).toFixed(2)}R` : '—'}
      </td>
    </tr>
  )
}

// ---------------------------------------------------------------------------
// Sort header cell
// ---------------------------------------------------------------------------

function SortHeader({
  label,
  column,
  activeCol,
  activeDir,
  onSort,
}: {
  label: string
  column: SortColumn
  activeCol: SortColumn | null
  activeDir: SortDir
  onSort: (col: SortColumn) => void
}) {
  const isActive = activeCol === column
  return (
    <th
      className="cursor-pointer select-none px-3 pb-2 text-left text-xs uppercase tracking-wider text-text-secondary hover:text-text-primary"
      onClick={() => onSort(column)}
    >
      {label}
      {isActive && (
        <span className="ml-1" aria-label={activeDir === 'asc' ? 'ascending' : 'descending'}>
          {activeDir === 'asc' ? '↑' : '↓'}
        </span>
      )}
    </th>
  )
}

// ---------------------------------------------------------------------------
// TradeListPage
// ---------------------------------------------------------------------------

const PAGE_SIZE = 25

const TRADE_TYPE_OPTIONS = [
  { label: 'All', value: '' },
  { label: 'MIS', value: 'MIS' },
  { label: 'CNC (Delivery)', value: 'CNC' },
  { label: 'CNC (Intraday)', value: 'CNC_SAME_DAY' },
  { label: 'Futures', value: 'NRML_FUT' },
  { label: 'Options', value: 'NRML_OPT' },
]

export function TradeListPage() {
  const navigate = useNavigate()
  const { selectedAccount } = useAccount()
  const accountId = selectedAccount?.id ?? ''

  // Filter state
  const [status, setStatus] = useState('')
  const [direction, setDirection] = useState('')
  const [tradeType, setTradeType] = useState('')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [instrumentInput, setInstrumentInput] = useState('')
  const [instrument, setInstrument] = useState('')

  // Sort state
  const [sortCol, setSortCol] = useState<SortColumn | null>(null)
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  // Pagination
  const [offset, setOffset] = useState(0)

  // Debounce instrument
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setInstrument(instrumentInput), 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [instrumentInput])

  // Reset offset when filters change
  useEffect(() => {
    setOffset(0)
  }, [status, direction, tradeType, fromDate, toDate, instrument])

  const hasFilters =
    !!status || !!direction || !!tradeType || !!fromDate || !!toDate || !!instrumentInput

  function clearFilters() {
    setStatus('')
    setDirection('')
    setTradeType('')
    setFromDate('')
    setToDate('')
    setInstrumentInput('')
    setInstrument('')
    setOffset(0)
  }

  function handleSort(col: SortColumn) {
    if (sortCol !== col) {
      setSortCol(col)
      setSortDir('desc')
    } else if (sortDir === 'desc') {
      setSortDir('asc')
    } else {
      setSortCol(null)
      setSortDir('desc')
    }
  }

  const queryParams = {
    ...(accountId && { account_id: accountId }),
    ...(status && { status }),
    ...(direction && { direction }),
    ...(tradeType && { trade_type: tradeType }),
    ...(fromDate && { from_date: fromDate }),
    ...(toDate && { to_date: toDate }),
    ...(instrument && { instrument }),
    limit: PAGE_SIZE,
    offset,
    sort_by: sortCol ?? 'last_fill_at',
    sort_dir: sortDir,
  }

  const { data, isLoading, isError } = useQuery({
    queryKey: ['trades', 'list', queryParams],
    queryFn: () => tradesApi.listTrades(queryParams),
    enabled: true,
  })

  const items = data?.items ?? []
  const total = data?.total ?? 0
  const showing = {
    from: total === 0 ? 0 : offset + 1,
    to: Math.min(offset + PAGE_SIZE, total),
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-xl font-semibold text-text-primary">Trades</h1>

      {/* Filter bar */}
      <section aria-label="Trade filters" className="rounded-xl border border-border bg-surface-base p-4">
        <div className="flex flex-wrap gap-4">
          {/* Status tabs */}
          <div className="flex gap-1 rounded-lg border border-border p-0.5">
            {['', 'OPEN', 'PARTIAL', 'CLOSED'].map((s) => (
              <button
                key={s}
                onClick={() => setStatus(s)}
                className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
                  status === s
                    ? 'bg-accent text-white'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                {s === '' ? 'All' : s.charAt(0) + s.slice(1).toLowerCase()}
              </button>
            ))}
          </div>

          {/* Direction */}
          <select
            aria-label="Direction filter"
            value={direction}
            onChange={(e) => setDirection(e.target.value)}
            className="rounded-md border border-border bg-surface-base px-3 py-1.5 text-sm text-text-primary"
          >
            <option value="">All directions</option>
            <option value="LONG">Long</option>
            <option value="SHORT">Short</option>
          </select>

          {/* Trade type */}
          <select
            aria-label="Trade type filter"
            value={tradeType}
            onChange={(e) => setTradeType(e.target.value)}
            className="rounded-md border border-border bg-surface-base px-3 py-1.5 text-sm text-text-primary"
          >
            {TRADE_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>

          {/* Date range */}
          <div className="flex items-center gap-2">
            <input
              type="date"
              aria-label="From date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="rounded-md border border-border bg-surface-base px-3 py-1.5 text-sm text-text-primary"
            />
            <span className="text-sm text-text-secondary">to</span>
            <input
              type="date"
              aria-label="To date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="rounded-md border border-border bg-surface-base px-3 py-1.5 text-sm text-text-primary"
            />
          </div>

          {/* Instrument search */}
          <input
            type="text"
            aria-label="Instrument search"
            placeholder="Search symbol…"
            value={instrumentInput}
            onChange={(e) => setInstrumentInput(e.target.value)}
            className="rounded-md border border-border bg-surface-base px-3 py-1.5 text-sm text-text-primary placeholder:text-text-secondary"
          />

          {/* Clear filters */}
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary hover:text-text-primary"
            >
              Clear filters
            </button>
          )}
        </div>
      </section>

      {/* Table */}
      <section aria-label="Trade list" className="rounded-xl border border-border bg-surface-base">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-border">
                <SortHeader label="Date" column="trade_date" activeCol={sortCol} activeDir={sortDir} onSort={handleSort} />
                <th className="px-3 pb-2 text-left text-xs uppercase tracking-wider text-text-secondary">Symbol</th>
                <th className="px-3 pb-2 text-left text-xs uppercase tracking-wider text-text-secondary">Type</th>
                <th className="px-3 pb-2 text-left text-xs uppercase tracking-wider text-text-secondary">Direction</th>
                <th className="px-3 pb-2 text-left text-xs uppercase tracking-wider text-text-secondary">Status</th>
                <SortHeader label="Net P&L" column="net_pnl" activeCol={sortCol} activeDir={sortDir} onSort={handleSort} />
                <SortHeader label="R-multiple" column="r_multiple" activeCol={sortCol} activeDir={sortDir} onSort={handleSort} />
              </tr>
            </thead>
            <tbody>
              {isLoading &&
                Array.from({ length: 5 }).map((_, i) => <SkeletonTableRow key={i} />)}
              {!isLoading && isError && (
                <tr>
                  <td colSpan={7} className="px-3 py-6 text-center text-sm text-danger-emphasis">
                    Failed to load trades. Please try again.
                  </td>
                </tr>
              )}
              {!isLoading && !isError && items.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-3 py-8 text-center text-sm text-text-secondary">
                    No trades found. Try adjusting your filters.
                  </td>
                </tr>
              )}
              {!isLoading &&
                !isError &&
                items.map((trade) => (
                  <TradeRow
                    key={trade.id}
                    trade={trade}
                    onClick={() => navigate(`/trades/${trade.id}`)}
                  />
                ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {!isLoading && !isError && (
          <div className="flex items-center justify-between border-t border-border px-4 py-3">
            <p className="text-sm text-text-secondary">
              {total === 0
                ? 'No trades'
                : `Showing ${showing.from}–${showing.to} of ${total} trades`}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                disabled={offset === 0}
                className="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary disabled:opacity-40"
              >
                Previous
              </button>
              <button
                onClick={() => setOffset(offset + PAGE_SIZE)}
                disabled={offset + PAGE_SIZE >= total}
                className="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
