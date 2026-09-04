import { useKelly } from '../hooks/useKelly'
import type { AnalyticsFilterParams, Kelly } from '../types'

// ---------------------------------------------------------------------------
// Format a decimal fraction (e.g. "0.3142") as a percentage string ("31.4%")
// Returns "—" for null or unparseable values.
// ---------------------------------------------------------------------------

function formatKellyPct(value: string | null): string {
  if (value === null) return '—'
  const num = parseFloat(value)
  if (isNaN(num)) return '—'
  return `${(num * 100).toFixed(1)}%`
}

// ---------------------------------------------------------------------------
// Display (accepts already-fetched data)
// ---------------------------------------------------------------------------

function KellyDisplay({ data }: { data: Kelly }) {
  return (
    <div className="space-y-4">
      <div className="flex gap-8">
        <div className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Full Kelly
          </p>
          <p className="text-3xl font-bold tabular-nums text-text-primary">
            {formatKellyPct(data.kelly_pct)}
          </p>
        </div>
        <div className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Half-Kelly
          </p>
          <p className="text-3xl font-bold tabular-nums text-text-primary">
            {formatKellyPct(data.half_kelly_pct)}
          </p>
        </div>
      </div>
      <p className="text-xs text-text-secondary">
        Half-Kelly is the recommended starting point. Full Kelly maximises long-run growth but
        risks steep drawdowns.
      </p>
      <p className="text-xs text-text-secondary">
        Based on {data.trades_with_r} trades with a valid R-multiple.
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Public card (owns fetching)
// ---------------------------------------------------------------------------

export function KellyCard({ params = {} }: { params?: AnalyticsFilterParams }) {
  const { data, isLoading, isError } = useKelly(params)

  return (
    <section
      className="rounded-xl border border-border bg-surface-base p-5"
      aria-label="Kelly fraction"
    >
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        Kelly Fraction
      </h2>

      {isLoading && (
        <div
          className="h-24 animate-pulse rounded-lg bg-surface-subtle"
          role="status"
          aria-label="Loading Kelly fraction"
        />
      )}

      {isError && !isLoading && (
        <p className="text-sm text-danger-emphasis">Failed to load Kelly fraction.</p>
      )}

      {data && !isLoading && data.insufficient_sample && (
        <p className="text-sm text-text-secondary" role="note">
          Needs 30+ trades with a planned stop to calculate.
        </p>
      )}

      {data && !isLoading && !data.insufficient_sample && <KellyDisplay data={data} />}
    </section>
  )
}
