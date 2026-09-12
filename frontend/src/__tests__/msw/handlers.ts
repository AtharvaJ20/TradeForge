import { http, HttpResponse } from 'msw'

const BASE = 'http://localhost:8000'

// ---------------------------------------------------------------------------
// Analytics fixtures
// ---------------------------------------------------------------------------

export const ANALYTICS_SUMMARY_FIXTURE = {
  pnl: { total_trades: 30, gross_pnl: '29000.00', net_pnl: '27500.00', total_charges: '1500.00' },
  outcome: {
    win_count: 20, loss_count: 10, breakeven_count: 0, total_n: 30,
    win_rate: '67.00', loss_rate: '33.00', breakeven_rate: '0.00',
  },
  expectancy: {
    expectancy_r: '1.25', avg_r_win: '2.00', avg_r_loss: '-1.50',
    r_coverage_count: 30, total_count: 30, r_coverage_pct: '100.00',
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
    breakeven_count: 0, win_rate: '67.00', avg_net_pnl: '916.67',
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
// M-6 R-Multiple Distribution fixtures (Step 12.6)
// ---------------------------------------------------------------------------

export const R_DISTRIBUTION_FIXTURE = {
  mean_r: '0.45',
  median_r: '0.50',
  stddev_r: '1.20',
  p25_r: '-0.50',
  p75_r: '1.25',
  coverage_count: 20,
  total_count: 22,
  coverage_pct: '91.00',
  insufficient_sample: false,
  buckets: [
    { label: '< −2R', lower: null, upper: '-2', count: 2 },
    { label: '−2R to −1R', lower: '-2', upper: '-1', count: 3 },
    { label: '−1R to 0', lower: '-1', upper: '0', count: 4 },
    { label: '0 to +1R', lower: '0', upper: '1', count: 5 },
    { label: '+1R to +2R', lower: '1', upper: '2', count: 4 },
    { label: '> +2R', lower: '2', upper: null, count: 2 },
  ],
}

export const R_DISTRIBUTION_INSUFFICIENT_FIXTURE = {
  mean_r: null,
  median_r: null,
  stddev_r: null,
  p25_r: null,
  p75_r: null,
  coverage_count: 3,
  total_count: 5,
  coverage_pct: '60.00',
  insufficient_sample: true,
  buckets: [
    { label: '< −2R', lower: null, upper: '-2', count: 0 },
    { label: '−2R to −1R', lower: '-2', upper: '-1', count: 1 },
    { label: '−1R to 0', lower: '-1', upper: '0', count: 0 },
    { label: '0 to +1R', lower: '0', upper: '1', count: 2 },
    { label: '+1R to +2R', lower: '1', upper: '2', count: 0 },
    { label: '> +2R', lower: '2', upper: null, count: 0 },
  ],
}

// ---------------------------------------------------------------------------
// M-10 Dimension Breakdown fixtures (Step 12.6)
// ---------------------------------------------------------------------------

export const DIMENSION_BREAKDOWN_DIRECTION_FIXTURE = {
  dimension: 'direction',
  groups: [
    {
      label: 'LONG',
      trade_count: 18,
      win_count: 12,
      win_rate: '67.00',
      total_net_pnl: '22500.00',
      avg_net_pnl: '1250.00',
      avg_r_multiple: '0.85',
      avg_hold_duration_minutes: '72.50',
    },
    {
      label: 'SHORT',
      trade_count: 8,
      win_count: 4,
      win_rate: '50.00',
      total_net_pnl: '5000.00',
      avg_net_pnl: '625.00',
      avg_r_multiple: null,
      avg_hold_duration_minutes: '45.00',
    },
  ],
}

export const DIMENSION_BREAKDOWN_SETUP_FIXTURE = {
  dimension: 'setup',
  groups: [
    {
      label: 'Breakout',
      trade_count: 10,
      win_count: 7,
      win_rate: '70.00',
      total_net_pnl: '15000.00',
      avg_net_pnl: '1500.00',
      avg_r_multiple: '1.20',
      avg_hold_duration_minutes: '60.00',
    },
    {
      label: '(no setup)',
      trade_count: 5,
      win_count: 2,
      win_rate: '40.00',
      total_net_pnl: '-2000.00',
      avg_net_pnl: '-400.00',
      avg_r_multiple: null,
      avg_hold_duration_minutes: null,
    },
  ],
}

export const DIMENSION_BREAKDOWN_EMPTY_FIXTURE = {
  dimension: 'instrument',
  groups: [],
}

// ---------------------------------------------------------------------------
// N-4 Kelly Fraction fixtures (Step 12.7)
// ---------------------------------------------------------------------------

export const KELLY_FIXTURE = {
  kelly_pct: '0.3142',
  half_kelly_pct: '0.1571',
  trades_with_r: 45,
  insufficient_sample: false,
  min_n: 30,
}

export const KELLY_INSUFFICIENT_FIXTURE = {
  kelly_pct: null,
  half_kelly_pct: null,
  trades_with_r: 12,
  insufficient_sample: true,
  min_n: 30,
}

// ---------------------------------------------------------------------------
// N-2 Time-of-Day fixtures (Step 12.7)
// ---------------------------------------------------------------------------

export const TIME_OF_DAY_FIXTURE = {
  buckets: [
    {
      bucket: 'pre_open',
      label: 'Pre-Open',
      trade_count: 5,
      win_count: 3,
      win_rate: '60.00',
      expectancy_inr: '320.00',
      total_net_pnl: '1600.00',
    },
    {
      bucket: 'open_volatility',
      label: 'Open Volatility',
      trade_count: 12,
      win_count: 8,
      win_rate: '66.67',
      expectancy_inr: '450.00',
      total_net_pnl: '5400.00',
    },
    {
      bucket: 'mid_morning',
      label: 'Mid-Morning',
      trade_count: 0,
      win_count: 0,
      win_rate: '0.00',
      expectancy_inr: null,
      total_net_pnl: '0.00',
    },
    {
      bucket: 'lunch',
      label: 'Lunch',
      trade_count: 7,
      win_count: 4,
      win_rate: '57.14',
      expectancy_inr: '200.00',
      total_net_pnl: '1400.00',
    },
    {
      bucket: 'afternoon',
      label: 'Afternoon',
      trade_count: 3,
      win_count: 1,
      win_rate: '33.33',
      expectancy_inr: '-150.00',
      total_net_pnl: '-450.00',
    },
    {
      bucket: 'close',
      label: 'Close',
      trade_count: 2,
      win_count: 2,
      win_rate: '100.00',
      expectancy_inr: '750.00',
      total_net_pnl: '1500.00',
    },
  ],
}

// ---------------------------------------------------------------------------
// N-1 Rolling Expectancy fixtures (Step 12.7)
// ---------------------------------------------------------------------------

// 22 data points so we can verify last-20 slicing
export const ROLLING_EXPECTANCY_FIXTURE = {
  window: 20,
  insufficient_sample: false,
  data: Array.from({ length: 22 }, (_, i) => ({
    trade_index: i + 20,
    trade_date: `2025-01-${String(i + 1).padStart(2, '0')}`,
    rolling_exp_r: i % 3 === 0 ? null : i % 2 === 0 ? '0.42' : '-0.18',
    rolling_exp_inr: i % 2 === 0 ? '850.00' : '-200.00',
  })),
}

export const ROLLING_EXPECTANCY_INSUFFICIENT_FIXTURE = {
  window: 20,
  insufficient_sample: true,
  data: [],
}

// ---------------------------------------------------------------------------
// Behavioral analytics fixtures (Step 12.5)
// ---------------------------------------------------------------------------

export const STREAKS_FIXTURE = {
  current_win_streak: 0,
  current_loss_streak: 2,
  max_win_streak: 2,
  max_loss_streak: 2,
  avg_win_streak: '2.00',
  avg_loss_streak: '2.00',
}

export const STREAKS_EMPTY_FIXTURE = {
  current_win_streak: 0,
  current_loss_streak: 0,
  max_win_streak: 0,
  max_loss_streak: 0,
  avg_win_streak: '0.00',
  avg_loss_streak: '0.00',
}

export const HOLD_DURATION_FIXTURE = {
  buckets: [
    { bucket: '< 15 min', bucket_order: 1, count: 5, avg_net_pnl: '450.00', win_rate: '60.00' },
    { bucket: '15 min – 1 hr', bucket_order: 2, count: 12, avg_net_pnl: '820.00', win_rate: '75.00' },
    { bucket: '1 – 4 hr', bucket_order: 3, count: 8, avg_net_pnl: '-120.00', win_rate: '38.00' },
    { bucket: '4 – 24 hr', bucket_order: 4, count: 3, avg_net_pnl: '200.00', win_rate: '67.00' },
    { bucket: '> 7 days', bucket_order: 6, count: 2, avg_net_pnl: '1500.00', win_rate: '100.00' },
  ],
  avg_duration_minutes: '82.50',
  median_duration_minutes: '45.00',
}

export const HOLD_DURATION_EMPTY_FIXTURE = {
  buckets: [],
  avg_duration_minutes: null,
  median_duration_minutes: null,
}

export const EXIT_TYPES_FIXTURE = [
  { exit_type: 'TARGET_HIT', trade_count: 12, win_rate: '100.00', avg_net_pnl: '950.00', avg_r_multiple: '2.10' },
  { exit_type: 'STOP_HIT', trade_count: 10, win_rate: '0.00', avg_net_pnl: '-480.00', avg_r_multiple: '-1.00' },
  { exit_type: 'DISCRETIONARY', trade_count: 5, win_rate: '60.00', avg_net_pnl: '120.00', avg_r_multiple: '0.40' },
  { exit_type: null, trade_count: 3, win_rate: '33.00', avg_net_pnl: '-200.00', avg_r_multiple: null },
]

/** Variant: NULL exit_type > 20% of total — triggers data quality alert. */
export const EXIT_TYPES_HIGH_UNTAGGED_FIXTURE = [
  { exit_type: 'TARGET_HIT', trade_count: 3, win_rate: '100.00', avg_net_pnl: '900.00', avg_r_multiple: '2.00' },
  { exit_type: null, trade_count: 7, win_rate: '43.00', avg_net_pnl: '-100.00', avg_r_multiple: null },
]

// ---------------------------------------------------------------------------
// Filter dimension fixtures
// ---------------------------------------------------------------------------

export const FILTER_ACCOUNTS_FIXTURE = [
  { id: '00000000-0000-0000-0000-000000000011', label: 'Zerodha Main' },
  { id: '00000000-0000-0000-0000-000000000022', label: 'Upstox Secondary' },
]

export const FILTER_SETUPS_FIXTURE = ['Breakout', 'VWAP Reversion', '(no setup)']

export const FILTER_BROKERS_FIXTURE = ['UPSTOX', 'ZERODHA']

// ---------------------------------------------------------------------------
// Auth fixtures (Step 14)
// ---------------------------------------------------------------------------

export const AUTH_ME_FIXTURE = {
  id: '00000000-0000-0000-0000-000000000099',
  email: 'trader@example.com',
  is_email_verified: true,
  is_admin: false,
}

// ---------------------------------------------------------------------------
// Step 15 — User Profile fixtures
// ---------------------------------------------------------------------------

export const USER_PROFILE_FIXTURE = {
  id: '00000000-0000-0000-0000-000000000099',
  email: 'trader@example.com',
  display_name: 'Arjun Sharma',
  time_zone: 'Asia/Kolkata',
  base_currency: 'INR',
  is_email_verified: true,
  is_admin: false,
  created_at: '2026-06-01T10:00:00Z',
}

export const UPDATE_PROFILE_SUCCESS_FIXTURE = {
  ...USER_PROFILE_FIXTURE,
  display_name: 'Updated Name',
}

// ---------------------------------------------------------------------------
// Step 15 — Accounts fixtures
// ---------------------------------------------------------------------------

export const ACCOUNTS_LIST_FIXTURE = [
  {
    id: '00000000-0000-0000-0000-000000000001',
    user_id: '00000000-0000-0000-0000-000000000099',
    broker: 'ZERODHA',
    display_name: 'Zerodha Main',
    account_type: 'INDIVIDUAL',
    base_currency: 'INR',
    status: 'ACTIVE',
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
  },
  {
    id: '00000000-0000-0000-0000-000000000002',
    user_id: '00000000-0000-0000-0000-000000000099',
    broker: 'UPSTOX',
    display_name: 'Upstox Old',
    account_type: 'INDIVIDUAL',
    base_currency: 'INR',
    status: 'INACTIVE',
    created_at: '2026-07-01T10:00:00Z',
    updated_at: '2026-07-15T10:00:00Z',
  },
] as const

export const ACCOUNTS_EMPTY_FIXTURE: typeof ACCOUNTS_LIST_FIXTURE = [] as unknown as typeof ACCOUNTS_LIST_FIXTURE

export const CREATE_ACCOUNT_SUCCESS_FIXTURE = {
  id: '00000000-0000-0000-0000-000000000003',
  user_id: '00000000-0000-0000-0000-000000000099',
  broker: 'ZERODHA',
  display_name: 'New Account',
  account_type: 'INDIVIDUAL',
  base_currency: 'INR',
  status: 'ACTIVE',
  created_at: '2026-09-05T10:00:00Z',
  updated_at: '2026-09-05T10:00:00Z',
}

export const UPDATE_ACCOUNT_SUCCESS_FIXTURE = {
  ...ACCOUNTS_LIST_FIXTURE[0],
  display_name: 'Renamed Account',
}

export const LOGIN_SUCCESS_FIXTURE = AUTH_ME_FIXTURE

export const REGISTER_SUCCESS_FIXTURE = {
  message: 'If this email address is new, a verification link has been sent.',
}

export const LOGOUT_SUCCESS_FIXTURE = { message: 'Logged out successfully.' }

export const VERIFY_EMAIL_SUCCESS_FIXTURE = { message: 'Email verified successfully.' }

export const PASSWORD_RESET_REQUEST_SUCCESS_FIXTURE = {
  message: 'If this email address is registered, a password reset link has been sent.',
}

export const PASSWORD_RESET_CONFIRM_SUCCESS_FIXTURE = {
  message: 'Password reset successfully. Please log in with your new password.',
}

// ---------------------------------------------------------------------------
// Step 13 Risk Summary fixtures
// ---------------------------------------------------------------------------

export const RISK_SUMMARY_FIXTURE = {
  max_drawdown_inr: '42500.0000',
  max_drawdown_pct: '8.50',
  current_drawdown_inr: '14000.0000',
  current_drawdown_pct: '2.80',
  max_loss_streak: 4,
  current_loss_streak: 2,
  daily_loss_inr: '-2500.0000',
  daily_loss_trade_count: 2,
  total_at_risk_inr: '5000.0000',
  open_trade_count: 2,
  as_of_date: '2026-09-04',
}

export const RISK_SUMMARY_NO_DRAWDOWN_FIXTURE = {
  max_drawdown_inr: null,
  max_drawdown_pct: null,
  current_drawdown_inr: null,
  current_drawdown_pct: null,
  max_loss_streak: 0,
  current_loss_streak: 0,
  daily_loss_inr: '0.0000',
  daily_loss_trade_count: 0,
  total_at_risk_inr: null,
  open_trade_count: 0,
  as_of_date: '2026-09-04',
}

export const RISK_SUMMARY_NO_AT_RISK_FIXTURE = {
  ...RISK_SUMMARY_FIXTURE,
  total_at_risk_inr: null,
  open_trade_count: 1,
}

export const handlers = [
  // ---------------------------------------------------------------------------
  // Auth handlers (Step 14) — default: authenticated user
  // ---------------------------------------------------------------------------
  http.get(`${BASE}/v1/auth/me`, () => HttpResponse.json(AUTH_ME_FIXTURE)),

  // ---------------------------------------------------------------------------
  // Step 15 — User profile handlers
  // ---------------------------------------------------------------------------
  http.get(`${BASE}/v1/users/me`, () => HttpResponse.json(USER_PROFILE_FIXTURE)),
  http.patch(`${BASE}/v1/users/me`, () => HttpResponse.json(UPDATE_PROFILE_SUCCESS_FIXTURE)),

  // ---------------------------------------------------------------------------
  // Step 15 — Accounts handlers
  // ---------------------------------------------------------------------------
  http.get(`${BASE}/v1/accounts`, () => HttpResponse.json(ACCOUNTS_LIST_FIXTURE)),
  http.post(`${BASE}/v1/accounts`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>
    return HttpResponse.json({ ...CREATE_ACCOUNT_SUCCESS_FIXTURE, ...body })
  }),
  http.patch(`${BASE}/v1/accounts/:id`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>
    return HttpResponse.json({ ...UPDATE_ACCOUNT_SUCCESS_FIXTURE, ...body })
  }),
  http.delete(`${BASE}/v1/accounts/:id`, () => new HttpResponse(null, { status: 204 })),
  http.post(`${BASE}/v1/auth/login`, () => HttpResponse.json(LOGIN_SUCCESS_FIXTURE)),
  http.post(`${BASE}/v1/auth/logout`, () => HttpResponse.json(LOGOUT_SUCCESS_FIXTURE)),
  http.post(`${BASE}/v1/auth/register`, () => HttpResponse.json(REGISTER_SUCCESS_FIXTURE)),
  http.post(`${BASE}/v1/auth/verify-email`, () =>
    HttpResponse.json(VERIFY_EMAIL_SUCCESS_FIXTURE),
  ),
  http.post(`${BASE}/v1/auth/password-reset/request`, () =>
    HttpResponse.json(PASSWORD_RESET_REQUEST_SUCCESS_FIXTURE),
  ),
  http.post(`${BASE}/v1/auth/password-reset/confirm`, () =>
    HttpResponse.json(PASSWORD_RESET_CONFIRM_SUCCESS_FIXTURE),
  ),

  // GET analytics summary
  http.get(`${BASE}/v1/analytics/summary`, () => {
    return HttpResponse.json(ANALYTICS_SUMMARY_FIXTURE)
  }),

  // GET behavioral analytics
  http.get(`${BASE}/v1/analytics/streaks`, () => {
    return HttpResponse.json(STREAKS_FIXTURE)
  }),
  http.get(`${BASE}/v1/analytics/hold-duration`, () => {
    return HttpResponse.json(HOLD_DURATION_FIXTURE)
  }),
  http.get(`${BASE}/v1/analytics/by-exit-type`, () => {
    return HttpResponse.json(EXIT_TYPES_FIXTURE)
  }),

  // GET R-Multiple Distribution
  http.get(`${BASE}/v1/analytics/r-distribution`, () => {
    return HttpResponse.json(R_DISTRIBUTION_FIXTURE)
  }),

  // GET Kelly Fraction (N-4)
  http.get(`${BASE}/v1/analytics/kelly`, () => {
    return HttpResponse.json(KELLY_FIXTURE)
  }),

  // GET Time-of-Day (N-2)
  http.get(`${BASE}/v1/analytics/time-of-day`, () => {
    return HttpResponse.json(TIME_OF_DAY_FIXTURE)
  }),

  // GET Rolling Expectancy (N-1)
  http.get(`${BASE}/v1/analytics/rolling-expectancy`, () => {
    return HttpResponse.json(ROLLING_EXPECTANCY_FIXTURE)
  }),

  // GET Risk Summary (Step 13)
  http.get(`${BASE}/v1/risk/summary`, () => {
    return HttpResponse.json(RISK_SUMMARY_FIXTURE)
  }),

  // GET Dimension Breakdown
  http.get(`${BASE}/v1/analytics/breakdown`, () => {
    return HttpResponse.json(DIMENSION_BREAKDOWN_DIRECTION_FIXTURE)
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

  // ---------------------------------------------------------------------------
  // Step 16 — Trades handlers (default: success)
  // ---------------------------------------------------------------------------
  http.post(`${BASE}/v1/trades`, () => HttpResponse.json(TRADE_OPEN_FIXTURE, { status: 201 })),
  http.post(`${BASE}/v1/trades/:id/fills`, () => HttpResponse.json(TRADE_OPEN_FIXTURE)),
  http.delete(`${BASE}/v1/trades/:id`, () => new HttpResponse(null, { status: 204 })),

  // ---------------------------------------------------------------------------
  // Step 17 — Imports handlers (default: success)
  // ---------------------------------------------------------------------------
  http.post(`${BASE}/v1/accounts/:accountId/import`, () =>
    HttpResponse.json(IMPORT_SUCCESS_FIXTURE, { status: 201 }),
  ),
  http.get(`${BASE}/v1/imports`, () => HttpResponse.json(IMPORT_HISTORY_FIXTURE)),

  // ---------------------------------------------------------------------------
  // Step 18 — Dashboard handlers
  // ---------------------------------------------------------------------------
  http.get(`${BASE}/v1/dashboard/summary`, () => HttpResponse.json(DASHBOARD_SUMMARY)),
  http.get(`${BASE}/v1/trades`, () => HttpResponse.json(TRADES_LIST)),
  http.get(`${BASE}/v1/journal/recent`, () => HttpResponse.json(JOURNAL_RECENT)),

  // ---------------------------------------------------------------------------
  // Step 19 — Trade detail handler (default: CLOSED trade)
  // ---------------------------------------------------------------------------
  http.get(`${BASE}/v1/trades/:tradeId`, () => HttpResponse.json(TRADE_DETAIL_CLOSED)),
]

/** Override handler: GET returns 404 (no journal entry). */
export const noEntryHandler = http.get(`${BASE}/v1/journal/trades/:tradeId`, () => {
  return new HttpResponse(null, { status: 404 })
})

// ---------------------------------------------------------------------------
// Auth override handlers (Step 14) — use with server.use(...) in tests
// ---------------------------------------------------------------------------

export const authMeUnauthorizedHandler = http.get(`${BASE}/v1/auth/me`, () => {
  return new HttpResponse(JSON.stringify({ detail: 'Not authenticated' }), {
    status: 401,
    headers: { 'Content-Type': 'application/json' },
  })
})

export const loginInvalidCredentialsHandler = http.post(`${BASE}/v1/auth/login`, () => {
  return new HttpResponse(JSON.stringify({ detail: 'INVALID_CREDENTIALS' }), {
    status: 401,
    headers: { 'Content-Type': 'application/json' },
  })
})

export const loginAccountLockedHandler = http.post(`${BASE}/v1/auth/login`, () => {
  return new HttpResponse(JSON.stringify({ detail: 'ACCOUNT_LOCKED' }), {
    status: 423,
    headers: { 'Content-Type': 'application/json' },
  })
})

export const loginEmailNotVerifiedHandler = http.post(`${BASE}/v1/auth/login`, () => {
  return new HttpResponse(JSON.stringify({ detail: 'EMAIL_NOT_VERIFIED' }), {
    status: 403,
    headers: { 'Content-Type': 'application/json' },
  })
})

export const loginRateLimitedHandler = http.post(`${BASE}/v1/auth/login`, () => {
  return new HttpResponse(JSON.stringify({ detail: 'RATE_LIMITED' }), {
    status: 429,
    headers: { 'Content-Type': 'application/json' },
  })
})

export const registerRateLimitedHandler = http.post(`${BASE}/v1/auth/register`, () => {
  return new HttpResponse(JSON.stringify({ detail: 'RATE_LIMITED' }), {
    status: 429,
    headers: { 'Content-Type': 'application/json' },
  })
})

export const registerPolicyViolationHandler = (detail: string) =>
  http.post(`${BASE}/v1/auth/register`, () => {
    return new HttpResponse(JSON.stringify({ detail }), {
      status: 422,
      headers: { 'Content-Type': 'application/json' },
    })
  })

export const verifyEmailInvalidTokenHandler = http.post(`${BASE}/v1/auth/verify-email`, () => {
  return new HttpResponse(JSON.stringify({ detail: 'INVALID_OR_EXPIRED_TOKEN' }), {
    status: 400,
    headers: { 'Content-Type': 'application/json' },
  })
})

export const passwordResetRateLimitedHandler = http.post(
  `${BASE}/v1/auth/password-reset/request`,
  () => {
    return new HttpResponse(JSON.stringify({ detail: 'RATE_LIMITED' }), {
      status: 429,
      headers: { 'Content-Type': 'application/json' },
    })
  },
)

export const resetConfirmInvalidTokenHandler = http.post(
  `${BASE}/v1/auth/password-reset/confirm`,
  () => {
    return new HttpResponse(JSON.stringify({ detail: 'INVALID_OR_EXPIRED_TOKEN' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    })
  },
)

export const resetConfirmPolicyViolationHandler = (detail: string) =>
  http.post(`${BASE}/v1/auth/password-reset/confirm`, () => {
    return new HttpResponse(JSON.stringify({ detail }), {
      status: 422,
      headers: { 'Content-Type': 'application/json' },
    })
  })

// ---------------------------------------------------------------------------
// Step 15 override handlers
// ---------------------------------------------------------------------------

export const updateProfileInvalidTzHandler = http.patch(`${BASE}/v1/users/me`, () =>
  new HttpResponse(JSON.stringify({ detail: 'INVALID_TIMEZONE' }), {
    status: 422,
    headers: { 'Content-Type': 'application/json' },
  }),
)

export const updateProfileBlankNameHandler = http.patch(`${BASE}/v1/users/me`, () =>
  new HttpResponse(JSON.stringify({ detail: 'DISPLAY_NAME_BLANK' }), {
    status: 422,
    headers: { 'Content-Type': 'application/json' },
  }),
)

export const accountsEmptyHandler = http.get(`${BASE}/v1/accounts`, () =>
  HttpResponse.json([]),
)

export const createAccountInvalidHandler = http.post(`${BASE}/v1/accounts`, () =>
  new HttpResponse(JSON.stringify({ detail: 'VALIDATION_ERROR' }), {
    status: 422,
    headers: { 'Content-Type': 'application/json' },
  }),
)

// ---------------------------------------------------------------------------
// Step 17 — Import fixtures
// ---------------------------------------------------------------------------

export const IMPORT_SUCCESS_FIXTURE = {
  import_record_id: '00000000-0000-0000-0000-000000000501',
  fills_ingested: 42,
  fills_skipped: 3,
  row_errors: 0,
  trades_created: 8,
  trades_closed: 5,
  pnl_succeeded: 5,
  pnl_failed: 0,
  status: 'COMPLETE',
}

export const IMPORT_PARTIAL_FIXTURE = {
  import_record_id: '00000000-0000-0000-0000-000000000502',
  fills_ingested: 20,
  fills_skipped: 0,
  row_errors: 5,
  trades_created: 4,
  trades_closed: 2,
  pnl_succeeded: 2,
  pnl_failed: 0,
  status: 'PARTIAL',
}

export const IMPORT_FAILED_FIXTURE = {
  import_record_id: '00000000-0000-0000-0000-000000000503',
  fills_ingested: 0,
  fills_skipped: 0,
  row_errors: 10,
  trades_created: 0,
  trades_closed: 0,
  pnl_succeeded: 0,
  pnl_failed: 0,
  status: 'FAILED',
}

export const IMPORT_HISTORY_FIXTURE = [
  {
    id: '00000000-0000-0000-0000-000000000501',
    account_id: '00000000-0000-0000-0000-000000000001',
    broker: 'ZERODHA',
    file_name: 'tradebook.csv',
    row_count: 42,
    error_count: 0,
    status: 'COMPLETE',
    imported_at: '2026-09-07T10:00:00Z',
    created_at: '2026-09-07T10:00:00Z',
  },
  {
    id: '00000000-0000-0000-0000-000000000502',
    account_id: '00000000-0000-0000-0000-000000000001',
    broker: 'ZERODHA',
    file_name: 'tradebook2.csv',
    row_count: 20,
    error_count: 5,
    status: 'PARTIAL',
    imported_at: '2026-09-06T10:00:00Z',
    created_at: '2026-09-06T10:00:00Z',
  },
]

export const IMPORT_HISTORY_EMPTY_FIXTURE: typeof IMPORT_HISTORY_FIXTURE = []

// ---------------------------------------------------------------------------
// Step 16 — Trades fixtures
// ---------------------------------------------------------------------------

export const TRADE_OPEN_FIXTURE = {
  id: '00000000-0000-0000-0000-000000000101',
  account_id: '00000000-0000-0000-0000-000000000001',
  instrument_id: '00000000-0000-0000-0000-000000000201',
  trade_type: 'MIS',
  direction: 'LONG',
  status: 'OPEN',
  trade_date: '2026-09-06',
  first_fill_at: '2026-09-06T04:45:00Z',
  last_fill_at: null,
  total_entry_quantity: '10',
  total_exit_quantity: '0',
  net_position: '10',
  average_entry: '500.00',
  average_exit: null,
  planned_stop: null,
  planned_target: null,
  is_deleted: false,
  created_at: '2026-09-06T04:45:00Z',
  updated_at: '2026-09-06T04:45:00Z',
}

// ---------------------------------------------------------------------------
// Step 16 — Trades override handlers
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Step 18 — Dashboard fixtures
// ---------------------------------------------------------------------------

const ACCOUNT_ID_0001 = '00000000-0000-0000-0000-000000000001'

export const DASHBOARD_SUMMARY = {
  account_id: ACCOUNT_ID_0001,
  as_of_date: '2026-09-08',
  all_time_net_pnl: '27500.00',
  mtd_net_pnl: '5000.00',
  wtd_net_pnl: '1500.00',
  starting_capital: '500000.00',
  realized_equity: '527500.00',
  total_closed_trades: 30,
  open_trade_count: 2,
}

export const DASHBOARD_SUMMARY_EMPTY = {
  account_id: ACCOUNT_ID_0001,
  as_of_date: '2026-09-08',
  all_time_net_pnl: '0.00',
  mtd_net_pnl: '0.00',
  wtd_net_pnl: '0.00',
  starting_capital: null,
  realized_equity: null,
  total_closed_trades: 0,
  open_trade_count: 0,
}

const TRADES_LIST_ITEMS = Array.from({ length: 10 }, (_, i) => ({
  id: `trade-${String(i + 1).padStart(3, '0')}`,
  account_id: ACCOUNT_ID_0001,
  symbol: `SYM${i + 1}`,
  instrument_type: 'EQ',
  direction: i % 2 === 0 ? 'LONG' : 'SHORT',
  status: 'CLOSED',
  trade_date: '2026-09-01',
  last_fill_at: `2026-09-0${(i % 7) + 1}T10:00:00Z`,
  net_pnl: i % 3 === 0 ? String(-(i + 1) * 100) : String((i + 1) * 200),
  r_multiple: i % 3 === 0 ? '-1.00' : '1.50',
}))

export const TRADES_LIST = {
  items: TRADES_LIST_ITEMS,
  total: 10,
  limit: 25,
  offset: 0,
}

export const TRADES_LIST_EMPTY = {
  items: [],
  total: 0,
  limit: 25,
  offset: 0,
}

export const TRADES_LIST_FILTERED = {
  items: TRADES_LIST_ITEMS.slice(0, 3).map(t => ({ ...t, direction: 'LONG' })),
  total: 3,
  limit: 25,
  offset: 0,
}

// ---------------------------------------------------------------------------
// Step 19 — Trade Detail fixtures
// ---------------------------------------------------------------------------

const TRADE_DETAIL_FILLS_CLOSED = [
  {
    id: 'fill-001',
    side: 'BUY',
    quantity: '100',
    price: '2850.00',
    fill_role: 'ENTRY',
    fill_timestamp: '2026-09-01T09:15:00+05:30',
    import_source: 'CSV',
    broker: 'ZERODHA',
  },
  {
    id: 'fill-002',
    side: 'BUY',
    quantity: '50',
    price: '2840.00',
    fill_role: 'ENTRY',
    fill_timestamp: '2026-09-01T09:20:00+05:30',
    import_source: 'CSV',
    broker: 'ZERODHA',
  },
  {
    id: 'fill-003',
    side: 'SELL',
    quantity: '150',
    price: '2950.00',
    fill_role: 'EXIT',
    fill_timestamp: '2026-09-01T11:45:00+05:30',
    import_source: 'CSV',
    broker: 'ZERODHA',
  },
]

export const TRADE_DETAIL_CLOSED = {
  id: 'trade-detail-001',
  account_id: ACCOUNT_ID_0001,
  symbol: 'RELIANCE',
  instrument_name: 'RELIANCE INDUSTRIES LTD',
  exchange_segment: 'NSE_FO',
  instrument_type: 'FUT',
  expiry_date: '2026-09-25',
  strike_price: null,
  direction: 'LONG',
  trade_type: 'MIS',
  status: 'CLOSED',
  trade_date: '2026-09-01',
  first_fill_at: '2026-09-01T09:15:00+05:30',
  last_fill_at: '2026-09-01T11:45:00+05:30',
  total_entry_quantity: '150',
  total_exit_quantity: '150',
  average_entry: '2846.67',
  average_exit: '2950.00',
  planned_stop: '2800.00',
  planned_target: '2950.00',
  planned_risk_amount: '7000.00',
  setup_name: 'Bull flag breakout',
  hold_duration_seconds: 8100,
  fills: TRADE_DETAIL_FILLS_CLOSED,
  pnl: {
    gross_pnl: '15500.00',
    net_pnl: '14200.00',
    total_charges: '1300.00',
    brokerage: '40.00',
    stt: '235.00',
    exchange_charges: '185.00',
    sebi_charges: '12.00',
    stamp_duty: '43.00',
    gst: '40.50',
    ipft: '9.00',
    r_multiple: '2.03',
  },
}

export const TRADE_DETAIL_OPEN = {
  id: 'trade-detail-002',
  account_id: ACCOUNT_ID_0001,
  symbol: 'INFY',
  instrument_name: 'INFOSYS LTD',
  exchange_segment: 'NSE_EQ',
  instrument_type: 'EQ',
  expiry_date: null,
  strike_price: null,
  direction: 'LONG',
  trade_type: 'CNC',
  status: 'OPEN',
  trade_date: '2026-09-05',
  first_fill_at: '2026-09-05T09:30:00+05:30',
  last_fill_at: null,
  total_entry_quantity: '200',
  total_exit_quantity: '0',
  average_entry: '1550.00',
  average_exit: null,
  planned_stop: '1500.00',
  planned_target: '1650.00',
  planned_risk_amount: '10000.00',
  setup_name: null,
  hold_duration_seconds: null,
  fills: [
    {
      id: 'fill-101',
      side: 'BUY',
      quantity: '200',
      price: '1550.00',
      fill_role: 'ENTRY',
      fill_timestamp: '2026-09-05T09:30:00+05:30',
      import_source: 'CSV',
      broker: 'ZERODHA',
    },
  ],
  pnl: null,
}

export const TRADE_DETAIL_PARTIAL = {
  id: 'trade-detail-003',
  account_id: ACCOUNT_ID_0001,
  symbol: 'HDFC',
  instrument_name: 'HDFC BANK LTD',
  exchange_segment: 'NSE_EQ',
  instrument_type: 'EQ',
  expiry_date: null,
  strike_price: null,
  direction: 'LONG',
  trade_type: 'CNC',
  status: 'PARTIAL',
  trade_date: '2026-09-03',
  first_fill_at: '2026-09-03T09:15:00+05:30',
  last_fill_at: '2026-09-03T11:00:00+05:30',
  total_entry_quantity: '100',
  total_exit_quantity: '50',
  average_entry: '1700.00',
  average_exit: '1750.00',
  planned_stop: null,
  planned_target: null,
  planned_risk_amount: null,
  setup_name: null,
  hold_duration_seconds: 6300,
  fills: [
    {
      id: 'fill-201',
      side: 'BUY',
      quantity: '100',
      price: '1700.00',
      fill_role: 'ENTRY',
      fill_timestamp: '2026-09-03T09:15:00+05:30',
      import_source: 'CSV',
      broker: 'ZERODHA',
    },
    {
      id: 'fill-202',
      side: 'SELL',
      quantity: '50',
      price: '1750.00',
      fill_role: 'EXIT',
      fill_timestamp: '2026-09-03T11:00:00+05:30',
      import_source: 'CSV',
      broker: 'ZERODHA',
    },
  ],
  pnl: null,
}

export const TRADE_DETAIL_SCALP = {
  ...TRADE_DETAIL_CLOSED,
  id: 'trade-detail-004',
  symbol: 'TCS',
  instrument_name: 'TATA CONSULTANCY SERVICES LTD',
  hold_duration_seconds: 45,
}

export const TRADE_DETAIL_NOT_FOUND_RESPONSE = { detail: 'TRADE_NOT_FOUND' }

export const JOURNAL_RECENT = Array.from({ length: 5 }, (_, i) => ({
  trade_id: `trade-${String(i + 1).padStart(3, '0')}`,
  symbol: `SYM${i + 1}`,
  instrument_type: 'EQUITY',
  trade_date: `2026-09-0${i + 1}`,
  last_fill_at: `2026-09-0${i + 1}T10:00:00Z`,
  discipline_score: 7 + (i % 3),
  emotion_before: i % 2 === 0 ? 'CALM' : 'ANXIOUS',
  emotion_during: 'CONFIDENT',
  emotion_after: i % 2 === 0 ? 'SATISFIED' : 'CALM',
}))

export const JOURNAL_RECENT_EMPTY: typeof JOURNAL_RECENT = []

// ---------------------------------------------------------------------------
// Step 17 — Import override handlers
// ---------------------------------------------------------------------------

export const importPartialHandler = http.post(`${BASE}/v1/accounts/:accountId/import`, () =>
  HttpResponse.json(IMPORT_PARTIAL_FIXTURE, { status: 201 }),
)

export const importFailedStatusHandler = http.post(`${BASE}/v1/accounts/:accountId/import`, () =>
  HttpResponse.json(IMPORT_FAILED_FIXTURE, { status: 201 }),
)

export const importDuplicateHandler = http.post(`${BASE}/v1/accounts/:accountId/import`, () =>
  new HttpResponse(JSON.stringify({ detail: 'DUPLICATE_IMPORT' }), {
    status: 409,
    headers: { 'Content-Type': 'application/json' },
  }),
)

export const importFileTooLargeHandler = http.post(`${BASE}/v1/accounts/:accountId/import`, () =>
  new HttpResponse(JSON.stringify({ detail: 'FILE_TOO_LARGE' }), {
    status: 413,
    headers: { 'Content-Type': 'application/json' },
  }),
)

export const importEmptyFileHandler = http.post(`${BASE}/v1/accounts/:accountId/import`, () =>
  new HttpResponse(JSON.stringify({ detail: 'EMPTY_FILE' }), {
    status: 422,
    headers: { 'Content-Type': 'application/json' },
  }),
)

export const importUnrecognizedFormatHandler = http.post(
  `${BASE}/v1/accounts/:accountId/import`,
  () =>
    new HttpResponse(JSON.stringify({ detail: 'UNRECOGNIZED_FILE_FORMAT' }), {
      status: 422,
      headers: { 'Content-Type': 'application/json' },
    }),
)

export const importMissingProductTypeHandler = http.post(
  `${BASE}/v1/accounts/:accountId/import`,
  () =>
    new HttpResponse(JSON.stringify({ detail: 'MISSING_PRODUCT_TYPE' }), {
      status: 422,
      headers: { 'Content-Type': 'application/json' },
    }),
)

export const importAccountInactiveHandler = http.post(
  `${BASE}/v1/accounts/:accountId/import`,
  () =>
    new HttpResponse(JSON.stringify({ detail: 'ACCOUNT_INACTIVE' }), {
      status: 422,
      headers: { 'Content-Type': 'application/json' },
    }),
)

export const importHistoryEmptyHandler = http.get(`${BASE}/v1/imports`, () =>
  HttpResponse.json(IMPORT_HISTORY_EMPTY_FIXTURE),
)

// ---------------------------------------------------------------------------
// Step 19 — Trade detail override handlers
// ---------------------------------------------------------------------------

export const tradeDetailOpenHandler = http.get(`${BASE}/v1/trades/:tradeId`, () =>
  HttpResponse.json(TRADE_DETAIL_OPEN),
)

export const tradeDetailPartialHandler = http.get(`${BASE}/v1/trades/:tradeId`, () =>
  HttpResponse.json(TRADE_DETAIL_PARTIAL),
)

export const tradeDetailScalpHandler = http.get(`${BASE}/v1/trades/:tradeId`, () =>
  HttpResponse.json(TRADE_DETAIL_SCALP),
)

export const tradeDetailNotFoundHandler = http.get(`${BASE}/v1/trades/:tradeId`, () =>
  new HttpResponse(JSON.stringify(TRADE_DETAIL_NOT_FOUND_RESPONSE), {
    status: 404,
    headers: { 'Content-Type': 'application/json' },
  }),
)

export const tradesListFilteredHandler = http.get(`${BASE}/v1/trades`, () =>
  HttpResponse.json(TRADES_LIST_FILTERED),
)

export const tradesListEmptyHandler = http.get(`${BASE}/v1/trades`, () =>
  HttpResponse.json(TRADES_LIST_EMPTY),
)

export const accountsNonZerodhaActiveHandler = http.get(`${BASE}/v1/accounts`, () =>
  HttpResponse.json([
    {
      id: '00000000-0000-0000-0000-000000000003',
      user_id: '00000000-0000-0000-0000-000000000099',
      broker: 'ANGEL_ONE',
      display_name: 'Angel One Account',
      account_type: 'INDIVIDUAL',
      base_currency: 'INR',
      status: 'ACTIVE',
      created_at: '2026-08-01T10:00:00Z',
      updated_at: '2026-08-01T10:00:00Z',
    },
  ]),
)

// ---------------------------------------------------------------------------
// Step 16 — Trades override handlers
// ---------------------------------------------------------------------------

export const createTradeInstrumentNotFoundHandler = http.post(`${BASE}/v1/trades`, () =>
  new HttpResponse(JSON.stringify({ detail: 'INSTRUMENT_NOT_FOUND' }), {
    status: 422,
    headers: { 'Content-Type': 'application/json' },
  }),
)

export const createTradeFillsNotChronologicalHandler = http.post(`${BASE}/v1/trades`, () =>
  new HttpResponse(JSON.stringify({ detail: 'FILLS_NOT_CHRONOLOGICAL' }), {
    status: 422,
    headers: { 'Content-Type': 'application/json' },
  }),
)
