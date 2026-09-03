import type { DrawdownStats } from '../types'
import { formatPctDirect, formatINRNullable } from '../formatters'

export function DrawdownCard({ drawdown }: { drawdown: DrawdownStats }) {
  const hasData = drawdown.max_drawdown_pct !== null

  return (
    <section
      className="rounded-xl border border-border bg-surface-base p-5"
      aria-label="Drawdown"
    >
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        Drawdown
      </h2>
      {!hasData ? (
        <p className="text-sm text-text-muted" role="note">
          No drawdown data for this period.
        </p>
      ) : (
        <dl className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-subtle p-4">
            <dt className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
              Max drawdown %
            </dt>
            <dd
              className="text-2xl font-bold tabular-nums text-danger-emphasis"
              aria-label={`Max drawdown %: ${formatPctDirect(drawdown.max_drawdown_pct)}`}
            >
              {formatPctDirect(drawdown.max_drawdown_pct)}
            </dd>
          </div>
          <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-subtle p-4">
            <dt className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
              Max drawdown ₹
            </dt>
            <dd
              className="text-2xl font-bold tabular-nums text-danger-emphasis"
              aria-label={`Max drawdown INR: ${formatINRNullable(drawdown.max_drawdown_inr)}`}
            >
              {formatINRNullable(drawdown.max_drawdown_inr)}
            </dd>
          </div>
          <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-subtle p-4">
            <dt className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
              Avg drawdown %
            </dt>
            <dd
              className="text-lg font-bold tabular-nums text-danger-emphasis"
              aria-label={`Avg drawdown %: ${formatPctDirect(drawdown.avg_drawdown_pct)}`}
            >
              {formatPctDirect(drawdown.avg_drawdown_pct)}
            </dd>
          </div>
          <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-subtle p-4">
            <dt className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
              Current drawdown %
            </dt>
            <dd
              className="text-lg font-bold tabular-nums text-danger-emphasis"
              aria-label={`Current drawdown %: ${formatPctDirect(drawdown.current_drawdown_pct)}`}
            >
              {formatPctDirect(drawdown.current_drawdown_pct)}
            </dd>
          </div>
        </dl>
      )}
    </section>
  )
}
