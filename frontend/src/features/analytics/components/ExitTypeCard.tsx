import { useExitTypes } from '../hooks/useExitTypes'
import type { AnalyticsFilterParams, ExitTypeRow, ExitTypes } from '../types'
import { formatINR, formatPctFraction, formatDecimal } from '../formatters'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function untaggedPct(rows: ExitTypes): number {
  const total = rows.reduce((sum, r) => sum + r.trade_count, 0)
  if (total === 0) return 0
  const untagged = rows.find(r => r.exit_type === null)?.trade_count ?? 0
  return (untagged / total) * 100
}

function exitTypeLabel(row: ExitTypeRow): string {
  return row.exit_type ?? 'Untagged'
}

// ---------------------------------------------------------------------------
// Display (pure)
// ---------------------------------------------------------------------------

function ExitTypeDisplay({ rows }: { rows: ExitTypes }) {
  if (rows.length === 0) {
    return <p className="text-sm text-text-secondary">No closed trades yet.</p>
  }

  const untaggedPctValue = untaggedPct(rows)
  const showAlert = untaggedPctValue > 20

  return (
    <>
      {showAlert && (
        <div
          className="mb-4 rounded-lg border border-warning/40 bg-surface-warning p-3"
          role="alert"
        >
          <p className="text-sm text-warning-emphasis">
            {untaggedPctValue.toFixed(0)}% of exits have no exit type — check broker adapter
            configuration.
          </p>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-text-secondary">
              <th scope="col" className="pb-2 pr-4 font-semibold">Exit type</th>
              <th scope="col" className="pb-2 pr-4 text-right font-semibold">N</th>
              <th scope="col" className="pb-2 pr-4 text-right font-semibold">Win rate</th>
              <th scope="col" className="pb-2 pr-4 text-right font-semibold">Avg net P&amp;L</th>
              <th scope="col" className="pb-2 text-right font-semibold">Avg R</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(row => (
              <tr
                key={row.exit_type ?? '__untagged__'}
                className="border-b border-border/50 last:border-0"
              >
                <td className="py-2 pr-4 font-medium text-text-primary">
                  {exitTypeLabel(row)}
                </td>
                <td className="py-2 pr-4 text-right tabular-nums text-text-primary">
                  {row.trade_count}
                </td>
                <td className="py-2 pr-4 text-right tabular-nums text-text-primary">
                  {formatPctFraction(row.win_rate)}
                </td>
                <td className={`py-2 pr-4 text-right tabular-nums ${
                  parseFloat(row.avg_net_pnl) >= 0 ? 'text-success-emphasis' : 'text-danger-emphasis'
                }`}>
                  {formatINR(row.avg_net_pnl)}
                </td>
                <td className="py-2 text-right tabular-nums text-text-primary">
                  {formatDecimal(row.avg_r_multiple)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Public card (owns fetching)
// ---------------------------------------------------------------------------

export function ExitTypeCard({ params = {} }: { params?: AnalyticsFilterParams }) {
  const { data, isLoading, isError } = useExitTypes(params)

  return (
    <section
      className="rounded-xl border border-border bg-surface-base p-5"
      aria-label="Exit type analysis"
    >
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        Exit Type
      </h2>

      {isLoading && (
        <div
          className="h-24 animate-pulse rounded-lg bg-surface-subtle"
          role="status"
          aria-label="Loading exit type data"
        />
      )}

      {isError && !isLoading && (
        <p className="text-sm text-danger-emphasis">Failed to load exit type data.</p>
      )}

      {data && !isLoading && <ExitTypeDisplay rows={data} />}
    </section>
  )
}
