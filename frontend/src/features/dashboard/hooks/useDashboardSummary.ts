import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '../api'

export function useDashboardSummary(accountId: string) {
  return useQuery({
    queryKey: ['dashboard', 'summary', accountId],
    queryFn: () => dashboardApi.getSummary(accountId),
    retry: 1,
    enabled: !!accountId,
  })
}
