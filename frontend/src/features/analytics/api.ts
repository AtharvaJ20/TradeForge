import { apiClient } from '@/lib/api-client'
import {
  AnalyticsSummarySchema,
  FilterAccountsSchema,
  FilterBrokersSchema,
  FilterSetupsSchema,
} from './schemas'
import type { AccountDimension, AnalyticsSummary, AnalyticsFilterParams } from './types'

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

export async function fetchFilterAccounts(): Promise<AccountDimension[]> {
  const raw = await apiClient.get('/v1/analytics/filters/accounts')
  return FilterAccountsSchema.parse(raw)
}

export async function fetchFilterSetups(): Promise<string[]> {
  const raw = await apiClient.get('/v1/analytics/filters/setups')
  return FilterSetupsSchema.parse(raw)
}

export async function fetchFilterBrokers(): Promise<string[]> {
  const raw = await apiClient.get('/v1/analytics/filters/brokers')
  return FilterBrokersSchema.parse(raw)
}
