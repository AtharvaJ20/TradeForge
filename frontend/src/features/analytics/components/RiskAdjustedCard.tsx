import { cn } from '@/lib/utils'
import type { SharpeResult, SortinoResult } from '../types'

export interface RiskAdjustedCardProps {
  sharpe: SharpeResult
  sortino: SortinoResult
}

function formatSignedDecimal(value: string | null): string {
  if (value === null) return '—'
  const num = parseFloat(value)
  if (isNaN(num)) return '—'
  const sign = num > 0 ? '+' : ''
  return `${sign}${num.toFixed(2)}`
}

interface TileProps {
  label: string
  ratio: string | null
  coverageCount: number
  insufficientSample: boolean
  noDownsideTrades?: boolean
}

function Tile({
  label,
  ratio,
  coverageCount,
  insufficientSample,
  noDownsideTrades = false,
}: TileProps) {
  let displayValue: string
  let nullReason: string | null = null

  if (insufficientSample) {
    displayValue = '—'
    nullReason = `Insufficient data (n = ${coverageCount})`
  } else if (noDownsideTrades) {
    displayValue = '—'
    nullReason = 'No negative-R trades in sample'
  } else {
    displayValue = formatSignedDecimal(ratio)
  }

  const numericRatio = ratio !== null ? parseFloat(ratio) : NaN
  const isPositive = !insufficientSample && !noDownsideTrades && numericRatio > 0
  const isNegative = !insufficientSample && !noDownsideTrades && numericRatio < 0

  return (
    <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-subtle p-4">
      <dt className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
        {label}
      </dt>
      <dd
        className={cn(
          'text-2xl font-bold tabular-nums',
          isPositive && 'text-success-emphasis',
          isNegative && 'text-danger-emphasis',
          !isPositive && !isNegative && 'text-text-primary',
        )}
        aria-label={`${label}: ${displayValue}`}
      >
        {displayValue}
      </dd>
      {nullReason !== null ? (
        <p className="text-xs text-text-muted" role="note">
          {nullReason}
        </p>
      ) : (
        <p className="text-xs text-text-muted">{coverageCount} trades with R</p>
      )}
    </div>
  )
}

/** Step 12.1 — Risk-adjusted returns card: Sharpe and Sortino ratios. */
export function RiskAdjustedCard({ sharpe, sortino }: RiskAdjustedCardProps) {
  return (
    <section
      className="rounded-xl border border-border bg-surface-base p-5"
      aria-label="Risk-adjusted returns"
    >
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        Risk-adjusted returns
      </h2>
      <dl className="grid grid-cols-2 gap-3">
        <Tile
          label="Sharpe ratio"
          ratio={sharpe.sharpe_ratio}
          coverageCount={sharpe.r_coverage_count}
          insufficientSample={sharpe.insufficient_sample}
        />
        <Tile
          label="Sortino ratio"
          ratio={sortino.sortino_ratio}
          coverageCount={sortino.r_coverage_count}
          insufficientSample={sortino.insufficient_sample}
          noDownsideTrades={sortino.no_downside_trades}
        />
      </dl>
      <p className="mt-3 text-xs text-text-muted">
        Annualised at {sharpe.n_per_year} trading sessions · NSE convention
      </p>
    </section>
  )
}
