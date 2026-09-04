import { useQuery } from '@tanstack/react-query'
import { fetchRDistribution } from '../api'
import type { AnalyticsFilterParams } from '../types'

export const rDistributionKeys = {
  all: (params: AnalyticsFilterParams = {}) =>
    ['analytics', 'r-distribution', params] as const,
}

export function useRDistribution(params: AnalyticsFilterParams = {}) {
  return useQuery({
    queryKey: rDistributionKeys.all(params),
    queryFn: () => fetchRDistribution(params),
    retry: 1,
  })
}
