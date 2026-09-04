import { useQuery } from '@tanstack/react-query'
import { fetchHoldDuration } from '../api'
import type { AnalyticsFilterParams } from '../types'

export const holdDurationKeys = {
  all: (params: AnalyticsFilterParams = {}) =>
    ['analytics', 'hold-duration', params] as const,
}

export function useHoldDuration(params: AnalyticsFilterParams = {}) {
  return useQuery({
    queryKey: holdDurationKeys.all(params),
    queryFn: () => fetchHoldDuration(params),
    retry: 1,
  })
}
