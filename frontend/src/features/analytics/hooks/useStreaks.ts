import { useQuery } from '@tanstack/react-query'
import { fetchStreaks } from '../api'
import type { AnalyticsFilterParams } from '../types'

export const streaksKeys = {
  all: (params: AnalyticsFilterParams = {}) =>
    ['analytics', 'streaks', params] as const,
}

export function useStreaks(params: AnalyticsFilterParams = {}) {
  return useQuery({
    queryKey: streaksKeys.all(params),
    queryFn: () => fetchStreaks(params),
    retry: 1,
  })
}
