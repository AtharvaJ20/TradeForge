import type { DirectionPerformance } from '../types'
import { formatPctFraction, formatINR, formatSigned } from '../formatters'

export function DirectionBreakdownTable({ rows }: { rows: DirectionPerformance[] }) {
  if (rows.length === 0) {
    return (
      <section
        className="rounded-xl border border-border bg-surface-base p-5"
        aria-label="Direction breakdown"
      >
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
          Direction Breakdown
        </h2>
        <p className="text-sm text-text-muted" role="note">
          No direction data available.
        </p>
      </section>
    )
  }

  return (
    <section
      className="rounded-xl border border-border bg-surface-base p-5"
      aria-label="Direction breakdown"
    >
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        Direction Breakdown
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <caption className="sr-only">
            Trade performance broken down by direction (LONG / SHORT)
          </caption>
          <thead>
            <tr className="border-b border-border">
              <th
                scope="col"
                className="pb-2 text-left text-xs font-semibold uppercase tracking-wider text-text-secondary"
              >
                Direction
              </th>
              <th
                scope="col"
                className="pb-2 text-right text-xs font-semibold uppercase tracking-wider text-text-secondary"
              >
                Trades
              </th>
              <th
                scope="col"
                className="pb-2 text-right text-xs font-semibold uppercase tracking-wider text-text-secondary"
              >
                Win rate
              </th>
              <th
                scope="col"
                className="pb-2 text-right text-xs font-semibold uppercase tracking-wider text-text-secondary"
              >
                Avg net P&L
              </th>
              <th
                scope="col"
                className="pb-2 text-right text-xs font-semibold uppercase tracking-wider text-text-secondary"
              >
                Avg R
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.direction} className="border-b border-border last:border-0">
                <td className="py-2 font-medium text-text-primary">{row.direction}</td>
                <td className="py-2 text-right tabular-nums text-text-primary">
                  {row.trade_count}
                </td>
                <td className="py-2 text-right tabular-nums text-success-emphasis">
                  {formatPctFraction(row.win_rate)}
                </td>
                <td className="py-2 text-right tabular-nums text-text-primary">
                  {formatINR(row.avg_net_pnl)}
                </td>
                <td className="py-2 text-right tabular-nums text-text-primary">
                  {formatSigned(row.avg_r_multiple)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
