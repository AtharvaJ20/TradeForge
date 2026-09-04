import { useQuery } from '@tanstack/react-query'
import { fetchTimeOfDay } from '../api'
import type { AnalyticsFilterParams } from '../types'

export const timeOfDayKeys = {
  all: (params: AnalyticsFilterParams = {}) => ['analytics', 'time-of-day', params] as const,
}

export function useTimeOfDay(params: AnalyticsFilterParams = {}) {
  return useQuery({
    queryKey: timeOfDayKeys.all(params),
    queryFn: () => fetchTimeOfDay(params),
    retry: 1,
  })
}
