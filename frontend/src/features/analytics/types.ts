import type { z } from 'zod'
import type {
  AnalyticsSummarySchema,
  RiskAdjustedSchema,
  SharpeResultSchema,
  SortinoResultSchema,
} from './schemas'

export type AnalyticsSummary = z.infer<typeof AnalyticsSummarySchema>
export type RiskAdjusted = z.infer<typeof RiskAdjustedSchema>
export type SharpeResult = z.infer<typeof SharpeResultSchema>
export type SortinoResult = z.infer<typeof SortinoResultSchema>
