import { useRiskSummary } from '../hooks/useRiskSummary'
import type { AnalyticsFilterParams, RiskSummary } from '../types'

// ---------------------------------------------------------------------------
// Local formatters
// ---------------------------------------------------------------------------

function applyThousands(intPart: string): string {
  return intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

function formatInrDecimals(abs: number): string {
  const [int, dec] = abs.toFixed(2).split('.')
  return `₹${applyThousands(int ?? '0')}.${dec ?? '00'}`
}

// Format a drawdown pct string as "−X.XX%" or "—" (backend returns positive pct)
function formatDrawdownPct(value: string | null): string {
  if (value === null) return '—'
  const num = parseFloat(value)
  if (isNaN(num)) return '—'
  return `−${num.toFixed(2)}%`
}

// Format total_at_risk_inr as "₹X,XXX.XX" or "—" when null
function formatAtRisk(value: string | null): string {
  if (value === null) return '—'
  const num = parseFloat(value)
  if (isNaN(num)) return '—'
  return formatInrDecimals(Math.abs(num))
}

// Format daily_loss_inr: "−₹X,XXX.XX" (red) when non-zero, "₹0.00" (neutral) when zero
function formatDailyLoss(value: string | null): { text: string; isLoss: boolean } {
  if (value === null) return { text: '₹0.00', isLoss: false }
  const num = parseFloat(value)
  if (isNaN(num) || num === 0) return { text: '₹0.00', isLoss: false }
  return { text: `−${formatInrDecimals(Math.abs(num))}`, isLoss: true }
}

// Color class for current loss streak (neutral at 0-2, amber at 3-4, red at 5+)
function streakColorClass(count: number): string {
  if (count >= 5) return 'text-danger-emphasis'
  if (count >= 3) return 'text-warning-emphasis'
  return 'text-text-primary'
}

// ---------------------------------------------------------------------------
// StatCell — reusable display tile
// ---------------------------------------------------------------------------

interface StatCellProps {
  label: string
  value: string | number
  valueClassName?: string
}

function StatCell({ label, value, valueClassName = 'text-text-primary' }: StatCellProps) {
  return (
    <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface-subtle p-4">
      <dt className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
        {label}
      </dt>
      <dd className={`text-2xl font-bold tabular-nums ${valueClassName}`}>{value}</dd>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Display sub-component
// ---------------------------------------------------------------------------

function RiskSummaryDisplay({ data }: { data: RiskSummary }) {
  const dailyLoss = formatDailyLoss(data.daily_loss_inr)

  return (
    <dl className="grid grid-cols-2 gap-3">
      <StatCell
        label="Max Drawdown"
        value={formatDrawdownPct(data.max_drawdown_pct)}
        valueClassName="text-danger-emphasis"
      />
      <StatCell
        label="Current Drawdown"
        value={formatDrawdownPct(data.current_drawdown_pct)}
        valueClassName="text-danger-emphasis"
      />
      <StatCell
        label="Max Loss Streak"
        value={`${data.max_loss_streak} trades`}
        valueClassName="text-text-primary"
      />
      <StatCell
        label="Current Loss Streak"
        value={`${data.current_loss_streak} trades`}
        valueClassName={streakColorClass(data.current_loss_streak)}
      />
      <StatCell
        label="Today's Loss"
        value={dailyLoss.text}
        valueClassName={dailyLoss.isLoss ? 'text-danger-emphasis' : 'text-text-primary'}
      />
      <StatCell
        label="Planned At-Risk"
        value={formatAtRisk(data.total_at_risk_inr)}
        valueClassName="text-text-primary"
      />
      <StatCell
        label="Open Trades"
        value={data.open_trade_count}
        valueClassName="text-text-primary"
      />
    </dl>
  )
}

// ---------------------------------------------------------------------------
// Public card (owns fetching)
// ---------------------------------------------------------------------------

export function RiskSummaryCard({ params = {} }: { params?: AnalyticsFilterParams }) {
  const { data, isLoading, isError } = useRiskSummary(params)

  return (
    <section
      className="rounded-xl border border-border bg-surface-base p-5"
      aria-labelledby="risk-summary-heading"
    >
      <h2
        id="risk-summary-heading"
        className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary"
      >
        Risk Summary
      </h2>

      {isLoading && (
        <div
          className="h-24 animate-pulse rounded-lg bg-surface-subtle"
          role="status"
          aria-label="Loading risk summary"
        />
      )}

      {isError && !isLoading && (
        <p className="text-sm text-danger-emphasis">Failed to load risk summary.</p>
      )}

      {data && !isLoading && <RiskSummaryDisplay data={data} />}
    </section>
  )
}
