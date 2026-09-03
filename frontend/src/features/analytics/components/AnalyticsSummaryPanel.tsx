import { useAnalyticsSummary } from '../hooks/useAnalyticsSummary'
import { RiskAdjustedCard } from './RiskAdjustedCard'

/** Skeleton placeholder matching RiskAdjustedCard dimensions. */
function SkeletonRiskAdjustedCard() {
  return (
    <div
      className="rounded-xl border border-border bg-surface-base p-5"
      role="status"
      aria-busy="true"
      aria-label="Loading analytics"
    >
      <div className="mb-4 h-3 w-36 animate-pulse rounded bg-surface-subtle" />
      <div className="grid grid-cols-2 gap-3">
        <div className="h-24 animate-pulse rounded-lg bg-surface-subtle" />
        <div className="h-24 animate-pulse rounded-lg bg-surface-subtle" />
      </div>
      <div className="mt-3 h-3 w-48 animate-pulse rounded bg-surface-subtle" />
    </div>
  )
}

/** Fetches /v1/analytics/summary and renders risk-adjusted metrics. */
export function AnalyticsSummaryPanel() {
  const { data, isLoading, isError } = useAnalyticsSummary()

  if (isLoading) return <SkeletonRiskAdjustedCard />

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
    <RiskAdjustedCard
      sharpe={data.risk_adjusted.sharpe}
      sortino={data.risk_adjusted.sortino}
    />
  )
}
