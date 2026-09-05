import { useState } from 'react'
import { accountsApi } from '@/features/accounts/api'
import { ApiError } from '@/lib/api-client'
import type { Account } from '@/features/accounts/types'

const ACCOUNT_TYPES = ['INDIVIDUAL', 'HUF'] as const

interface Props {
  account: Account
  onClose: () => void
  onUpdated: () => void
}

export function EditAccountModal({ account, onClose, onUpdated }: Props) {
  const [displayName, setDisplayName] = useState(account.display_name)
  const [accountType, setAccountType] = useState(account.account_type)
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
      await accountsApi.update(account.id, {
        display_name: displayName.trim(),
        account_type: accountType,
      })
      onUpdated()
      onClose()
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail)
      } else {
        setError('Failed to update account')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Edit account"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    >
      <div className="w-full max-w-md rounded-xl border border-border bg-surface-base p-6 shadow-lg">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-text-primary">Edit Account</h2>
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
            <label htmlFor="edit-display-name" className="text-sm font-medium text-text-primary">
              Display Name <span aria-hidden="true">*</span>
            </label>
            <input
              id="edit-display-name"
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
            <label htmlFor="edit-account-type" className="text-sm font-medium text-text-primary">
              Account Type
            </label>
            <select
              id="edit-account-type"
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
            <p className="text-sm text-text-secondary">
              <span className="font-medium text-text-primary">Broker:</span> {account.broker}
            </p>
            <p className="text-sm text-text-secondary">
              <span className="font-medium text-text-primary">Currency:</span>{' '}
              {account.base_currency}
            </p>
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
              {isSubmitting ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
