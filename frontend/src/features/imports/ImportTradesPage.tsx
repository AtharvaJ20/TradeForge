import { useState, useEffect, useId } from 'react'
import { useAccount } from '@/features/accounts/context/AccountContext'
import { ApiError } from '@/lib/api-client'
import { importsApi } from './api'
import type { ImportRecordOut, ImportSummaryOut } from './types'

// ---------------------------------------------------------------------------
// Local types
// ---------------------------------------------------------------------------

type ImportResult =
  | { kind: 'success'; summary: ImportSummaryOut }
  | { kind: 'error'; code: string; status: number }

// ---------------------------------------------------------------------------
// Small layout helpers (matching AddTradePage conventions)
// ---------------------------------------------------------------------------

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className="mb-4 text-base font-semibold text-text-primary">{children}</h2>
}

function FieldRow({ children }: { children: React.ReactNode }) {
  return <div className="mb-4">{children}</div>
}

function Label({ htmlFor, children }: { htmlFor: string; children: React.ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-text-primary">
      {children}
    </label>
  )
}

function inputClass() {
  return 'w-full rounded-lg border border-border bg-surface-base px-3 py-2 text-sm text-text-primary focus:border-border-focus focus:outline-none focus:ring-2 focus:ring-border-focus/20'
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const variants: Record<string, string> = {
    COMPLETE: 'bg-surface-success text-success-emphasis',
    PARTIAL: 'bg-surface-warning text-warning-emphasis',
    FAILED: 'bg-surface-danger text-danger-emphasis',
    EMPTY: 'bg-surface-subtle text-text-secondary',
  }
  const cls = variants[status] ?? variants['EMPTY']
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold ${cls}`}>
      {status}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Import result banner
// ---------------------------------------------------------------------------

function ResultBanner({
  result,
  onReset,
}: {
  result: ImportResult
  onReset: () => void
}) {
  if (result.kind === 'success') {
    const { summary } = result
    if (summary.status === 'COMPLETE') {
      return (
        <div role="status" className="mb-4 rounded-lg bg-surface-success px-4 py-3 text-sm text-success-emphasis">
          <p className="font-semibold">Import complete — {summary.fills_ingested} fills imported.</p>
          {summary.fills_skipped > 0 && (
            <p className="mt-0.5 text-xs">{summary.fills_skipped} fills skipped (already imported).</p>
          )}
        </div>
      )
    }
    if (summary.status === 'PARTIAL') {
      return (
        <div role="status" className="mb-4 rounded-lg bg-surface-warning px-4 py-3 text-sm text-warning-emphasis">
          <p className="font-semibold">
            Import partially completed — {summary.fills_ingested} fills imported,{' '}
            {summary.row_errors} rows could not be read. Check that the file is a valid Zerodha export.
          </p>
        </div>
      )
    }
    if (summary.status === 'FAILED') {
      return (
        <div role="alert" className="mb-4 rounded-lg bg-surface-danger px-4 py-3 text-sm text-danger-emphasis">
          <p className="font-semibold">Import failed — no fills could be read. Check the file format.</p>
        </div>
      )
    }
    // EMPTY success-path deliberately not implemented (G-17-1: unreachable in Phase 1 via Zerodha adapter)
    return null
  }

  // Error result
  const { code } = result
  if (code === 'DUPLICATE_IMPORT') {
    return (
      <div role="alert" className="mb-4 rounded-lg bg-surface-danger px-4 py-3 text-sm text-danger-emphasis">
        This file has already been imported to this account.
      </div>
    )
  }
  if (code === 'FILE_TOO_LARGE') {
    return (
      <div role="alert" className="mb-4 rounded-lg bg-surface-danger px-4 py-3 text-sm text-danger-emphasis">
        The file is too large. Zerodha tradebook exports are typically under 1 MB.
      </div>
    )
  }
  if (code === 'EMPTY_FILE') {
    return (
      <div role="alert" className="mb-4 rounded-lg bg-surface-warning px-4 py-3 text-sm text-warning-emphasis">
        The file contains no data rows. Check that you have exported the correct date range from Zerodha.
      </div>
    )
  }
  if (code === 'UNRECOGNIZED_FILE_FORMAT') {
    return (
      <div role="alert" className="mb-4 rounded-lg bg-surface-danger px-4 py-3 text-sm text-danger-emphasis">
        File format not recognised. Only Zerodha CSV exports are supported in Phase 1.
      </div>
    )
  }
  if (code === 'MISSING_PRODUCT_TYPE') {
    return (
      <div role="alert" className="mb-4 rounded-lg bg-surface-warning px-4 py-3 text-sm text-warning-emphasis">
        This file contains F&amp;O rows but no product type column. Select a product type above and try again.
      </div>
    )
  }
  if (code === 'ACCOUNT_INACTIVE') {
    return (
      <div role="alert" className="mb-4 rounded-lg bg-surface-danger px-4 py-3 text-sm text-danger-emphasis">
        This account is inactive. Reactivate it in Settings before importing.
      </div>
    )
  }
  // Generic fallback
  return (
    <div role="alert" className="mb-4 rounded-lg bg-surface-danger px-4 py-3 text-sm text-danger-emphasis">
      An unexpected error occurred. Please try again.
    </div>
  )

  // Reset button rendered separately below result so "Import another file" is always visible
  void onReset
}

// ---------------------------------------------------------------------------
// Import history table
// ---------------------------------------------------------------------------

function HistoryTable({
  records,
  loading,
}: {
  records: ImportRecordOut[]
  loading: boolean
}) {
  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-8 animate-pulse rounded bg-surface-subtle"
            aria-hidden="true"
          />
        ))}
      </div>
    )
  }

  if (records.length === 0) {
    return (
      <p className="text-sm text-text-secondary">No imports yet for this account.</p>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
            <th className="pb-2 pr-4">Date</th>
            <th className="pb-2 pr-4">Broker</th>
            <th className="pb-2 pr-4">File</th>
            <th className="pb-2 pr-4">Fills</th>
            <th className="pb-2 pr-4">Errors</th>
            <th className="pb-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {records.map((r) => (
            <tr key={r.id} className="border-b border-border/50 last:border-0">
              <td className="py-2 pr-4 text-text-secondary">
                {new Date(r.imported_at).toLocaleString('en-IN', {
                  dateStyle: 'short',
                  timeStyle: 'short',
                })}
              </td>
              <td className="py-2 pr-4 text-text-primary">{r.broker}</td>
              <td className="py-2 pr-4 text-text-secondary">{r.file_name ?? '—'}</td>
              <td className="py-2 pr-4 text-text-primary">{r.row_count}</td>
              <td className="py-2 pr-4 text-text-primary">{r.error_count}</td>
              <td className="py-2">
                <StatusBadge status={r.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ImportTradesPage
// ---------------------------------------------------------------------------

export function ImportTradesPage() {
  const uid = useId()
  const { accounts, selectedAccount, isLoading: accountsLoading } = useAccount()

  // Form state
  const [accountId, setAccountId] = useState('')
  const [productTypeHint, setProductTypeHint] = useState<'MIS' | 'CNC' | 'NRML' | ''>('')
  const [showProductTypeHint, setShowProductTypeHint] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [fileSizeWarning, setFileSizeWarning] = useState(false)

  // Submission state
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [result, setResult] = useState<ImportResult | null>(null)

  // History state
  const [history, setHistory] = useState<ImportRecordOut[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyTick, setHistoryTick] = useState(0)

  // Default to selected account on load
  useEffect(() => {
    if (!accountsLoading && selectedAccount && !accountId) {
      setAccountId(selectedAccount.id)
    }
  }, [accountsLoading, selectedAccount, accountId])

  // Fetch import history when account changes or after successful import
  useEffect(() => {
    if (!accountId) return
    setHistoryLoading(true)
    importsApi
      .list(accountId)
      .then((data) => setHistory(data))
      .catch(() => setHistory([]))
      .finally(() => setHistoryLoading(false))
  }, [accountId, historyTick])

  // Derived
  const activeAccounts = accounts.filter((a) => a.status === 'ACTIVE')
  const selectedAccountObj = accounts.find((a) => a.id === accountId) ?? null
  const isZerodha = selectedAccountObj?.broker === 'ZERODHA'
  const canSubmit = !!accountId && !!file && !fileError && isZerodha && !isSubmitting

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0] ?? null
    setFile(selected)
    setResult(null)

    if (!selected) {
      setFileError(null)
      setFileSizeWarning(false)
      return
    }

    if (!selected.name.toLowerCase().endsWith('.csv')) {
      setFileError('Please select a CSV file')
      setFileSizeWarning(false)
      return
    }

    setFileError(null)
    setFileSizeWarning(selected.size > 5 * 1024 * 1024)
  }

  function handleReset() {
    setFile(null)
    setFileError(null)
    setFileSizeWarning(false)
    setResult(null)
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!file || !accountId || !isZerodha) return

    const formData = new FormData()
    formData.append('file', file)
    if (productTypeHint) {
      formData.append('product_type_hint', productTypeHint)
    }

    setIsSubmitting(true)
    setResult(null)

    try {
      const summary = await importsApi.upload(accountId, formData)
      setResult({ kind: 'success', summary })
      setHistoryTick((t) => t + 1)
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.detail === 'MISSING_PRODUCT_TYPE') {
          setShowProductTypeHint(true)
        }
        setResult({ kind: 'error', code: err.detail, status: err.status })
      } else {
        setResult({ kind: 'error', code: 'UNKNOWN_ERROR', status: 500 })
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-2 text-2xl font-bold text-text-primary">Import Trades</h1>

      {/* R-16-6 risk notice */}
      <p className="mb-6 text-sm text-text-secondary">
        If you&apos;ve manually added fills to an open position, review those trades after
        importing a file that covers the same period. Duplicate fills can be removed from the
        Trades screen.
      </p>

      {/* ------------------------------------------------------------------ */}
      {/* Section 1 — Upload form                                             */}
      {/* ------------------------------------------------------------------ */}
      <section className="mb-6 rounded-xl border border-border bg-surface-base p-6">
        <SectionHeading>Upload Zerodha CSV</SectionHeading>

        <form onSubmit={(e) => void handleSubmit(e)} noValidate>
          {/* Account selector */}
          <FieldRow>
            <Label htmlFor={`${uid}-account`}>Account</Label>
            <select
              id={`${uid}-account`}
              aria-label="Account"
              value={accountId}
              onChange={(e) => {
                setAccountId(e.target.value)
                setResult(null)
              }}
              className={inputClass()}
            >
              <option value="">Select account…</option>
              {activeAccounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.display_name} ({a.broker})
                </option>
              ))}
            </select>
          </FieldRow>

          {/* Zerodha-only guard */}
          {accountId && !isZerodha && (
            <p role="note" className="mb-4 rounded-lg bg-surface-info px-3 py-2 text-sm text-text-secondary">
              CSV import is currently supported for Zerodha accounts only.
            </p>
          )}

          {/* Product type hint (optional, shown when needed or after MISSING_PRODUCT_TYPE error) */}
          {(showProductTypeHint || productTypeHint !== '') && (
            <FieldRow>
              <Label htmlFor={`${uid}-product-type-hint`}>F&amp;O product type (if needed)</Label>
              <select
                id={`${uid}-product-type-hint`}
                aria-label="F&O product type (if needed)"
                value={productTypeHint}
                onChange={(e) => setProductTypeHint(e.target.value as 'MIS' | 'CNC' | 'NRML' | '')}
                className={inputClass()}
              >
                <option value="">Auto-detect (default)</option>
                <option value="MIS">MIS — Intraday</option>
                <option value="CNC">CNC — Delivery</option>
                <option value="NRML">NRML — Overnight</option>
              </select>
              <p className="mt-1 text-xs text-text-secondary">
                Select only if your file contains F&amp;O rows and the import reports a product type
                error.
              </p>
            </FieldRow>
          )}

          {/* File input */}
          <FieldRow>
            <Label htmlFor={`${uid}-file`}>Broker CSV file</Label>
            <input
              id={`${uid}-file`}
              aria-label="Broker CSV file"
              type="file"
              accept=".csv"
              onChange={handleFileChange}
              className="w-full text-sm text-text-secondary file:mr-3 file:rounded file:border-0 file:bg-surface-subtle file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-text-primary hover:file:bg-surface-info"
            />
            {file && !fileError && (
              <p className="mt-1 text-xs text-text-secondary">Selected: {file.name}</p>
            )}
            {fileError && (
              <p role="alert" className="mt-1 text-xs text-danger-emphasis">
                {fileError}
              </p>
            )}
            {fileSizeWarning && !fileError && (
              <p role="note" className="mt-1 text-xs text-warning-emphasis">
                This file is unusually large for a broker export. Proceed?
              </p>
            )}
          </FieldRow>

          {/* Result banner (above the submit button, inside form) */}
          {result && <ResultBanner result={result} onReset={handleReset} />}

          {/* Action buttons */}
          {result ? (
            <button
              type="button"
              onClick={handleReset}
              className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-subtle hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/50"
            >
              Import another file
            </button>
          ) : (
            <button
              type="submit"
              disabled={!canSubmit}
              className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:bg-primary-emphasis focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting ? 'Importing…' : 'Import'}
            </button>
          )}
        </form>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Section 2 — Import history                                          */}
      {/* ------------------------------------------------------------------ */}
      <section className="rounded-xl border border-border bg-surface-base p-6">
        <SectionHeading>Import history</SectionHeading>
        <HistoryTable records={history} loading={historyLoading} />
      </section>
    </div>
  )
}
