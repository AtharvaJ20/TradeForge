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
