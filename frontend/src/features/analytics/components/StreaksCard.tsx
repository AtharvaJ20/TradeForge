import { useStreaks } from '../hooks/useStreaks'
import type { AnalyticsFilterParams, Streaks } from '../types'
import { formatDecimal } from '../formatters'

// ---------------------------------------------------------------------------
// Pure display sub-component (accepts already-fetched data)
// ---------------------------------------------------------------------------

interface StatTileProps {
  label: string
  value: string | number
  className?: string
}

function StatTile({ label, value, className = '' }: StatTileProps) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs uppercase tracking-wider text-text-secondary">{label}</span>
      <span className={`text-2xl font-bold tabular-nums ${className}`}>{value}</span>
    </div>
  )
}

function currentStreakDisplay(data: Streaks): { value: string; className: string } {
  if (data.current_win_streak > 0) {
    return { value: `+${data.current_win_streak}`, className: 'text-success-emphasis' }
  }
  if (data.current_loss_streak > 0) {
    return { value: `-${data.current_loss_streak}`, className: 'text-danger-emphasis' }
  }
  return { value: '0', className: 'text-text-primary' }
}

function isEmpty(data: Streaks): boolean {
  return (
    data.current_win_streak === 0 &&
    data.current_loss_streak === 0 &&
    data.max_win_streak === 0 &&
    data.max_loss_streak === 0
  )
}

interface StreaksDisplayProps {
  data: Streaks
}

function StreaksDisplay({ data }: StreaksDisplayProps) {
  if (isEmpty(data)) {
    return (
      <p className="text-sm text-text-secondary">No closed trades yet.</p>
    )
  }

  const current = currentStreakDisplay(data)

  return (
    <div className="space-y-4">
      <div>
        <p className="mb-1 text-xs uppercase tracking-wider text-text-secondary">
          Current streak
        </p>
        <span className={`text-4xl font-bold tabular-nums ${current.className}`}>
          {current.value}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <StatTile
          label="Max win streak"
          value={data.max_win_streak}
          className="text-success-emphasis"
        />
        <StatTile
          label="Max loss streak"
          value={data.max_loss_streak}
          className="text-danger-emphasis"
        />
        <StatTile
          label="Avg win run"
          value={formatDecimal(data.avg_win_streak, 1)}
          className="text-text-primary"
        />
        <StatTile
          label="Avg loss run"
          value={formatDecimal(data.avg_loss_streak, 1)}
          className="text-text-primary"
        />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Public card (owns fetching)
// ---------------------------------------------------------------------------

export function StreaksCard({ params = {} }: { params?: AnalyticsFilterParams }) {
  const { data, isLoading, isError } = useStreaks(params)

  return (
    <section
      className="rounded-xl border border-border bg-surface-base p-5"
      aria-label="Consecutive streaks"
    >
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        Streaks
      </h2>

      {isLoading && (
        <div
          className="h-24 animate-pulse rounded-lg bg-surface-subtle"
          role="status"
          aria-label="Loading streaks"
        />
      )}

      {isError && !isLoading && (
        <p className="text-sm text-danger-emphasis">Failed to load streaks.</p>
      )}

      {data && !isLoading && <StreaksDisplay data={data} />}
    </section>
  )
}
