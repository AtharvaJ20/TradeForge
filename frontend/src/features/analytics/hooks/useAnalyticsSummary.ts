import { useQuery } from '@tanstack/react-query'
import { fetchAnalyticsSummary } from '../api'

export const analyticsKeys = {
  summary: () => ['analytics', 'summary'] as const,
}

export function useAnalyticsSummary() {
  return useQuery({
    queryKey: analyticsKeys.summary(),
    queryFn: fetchAnalyticsSummary,
    retry: 1,
  })
}
