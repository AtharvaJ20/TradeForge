import type { ChargesBreakdown } from '../types'
import { formatINR, formatPctDirect } from '../formatters'

const CHARGE_ROWS: Array<{ field: keyof ChargesBreakdown; label: string }> = [
  { field: 'total_brokerage', label: 'Brokerage' },
  { field: 'total_stt', label: 'STT' },
  { field: 'total_exchange_charges', label: 'Exchange charges' },
  { field: 'total_sebi_charges', label: 'SEBI charges' },
  { field: 'total_stamp_duty', label: 'Stamp duty' },
  { field: 'total_gst', label: 'GST' },
  { field: 'total_ipft', label: 'IPFT' },
]

export function ChargesCard({ charges }: { charges: ChargesBreakdown }) {
  return (
    <section
      className="rounded-xl border border-border bg-surface-base p-5"
      aria-label="Charges breakdown"
    >
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        Charges
      </h2>
      <dl className="space-y-2">
        {CHARGE_ROWS.map(({ field, label }) => (
          <div key={field} className="flex items-center justify-between text-sm">
            <dt className="text-text-secondary">{label}</dt>
            <dd
              className="tabular-nums text-text-primary"
              aria-label={`${label}: ${formatINR(charges[field] as string)}`}
            >
              {formatINR(charges[field] as string)}
            </dd>
          </div>
        ))}
        <div className="flex items-center justify-between border-t border-border pt-2 text-sm font-semibold">
          <dt className="text-text-primary">Total charges</dt>
          <dd
            className="tabular-nums text-danger-emphasis"
            aria-label={`Total charges: ${formatINR(charges.total_charges)}`}
          >
            {formatINR(charges.total_charges)}
          </dd>
        </div>
      </dl>

      {/* G-CORR-03: charge_drag_pct is null when gross P&L ≤ 0; show charges_added_to_loss instead */}
      <div className="mt-3 rounded-lg border border-border bg-surface-subtle p-3">
        {charges.charge_drag_pct !== null ? (
          <p className="text-sm text-text-secondary">
            Charge drag:{' '}
            <span className="font-semibold text-danger-emphasis">
              {formatPctDirect(charges.charge_drag_pct)}
            </span>{' '}
            of gross P&L
          </p>
        ) : charges.charges_added_to_loss !== null ? (
          <p className="text-sm text-text-secondary">
            Charges added to loss:{' '}
            <span className="font-semibold text-danger-emphasis">
              {formatINR(charges.charges_added_to_loss)}
            </span>
          </p>
        ) : null}
      </div>
    </section>
  )
}
