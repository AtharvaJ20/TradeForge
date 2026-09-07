import { apiClient } from '@/lib/api-client'
import type { CreateTradeBody, AddFillBody, Trade } from './types'

export const tradesApi = {
  create: (body: CreateTradeBody) =>
    apiClient.post<Trade>('/v1/trades', body),
  addFill: (tradeId: string, body: AddFillBody) =>
    apiClient.post<Trade>(`/v1/trades/${tradeId}/fills`, body),
  delete: (tradeId: string) =>
    apiClient.delete<void>(`/v1/trades/${tradeId}`),
}
