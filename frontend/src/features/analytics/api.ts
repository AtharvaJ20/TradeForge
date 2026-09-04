import { apiClient } from '@/lib/api-client'
import {
  AnalyticsSummarySchema,
  DimensionBreakdownSchema,
  ExitTypesSchema,
  FilterAccountsSchema,
  FilterBrokersSchema,
  FilterSetupsSchema,
  HoldDurationSchema,
  KellySchema,
  RDistributionSchema,
  RollingExpectancySchema,
  StreaksSchema,
  TimeOfDaySchema,
} from './schemas'
import type {
  AccountDimension,
  AnalyticsSummary,
  AnalyticsFilterParams,
  DimensionBreakdown,
  ExitTypes,
  HoldDuration,
  Kelly,
  RDistribution,
  RollingExpectancy,
  Streaks,
  TimeOfDay,
} from './types'

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

export async function fetchStreaks(params: AnalyticsFilterParams = {}): Promise<Streaks> {
  const qs = buildQueryString(params)
  const raw = await apiClient.get(`/v1/analytics/streaks${qs}`)
  return StreaksSchema.parse(raw)
}

export async function fetchHoldDuration(
  params: AnalyticsFilterParams = {},
): Promise<HoldDuration> {
  const qs = buildQueryString(params)
  const raw = await apiClient.get(`/v1/analytics/hold-duration${qs}`)
  return HoldDurationSchema.parse(raw)
}

export async function fetchExitTypes(params: AnalyticsFilterParams = {}): Promise<ExitTypes> {
  const qs = buildQueryString(params)
  const raw = await apiClient.get(`/v1/analytics/by-exit-type${qs}`)
  return ExitTypesSchema.parse(raw)
}

export async function fetchRDistribution(
  params: AnalyticsFilterParams = {},
): Promise<RDistribution> {
  const qs = buildQueryString(params)
  const raw = await apiClient.get(`/v1/analytics/r-distribution${qs}`)
  return RDistributionSchema.parse(raw)
}

export async function fetchKelly(params: AnalyticsFilterParams = {}): Promise<Kelly> {
  const qs = buildQueryString(params)
  const raw = await apiClient.get(`/v1/analytics/kelly${qs}`)
  return KellySchema.parse(raw)
}

export async function fetchTimeOfDay(params: AnalyticsFilterParams = {}): Promise<TimeOfDay> {
  const qs = buildQueryString(params)
  const raw = await apiClient.get(`/v1/analytics/time-of-day${qs}`)
  return TimeOfDaySchema.parse(raw)
}

export async function fetchRollingExpectancy(
  params: AnalyticsFilterParams = {},
): Promise<RollingExpectancy> {
  const qs = buildQueryString(params)
  const raw = await apiClient.get(`/v1/analytics/rolling-expectancy${qs}`)
  return RollingExpectancySchema.parse(raw)
}

export async function fetchDimensionBreakdown(
  params: AnalyticsFilterParams = {},
  dimension = 'direction',
): Promise<DimensionBreakdown> {
  const filterQs = buildQueryString(params)
  const dimParam = `dimension=${encodeURIComponent(dimension)}`
  const qs = filterQs ? `${filterQs}&${dimParam}` : `?${dimParam}`
  const raw = await apiClient.get(`/v1/analytics/breakdown${qs}`)
  return DimensionBreakdownSchema.parse(raw)
}
