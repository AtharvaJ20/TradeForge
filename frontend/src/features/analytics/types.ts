import type { z } from 'zod'
import type {
  AccountDimensionSchema,
  AnalyticsSummarySchema,
  DimensionBreakdownSchema,
  DimensionGroupSchema,
  ExitTypeRowSchema,
  ExitTypesSchema,
  HoldDurationBucketSchema,
  HoldDurationSchema,
  KellySchema,
  RBucketSchema,
  RDistributionSchema,
  RiskAdjustedSchema,
  RiskSummarySchema,
  RollingExpectancyPointSchema,
  RollingExpectancySchema,
  SharpeResultSchema,
  SortinoResultSchema,
  StreaksSchema,
  TimeOfDayBucketSchema,
  TimeOfDaySchema,
} from './schemas'

export type AccountDimension = z.infer<typeof AccountDimensionSchema>
export type AnalyticsSummary = z.infer<typeof AnalyticsSummarySchema>
export type RiskAdjusted = z.infer<typeof RiskAdjustedSchema>
export type SharpeResult = z.infer<typeof SharpeResultSchema>
export type SortinoResult = z.infer<typeof SortinoResultSchema>

// Step 12.5 behavioral analytics types
export type Streaks = z.infer<typeof StreaksSchema>
export type HoldDurationBucket = z.infer<typeof HoldDurationBucketSchema>
export type HoldDuration = z.infer<typeof HoldDurationSchema>
export type ExitTypeRow = z.infer<typeof ExitTypeRowSchema>
export type ExitTypes = z.infer<typeof ExitTypesSchema>

// Step 12.6 M-6 + M-10 types
export type RBucket = z.infer<typeof RBucketSchema>
export type RDistribution = z.infer<typeof RDistributionSchema>
export type DimensionGroup = z.infer<typeof DimensionGroupSchema>
export type DimensionBreakdown = z.infer<typeof DimensionBreakdownSchema>

// Step 12.7 N-4 + N-2 + N-1 types
export type Kelly = z.infer<typeof KellySchema>
export type RiskSummary = z.infer<typeof RiskSummarySchema>
export type TimeOfDayBucket = z.infer<typeof TimeOfDayBucketSchema>
export type TimeOfDay = z.infer<typeof TimeOfDaySchema>
export type RollingExpectancyPoint = z.infer<typeof RollingExpectancyPointSchema>
export type RollingExpectancy = z.infer<typeof RollingExpectancySchema>

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
