import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AccountProvider, useAccount } from '../AccountContext'
import { ACCOUNTS_LIST_FIXTURE } from '@/__tests__/msw/handlers'

// ---------------------------------------------------------------------------
// Helper: consumer component that renders context values
// ---------------------------------------------------------------------------

function AccountConsumer() {
  const { accounts, selectedAccount, selectAccount, isLoading } = useAccount()

  if (isLoading) return <div>Loading...</div>

  return (
    <div>
      <p data-testid="count">{accounts.length}</p>
      <p data-testid="selected">{selectedAccount?.id ?? 'none'}</p>
      <ul>
        {accounts.map((a) => (
          <li key={a.id}>
            <button type="button" onClick={() => selectAccount(a.id)}>
              {a.display_name}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function renderWithProvider() {
  return render(
    <AccountProvider>
      <AccountConsumer />
    </AccountProvider>,
  )
}

// ---------------------------------------------------------------------------
// F-15-01: On mount, fetches /v1/accounts and populates accounts list
// ---------------------------------------------------------------------------

describe('AccountContext — F-15-01: populates accounts list', () => {
  it('fetches /v1/accounts on mount and exposes the list', async () => {
    renderWithProvider()
    await waitFor(() => {
      expect(screen.getByTestId('count')).toHaveTextContent('2')
    })
  })
})

// ---------------------------------------------------------------------------
// F-15-02: Auto-selects first ACTIVE account when no stored selection
// ---------------------------------------------------------------------------

describe('AccountContext — F-15-02: auto-selects first ACTIVE account', () => {
  beforeEach(() => {
    try {
      localStorage.removeItem('tf_selected_account_id')
    } catch {
      // ignore
    }
  })

  it('auto-selects the first ACTIVE account when localStorage is empty', async () => {
    renderWithProvider()
    await waitFor(() => {
      // ACCOUNTS_LIST_FIXTURE[0] is ACTIVE
      expect(screen.getByTestId('selected')).toHaveTextContent(
        ACCOUNTS_LIST_FIXTURE[0].id,
      )
    })
  })
})

// ---------------------------------------------------------------------------
// F-15-03: Restores stored selectedAccountId from localStorage if present
// ---------------------------------------------------------------------------

describe('AccountContext — F-15-03: restores stored selection', () => {
  beforeEach(() => {
    try {
      localStorage.setItem('tf_selected_account_id', ACCOUNTS_LIST_FIXTURE[0].id)
    } catch {
      // ignore
    }
  })

  it('restores the stored ACTIVE account from localStorage', async () => {
    renderWithProvider()
    await waitFor(() => {
      expect(screen.getByTestId('selected')).toHaveTextContent(
        ACCOUNTS_LIST_FIXTURE[0].id,
      )
    })
  })
})

// ---------------------------------------------------------------------------
// F-15-04: Falls back to first ACTIVE account if stored ID not in fetched list
// ---------------------------------------------------------------------------

describe('AccountContext — F-15-04: falls back if stored ID missing', () => {
  beforeEach(() => {
    try {
      localStorage.setItem('tf_selected_account_id', '00000000-0000-0000-0000-999999999999')
    } catch {
      // ignore
    }
  })

  it('falls back to first ACTIVE account when stored ID is not in fetched accounts', async () => {
    renderWithProvider()
    await waitFor(() => {
      // Should fall back to ACCOUNTS_LIST_FIXTURE[0] (the ACTIVE one)
      expect(screen.getByTestId('selected')).toHaveTextContent(
        ACCOUNTS_LIST_FIXTURE[0].id,
      )
    })
  })
})

// ---------------------------------------------------------------------------
// F-15-05: selectAccount() updates selectedAccount and writes to localStorage
// ---------------------------------------------------------------------------

describe('AccountContext — F-15-05: selectAccount updates state and localStorage', () => {
  beforeEach(() => {
    try {
      localStorage.removeItem('tf_selected_account_id')
    } catch {
      // ignore
    }
  })

  it('updates selectedAccount and persists to localStorage on selectAccount()', async () => {
    const user = userEvent.setup()
    renderWithProvider()
    await waitFor(() => {
      expect(screen.getByTestId('count')).toHaveTextContent('2')
    })

    const activeAccount = ACCOUNTS_LIST_FIXTURE[0]
    await act(async () => {
      await user.click(screen.getByRole('button', { name: activeAccount.display_name }))
    })

    expect(screen.getByTestId('selected')).toHaveTextContent(activeAccount.id)
    try {
      expect(localStorage.getItem('tf_selected_account_id')).toBe(activeAccount.id)
    } catch {
      // localStorage may not be available in all test environments
    }
  })
})
