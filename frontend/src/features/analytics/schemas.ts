import { z } from 'zod'

// Pydantic v2 serialises Decimal fields as strings in JSON mode.
const decimalString = z.string().nullable()

export const SharpeResultSchema = z.object({
  sharpe_ratio: decimalString,
  mean_r: decimalString,
  std_r: decimalString,
  n_per_year: z.number().int(),
  r_coverage_count: z.number().int(),
  insufficient_sample: z.boolean(),
})

export const SortinoResultSchema = z.object({
  sortino_ratio: decimalString,
  mean_r: decimalString,
  downside_dev: decimalString,
  n_per_year: z.number().int(),
  r_coverage_count: z.number().int(),
  insufficient_sample: z.boolean(),
  no_downside_trades: z.boolean(),
})

export const RiskAdjustedSchema = z.object({
  sharpe: SharpeResultSchema,
  sortino: SortinoResultSchema,
})

// Stub schemas for summary fields not yet rendered.
// Full validation keeps the contract honest even before dedicated panels exist.
const PnlSummarySchema = z.object({
  total_trades: z.number().int(),
  gross_pnl: z.string(),
  net_pnl: z.string(),
  total_charges: z.string(),
})

const OutcomeDistributionSchema = z.object({
  win_count: z.number().int(),
  loss_count: z.number().int(),
  breakeven_count: z.number().int(),
  total_n: z.number().int(),
  win_rate: z.string(),
  loss_rate: z.string(),
  breakeven_rate: z.string(),
})

const ExpectancyResultSchema = z.object({
  expectancy_r: decimalString,
  avg_r_win: decimalString,
  avg_r_loss: decimalString,
  r_coverage_count: z.number().int(),
  total_count: z.number().int(),
  r_coverage_pct: z.string(),
  insufficient_sample: z.boolean(),
})

const ProfitFactorSchema = z.object({
  profit_factor: decimalString,
  gross_profit: z.string(),
  gross_loss: z.string(),
})

const PlannedRRSchema = z.object({
  avg_planned_rr: decimalString,
  trade_count_with_rr: z.number().int(),
  total_count: z.number().int(),
  coverage_pct: z.string(),
})

const DrawdownStatsSchema = z.object({
  max_drawdown_pct: decimalString,
  max_drawdown_inr: decimalString,
  avg_drawdown_pct: decimalString,
  current_drawdown_pct: decimalString,
})

const DirectionPerformanceSchema = z.object({
  direction: z.string(),
  trade_count: z.number().int(),
  win_count: z.number().int(),
  loss_count: z.number().int(),
  breakeven_count: z.number().int(),
  win_rate: z.string(),
  avg_net_pnl: z.string(),
  total_net_pnl: z.string(),
  avg_r_multiple: decimalString,
})

const ChargesBreakdownSchema = z.object({
  total_brokerage: z.string(),
  total_stt: z.string(),
  total_exchange_charges: z.string(),
  total_sebi_charges: z.string(),
  total_stamp_duty: z.string(),
  total_gst: z.string(),
  total_ipft: z.string(),
  total_charges: z.string(),
  total_gross_pnl: z.string(),
  charge_drag_pct: decimalString,
  charges_added_to_loss: decimalString,
})

// ---------------------------------------------------------------------------
// Filter dimension schemas (Step 12.4)
// ---------------------------------------------------------------------------

export const AccountDimensionSchema = z.object({
  id: z.string().uuid(),
  label: z.string(),
})

export const FilterAccountsSchema = z.array(AccountDimensionSchema)
export const FilterSetupsSchema = z.array(z.string())
export const FilterBrokersSchema = z.array(z.string())

// ---------------------------------------------------------------------------
// Behavioral analytics schemas (Step 12.5 — M-12, M-13, M-14)
// ---------------------------------------------------------------------------

export const StreaksSchema = z.object({
  current_win_streak: z.number().int(),
  current_loss_streak: z.number().int(),
  max_win_streak: z.number().int(),
  max_loss_streak: z.number().int(),
  avg_win_streak: z.string(),
  avg_loss_streak: z.string(),
})

export const HoldDurationBucketSchema = z.object({
  bucket: z.string(),
  bucket_order: z.number().int(),
  count: z.number().int(),
  avg_net_pnl: z.string(),
  win_rate: z.string(),
})

export const HoldDurationSchema = z.object({
  buckets: z.array(HoldDurationBucketSchema),
  avg_duration_minutes: z.string().nullable(),
  median_duration_minutes: z.string().nullable(),
})

export const ExitTypeRowSchema = z.object({
  exit_type: z.string().nullable(),
  trade_count: z.number().int(),
  win_rate: z.string(),
  avg_net_pnl: z.string(),
  avg_r_multiple: z.string().nullable(),
})

export const ExitTypesSchema = z.array(ExitTypeRowSchema)

// ---------------------------------------------------------------------------
// M-6 R-Multiple Distribution schemas (Step 12.6)
// ---------------------------------------------------------------------------

export const RBucketSchema = z.object({
  label: z.string(),
  lower: decimalString,
  upper: decimalString,
  count: z.number().int(),
})

export const RDistributionSchema = z.object({
  mean_r: decimalString,
  median_r: decimalString,
  stddev_r: decimalString,
  p25_r: decimalString,
  p75_r: decimalString,
  coverage_count: z.number().int(),
  total_count: z.number().int(),
  coverage_pct: z.string(),
  insufficient_sample: z.boolean(),
  buckets: z.array(RBucketSchema),
})

// ---------------------------------------------------------------------------
// M-10 Dimension Breakdown schemas (Step 12.6)
// ---------------------------------------------------------------------------

export const DimensionGroupSchema = z.object({
  label: z.string(),
  trade_count: z.number().int(),
  win_count: z.number().int(),
  win_rate: z.string(),
  total_net_pnl: z.string(),
  avg_net_pnl: z.string(),
  avg_r_multiple: decimalString,
  avg_hold_duration_minutes: decimalString,
})

export const DimensionBreakdownSchema = z.object({
  dimension: z.string(),
  groups: z.array(DimensionGroupSchema),
})

// ---------------------------------------------------------------------------
// N-4 Kelly Fraction schemas (Step 12.7)
// ---------------------------------------------------------------------------

export const KellySchema = z.object({
  kelly_pct: decimalString,
  half_kelly_pct: decimalString,
  trades_with_r: z.number().int(),
  insufficient_sample: z.boolean(),
  min_n: z.number().int(),
})

// ---------------------------------------------------------------------------
// N-2 Time-of-Day schemas (Step 12.7)
// ---------------------------------------------------------------------------

export const TimeOfDayBucketSchema = z.object({
  bucket: z.string(),
  label: z.string(),
  trade_count: z.number().int(),
  win_count: z.number().int(),
  win_rate: z.string(),        // 0–100 scale (percentage)
  expectancy_inr: decimalString,
  total_net_pnl: z.string(),
})

export const TimeOfDaySchema = z.object({
  buckets: z.array(TimeOfDayBucketSchema),
})

// ---------------------------------------------------------------------------
// N-1 Rolling Expectancy schemas (Step 12.7)
// ---------------------------------------------------------------------------

export const RollingExpectancyPointSchema = z.object({
  trade_index: z.number().int(),
  trade_date: z.string(),
  rolling_exp_r: decimalString,
  rolling_exp_inr: z.string(),
})

export const RollingExpectancySchema = z.object({
  window: z.number().int(),
  insufficient_sample: z.boolean(),
  data: z.array(RollingExpectancyPointSchema),
})

// ---------------------------------------------------------------------------
// Step 13 Risk Summary schema
// ---------------------------------------------------------------------------

export const RiskSummarySchema = z.object({
  max_drawdown_inr: decimalString,
  max_drawdown_pct: decimalString,
  current_drawdown_inr: decimalString,
  current_drawdown_pct: decimalString,
  max_loss_streak: z.number().int(),
  current_loss_streak: z.number().int(),
  daily_loss_inr: z.string(),
  daily_loss_trade_count: z.number().int(),
  total_at_risk_inr: decimalString,
  open_trade_count: z.number().int(),
  as_of_date: z.string(),
})

export const AnalyticsSummarySchema = z.object({
  pnl: PnlSummarySchema,
  outcome: OutcomeDistributionSchema,
  expectancy: ExpectancyResultSchema,
  profit_factor: ProfitFactorSchema,
  planned_rr: PlannedRRSchema,
  drawdown: DrawdownStatsSchema,
  direction: z.array(DirectionPerformanceSchema),
  charges: ChargesBreakdownSchema,
  risk_adjusted: RiskAdjustedSchema,
})
