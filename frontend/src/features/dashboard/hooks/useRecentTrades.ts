import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '../api'

export function useRecentTrades(accountId: string) {
  return useQuery({
    queryKey: ['dashboard', 'trades', accountId],
    queryFn: () =>
      dashboardApi.listTrades(accountId, {
        status: 'CLOSED',
        limit: 10,
        sort_by: 'last_fill_at',
        sort_dir: 'desc',
      }),
    retry: 1,
    enabled: !!accountId,
  })
}
