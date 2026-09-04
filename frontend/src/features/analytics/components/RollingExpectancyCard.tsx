import { useRollingExpectancy } from '../hooks/useRollingExpectancy'
import type { AnalyticsFilterParams, RollingExpectancy, RollingExpectancyPoint } from '../types'
import { formatINR } from '../formatters'

// ---------------------------------------------------------------------------
// Format rolling_exp_r with sign and colour class
// ---------------------------------------------------------------------------

function formatExpR(value: string | null): { text: string; className: string } {
  if (value === null) return { text: '—', className: 'text-text-secondary' }
  const num = parseFloat(value)
  if (isNaN(num)) return { text: '—', className: 'text-text-secondary' }
  const sign = num > 0 ? '+' : ''
  const text = `${sign}${num.toFixed(2)}R`
  const className = num > 0 ? 'text-success-emphasis' : num < 0 ? 'text-danger-emphasis' : 'text-text-primary'
  return { text, className }
}

// ---------------------------------------------------------------------------
// Table row
// ---------------------------------------------------------------------------

function DataRow({ point }: { point: RollingExpectancyPoint }) {
  const expR = formatExpR(point.rolling_exp_r)

  return (
    <tr className="border-b border-border last:border-0">
      <td className="py-2 tabular-nums text-text-secondary">{point.trade_index}</td>
      <td className="py-2 text-right tabular-nums text-text-primary">{point.trade_date}</td>
      <td className={`py-2 text-right tabular-nums font-medium ${expR.className}`}>
        {expR.text}
      </td>
      <td className="py-2 text-right tabular-nums text-text-primary">
        {formatINR(point.rolling_exp_inr)}
      </td>
    </tr>
  )
}

// ---------------------------------------------------------------------------
// Table display (accepts already-fetched data)
// Shows the last 20 rows, most-recent at the bottom
// ---------------------------------------------------------------------------

function RollingExpectancyTable({ data }: { data: RollingExpectancy }) {
  const rows = data.data.slice(-20)

  return (
    <div className="overflow-x-auto max-h-96 overflow-y-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">20-trade rolling expectancy series</caption>
        <thead className="sticky top-0 bg-surface-base">
          <tr className="border-b border-border">
            <th
              scope="col"
              className="pb-2 text-left text-xs font-semibold uppercase tracking-wider text-text-secondary"
            >
              Trade #
            </th>
            <th
              scope="col"
              className="pb-2 text-right text-xs font-semibold uppercase tracking-wider text-text-secondary"
            >
              Date
            </th>
            <th
              scope="col"
              className="pb-2 text-right text-xs font-semibold uppercase tracking-wider text-text-secondary"
            >
              Rolling Exp (R)
            </th>
            <th
              scope="col"
              className="pb-2 text-right text-xs font-semibold uppercase tracking-wider text-text-secondary"
            >
              Rolling Exp (₹)
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map(point => (
            <DataRow key={point.trade_index} point={point} />
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Public card (owns fetching)
// ---------------------------------------------------------------------------

export function RollingExpectancyCard({ params = {} }: { params?: AnalyticsFilterParams }) {
  const { data, isLoading, isError } = useRollingExpectancy(params)

  return (
    <section
      className="rounded-xl border border-border bg-surface-base p-5"
      aria-label="Rolling expectancy"
    >
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        Rolling Expectancy (20-trade window)
      </h2>

      {isLoading && (
        <div
          className="h-40 animate-pulse rounded-lg bg-surface-subtle"
          role="status"
          aria-label="Loading rolling expectancy"
        />
      )}

      {isError && !isLoading && (
        <p className="text-sm text-danger-emphasis">Failed to load rolling expectancy.</p>
      )}

      {data && !isLoading && data.insufficient_sample && (
        <p className="text-sm text-text-secondary" role="note">
          Needs 20+ closed trades to compute rolling expectancy.
        </p>
      )}

      {data && !isLoading && !data.insufficient_sample && (
        <RollingExpectancyTable data={data} />
      )}
    </section>
  )
}
