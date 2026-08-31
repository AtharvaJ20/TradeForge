import { cn, formatInr, calcPlannedRisk, calcRR } from '@/lib/utils'
import type { TradeForJournal } from '../types'

interface TradeContextPanelProps {
  trade: TradeForJournal
  plannedStop: string | null
  plannedTarget: string | null
}

function Fact({ label, value, className }: { label: string; value: string | null; className?: string }) {
  return (
    <div>
      <dt className="text-xs text-text-secondary">{label}</dt>
      <dd className={cn('text-sm font-medium text-text-primary', className)}>
        {value ?? '—'}
      </dd>
    </div>
  )
}

/** C-01 TradeContextPanel — non-editable trade facts derived from the trade record. */
export function TradeContextPanel({ trade, plannedStop, plannedTarget }: TradeContextPanelProps) {
  const plannedRisk = calcPlannedRisk(trade.averageEntry, plannedStop, trade.totalEntryQuantity)
  const rr = calcRR(trade.averageEntry, plannedStop, plannedTarget)
  const directionColor = trade.direction === 'LONG' ? 'text-success-emphasis' : 'text-danger-emphasis'

  return (
    <section aria-label="Trade context" className="rounded-lg border border-border bg-surface-subtle p-4">
      <div className="mb-3 flex items-baseline gap-2">
        <h2 className="font-semibold text-text-primary">{trade.symbol}</h2>
        <span className="text-xs text-text-secondary">{trade.exchange}</span>
        <span
          className={cn('ml-auto text-xs font-semibold uppercase', directionColor)}
          aria-label={`Direction: ${trade.direction}`}
        >
          {trade.direction}
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
        <Fact label="Avg Entry" value={trade.averageEntry !== null ? formatInr(trade.averageEntry) : null} />
        <Fact label="Quantity" value={trade.totalEntryQuantity} />
        <Fact label="Planned Stop" value={plannedStop !== null ? formatInr(plannedStop) : null} />
        <Fact label="Planned Target" value={plannedTarget !== null ? formatInr(plannedTarget) : null} />
        <Fact label="Planned Risk" value={plannedRisk !== null ? formatInr(plannedRisk) : null} />
        <Fact label="Planned R:R" value={rr} />
      </dl>
    </section>
  )
}
