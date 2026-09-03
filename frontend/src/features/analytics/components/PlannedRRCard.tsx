import type { PlannedRR } from '../types'
import { formatDecimal, formatPctFraction } from '../formatters'

export function PlannedRRCard({ plannedRR }: { plannedRR: PlannedRR }) {
  const displayRR = formatDecimal(plannedRR.avg_planned_rr)
  const coveragePct = formatPctFraction(plannedRR.coverage_pct)

  return (
    <section
      className="rounded-xl border border-border bg-surface-base p-5"
      aria-label="Planned R:R"
    >
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        Planned R:R
      </h2>
      <dl className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-subtle p-4">
          <dt className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Avg planned R:R
          </dt>
          <dd
            className="text-2xl font-bold tabular-nums text-text-primary"
            aria-label={`Avg planned R:R: ${displayRR}`}
          >
            {displayRR}
          </dd>
          {plannedRR.avg_planned_rr === null && (
            <p className="text-xs text-text-muted" role="note">
              No trades with stop + target set
            </p>
          )}
        </div>
        <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-subtle p-4">
          <dt className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Coverage
          </dt>
          <dd
            className="text-2xl font-bold tabular-nums text-text-primary"
            aria-label={`Coverage: ${coveragePct}`}
          >
            {coveragePct}
          </dd>
          <p className="text-xs text-text-muted">
            {plannedRR.trade_count_with_rr} of {plannedRR.total_count} trades
          </p>
        </div>
      </dl>
    </section>
  )
}
