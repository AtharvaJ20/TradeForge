import { useState } from 'react'
import { accountsApi } from '@/features/accounts/api'
import { ApiError } from '@/lib/api-client'
import { useFocusTrap } from '@/shared/hooks/useFocusTrap'

const BROKERS = ['ZERODHA', 'UPSTOX', 'ANGEL_ONE', 'MANUAL'] as const
const ACCOUNT_TYPES = ['INDIVIDUAL', 'HUF'] as const

interface Props {
  onClose: () => void
  onCreated: () => void
}

export function CreateAccountModal({ onClose, onCreated }: Props) {
  const dialogRef = useFocusTrap(onClose)
  const [displayName, setDisplayName] = useState('')
  const [broker, setBroker] = useState<string>(BROKERS[0])
  const [accountType, setAccountType] = useState<string>(ACCOUNT_TYPES[0])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [nameError, setNameError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setNameError(null)

    if (!displayName.trim()) {
      setNameError('Display name is required')
      return
    }

    setIsSubmitting(true)
    try {
      await accountsApi.create({
        broker,
        display_name: displayName.trim(),
        account_type: accountType,
        base_currency: 'INR',
      })
      onCreated()
      onClose()
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail)
      } else {
        setError('Failed to create account')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-label="Create account"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    >
      <div className="w-full max-w-md rounded-xl border border-border bg-surface-base p-6 shadow-lg">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-text-primary">Add Account</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded p-1 text-text-secondary hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/50"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label htmlFor="create-display-name" className="text-sm font-medium text-text-primary">
              Display Name <span aria-hidden="true">*</span>
            </label>
            <input
              id="create-display-name"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              maxLength={100}
              required
              className="rounded-lg border border-border bg-surface-base px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
            {nameError && (
              <p role="alert" className="text-xs text-red-500">
                {nameError}
              </p>
            )}
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="create-broker" className="text-sm font-medium text-text-primary">
              Broker
            </label>
            <select
              id="create-broker"
              value={broker}
              onChange={(e) => setBroker(e.target.value)}
              className="rounded-lg border border-border bg-surface-base px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/50"
            >
              {BROKERS.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="create-account-type" className="text-sm font-medium text-text-primary">
              Account Type
            </label>
            <select
              id="create-account-type"
              value={accountType}
              onChange={(e) => setAccountType(e.target.value)}
              className="rounded-lg border border-border bg-surface-base px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/50"
            >
              {ACCOUNT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="create-currency" className="text-sm font-medium text-text-primary">
              Base Currency
            </label>
            <select
              id="create-currency"
              value="INR"
              disabled
              className="rounded-lg border border-border bg-surface-subtle px-3 py-2 text-sm text-text-secondary focus:outline-none"
            >
              <option value="INR">INR</option>
            </select>
          </div>

          {error && (
            <p role="alert" className="text-sm text-red-500">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2 mt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:opacity-50"
            >
              {isSubmitting ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
