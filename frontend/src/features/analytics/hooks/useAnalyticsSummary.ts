import { useQuery } from '@tanstack/react-query'
import { fetchAnalyticsSummary } from '../api'
import type { AnalyticsFilterParams } from '../types'

export const analyticsKeys = {
  summary: (params: AnalyticsFilterParams = {}) =>
    ['analytics', 'summary', params] as const,
}

export function useAnalyticsSummary(params: AnalyticsFilterParams = {}) {
  return useQuery({
    queryKey: analyticsKeys.summary(params),
    queryFn: () => fetchAnalyticsSummary(params),
    retry: 1,
  })
}
