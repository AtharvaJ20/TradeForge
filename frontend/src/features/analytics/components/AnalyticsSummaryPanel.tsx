import { useAnalyticsSummary } from '../hooks/useAnalyticsSummary'
import type { AnalyticsFilterParams } from '../types'
import { PnlSummaryCard } from './PnlSummaryCard'
import { OutcomeCard } from './OutcomeCard'
import { ExpectancyCard } from './ExpectancyCard'
import { ProfitFactorCard } from './ProfitFactorCard'
import { PlannedRRCard } from './PlannedRRCard'
import { DrawdownCard } from './DrawdownCard'
import { RiskAdjustedCard } from './RiskAdjustedCard'
import { DirectionBreakdownTable } from './DirectionBreakdownTable'
import { ChargesCard } from './ChargesCard'
import { StreaksCard } from './StreaksCard'
import { HoldDurationCard } from './HoldDurationCard'
import { ExitTypeCard } from './ExitTypeCard'

function SkeletonPanel() {
  return (
    <div
      className="space-y-4"
      role="status"
      aria-busy="true"
      aria-label="Loading analytics"
    >
      <div className="grid grid-cols-2 gap-4">
        <div className="h-40 animate-pulse rounded-xl bg-surface-subtle" />
        <div className="h-40 animate-pulse rounded-xl bg-surface-subtle" />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="h-40 animate-pulse rounded-xl bg-surface-subtle" />
        <div className="h-40 animate-pulse rounded-xl bg-surface-subtle" />
      </div>
      <div className="h-36 animate-pulse rounded-xl bg-surface-subtle" />
      <div className="h-36 animate-pulse rounded-xl bg-surface-subtle" />
      <div className="h-48 animate-pulse rounded-xl bg-surface-subtle" />
    </div>
  )
}

/** Fetches /v1/analytics/summary and renders all 9 analytics sections. */
export function AnalyticsSummaryPanel({ params }: { params?: AnalyticsFilterParams } = {}) {
  const { data, isLoading, isError } = useAnalyticsSummary(params)

  if (isLoading) return <SkeletonPanel />

  if (isError) {
    return (
      <div
        className="rounded-xl border border-danger/30 bg-surface-danger p-5"
        role="alert"
        aria-label="Analytics error"
      >
        <p className="text-sm font-medium text-danger-emphasis">
          Failed to load analytics. Please try again.
        </p>
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <PnlSummaryCard pnl={data.pnl} />
        <OutcomeCard outcome={data.outcome} />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <ExpectancyCard expectancy={data.expectancy} />
        <ProfitFactorCard profitFactor={data.profit_factor} />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <PlannedRRCard plannedRR={data.planned_rr} />
        <DrawdownCard drawdown={data.drawdown} />
      </div>

      <RiskAdjustedCard
        sharpe={data.risk_adjusted.sharpe}
        sortino={data.risk_adjusted.sortino}
      />

      <DirectionBreakdownTable rows={data.direction} />

      <ChargesCard charges={data.charges} />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <StreaksCard params={params} />
        <HoldDurationCard params={params} />
      </div>

      <ExitTypeCard params={params} />
    </div>
  )
}
