import { cn } from '@/lib/utils'
import type { ProfitFactor } from '../types'
import { formatDecimal, formatINR } from '../formatters'

export function ProfitFactorCard({ profitFactor }: { profitFactor: ProfitFactor }) {
  const pfNum =
    profitFactor.profit_factor !== null ? parseFloat(profitFactor.profit_factor) : NaN
  const isGood = !isNaN(pfNum) && pfNum > 1
  const isBad = !isNaN(pfNum) && pfNum < 1
  const displayPF = formatDecimal(profitFactor.profit_factor)

  return (
    <section
      className="rounded-xl border border-border bg-surface-base p-5"
      aria-label="Profit factor"
    >
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        Profit Factor
      </h2>
      <dl className="grid grid-cols-3 gap-3">
        <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-subtle p-4">
          <dt className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Profit factor
          </dt>
          <dd
            className={cn(
              'text-2xl font-bold tabular-nums',
              isGood && 'text-success-emphasis',
              isBad && 'text-danger-emphasis',
              !isGood && !isBad && 'text-text-primary',
            )}
            aria-label={`Profit factor: ${displayPF}`}
          >
            {displayPF}
          </dd>
          {profitFactor.profit_factor === null && (
            <p className="text-xs text-text-muted" role="note">
              No losing trades
            </p>
          )}
        </div>
        <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-subtle p-4">
          <dt className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Gross profit
          </dt>
          <dd
            className="text-lg font-bold tabular-nums text-success-emphasis"
            aria-label={`Gross profit: ${formatINR(profitFactor.gross_profit)}`}
          >
            {formatINR(profitFactor.gross_profit)}
          </dd>
        </div>
        <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-subtle p-4">
          <dt className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Gross loss
          </dt>
          <dd
            className="text-lg font-bold tabular-nums text-danger-emphasis"
            aria-label={`Gross loss: ${formatINR(profitFactor.gross_loss)}`}
          >
            {formatINR(profitFactor.gross_loss)}
          </dd>
        </div>
      </dl>
    </section>
  )
}
