import { useState } from 'react'
import { useAccount } from '@/features/accounts/context/AccountContext'
import { accountsApi } from '@/features/accounts/api'
import { useFocusTrap } from '@/shared/hooks/useFocusTrap'
import { CreateAccountModal } from './CreateAccountModal'
import { EditAccountModal } from './EditAccountModal'
import type { Account } from '@/features/accounts/types'

interface DeactivateConfirmDialogProps {
  account: Account
  isDeactivating: boolean
  onCancel: () => void
  onConfirm: () => void
}

function DeactivateConfirmDialog({
  account,
  isDeactivating,
  onCancel,
  onConfirm,
}: DeactivateConfirmDialogProps) {
  const dialogRef = useFocusTrap(onCancel)

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-label="Confirm deactivation"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    >
      <div className="w-full max-w-sm rounded-xl border border-border bg-surface-base p-6 shadow-lg">
        <p className="text-sm text-text-primary mb-4">
          Are you sure you want to deactivate{' '}
          <strong>{account.display_name}</strong>? It will no longer appear in
          analytics or trade imports.
        </p>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/50"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={isDeactivating}
            onClick={onConfirm}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500/50 disabled:opacity-50"
          >
            {isDeactivating ? 'Deactivating…' : 'Deactivate'}
          </button>
        </div>
      </div>
    </div>
  )
}

export function AccountsSection() {
  const { accounts, selectedAccount, selectAccount, refetchAccounts, isLoading } = useAccount()
  const [showCreate, setShowCreate] = useState(false)
  const [editAccount, setEditAccount] = useState<Account | null>(null)
  const [deactivateAccount, setDeactivateAccount] = useState<Account | null>(null)
  const [deactivating, setDeactivating] = useState(false)

  async function handleDeactivate(account: Account) {
    setDeactivating(true)
    try {
      await accountsApi.deactivate(account.id)
      refetchAccounts()
    } finally {
      setDeactivating(false)
      setDeactivateAccount(null)
    }
  }

  if (isLoading) {
    return <div className="text-text-secondary text-sm">Loading accounts…</div>
  }

  return (
    <section aria-label="Accounts settings" className="max-w-2xl">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-text-primary">Trading Accounts</h2>
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary/50"
        >
          Add Account
        </button>
      </div>

      {accounts.length === 0 ? (
        <p className="text-sm text-text-secondary">No accounts yet. Add one to get started.</p>
      ) : (
        <ul className="flex flex-col gap-3" role="list">
          {accounts.map((account) => (
            <li
              key={account.id}
              className="rounded-xl border border-border bg-surface-base p-4 flex flex-col gap-2"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-text-primary text-sm">
                    {account.display_name}
                  </span>
                  {selectedAccount?.id === account.id && (
                    <span className="rounded-full bg-surface-info px-2 py-0.5 text-xs font-medium text-primary">
                      Selected
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {account.status === 'ACTIVE' && selectedAccount?.id !== account.id && (
                    <button
                      type="button"
                      onClick={() => selectAccount(account.id)}
                      className="text-xs text-primary hover:underline focus:outline-none focus:ring-2 focus:ring-primary/50 rounded"
                    >
                      Select
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setEditAccount(account)}
                    className="rounded border border-border px-2 py-1 text-xs text-text-secondary hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/50"
                  >
                    Edit
                  </button>
                  {account.status === 'ACTIVE' && (
                    <button
                      type="button"
                      onClick={() => setDeactivateAccount(account)}
                      className="rounded border border-border px-2 py-1 text-xs text-red-500 hover:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-500/50"
                    >
                      Deactivate
                    </button>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-3 text-xs text-text-secondary">
                <span
                  className="rounded-full border border-border px-2 py-0.5 font-medium"
                  aria-label={`Broker: ${account.broker}`}
                >
                  {account.broker}
                </span>
                <span>{account.account_type}</span>
                <span
                  className={`rounded-full px-2 py-0.5 font-medium ${
                    account.status === 'ACTIVE'
                      ? 'bg-green-50 text-green-700'
                      : 'bg-surface-subtle text-text-secondary'
                  }`}
                >
                  {account.status}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}

      {deactivateAccount && (
        <DeactivateConfirmDialog
          account={deactivateAccount}
          isDeactivating={deactivating}
          onCancel={() => setDeactivateAccount(null)}
          onConfirm={() => void handleDeactivate(deactivateAccount)}
        />
      )}

      {showCreate && (
        <CreateAccountModal
          onClose={() => setShowCreate(false)}
          onCreated={refetchAccounts}
        />
      )}

      {editAccount && (
        <EditAccountModal
          account={editAccount}
          onClose={() => setEditAccount(null)}
          onUpdated={refetchAccounts}
        />
      )}
    </section>
  )
}
