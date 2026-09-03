import { useState } from 'react'
import { JournalPanel } from './features/journal'
import { AnalyticsSummaryPanel, AnalyticsFilterBar } from './features/analytics'
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

  return (
    <div className="min-h-screen bg-surface-base flex flex-col items-center justify-center gap-6 p-4">
      <div className="w-full max-w-xl">
        <AnalyticsFilterBar value={filterParams} onChange={setFilterParams} />
      </div>
      <div className="w-full max-w-xl">
        <AnalyticsSummaryPanel params={filterParams} />
      </div>
      <div className="w-full max-w-xl h-[700px] rounded-xl border border-border bg-surface-raised shadow-lg overflow-hidden">
        <JournalPanel trade={DEMO_TRADE} />
      </div>
    </div>
  )
}
