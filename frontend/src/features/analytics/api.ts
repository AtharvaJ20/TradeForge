import { apiClient } from '@/lib/api-client'
import { AnalyticsSummarySchema } from './schemas'
import type { AnalyticsSummary } from './types'

export async function fetchAnalyticsSummary(): Promise<AnalyticsSummary> {
  const raw = await apiClient.get('/v1/analytics/summary')
  return AnalyticsSummarySchema.parse(raw)
}
