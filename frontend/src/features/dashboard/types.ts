export interface DashboardSummaryOut {
  account_id: string
  as_of_date: string
  all_time_net_pnl: string
  mtd_net_pnl: string
  wtd_net_pnl: string
  starting_capital: string | null
  realized_equity: string | null
  total_closed_trades: number
  open_trade_count: number
}

export interface TradeListItemOut {
  id: string
  symbol: string
  instrument_type: string
  direction: string
  status: string
  trade_date: string
  last_fill_at: string | null
  net_pnl: string | null
  r_multiple: string | null
}

export interface RecentJournalItemOut {
  trade_id: string
  symbol: string
  instrument_type: string
  trade_date: string
  last_fill_at: string | null
  discipline_score: number | null
  emotion_before: string | null
  emotion_during: string | null
  emotion_after: string | null
}
