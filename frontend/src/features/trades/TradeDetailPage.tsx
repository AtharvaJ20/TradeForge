import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { JournalPanel } from '@/features/journal/components/JournalPanel'
import { tradesApi } from './api'
import { toTradeForJournal } from './adapters'
import { EXCHANGE_SEGMENT_LABELS } from './constants'
import type { TradeDetailOut, PnlBreakdownOut } from './types'

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  return iso.slice(0, 10)
}

function formatTs(iso: string): string {
  return new Date(iso).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })
}

function formatPnl(value: string): string {
  const n = parseFloat(value)
  const abs = Math.round(Math.abs(n)).toLocaleString('en-IN')
  if (n > 0) return `+₹${abs}`
  if (n < 0) return `-₹${abs}`
  return '₹0'
}

function pnlClass(value: string): string {
  const n = parseFloat(value)
  if (n > 0) return 'text-success-emphasis'
  if (n < 0) return 'text-danger-emphasis'
  return 'text-text-primary'
}

function formatHoldDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const days = Math.floor(hours / 24)
  const remHours = hours % 24
  if (days > 0) return `${days}d ${remHours}h`
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

function formatExchangeSegment(raw: string): string {
  return EXCHANGE_SEGMENT_LABELS[raw] ?? `?${raw}`
}

// ---------------------------------------------------------------------------
// Chips
// ---------------------------------------------------------------------------

function DirectionChip({ direction }: { direction: string }) {
  const cls =
    direction === 'LONG'
      ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
      : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-sm font-medium ${cls}`}>
      {direction === 'LONG' ? 'Long' : 'Short'}
    </span>
  )
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    OPEN: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
    PARTIAL: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
    CLOSED: 'bg-surface-subtle text-text-secondary',
  }
  const cls = map[status] ?? 'bg-surface-subtle text-text-secondary'
  const label = status.charAt(0) + status.slice(1).toLowerCase()
  return (
    <span className={`inline-block rounded-full px-3 py-0.5 text-sm font-medium ${cls}`}>
      {label}
    </span>
  )
}

function SideChip({ side }: { side: string }) {
  const cls =
    side === 'BUY'
      ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
      : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${cls}`}>{side}</span>
  )
}

function RoleChip({ role }: { role: string | null }) {
  if (!role) return <span className="text-text-secondary">—</span>
  const cls =
    role === 'ENTRY'
      ? 'bg-surface-subtle text-text-primary'
      : 'bg-surface-subtle text-text-secondary'
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${cls}`}>{role}</span>
  )
}

function SourceChip({ source }: { source: string }) {
  return (
    <span className="inline-block rounded px-1.5 py-0.5 text-xs font-medium bg-surface-subtle text-text-secondary">
      {source === 'CSV' ? 'CSV' : 'Manual'}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Section 1 — Trade Summary
// ---------------------------------------------------------------------------

function TradeSummary({ trade }: { trade: TradeDetailOut }) {
  const holdLabel =
    trade.status === 'CLOSED'
      ? 'Hold duration'
      : trade.status === 'PARTIAL'
        ? 'Elapsed'
        : null

  const holdValue =
    trade.hold_duration_seconds !== null
      ? formatHoldDuration(trade.hold_duration_seconds)
      : 'Open'

  const quantity =
    trade.status === 'OPEN' || trade.total_exit_quantity === '0'
      ? `${trade.total_entry_quantity} entered`
      : `${trade.total_entry_quantity} entered / ${trade.total_exit_quantity} exited`

  return (
    <section
      aria-label="Trade Summary"
      className="rounded-xl border border-border bg-surface-base p-5"
    >
      <div className="mb-4 flex flex-wrap items-start gap-3">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">{trade.symbol}</h2>
          {trade.instrument_name && (
            <p className="text-sm text-text-secondary">{trade.instrument_name}</p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <DirectionChip direction={trade.direction} />
          <StatusBadge status={trade.status} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-text-secondary">Exchange</p>
          <p className="text-sm font-medium text-text-primary">
            {formatExchangeSegment(trade.exchange_segment)}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wider text-text-secondary">Trade date</p>
          <p className="text-sm font-medium text-text-primary">{formatDate(trade.trade_date)}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wider text-text-secondary">Quantity</p>
          <p className="text-sm font-medium text-text-primary">{quantity}</p>
        </div>
        {holdLabel ? (
          <div>
            <p className="text-xs uppercase tracking-wider text-text-secondary">{holdLabel}</p>
            <p className="text-sm font-medium text-text-primary">{holdValue}</p>
          </div>
        ) : (
          <div>
            <p className="text-xs uppercase tracking-wider text-text-secondary">Hold</p>
            <p className="text-sm font-medium text-text-primary">{holdValue}</p>
          </div>
        )}
        {trade.average_entry && (
          <div>
            <p className="text-xs uppercase tracking-wider text-text-secondary">Avg entry</p>
            <p className="text-sm font-medium tabular-nums text-text-primary">
              ₹{trade.average_entry}
            </p>
          </div>
        )}
        {trade.average_exit && (
          <div>
            <p className="text-xs uppercase tracking-wider text-text-secondary">Avg exit</p>
            <p className="text-sm font-medium tabular-nums text-text-primary">
              ₹{trade.average_exit}
            </p>
          </div>
        )}
        {trade.setup_name && (
          <div>
            <p className="text-xs uppercase tracking-wider text-text-secondary">Setup</p>
            <p className="text-sm font-medium text-text-primary">{trade.setup_name}</p>
          </div>
        )}
        {trade.planned_stop && (
          <div>
            <p className="text-xs uppercase tracking-wider text-text-secondary">Planned stop</p>
            <p className="text-sm font-medium tabular-nums text-text-primary">
              ₹{trade.planned_stop}
            </p>
          </div>
        )}
        {trade.planned_target && (
          <div>
            <p className="text-xs uppercase tracking-wider text-text-secondary">Planned target</p>
            <p className="text-sm font-medium tabular-nums text-text-primary">
              ₹{trade.planned_target}
            </p>
          </div>
        )}
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Section 2 — Execution Timeline
// ---------------------------------------------------------------------------

function ExecutionTimeline({ trade }: { trade: TradeDetailOut }) {
  return (
    <section
      aria-label="Execution Timeline"
      className="rounded-xl border border-border bg-surface-base p-5"
    >
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        Execution Timeline
      </h2>
      {trade.fills.length === 0 ? (
        <p className="text-sm text-text-secondary">No fill data available.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-border">
                {['Timestamp', 'Side', 'Role', 'Quantity', 'Price', 'Broker', 'Source'].map((h) => (
                  <th
                    key={h}
                    className="pb-2 pr-4 text-xs uppercase tracking-wider text-text-secondary"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trade.fills.map((fill) => (
                <tr key={fill.id} className="border-b border-border last:border-0">
                  <td className="py-2 pr-4 text-sm tabular-nums text-text-secondary">
                    {formatTs(fill.fill_timestamp)}
                  </td>
                  <td className="py-2 pr-4">
                    <SideChip side={fill.side} />
                  </td>
                  <td className="py-2 pr-4">
                    <RoleChip role={fill.fill_role} />
                  </td>
                  <td className="py-2 pr-4 text-sm tabular-nums text-text-primary">
                    {fill.quantity}
                  </td>
                  <td className="py-2 pr-4 text-sm tabular-nums text-text-primary">
                    ₹{fill.price}
                  </td>
                  <td className="py-2 pr-4 text-sm text-text-secondary">{fill.broker}</td>
                  <td className="py-2">
                    <SourceChip source={fill.import_source} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Section 3 — P&L Breakdown
// ---------------------------------------------------------------------------

function PnlRow({ label, value, bold }: { label: string; value: string; bold?: boolean }) {
  const cls = bold ? 'font-semibold' : ''
  return (
    <div className={`flex justify-between py-1.5 ${cls}`}>
      <span className="text-sm text-text-secondary">{label}</span>
      <span className={`text-sm tabular-nums text-text-primary ${bold ? 'font-semibold' : ''}`}>
        {formatPnl(value)}
      </span>
    </div>
  )
}

function PnlBreakdownSection({ trade }: { trade: TradeDetailOut }) {
  const isOpen = trade.status === 'OPEN'
  const isPartial = trade.status === 'PARTIAL'

  if (isOpen || isPartial) {
    const message = isOpen
      ? 'No exits yet — P&L will be available when the trade closes.'
      : 'Partially closed — final P&L will be calculated when all positions are exited.'
    return (
      <section
        aria-label="P&L Breakdown"
        className="rounded-xl border border-border bg-surface-base p-5"
      >
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-text-secondary">
          P&L Breakdown
        </h2>
        <p className="text-sm text-text-secondary">{message}</p>
      </section>
    )
  }

  if (!trade.pnl) return null

  const pnl: PnlBreakdownOut = trade.pnl
  return (
    <section
      aria-label="P&L Breakdown"
      className="rounded-xl border border-border bg-surface-base p-5"
    >
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        P&L Breakdown
      </h2>
      <div className="divide-y divide-border">
        <PnlRow label="Gross P&L" value={pnl.gross_pnl} />
        <PnlRow label="Brokerage" value={pnl.brokerage} />
        <PnlRow label="STT" value={pnl.stt} />
        <PnlRow label="Exchange charges" value={pnl.exchange_charges} />
        <PnlRow label="SEBI charges" value={pnl.sebi_charges} />
        <PnlRow label="Stamp duty" value={pnl.stamp_duty} />
        <PnlRow label="GST" value={pnl.gst} />
        <PnlRow label="IPFT" value={pnl.ipft} />
        <PnlRow label="Total charges" value={pnl.total_charges} bold />
        <div className={`flex justify-between py-1.5 font-semibold`}>
          <span className="text-sm text-text-secondary">Net P&L</span>
          <span className={`text-sm tabular-nums font-semibold ${pnlClass(pnl.net_pnl)}`}>
            {formatPnl(pnl.net_pnl)}
          </span>
        </div>
        <div className="flex justify-between py-1.5">
          <span className="text-sm text-text-secondary">R-multiple</span>
          <span className="text-sm tabular-nums text-text-primary">
            {pnl.r_multiple !== null ? `${parseFloat(pnl.r_multiple).toFixed(2)}R` : '—'}
          </span>
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function TradeDetailSkeleton() {
  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="h-6 w-24 animate-pulse rounded bg-surface-subtle" />
      <div className="rounded-xl border border-border bg-surface-base p-5">
        <div className="h-8 w-40 animate-pulse rounded bg-surface-subtle" />
        <div className="mt-4 grid grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-10 animate-pulse rounded bg-surface-subtle" />
          ))}
        </div>
      </div>
      <div className="h-40 animate-pulse rounded-xl bg-surface-subtle" />
      <div className="h-48 animate-pulse rounded-xl bg-surface-subtle" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// TradeDetailPage
// ---------------------------------------------------------------------------

export function TradeDetailPage() {
  const { tradeId } = useParams<{ tradeId: string }>()

  const { data: trade, isLoading, isError } = useQuery({
    queryKey: ['trades', 'detail', tradeId],
    queryFn: () => tradesApi.getTradeDetail(tradeId!),
    enabled: !!tradeId,
    retry: (failureCount, error) => {
      if ((error as { status?: number })?.status === 404) return false
      return failureCount < 2
    },
  })

  if (isLoading) return <TradeDetailSkeleton />

  if (isError || !trade) {
    return (
      <div className="flex flex-col gap-4 p-6">
        <Link to="/trades" className="text-sm text-text-secondary hover:text-text-primary">
          ← Back to trades
        </Link>
        <div className="rounded-xl border border-border bg-surface-base p-8 text-center">
          <p className="text-sm text-danger-emphasis">Trade not found.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <Link to="/trades" className="text-sm text-text-secondary hover:text-text-primary">
        ← Back to trades
      </Link>

      <TradeSummary trade={trade} />
      <ExecutionTimeline trade={trade} />
      <PnlBreakdownSection trade={trade} />

      <section
        aria-label="Journal"
        className="rounded-xl border border-border bg-surface-base p-5"
      >
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
          Journal
        </h2>
        <JournalPanel trade={toTradeForJournal(trade)} />
      </section>
    </div>
  )
}
