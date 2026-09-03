import { http, HttpResponse } from 'msw'

const BASE = 'http://localhost:8000'

// ---------------------------------------------------------------------------
// Analytics fixtures
// ---------------------------------------------------------------------------

export const ANALYTICS_SUMMARY_FIXTURE = {
  pnl: { total_trades: 30, gross_pnl: '29000.00', net_pnl: '27500.00', total_charges: '1500.00' },
  outcome: {
    win_count: 20, loss_count: 10, breakeven_count: 0, total_n: 30,
    win_rate: '0.67', loss_rate: '0.33', breakeven_rate: '0.00',
  },
  expectancy: {
    expectancy_r: '1.25', avg_r_win: '2.00', avg_r_loss: '-1.50',
    r_coverage_count: 30, total_count: 30, r_coverage_pct: '1.00',
    insufficient_sample: false,
  },
  profit_factor: { profit_factor: '3.14', gross_profit: '19000.00', gross_loss: '-6050.00' },
  planned_rr: { avg_planned_rr: null, trade_count_with_rr: 0, total_count: 30, coverage_pct: '0.00' },
  drawdown: {
    max_drawdown_pct: null, max_drawdown_inr: null,
    avg_drawdown_pct: null, current_drawdown_pct: null,
  },
  direction: [{
    direction: 'LONG', trade_count: 30, win_count: 20, loss_count: 10,
    breakeven_count: 0, win_rate: '0.67', avg_net_pnl: '916.67',
    total_net_pnl: '27500.00', avg_r_multiple: '0.75',
  }],
  charges: {
    total_brokerage: '600.00', total_stt: '300.00', total_exchange_charges: '240.00',
    total_sebi_charges: '60.00', total_stamp_duty: '150.00', total_gst: '120.00',
    total_ipft: '30.00', total_charges: '1500.00', total_gross_pnl: '29000.00',
    charge_drag_pct: '5.17', charges_added_to_loss: null,
  },
  risk_adjusted: {
    sharpe: {
      sharpe_ratio: '2.34', mean_r: '0.45', std_r: '0.61',
      n_per_year: 252, r_coverage_count: 30, insufficient_sample: false,
    },
    sortino: {
      sortino_ratio: '1.89', mean_r: '0.45', downside_dev: '0.75',
      n_per_year: 252, r_coverage_count: 30, insufficient_sample: false,
      no_downside_trades: false,
    },
  },
}

/** Variant: fewer than 30 trades → insufficient_sample for both ratios. */
export const ANALYTICS_SUMMARY_INSUFFICIENT_FIXTURE = {
  ...ANALYTICS_SUMMARY_FIXTURE,
  risk_adjusted: {
    sharpe: {
      sharpe_ratio: null, mean_r: null, std_r: null,
      n_per_year: 252, r_coverage_count: 5, insufficient_sample: true,
    },
    sortino: {
      sortino_ratio: null, mean_r: null, downside_dev: null,
      n_per_year: 252, r_coverage_count: 5, insufficient_sample: true,
      no_downside_trades: false,
    },
  },
}

/** Variant: no negative-R trades → sortino has no_downside_trades flag. */
export const ANALYTICS_SUMMARY_NO_DOWNSIDE_FIXTURE = {
  ...ANALYTICS_SUMMARY_FIXTURE,
  risk_adjusted: {
    ...ANALYTICS_SUMMARY_FIXTURE.risk_adjusted,
    sortino: {
      sortino_ratio: null, mean_r: '0.45', downside_dev: null,
      n_per_year: 252, r_coverage_count: 30, insufficient_sample: false,
      no_downside_trades: true,
    },
  },
}

// ---------------------------------------------------------------------------
// Journal fixtures
// ---------------------------------------------------------------------------

/** Minimal valid journal entry fixture. */
export const ENTRY_FIXTURE = {
  id: 'aaa-111',
  trade_id: 'trade-001',
  planned_entry: '500.00',
  planned_stop: '490.00',
  planned_target: '520.00',
  planned_risk_amount: '1000.00',
  setup_name: 'Bull flag',
  notes: 'Good execution',
  discipline_score: 8,
  mistakes: [],
  emotion_before: 'CALM',
  emotion_during: 'CONFIDENT',
  emotion_after: 'CALM',
  pnl: {
    status: 'PENDING_CALCULATION',
    net_pnl: null,
    gross_pnl: null,
    total_charges: null,
    r_multiple: null,
  },
  attachments: [],
  created_at: '2026-08-23T09:00:00Z',
  updated_at: '2026-08-23T09:00:00Z',
}

export const AUDIT_FIXTURE = [
  {
    id: 'aud-1',
    field_name: 'discipline_score',
    previous_value: '7',
    new_value: '8',
    change_reason: 'Re-evaluated',
    changed_at: '2026-08-23T10:00:00Z',
  },
]

export const PRESIGN_FIXTURE = {
  attachment_id: 'att-001',
  upload_url: 'https://stub-s3.local/upload',
  s3_key: 'trades/trade-001/att-001',
  expires_in_seconds: 300,
}

export const CONFIRM_FIXTURE = {
  id: 'att-001',
  filename: 'chart.png',
  content_type: 'image/png',
  byte_size: 102400,
  status: 'CONFIRMED',
  download_url: 'https://stub-s3.local/download/att-001',
  confirmed_at: '2026-08-23T10:01:00Z',
}

// ---------------------------------------------------------------------------
// Filter dimension fixtures
// ---------------------------------------------------------------------------

export const FILTER_ACCOUNTS_FIXTURE = [
  { id: '00000000-0000-0000-0000-000000000011', label: 'Zerodha Main' },
  { id: '00000000-0000-0000-0000-000000000022', label: 'Upstox Secondary' },
]

export const FILTER_SETUPS_FIXTURE = ['Breakout', 'VWAP Reversion', '(no setup)']

export const FILTER_BROKERS_FIXTURE = ['UPSTOX', 'ZERODHA']

export const handlers = [
  // GET analytics summary
  http.get(`${BASE}/v1/analytics/summary`, () => {
    return HttpResponse.json(ANALYTICS_SUMMARY_FIXTURE)
  }),

  // GET filter dimensions
  http.get(`${BASE}/v1/analytics/filters/accounts`, () => {
    return HttpResponse.json(FILTER_ACCOUNTS_FIXTURE)
  }),
  http.get(`${BASE}/v1/analytics/filters/setups`, () => {
    return HttpResponse.json(FILTER_SETUPS_FIXTURE)
  }),
  http.get(`${BASE}/v1/analytics/filters/brokers`, () => {
    return HttpResponse.json(FILTER_BROKERS_FIXTURE)
  }),

  // GET journal entry — success
  http.get(`${BASE}/v1/journal/trades/:tradeId`, () => {
    return HttpResponse.json(ENTRY_FIXTURE)
  }),

  // GET journal entry — 404 (no entry yet)
  // Swap in tests via server.use(handlers.noEntry)

  // PUT upsert
  http.put(`${BASE}/v1/journal/trades/:tradeId`, async ({ request }) => {
    const body = await request.json()
    return HttpResponse.json({ ...ENTRY_FIXTURE, ...body })
  }),

  // GET audit history
  http.get(`${BASE}/v1/journal/trades/:tradeId/audit`, () => {
    return HttpResponse.json(AUDIT_FIXTURE)
  }),

  // POST presign
  http.post(`${BASE}/v1/journal/trades/:tradeId/attachments/presign`, () => {
    return HttpResponse.json(PRESIGN_FIXTURE)
  }),

  // POST confirm
  http.post(`${BASE}/v1/journal/trades/:tradeId/attachments/:attachmentId/confirm`, () => {
    return HttpResponse.json(CONFIRM_FIXTURE)
  }),

  // DELETE attachment
  http.delete(`${BASE}/v1/journal/trades/:tradeId/attachments/:attachmentId`, () => {
    return new HttpResponse(null, { status: 204 })
  }),
]

/** Override handler: GET returns 404 (no journal entry). */
export const noEntryHandler = http.get(`${BASE}/v1/journal/trades/:tradeId`, () => {
  return new HttpResponse(null, { status: 404 })
})
