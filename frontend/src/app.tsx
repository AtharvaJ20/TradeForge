import { useState } from 'react'
import { JournalPanel } from './features/journal'
import { AnalyticsSummaryPanel, AnalyticsFilterBar } from './features/analytics'
import { countActiveFilterDimensions } from './features/analytics/utils'
import { RDistributionCard } from './features/analytics/components/RDistributionCard'
import { DimensionBreakdownCard } from './features/analytics/components/DimensionBreakdownCard'
import { RiskSummaryCard } from './features/analytics/components/RiskSummaryCard'
import { KellyCard } from './features/analytics/components/KellyCard'
import { TimeOfDayCard } from './features/analytics/components/TimeOfDayCard'
import { RollingExpectancyCard } from './features/analytics/components/RollingExpectancyCard'
import type { AnalyticsFilterParams } from './features/analytics'

const DEMO_TRADE = {
  id: '00000000-0000-0000-0000-000000000001',
  symbol: 'RELIANCE',
  exchange: 'NSE' as const,
  tradeDate: '2026-08-23',
  firstFillAt: '2026-08-23T09:15:00Z',
  direction: 'LONG' as const,
  tradeType: 'MIS' as const,
  averageEntry: '2850.00',
  totalEntryQuantity: '10',
}

export function App() {
  const [filterParams, setFilterParams] = useState<AnalyticsFilterParams>({})
  const [filtersOpen, setFiltersOpen] = useState(true)

  const activeCount = countActiveFilterDimensions(filterParams)
  const badgeCount = Math.min(activeCount, 9)

  return (
    <div className="min-h-screen bg-surface-base flex flex-col items-center justify-center gap-6 p-4">
      {/* Filter toggle button with active-filter badge */}
      <div className="w-full max-w-xl flex items-center justify-between">
        <button
          type="button"
          aria-expanded={filtersOpen}
          aria-controls="analytics-filter-panel"
          onClick={() => setFiltersOpen(prev => !prev)}
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

      {/* Collapsible filter panel */}
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
      <div className="w-full max-w-xl h-[700px] rounded-xl border border-border bg-surface-raised shadow-lg overflow-hidden">
        <JournalPanel trade={DEMO_TRADE} />
      </div>
    </div>
  )
}
