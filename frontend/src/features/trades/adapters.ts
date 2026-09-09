import type { TradeForJournal, TradeType } from '../journal/types'
import type { TradeDetailOut } from './types'

/** Maps TradeDetailOut to the TradeForJournal interface required by JournalPanel. */
export function toTradeForJournal(t: TradeDetailOut): TradeForJournal {
  return {
    id: t.id,
    symbol: t.symbol,
    exchange: t.exchange_segment,
    tradeDate: t.trade_date,
    firstFillAt: t.first_fill_at,
    direction: t.direction as 'LONG' | 'SHORT',
    tradeType: t.trade_type as TradeType,
    averageEntry: t.average_entry ?? null,
    totalEntryQuantity: t.total_entry_quantity,
  }
}
