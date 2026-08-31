import { JournalPanel } from './features/journal'

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
  return (
    <div className="min-h-screen bg-surface-base flex items-center justify-center p-4">
      <div className="w-full max-w-xl h-[700px] rounded-xl border border-border bg-surface-raised shadow-lg overflow-hidden">
        <JournalPanel trade={DEMO_TRADE} />
      </div>
    </div>
  )
}
