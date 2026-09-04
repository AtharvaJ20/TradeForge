import { useHoldDuration } from '../hooks/useHoldDuration'
import type { AnalyticsFilterParams, HoldDuration } from '../types'
import { formatINR, formatPctFraction } from '../formatters'

// ---------------------------------------------------------------------------
// Display (pure)
// ---------------------------------------------------------------------------

function HoldDurationDisplay({ data }: { data: HoldDuration }) {
  if (data.buckets.length === 0) {
    return <p className="text-sm text-text-secondary">No closed trades yet.</p>
  }

  const sorted = [...data.buckets].sort((a, b) => a.bucket_order - b.bucket_order)

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-text-secondary">
              <th scope="col" className="pb-2 pr-4 font-semibold">Duration</th>
              <th scope="col" className="pb-2 pr-4 text-right font-semibold">N</th>
              <th scope="col" className="pb-2 pr-4 text-right font-semibold">Win rate</th>
              <th scope="col" className="pb-2 text-right font-semibold">Avg net P&amp;L</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(row => (
              <tr key={row.bucket} className="border-b border-border/50 last:border-0">
                <td className="py-2 pr-4 text-text-primary">{row.bucket}</td>
                <td className="py-2 pr-4 text-right tabular-nums text-text-primary">
                  {row.count}
                </td>
                <td className="py-2 pr-4 text-right tabular-nums text-text-primary">
                  {formatPctFraction(row.win_rate)}
                </td>
                <td className={`py-2 text-right tabular-nums ${
                  parseFloat(row.avg_net_pnl) >= 0 ? 'text-success-emphasis' : 'text-danger-emphasis'
                }`}>
                  {formatINR(row.avg_net_pnl)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.avg_duration_minutes !== null && (
        <p className="mt-3 text-xs text-text-secondary">
          Avg hold:{' '}
          <span className="font-medium text-text-primary">
            {parseFloat(data.avg_duration_minutes).toFixed(0)} min
          </span>
          {data.median_duration_minutes !== null && (
            <>
              {' '}· Median:{' '}
              <span className="font-medium text-text-primary">
                {parseFloat(data.median_duration_minutes).toFixed(0)} min
              </span>
            </>
          )}
        </p>
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// Public card (owns fetching)
// ---------------------------------------------------------------------------

export function HoldDurationCard({ params = {} }: { params?: AnalyticsFilterParams }) {
  const { data, isLoading, isError } = useHoldDuration(params)

  return (
    <section
      className="rounded-xl border border-border bg-surface-base p-5"
      aria-label="Hold duration distribution"
    >
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        Hold Duration
      </h2>

      {isLoading && (
        <div
          className="h-24 animate-pulse rounded-lg bg-surface-subtle"
          role="status"
          aria-label="Loading hold duration"
        />
      )}

      {isError && !isLoading && (
        <p className="text-sm text-danger-emphasis">Failed to load hold duration data.</p>
      )}

      {data && !isLoading && <HoldDurationDisplay data={data} />}
    </section>
  )
}
