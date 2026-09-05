import { useState } from 'react'
import { AnalyticsSummaryPanel, AnalyticsFilterBar } from '.'
import { countActiveFilterDimensions } from './utils'
import { RDistributionCard } from './components/RDistributionCard'
import { DimensionBreakdownCard } from './components/DimensionBreakdownCard'
import { RiskSummaryCard } from './components/RiskSummaryCard'
import { KellyCard } from './components/KellyCard'
import { TimeOfDayCard } from './components/TimeOfDayCard'
import { RollingExpectancyCard } from './components/RollingExpectancyCard'
import type { AnalyticsFilterParams } from '.'

export function AnalyticsPage() {
  const [filterParams, setFilterParams] = useState<AnalyticsFilterParams>({})
  const [filtersOpen, setFiltersOpen] = useState(true)

  const activeCount = countActiveFilterDimensions(filterParams)
  const badgeCount = Math.min(activeCount, 9)

  return (
    <div className="flex flex-col items-center gap-6 p-6">
      <div className="w-full max-w-xl flex items-center justify-between">
        <button
          type="button"
          aria-expanded={filtersOpen}
          aria-controls="analytics-filter-panel"
          onClick={() => setFiltersOpen((prev) => !prev)}
          className="relative inline-flex items-center gap-2 rounded-lg border border-border bg-surface-base px-3 py-1.5 text-sm font-medium text-text-primary hover:border-text-secondary"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 16 16"
            fill="currentColor"
            className="h-4 w-4 text-text-secondary"
            aria-hidden="true"
          >
            <path d="M1.5 3.75a.75.75 0 0 1 .75-.75h11.5a.75.75 0 0 1 0 1.5H2.25a.75.75 0 0 1-.75-.75ZM3 8a.75.75 0 0 1 .75-.75h8.5a.75.75 0 0 1 0 1.5h-8.5A.75.75 0 0 1 3 8Zm2.25 3.5a.75.75 0 0 1 .75-.75h4a.75.75 0 0 1 0 1.5h-4a.75.75 0 0 1-.75-.75Z" />
          </svg>
          Filters
          {badgeCount > 0 && (
            <span
              aria-label={`${badgeCount} active filter${badgeCount === 1 ? '' : 's'}`}
              className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full bg-accent text-xs font-semibold text-white"
            >
              {badgeCount}
            </span>
          )}
        </button>
      </div>

      {filtersOpen && (
        <div id="analytics-filter-panel" className="w-full max-w-xl">
          <AnalyticsFilterBar value={filterParams} onChange={setFilterParams} />
        </div>
      )}

      <div className="w-full max-w-xl">
        <AnalyticsSummaryPanel params={filterParams} />
      </div>
      <div className="w-full max-w-xl">
        <RDistributionCard params={filterParams} />
      </div>
      <div className="w-full max-w-xl">
        <DimensionBreakdownCard params={filterParams} />
      </div>
      <div className="w-full max-w-xl">
        <RiskSummaryCard params={filterParams} />
      </div>
      <div className="w-full max-w-xl">
        <KellyCard params={filterParams} />
      </div>
      <div className="w-full max-w-xl">
        <TimeOfDayCard params={filterParams} />
      </div>
      <div className="w-full max-w-xl">
        <RollingExpectancyCard params={filterParams} />
      </div>
    </div>
  )
}
