import type { OutcomeDistribution } from '../types'
import { formatPctFraction } from '../formatters'

export function OutcomeCard({ outcome }: { outcome: OutcomeDistribution }) {
  return (
    <section
      className="rounded-xl border border-border bg-surface-base p-5"
      aria-label="Outcome distribution"
    >
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        Outcomes
      </h2>
      <dl className="grid grid-cols-3 gap-3">
        <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-subtle p-4">
          <dt className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Win rate
          </dt>
          <dd
            className="text-2xl font-bold tabular-nums text-success-emphasis"
            aria-label={`Win rate: ${formatPctFraction(outcome.win_rate)}`}
          >
            {formatPctFraction(outcome.win_rate)}
          </dd>
          <p className="text-xs text-text-muted">{outcome.win_count} wins</p>
        </div>
        <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-subtle p-4">
          <dt className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Loss rate
          </dt>
          <dd
            className="text-2xl font-bold tabular-nums text-danger-emphasis"
            aria-label={`Loss rate: ${formatPctFraction(outcome.loss_rate)}`}
          >
            {formatPctFraction(outcome.loss_rate)}
          </dd>
          <p className="text-xs text-text-muted">{outcome.loss_count} losses</p>
        </div>
        <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-subtle p-4">
          <dt className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Breakeven
          </dt>
          <dd
            className="text-2xl font-bold tabular-nums text-text-primary"
            aria-label={`Breakeven rate: ${formatPctFraction(outcome.breakeven_rate)}`}
          >
            {formatPctFraction(outcome.breakeven_rate)}
          </dd>
          <p className="text-xs text-text-muted">{outcome.breakeven_count} trades</p>
        </div>
      </dl>
      <p className="mt-3 text-xs text-text-muted">{outcome.total_n} total trades</p>
    </section>
  )
}
