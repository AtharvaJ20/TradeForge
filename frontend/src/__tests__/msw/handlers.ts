import { http, HttpResponse } from 'msw'

const BASE = 'http://localhost:8000'

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

export const handlers = [
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
