import { apiClient } from '@/lib/api-client'
import type { TradeListPageOut } from '../trades/types'
import type { DashboardSummaryOut, TradeListItemOut, RecentJournalItemOut } from './types'

export const dashboardApi = {
  getSummary: (accountId: string) =>
    apiClient.get<DashboardSummaryOut>(`/v1/dashboard/summary?account_id=${accountId}`),

  listTrades: async (
    accountId: string,
    params?: {
      status?: string
      limit?: number
      offset?: number
      sort_by?: string
      sort_dir?: string
    },
  ): Promise<TradeListItemOut[]> => {
    const qs = new URLSearchParams({ account_id: accountId, limit: String(params?.limit ?? 10) })
    if (params?.status) qs.set('status', params.status)
    if (params?.offset) qs.set('offset', String(params.offset))
    if (params?.sort_by) qs.set('sort_by', params.sort_by)
    if (params?.sort_dir) qs.set('sort_dir', params.sort_dir)
    const page = await apiClient.get<TradeListPageOut>(`/v1/trades?${qs}`)
    return page.items
  },

  getRecentJournal: (accountId: string, limit = 5) =>
    apiClient.get<RecentJournalItemOut[]>(
      `/v1/journal/recent?account_id=${accountId}&limit=${limit}`,
    ),
}
