import { apiClient } from '@/lib/api-client'
import type { CreateTradeBody, AddFillBody, Trade, TradeListPageOut, TradeDetailOut } from './types'

export const tradesApi = {
  create: (body: CreateTradeBody) =>
    apiClient.post<Trade>('/v1/trades', body),
  addFill: (tradeId: string, body: AddFillBody) =>
    apiClient.post<Trade>(`/v1/trades/${tradeId}/fills`, body),
  delete: (tradeId: string) =>
    apiClient.delete<void>(`/v1/trades/${tradeId}`),

  listTrades: (params: {
    account_id?: string
    status?: string
    direction?: string
    trade_type?: string
    from_date?: string
    to_date?: string
    instrument?: string
    limit?: number
    offset?: number
    sort_by?: string
    sort_dir?: string
  }) => {
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v != null && v !== '') qs.set(k, String(v))
    })
    return apiClient.get<TradeListPageOut>(`/v1/trades?${qs}`)
  },

  getTradeDetail: (tradeId: string) =>
    apiClient.get<TradeDetailOut>(`/v1/trades/${tradeId}`),
}
