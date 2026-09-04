import { useQuery } from '@tanstack/react-query'
import { fetchRiskSummary } from '../api'
import type { AnalyticsFilterParams } from '../types'

export const riskSummaryKeys = {
  all: (params: AnalyticsFilterParams = {}) =>
    ['risk', 'summary', params] as const,
}

export function useRiskSummary(params: AnalyticsFilterParams = {}) {
  return useQuery({
    queryKey: riskSummaryKeys.all(params),
    queryFn: () => fetchRiskSummary(params),
    retry: 1,
  })
}
