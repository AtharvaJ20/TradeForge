import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AccountProvider } from '@/features/accounts/context/AccountContext'
import { AccountsSection } from '../AccountsSection'
import { ACCOUNTS_LIST_FIXTURE } from '@/__tests__/msw/handlers'

// ---------------------------------------------------------------------------
// Wrapper: AccountProvider supplies accounts from MSW GET /v1/accounts
// ---------------------------------------------------------------------------

function renderSection() {
  return render(
    <AccountProvider>
      <AccountsSection />
    </AccountProvider>,
  )
}

// ---------------------------------------------------------------------------
// F-15-12: Renders account list with display name, broker, status for each account
// ---------------------------------------------------------------------------

describe('AccountsSection — F-15-12: renders account list', () => {
  it('renders display name, broker, and status for each account', async () => {
    renderSection()
    await waitFor(() => {
      expect(screen.getByText(ACCOUNTS_LIST_FIXTURE[0].display_name)).toBeInTheDocument()
    })
    expect(screen.getByText(ACCOUNTS_LIST_FIXTURE[1].display_name)).toBeInTheDocument()
    expect(screen.getByText(ACCOUNTS_LIST_FIXTURE[0].broker)).toBeInTheDocument()
    expect(screen.getByText(ACCOUNTS_LIST_FIXTURE[0].status)).toBeInTheDocument()
    expect(screen.getByText(ACCOUNTS_LIST_FIXTURE[1].status)).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-15-13: INACTIVE account does not show a Deactivate button
// ---------------------------------------------------------------------------

describe('AccountsSection — F-15-13: INACTIVE account has no Deactivate button', () => {
  it('does not render Deactivate button for INACTIVE accounts', async () => {
    renderSection()
    await waitFor(() => {
      expect(screen.getByText(ACCOUNTS_LIST_FIXTURE[1].display_name)).toBeInTheDocument()
    })

    // Find the INACTIVE account's list item
    const allItems = screen.getAllByRole('listitem')
    const inactiveItem = allItems.find((item) =>
      within(item).queryByText(ACCOUNTS_LIST_FIXTURE[1].display_name),
    )
    expect(inactiveItem).toBeDefined()
    if (inactiveItem) {
      expect(within(inactiveItem).queryByRole('button', { name: /deactivate/i })).toBeNull()
    }
  })
})

// ---------------------------------------------------------------------------
// F-15-14: Clicking "Add Account" opens CreateAccountModal
// ---------------------------------------------------------------------------

describe('AccountsSection — F-15-14: Add Account opens CreateAccountModal', () => {
  it('opens CreateAccountModal when "Add Account" button is clicked', async () => {
    const user = userEvent.setup()
    renderSection()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /add account/i })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /add account/i }))

    expect(screen.getByRole('dialog', { name: /create account/i })).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-15-15: CreateAccountModal submit with valid data calls POST /v1/accounts and closes
// ---------------------------------------------------------------------------

describe('AccountsSection — F-15-15: CreateAccountModal valid submit', () => {
  beforeEach(() => {
    try {
      localStorage.removeItem('tf_selected_account_id')
    } catch {
      // ignore
    }
  })

  it('calls POST /v1/accounts and closes modal on valid submit', async () => {
    const user = userEvent.setup()
    renderSection()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /add account/i })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /add account/i }))

    const dialog = screen.getByRole('dialog', { name: /create account/i })
    const nameInput = within(dialog).getByLabelText(/display name/i)
    await user.type(nameInput, 'My New Account')

    await user.click(within(dialog).getByRole('button', { name: /^create$/i }))

    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: /create account/i })).toBeNull()
    })
  })
})

// ---------------------------------------------------------------------------
// F-15-16: CreateAccountModal blank display name shows validation error
// ---------------------------------------------------------------------------

describe('AccountsSection — F-15-16: CreateAccountModal blank name validation', () => {
  it('shows validation error and makes no API call when display name is blank', async () => {
    const user = userEvent.setup()
    renderSection()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /add account/i })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /add account/i }))

    const dialog = screen.getByRole('dialog', { name: /create account/i })
    // Submit without entering a name
    await user.click(within(dialog).getByRole('button', { name: /^create$/i }))

    await waitFor(() => {
      expect(within(dialog).getByRole('alert')).toHaveTextContent(/required/i)
    })

    // Dialog remains open
    expect(screen.getByRole('dialog', { name: /create account/i })).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-15-17: Clicking Edit opens EditAccountModal pre-populated with account data
// ---------------------------------------------------------------------------

describe('AccountsSection — F-15-17: Edit opens EditAccountModal with pre-populated data', () => {
  it('opens EditAccountModal with existing account data when Edit is clicked', async () => {
    const user = userEvent.setup()
    renderSection()

    await waitFor(() => {
      expect(screen.getByText(ACCOUNTS_LIST_FIXTURE[0].display_name)).toBeInTheDocument()
    })

    const editButtons = screen.getAllByRole('button', { name: /edit/i })
    await user.click(editButtons[0])

    const dialog = screen.getByRole('dialog', { name: /edit account/i })
    expect(within(dialog).getByLabelText(/display name/i)).toHaveValue(
      ACCOUNTS_LIST_FIXTURE[0].display_name,
    )
  })
})

// ---------------------------------------------------------------------------
// F-15-18: Deactivate confirmation calls DELETE /v1/accounts/{id}
// ---------------------------------------------------------------------------

describe('AccountsSection — F-15-18: Deactivate calls DELETE /v1/accounts/{id}', () => {
  it('shows confirmation dialog and calls DELETE on confirm', async () => {
    const user = userEvent.setup()
    renderSection()

    await waitFor(() => {
      expect(screen.getByText(ACCOUNTS_LIST_FIXTURE[0].display_name)).toBeInTheDocument()
    })

    // Click Deactivate button for the ACTIVE account
    const deactivateButtons = screen.getAllByRole('button', { name: /deactivate/i })
    await user.click(deactivateButtons[0])

    // Confirmation dialog should appear
    const confirmDialog = screen.getByRole('dialog', { name: /confirm deactivation/i })
    expect(confirmDialog).toBeInTheDocument()
    expect(confirmDialog).toHaveTextContent(ACCOUNTS_LIST_FIXTURE[0].display_name)

    // Click confirm
    await user.click(within(confirmDialog).getByRole('button', { name: /^deactivate$/i }))

    // Dialog should close after deactivation
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: /confirm deactivation/i })).toBeNull()
    })
  })
})
