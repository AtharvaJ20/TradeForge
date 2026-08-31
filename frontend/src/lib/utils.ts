/** Merge Tailwind class strings, filtering out falsy values. */
export function cn(...classes: (string | false | undefined | null)[]): string {
  return classes.filter(Boolean).join(' ')
}

/** Format a decimal string or number as Indian Rupees. Returns '—' for null. */
export function formatInr(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '—'
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num)
}

/** Format a decimal string/number as a signed R-multiple, e.g. "+2.15 R". */
export function formatRMultiple(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '—'
  const sign = num >= 0 ? '+' : ''
  return `${sign}${num.toFixed(2)} R`
}

/** Format bytes as human-readable string. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** Format an ISO datetime string in IST timezone. */
export function formatIst(isoString: string): string {
  try {
    return new Intl.DateTimeFormat('en-IN', {
      timeZone: 'Asia/Kolkata',
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(new Date(isoString))
  } catch {
    return isoString
  }
}

/** Format an ISO date string as "23 Aug 2026". */
export function formatDate(isoString: string): string {
  try {
    return new Intl.DateTimeFormat('en-IN', {
      timeZone: 'Asia/Kolkata',
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    }).format(new Date(isoString))
  } catch {
    return isoString
  }
}

/**
 * Calculate planned risk amount.
 * Formula: |averageEntry − plannedStop| × quantity
 * Returns null if any input is missing.
 */
export function calcPlannedRisk(
  averageEntry: string | null,
  plannedStop: string | null,
  quantity: string,
): string | null {
  if (!averageEntry || !plannedStop) return null
  const entry = parseFloat(averageEntry)
  const stop = parseFloat(plannedStop)
  const qty = parseFloat(quantity)
  if (isNaN(entry) || isNaN(stop) || isNaN(qty)) return null
  return (Math.abs(entry - stop) * qty).toFixed(2)
}

/**
 * Calculate planned R:R ratio as a display string, e.g. "1 : 2.0".
 * Returns null if any input is missing.
 */
export function calcRR(
  averageEntry: string | null,
  plannedStop: string | null,
  plannedTarget: string | null,
): string | null {
  if (!averageEntry || !plannedStop || !plannedTarget) return null
  const entry = parseFloat(averageEntry)
  const stop = parseFloat(plannedStop)
  const target = parseFloat(plannedTarget)
  if (isNaN(entry) || isNaN(stop) || isNaN(target)) return null
  const risk = Math.abs(entry - stop)
  if (risk === 0) return null
  const reward = Math.abs(target - entry)
  return `1 : ${(reward / risk).toFixed(1)}`
}
