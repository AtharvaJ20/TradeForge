/** Shared display formatters for the analytics feature. */

function thousands(n: number): string {
  return Math.round(Math.abs(n))
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

/** Format a non-nullable decimal string as a signed INR amount: ₹27,500 / -₹6,050 */
export function formatINR(value: string): string {
  const num = parseFloat(value)
  if (isNaN(num)) return '—'
  const prefix = num < 0 ? '-₹' : '₹'
  return `${prefix}${thousands(num)}`
}

/** Nullable variant — returns '—' for null. */
export function formatINRNullable(value: string | null): string {
  if (value === null) return '—'
  return formatINR(value)
}

/** Convert a fraction string (0.67) to a percentage display string (67.0%). */
export function formatPctFraction(value: string): string {
  const num = parseFloat(value)
  if (isNaN(num)) return '—'
  return `${(num * 100).toFixed(1)}%`
}

/** Format a value that is already a percentage (e.g. charge_drag_pct = 5.17 → 5.17%). */
export function formatPctDirect(value: string | null): string {
  if (value === null) return '—'
  const num = parseFloat(value)
  if (isNaN(num)) return '—'
  return `${num.toFixed(2)}%`
}

/** Format a nullable decimal with an explicit sign prefix: +2.34 / -1.50 / — */
export function formatSigned(value: string | null): string {
  if (value === null) return '—'
  const num = parseFloat(value)
  if (isNaN(num)) return '—'
  const sign = num > 0 ? '+' : ''
  return `${sign}${num.toFixed(2)}`
}

/** Format a nullable decimal to fixed decimal places. */
export function formatDecimal(value: string | null, dp = 2): string {
  if (value === null) return '—'
  const num = parseFloat(value)
  if (isNaN(num)) return '—'
  return num.toFixed(dp)
}
