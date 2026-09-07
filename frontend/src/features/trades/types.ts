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
