import { useQuery } from '@tanstack/react-query'
import { fetchRollingExpectancy } from '../api'
import type { AnalyticsFilterParams } from '../types'

export const rollingExpectancyKeys = {
  all: (params: AnalyticsFilterParams = {}) =>
    ['analytics', 'rolling-expectancy', params] as const,
}

export function useRollingExpectancy(params: AnalyticsFilterParams = {}) {
  return useQuery({
    queryKey: rollingExpectancyKeys.all(params),
    queryFn: () => fetchRollingExpectancy(params),
    retry: 1,
  })
}
