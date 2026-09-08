export interface DashboardSummaryOut {
  account_id: string
  as_of_date: string
  all_time_net_pnl: number
  mtd_net_pnl: number
  wtd_net_pnl: number
  starting_capital: number | null
  realized_equity: number | null
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
  net_pnl: number | null
  r_multiple: number | null
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
