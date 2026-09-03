import { cn } from '@/lib/utils'
import type { PnlSummary } from '../types'
import { formatINR } from '../formatters'

export function PnlSummaryCard({ pnl }: { pnl: PnlSummary }) {
  const netNum = parseFloat(pnl.net_pnl)
  const isNetPositive = netNum > 0
  const isNetNegative = netNum < 0

  return (
    <section
      className="rounded-xl border border-border bg-surface-base p-5"
      aria-label="P&L summary"
    >
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        P&L Summary
      </h2>
      <dl className="grid grid-cols-2 gap-3">
        <div className="col-span-2 flex flex-col gap-1.5 rounded-lg border border-border bg-surface-subtle p-4">
          <dt className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Net P&L
          </dt>
          <dd
            className={cn(
              'text-2xl font-bold tabular-nums',
              isNetPositive && 'text-success-emphasis',
              isNetNegative && 'text-danger-emphasis',
              !isNetPositive && !isNetNegative && 'text-text-primary',
            )}
            aria-label={`Net P&L: ${formatINR(pnl.net_pnl)}`}
          >
            {formatINR(pnl.net_pnl)}
          </dd>
        </div>
        <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-subtle p-4">
          <dt className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Gross P&L
          </dt>
          <dd
            className="text-lg font-bold tabular-nums text-text-primary"
            aria-label={`Gross P&L: ${formatINR(pnl.gross_pnl)}`}
          >
            {formatINR(pnl.gross_pnl)}
          </dd>
        </div>
        <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-subtle p-4">
          <dt className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Total charges
          </dt>
          <dd
            className="text-lg font-bold tabular-nums text-danger-emphasis"
            aria-label={`Total charges: ${formatINR(pnl.total_charges)}`}
          >
            {formatINR(pnl.total_charges)}
          </dd>
        </div>
      </dl>
      <p className="mt-3 text-xs text-text-muted">{pnl.total_trades} trades in period</p>
    </section>
  )
}
