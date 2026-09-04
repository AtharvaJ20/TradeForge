import { useTimeOfDay } from '../hooks/useTimeOfDay'
import type { AnalyticsFilterParams, TimeOfDay, TimeOfDayBucket } from '../types'
import { formatINRNullable } from '../formatters'

// ---------------------------------------------------------------------------
// Row display
// ---------------------------------------------------------------------------

function BucketRow({
  bucket,
  isBest,
}: {
  bucket: TimeOfDayBucket
  isBest: boolean
}) {
  const isEmpty = bucket.trade_count === 0

  const winRateDisplay = isEmpty ? '—' : `${parseFloat(bucket.win_rate).toFixed(1)}%`
  const expectancyDisplay = isEmpty ? '—' : formatINRNullable(bucket.expectancy_inr)

  return (
    <tr
      className={`border-b border-border last:border-0 ${isBest ? 'bg-success-subtle' : ''}`}
      aria-label={isBest ? `${bucket.label} — best session` : undefined}
    >
      <td className="py-2 font-medium text-text-primary">{bucket.label}</td>
      <td className="py-2 text-right tabular-nums text-text-primary">{bucket.trade_count}</td>
      <td className="py-2 text-right tabular-nums text-text-primary">{winRateDisplay}</td>
      <td className="py-2 text-right tabular-nums text-text-primary">{expectancyDisplay}</td>
      <td className="py-2 text-right tabular-nums text-text-primary">
        {formatINRNullable(bucket.total_net_pnl === '0' || bucket.total_net_pnl === '0.00'
          ? (isEmpty ? null : bucket.total_net_pnl)
          : bucket.total_net_pnl)}
      </td>
    </tr>
  )
}

// ---------------------------------------------------------------------------
// Table display (accepts already-fetched data)
// ---------------------------------------------------------------------------

function TimeOfDayTable({ data }: { data: TimeOfDay }) {
  const bestPnl = Math.max(...data.buckets.map(b => parseFloat(b.total_net_pnl)))
  const bestBucketKey = bestPnl > 0
    ? data.buckets.find(b => parseFloat(b.total_net_pnl) === bestPnl)?.bucket
    : null

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">Trade performance by NSE session band</caption>
        <thead>
          <tr className="border-b border-border">
            <th
              scope="col"
              className="pb-2 text-left text-xs font-semibold uppercase tracking-wider text-text-secondary"
            >
              Session
            </th>
            <th
              scope="col"
              className="pb-2 text-right text-xs font-semibold uppercase tracking-wider text-text-secondary"
            >
              Trades
            </th>
            <th
              scope="col"
              className="pb-2 text-right text-xs font-semibold uppercase tracking-wider text-text-secondary"
            >
              Win Rate
            </th>
            <th
              scope="col"
              className="pb-2 text-right text-xs font-semibold uppercase tracking-wider text-text-secondary"
            >
              Exp (₹)
            </th>
            <th
              scope="col"
              className="pb-2 text-right text-xs font-semibold uppercase tracking-wider text-text-secondary"
            >
              Total P&L
            </th>
          </tr>
        </thead>
        <tbody>
          {data.buckets.map(bucket => (
            <BucketRow
              key={bucket.bucket}
              bucket={bucket}
              isBest={bucket.bucket === bestBucketKey}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Public card (owns fetching)
// ---------------------------------------------------------------------------

export function TimeOfDayCard({ params = {} }: { params?: AnalyticsFilterParams }) {
  const { data, isLoading, isError } = useTimeOfDay(params)

  return (
    <section
      className="rounded-xl border border-border bg-surface-base p-5"
      aria-label="Time-of-day performance"
    >
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        Time-of-Day Performance
      </h2>

      {isLoading && (
        <div
          className="h-40 animate-pulse rounded-lg bg-surface-subtle"
          role="status"
          aria-label="Loading time-of-day performance"
        />
      )}

      {isError && !isLoading && (
        <p className="text-sm text-danger-emphasis">Failed to load time-of-day performance.</p>
      )}

      {data && !isLoading && <TimeOfDayTable data={data} />}
    </section>
  )
}
