import { useState } from 'react'
import { useDimensionBreakdown } from '../hooks/useDimensionBreakdown'
import type { AnalyticsFilterParams, DimensionGroup } from '../types'
import { formatINR, formatPctFraction, formatSigned, formatDecimal } from '../formatters'

// ---------------------------------------------------------------------------
// Dimension config
// ---------------------------------------------------------------------------

const DIMENSIONS = [
  { value: 'direction', label: 'Direction' },
  { value: 'setup', label: 'Setup' },
  { value: 'instrument', label: 'Instrument' },
  { value: 'trade_type', label: 'Trade Type' },
  { value: 'segment', label: 'Segment' },
] as const

type DimensionValue = (typeof DIMENSIONS)[number]['value']

// ---------------------------------------------------------------------------
// Sort logic
// ---------------------------------------------------------------------------

type SortKey = keyof DimensionGroup
type SortDir = 'asc' | 'desc'

function sortGroups(
  groups: DimensionGroup[],
  sortKey: SortKey,
  sortDir: SortDir,
): DimensionGroup[] {
  return [...groups].sort((a, b) => {
    const av = a[sortKey]
    const bv = b[sortKey]
    // null always sorts last
    if (av === null && bv === null) return 0
    if (av === null) return 1
    if (bv === null) return -1

    const an = typeof av === 'string' ? parseFloat(av) : (av as number)
    const bn = typeof bv === 'string' ? parseFloat(bv) : (bv as number)

    if (!isNaN(an) && !isNaN(bn)) {
      return sortDir === 'asc' ? an - bn : bn - an
    }
    // string compare
    const as = String(av)
    const bs = String(bv)
    return sortDir === 'asc' ? as.localeCompare(bs) : bs.localeCompare(as)
  })
}

// ---------------------------------------------------------------------------
// Table header
// ---------------------------------------------------------------------------

interface ThProps {
  label: string
  sortKey: SortKey
  currentSortKey: SortKey
  currentSortDir: SortDir
  onSort: (key: SortKey) => void
  align?: 'left' | 'right'
}

function Th({ label, sortKey, currentSortKey, currentSortDir, onSort, align = 'right' }: ThProps) {
  const active = currentSortKey === sortKey
  const arrow = active ? (currentSortDir === 'asc' ? ' ↑' : ' ↓') : ''

  return (
    <th
      scope="col"
      className={`cursor-pointer select-none pb-2 text-xs font-semibold uppercase tracking-wider text-text-secondary hover:text-text-primary ${align === 'left' ? 'text-left' : 'text-right'}`}
      onClick={() => onSort(sortKey)}
      aria-sort={active ? (currentSortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      {label}
      {arrow}
    </th>
  )
}

// ---------------------------------------------------------------------------
// Table display
// ---------------------------------------------------------------------------

function BreakdownTable({
  groups,
  dimensionLabel,
}: {
  groups: DimensionGroup[]
  dimensionLabel: string
}) {
  const [sortKey, setSortKey] = useState<SortKey>('total_net_pnl')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const sorted = sortGroups(groups, sortKey, sortDir)

  const thProps = { currentSortKey: sortKey, currentSortDir: sortDir, onSort: handleSort }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">
          Trade performance broken down by {dimensionLabel}
        </caption>
        <thead>
          <tr className="border-b border-border">
            <Th label={dimensionLabel} sortKey="label" {...thProps} align="left" />
            <Th label="Trades" sortKey="trade_count" {...thProps} />
            <Th label="Wins" sortKey="win_count" {...thProps} />
            <Th label="Win rate" sortKey="win_rate" {...thProps} />
            <Th label="Total P&L" sortKey="total_net_pnl" {...thProps} />
            <Th label="Avg P&L" sortKey="avg_net_pnl" {...thProps} />
            <Th label="Avg R" sortKey="avg_r_multiple" {...thProps} />
            <Th label="Avg hold" sortKey="avg_hold_duration_minutes" {...thProps} />
          </tr>
        </thead>
        <tbody>
          {sorted.map(row => (
            <tr key={row.label} className="border-b border-border last:border-0">
              <td className="py-2 font-medium text-text-primary">{row.label}</td>
              <td className="py-2 text-right tabular-nums text-text-primary">
                {row.trade_count}
              </td>
              <td className="py-2 text-right tabular-nums text-text-primary">
                {row.win_count}
              </td>
              <td className="py-2 text-right tabular-nums text-success-emphasis">
                {formatPctFraction(row.win_rate)}
              </td>
              <td className="py-2 text-right tabular-nums text-text-primary">
                {formatINR(row.total_net_pnl)}
              </td>
              <td className="py-2 text-right tabular-nums text-text-primary">
                {formatINR(row.avg_net_pnl)}
              </td>
              <td className="py-2 text-right tabular-nums text-text-primary">
                {formatSigned(row.avg_r_multiple)}
              </td>
              <td className="py-2 text-right tabular-nums text-text-primary">
                {row.avg_hold_duration_minutes !== null
                  ? `${formatDecimal(row.avg_hold_duration_minutes, 0)} min`
                  : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Public card (owns fetching + dimension selection)
// ---------------------------------------------------------------------------

export function DimensionBreakdownCard({ params = {} }: { params?: AnalyticsFilterParams }) {
  const [dimension, setDimension] = useState<DimensionValue>('direction')
  const { data, isLoading, isError } = useDimensionBreakdown(params, dimension)

  const activeDimension = DIMENSIONS.find(d => d.value === dimension)!

  return (
    <section
      className="rounded-xl border border-border bg-surface-base p-5"
      aria-label="Dimension breakdown"
    >
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        Dimension Breakdown
      </h2>

      {/* Dimension tab strip */}
      <div className="mb-4 flex flex-wrap gap-1" role="tablist" aria-label="Breakdown dimension">
        {DIMENSIONS.map(dim => (
          <button
            key={dim.value}
            role="tab"
            aria-selected={dimension === dim.value}
            onClick={() => setDimension(dim.value)}
            className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
              dimension === dim.value
                ? 'bg-accent text-white'
                : 'text-text-secondary hover:bg-surface-subtle hover:text-text-primary'
            }`}
          >
            {dim.label}
          </button>
        ))}
      </div>

      {isLoading && (
        <div
          className="h-32 animate-pulse rounded-lg bg-surface-subtle"
          role="status"
          aria-label="Loading dimension breakdown"
        />
      )}

      {isError && !isLoading && (
        <p className="text-sm text-danger-emphasis">Failed to load dimension breakdown.</p>
      )}

      {data && !isLoading && data.groups.length === 0 && (
        <p className="text-sm text-text-secondary" role="note">
          No trades match the current filter.
        </p>
      )}

      {data && !isLoading && data.groups.length > 0 && (
        <BreakdownTable groups={data.groups} dimensionLabel={activeDimension.label} />
      )}
    </section>
  )
}
