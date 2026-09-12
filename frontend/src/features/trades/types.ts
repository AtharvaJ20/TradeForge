export interface FillInput {
  side: 'BUY' | 'SELL'
  quantity: string          // Decimal as string — matches backend Numeric
  price: string
  fill_timestamp: string    // ISO 8601 with offset e.g. "2026-09-06T10:15:00+05:30"
}

export interface InstrumentInput {
  symbol: string
  exchange_segment: 'NSE_EQ' | 'NSE_FO' | 'BSE_EQ'
  instrument_type: 'EQ' | 'FUT' | 'CE' | 'PE'
  expiry_date?: string      // "YYYY-MM-DD"
  strike_price?: string
}

export interface CreateTradeBody {
  account_id: string
  instrument: InstrumentInput
  product_type: 'MIS' | 'CNC' | 'NRML'
  fills: FillInput[]
  planned_stop?: string
  planned_target?: string
}

export interface AddFillBody {
  fill: FillInput
}

// --- Read response types (Step 19) ---

export interface TradeListPageOut {
  items: TradeListItemOut[]
  total: number
  limit: number
  offset: number
}

export interface TradeListItemOut {
  id: string
  account_id: string | null
  symbol: string
  instrument_type: string
  direction: string
  status: string
  trade_date: string
  last_fill_at: string | null
  net_pnl: string | null
  r_multiple: string | null
}

export interface FillItemOut {
  id: string
  side: string
  quantity: string
  price: string
  fill_role: string | null
  fill_timestamp: string
  import_source: string
  broker: string
}

export interface PnlBreakdownOut {
  gross_pnl: string
  net_pnl: string
  total_charges: string
  brokerage: string
  stt: string
  exchange_charges: string
  sebi_charges: string
  stamp_duty: string
  gst: string
  ipft: string
  r_multiple: string | null
}

export interface TradeDetailOut {
  id: string
  account_id: string | null
  symbol: string
  instrument_name: string
  exchange_segment: string
  instrument_type: string
  expiry_date: string | null
  strike_price: string | null
  direction: string
  trade_type: string
  status: string
  trade_date: string
  first_fill_at: string
  last_fill_at: string | null
  total_entry_quantity: string
  total_exit_quantity: string
  average_entry: string | null
  average_exit: string | null
  planned_stop: string | null
  planned_target: string | null
  planned_risk_amount: string | null
  setup_name: string | null
  hold_duration_seconds: number | null
  fills: FillItemOut[]
  pnl: PnlBreakdownOut | null
}

export interface Trade {
  id: string
  account_id: string | null
  instrument_id: string
  trade_type: string
  direction: string
  status: 'OPEN' | 'PARTIAL' | 'CLOSED'
  trade_date: string
  first_fill_at: string
  last_fill_at: string | null
  total_entry_quantity: string
  total_exit_quantity: string
  net_position: string
  average_entry: string | null
  average_exit: string | null
  planned_stop: string | null
  planned_target: string | null
  is_deleted: boolean
  created_at: string
  updated_at: string
}
