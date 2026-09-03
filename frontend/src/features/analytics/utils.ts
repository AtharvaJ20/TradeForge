import type { AnalyticsFilterParams } from './types'

/**
 * Count how many filter dimensions are currently active.
 *
 * Decision D-3: counts dimensions (not selected values within them).
 * Date range counts as 1 if either date_from or date_to is set.
 * Each array dimension counts as 1 if it has ≥1 selected value.
 */
export function countActiveFilterDimensions(params: AnalyticsFilterParams): number {
  let count = 0

  if (params.date_from || params.date_to) count++
  if (params.account_ids && params.account_ids.length > 0) count++
  if (params.setup_names && params.setup_names.length > 0) count++
  if (params.brokers && params.brokers.length > 0) count++
  if (params.directions && params.directions.length > 0) count++
  if (params.trade_types && params.trade_types.length > 0) count++
  if (params.instrument_types && params.instrument_types.length > 0) count++
  if (params.exchange_segments && params.exchange_segments.length > 0) count++

  return count
}
