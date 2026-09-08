import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '../api'

export function useRecentJournal(accountId: string) {
  return useQuery({
    queryKey: ['dashboard', 'journal', accountId],
    queryFn: () => dashboardApi.getRecentJournal(accountId, 5),
    retry: 1,
    enabled: !!accountId,
  })
}
