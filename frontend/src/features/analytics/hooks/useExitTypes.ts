import { useQuery } from '@tanstack/react-query'
import { fetchExitTypes } from '../api'
import type { AnalyticsFilterParams } from '../types'

export const exitTypesKeys = {
  all: (params: AnalyticsFilterParams = {}) =>
    ['analytics', 'exit-types', params] as const,
}

export function useExitTypes(params: AnalyticsFilterParams = {}) {
  return useQuery({
    queryKey: exitTypesKeys.all(params),
    queryFn: () => fetchExitTypes(params),
    retry: 1,
  })
}
