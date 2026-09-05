import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { accountsApi } from '../api'
import type { Account } from '../types'

const STORAGE_KEY = 'tf_selected_account_id'

interface AccountContextValue {
  accounts: Account[]
  selectedAccount: Account | null
  selectAccount: (id: string) => void
  isLoading: boolean
  refetchAccounts: () => void
}

const AccountContext = createContext<AccountContextValue | null>(null)

export function AccountProvider({ children }: { children: React.ReactNode }) {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [selectedAccount, setSelectedAccount] = useState<Account | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [fetchTick, setFetchTick] = useState(0)

  useEffect(() => {
    setIsLoading(true)
    accountsApi
      .list()
      .then((data) => {
        setAccounts(data)
        const storedId = (() => {
          try {
            return localStorage.getItem(STORAGE_KEY)
          } catch {
            return null
          }
        })()
        const stored = storedId
          ? data.find((a) => a.id === storedId && a.status === 'ACTIVE') ?? null
          : null
        const firstActive = data.find((a) => a.status === 'ACTIVE') ?? null
        const selected = stored ?? firstActive
        setSelectedAccount(selected)
        if (selected) {
          try {
            localStorage.setItem(STORAGE_KEY, selected.id)
          } catch {
            // ignore
          }
        }
      })
      .catch(() => {
        setAccounts([])
        setSelectedAccount(null)
      })
      .finally(() => setIsLoading(false))
  }, [fetchTick])

  const selectAccount = useCallback(
    (id: string) => {
      const account = accounts.find((a) => a.id === id) ?? null
      setSelectedAccount(account)
      if (account) {
        try {
          localStorage.setItem(STORAGE_KEY, account.id)
        } catch {
          // ignore
        }
      }
    },
    [accounts],
  )

  const refetchAccounts = useCallback(() => {
    setFetchTick((t) => t + 1)
  }, [])

  return (
    <AccountContext.Provider
      value={{ accounts, selectedAccount, selectAccount, isLoading, refetchAccounts }}
    >
      {children}
    </AccountContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAccount(): AccountContextValue {
  const ctx = useContext(AccountContext)
  if (ctx === null) {
    throw new Error('useAccount must be used inside <AccountProvider>')
  }
  return ctx
}
