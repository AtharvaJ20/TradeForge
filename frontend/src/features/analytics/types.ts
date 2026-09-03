import type { z } from 'zod'
import type {
  AccountDimensionSchema,
  AnalyticsSummarySchema,
  RiskAdjustedSchema,
  SharpeResultSchema,
  SortinoResultSchema,
} from './schemas'

export type AccountDimension = z.infer<typeof AccountDimensionSchema>
export type AnalyticsSummary = z.infer<typeof AnalyticsSummarySchema>
export type RiskAdjusted = z.infer<typeof RiskAdjustedSchema>
export type SharpeResult = z.infer<typeof SharpeResultSchema>
export type SortinoResult = z.infer<typeof SortinoResultSchema>

// Sub-types derived from the top-level summary — used as component prop types.
export type PnlSummary = AnalyticsSummary['pnl']
export type OutcomeDistribution = AnalyticsSummary['outcome']
export type ExpectancyResult = AnalyticsSummary['expectancy']
export type ProfitFactor = AnalyticsSummary['profit_factor']
export type PlannedRR = AnalyticsSummary['planned_rr']
export type DrawdownStats = AnalyticsSummary['drawdown']
export type DirectionPerformance = AnalyticsSummary['direction'][number]
export type ChargesBreakdown = AnalyticsSummary['charges']

/** All 9 global filter dimensions accepted by every /v1/analytics endpoint. */
export interface AnalyticsFilterParams {
  date_from?: string
  date_to?: string
  account_ids?: string[]
  instrument_types?: string[]
  exchange_segments?: string[]
  trade_types?: string[]
  directions?: string[]
  setup_names?: string[]
  brokers?: string[]
}
