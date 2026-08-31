import { cn, formatInr, formatRMultiple } from '@/lib/utils'
import type { PnlStatus } from '../types'

export interface PnlStatusBlockProps {
  status: PnlStatus
  netPnl: string | null
  grossPnl: string | null
  totalCharges: string | null
  rMultiple: string | null
  onAddStop?: () => void
}

/** C-02 PnlStatusBlock — three-state P&L availability indicator. */
export function PnlStatusBlock({
  status,
  netPnl,
  grossPnl,
  totalCharges,
  rMultiple,
  onAddStop,
}: PnlStatusBlockProps) {
  if (status === 'PENDING_STOP') {
    return (
      <div
        className="rounded-lg border border-warning/30 bg-surface-warning p-4"
        role="status"
        aria-label="P&amp;L status: stop price not set"
      >
        <div className="flex items-start gap-3">
          <span className="mt-0.5 text-warning" aria-hidden="true">○</span>
          <div className="flex-1 space-y-1">
            <p className="font-medium text-warning-emphasis">Set a stop to unlock R-multiple</p>
            <p className="text-sm text-text-secondary">
              Add your planned stop to calculate risk and R-multiple when P&amp;L runs.
            </p>
          </div>
          {onAddStop && (
            <button
              type="button"
              onClick={onAddStop}
              className="shrink-0 text-sm font-medium text-warning-emphasis underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-border-focus"
            >
              Add Stop →
            </button>
          )}
        </div>
      </div>
    )
  }

  if (status === 'PENDING_CALCULATION') {
    return (
      <div
        className="rounded-lg border border-info/30 bg-surface-info p-4"
        role="status"
        aria-label="P&amp;L status: calculation pending"
      >
        <div className="flex items-start gap-3">
          <span
            className="mt-0.5 text-info motion-safe:animate-spin-slow"
            aria-hidden="true"
          >
            ◑
          </span>
          <div className="space-y-1">
            <p className="font-medium text-info">P&amp;L calculating</p>
            <p className="text-sm text-text-secondary">
              Stop is set. Results appear once the calculation engine runs after session close.
            </p>
          </div>
        </div>
      </div>
    )
  }

  // AVAILABLE
  const isProfit = netPnl !== null && parseFloat(netPnl) > 0
  const isLoss = netPnl !== null && parseFloat(netPnl) < 0

  return (
    <div
      className={cn(
        'rounded-lg border p-4',
        isProfit && 'border-success/30 bg-surface-success',
        isLoss && 'border-danger/30 bg-surface-danger',
        !isProfit && !isLoss && 'border-border bg-surface-neutral',
      )}
      role="region"
      aria-label="P&amp;L summary"
    >
      <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-secondary">
        ✓ P&amp;L Available
      </p>
      <dl className="grid grid-cols-4 gap-4">
        <div>
          <dt className="text-xs text-text-secondary">Net P&amp;L</dt>
          <dd
            className={cn(
              'text-lg font-semibold',
              isProfit && 'text-success-emphasis',
              isLoss && 'text-danger-emphasis',
              !isProfit && !isLoss && 'text-text-primary',
            )}
            aria-label={`Net P&L: ${formatInr(netPnl)}`}
          >
            {netPnl !== null && parseFloat(netPnl) > 0 ? '+' : ''}
            {formatInr(netPnl)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-text-secondary">R-multiple</dt>
          <dd
            className={cn(
              'text-lg font-semibold',
              isProfit && 'text-success-emphasis',
              isLoss && 'text-danger-emphasis',
              !isProfit && !isLoss && 'text-text-primary',
            )}
            aria-label={`R-multiple: ${formatRMultiple(rMultiple)}`}
          >
            {formatRMultiple(rMultiple)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-text-secondary">Gross</dt>
          <dd className="text-sm text-text-secondary" aria-label={`Gross P&L: ${formatInr(grossPnl)}`}>
            {formatInr(grossPnl)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-text-secondary">Charges</dt>
          <dd className="text-sm text-text-secondary" aria-label={`Total charges: ${formatInr(totalCharges)}`}>
            {formatInr(totalCharges)}
          </dd>
        </div>
      </dl>
    </div>
  )
}
