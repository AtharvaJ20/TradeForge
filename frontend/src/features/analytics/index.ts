// Public barrel — only export what consumers outside this feature need.
export { AnalyticsSummaryPanel } from './components/AnalyticsSummaryPanel'
export { AnalyticsFilterBar } from './components/AnalyticsFilterBar'
export type { AnalyticsFilterBarProps } from './components/AnalyticsFilterBar'
export { RiskAdjustedCard } from './components/RiskAdjustedCard'
export { PnlSummaryCard } from './components/PnlSummaryCard'
export { OutcomeCard } from './components/OutcomeCard'
export { ExpectancyCard } from './components/ExpectancyCard'
export { ProfitFactorCard } from './components/ProfitFactorCard'
export { PlannedRRCard } from './components/PlannedRRCard'
export { DrawdownCard } from './components/DrawdownCard'
export { DirectionBreakdownTable } from './components/DirectionBreakdownTable'
export { ChargesCard } from './components/ChargesCard'
export type {
  AnalyticsSummary,
  RiskAdjusted,
  SharpeResult,
  SortinoResult,
  AnalyticsFilterParams,
  AccountDimension,
  PnlSummary,
  OutcomeDistribution,
  ExpectancyResult,
  ProfitFactor,
  PlannedRR,
  DrawdownStats,
  DirectionPerformance,
  ChargesBreakdown,
} from './types'
export { useFilterDimensions } from './hooks/useFilterDimensions'
export { countActiveFilterDimensions } from './utils'
