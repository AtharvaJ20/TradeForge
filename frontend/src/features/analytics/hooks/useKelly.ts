import { useQuery } from '@tanstack/react-query'
import { fetchKelly } from '../api'
import type { AnalyticsFilterParams } from '../types'

export const kellyKeys = {
  all: (params: AnalyticsFilterParams = {}) => ['analytics', 'kelly', params] as const,
}

export function useKelly(params: AnalyticsFilterParams = {}) {
  return useQuery({
    queryKey: kellyKeys.all(params),
    queryFn: () => fetchKelly(params),
    retry: 1,
  })
}
