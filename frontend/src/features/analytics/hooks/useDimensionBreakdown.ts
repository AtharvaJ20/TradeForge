import { useQuery } from '@tanstack/react-query'
import { fetchDimensionBreakdown } from '../api'
import type { AnalyticsFilterParams } from '../types'

export const dimensionBreakdownKeys = {
  all: (params: AnalyticsFilterParams = {}, dimension: string) =>
    ['analytics', 'breakdown', dimension, params] as const,
}

export function useDimensionBreakdown(
  params: AnalyticsFilterParams = {},
  dimension = 'direction',
) {
  return useQuery({
    queryKey: dimensionBreakdownKeys.all(params, dimension),
    queryFn: () => fetchDimensionBreakdown(params, dimension),
    retry: 1,
  })
}
