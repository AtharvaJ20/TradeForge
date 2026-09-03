import { cn } from '@/lib/utils'
import type { ExpectancyResult } from '../types'
import { formatSigned, formatPctFraction } from '../formatters'

export function ExpectancyCard({ expectancy }: { expectancy: ExpectancyResult }) {
  const displayR = expectancy.insufficient_sample ? '—' : formatSigned(expectancy.expectancy_r)
  const rNum = expectancy.expectancy_r !== null ? parseFloat(expectancy.expectancy_r) : NaN
  const isPositive = !expectancy.insufficient_sample && rNum > 0
  const isNegative = !expectancy.insufficient_sample && rNum < 0

  return (
    <section
      className="rounded-xl border border-border bg-surface-base p-5"
      aria-label="Expectancy"
    >
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        Expectancy
      </h2>
      <dl className="grid grid-cols-3 gap-3">
        <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-subtle p-4">
          <dt className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Expectancy (R)
          </dt>
          <dd
            className={cn(
              'text-2xl font-bold tabular-nums',
              isPositive && 'text-success-emphasis',
              isNegative && 'text-danger-emphasis',
              !isPositive && !isNegative && 'text-text-primary',
            )}
            aria-label={`Expectancy R: ${displayR}`}
          >
            {displayR}
          </dd>
          {expectancy.insufficient_sample ? (
            <p className="text-xs text-text-muted" role="note">
              Insufficient data (n = {expectancy.r_coverage_count})
            </p>
          ) : (
            <p className="text-xs text-text-muted">
              R coverage: {formatPctFraction(expectancy.r_coverage_pct)}
            </p>
          )}
        </div>
        <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-subtle p-4">
          <dt className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Avg win (R)
          </dt>
          <dd
            className="text-lg font-bold tabular-nums text-success-emphasis"
            aria-label={`Avg win R: ${formatSigned(expectancy.avg_r_win)}`}
          >
            {formatSigned(expectancy.avg_r_win)}
          </dd>
        </div>
        <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-subtle p-4">
          <dt className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Avg loss (R)
          </dt>
          <dd
            className="text-lg font-bold tabular-nums text-danger-emphasis"
            aria-label={`Avg loss R: ${formatSigned(expectancy.avg_r_loss)}`}
          >
            {formatSigned(expectancy.avg_r_loss)}
          </dd>
        </div>
      </dl>
    </section>
  )
}
