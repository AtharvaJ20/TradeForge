import { apiClient } from '@/lib/api-client'
import { AnalyticsSummarySchema } from './schemas'
import type { AnalyticsSummary, AnalyticsFilterParams } from './types'

function buildQueryString(params: AnalyticsFilterParams): string {
  const parts: string[] = []
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue
    if (Array.isArray(value)) {
      for (const item of value) {
        parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(item))}`)
      }
    } else {
      parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    }
  }
  return parts.length > 0 ? `?${parts.join('&')}` : ''
}

export async function fetchAnalyticsSummary(
  params: AnalyticsFilterParams = {},
): Promise<AnalyticsSummary> {
  const qs = buildQueryString(params)
  const raw = await apiClient.get(`/v1/analytics/summary${qs}`)
  return AnalyticsSummarySchema.parse(raw)
}
