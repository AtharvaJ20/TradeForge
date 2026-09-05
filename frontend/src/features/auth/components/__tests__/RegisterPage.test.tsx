import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { RegisterPage } from '../RegisterPage'
import { ApiError } from '@/lib/api-client'
import type { useRegister } from '../../hooks/useRegister'

// ---------------------------------------------------------------------------
// Mock useRegister — isolate RegisterPage from network
// ---------------------------------------------------------------------------

vi.mock('../../hooks/useRegister', () => ({
  useRegister: vi.fn(),
}))

import { useRegister as _useRegister } from '../../hooks/useRegister'

const mockUseRegister = vi.mocked(_useRegister)

function makeRegister(overrides: Partial<ReturnType<typeof useRegister>> = {}): ReturnType<typeof useRegister> {
  return {
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
    isSuccess: false,
    isError: false,
    isIdle: true,
    error: null,
    data: undefined,
    reset: vi.fn(),
    context: undefined,
    failureCount: 0,
    failureReason: null,
    isPaused: false,
    status: 'idle',
    submittedAt: 0,
    variables: undefined,
    ...overrides,
  } as ReturnType<typeof useRegister>
}

beforeEach(() => {
  mockUseRegister.mockReturnValue(makeRegister())
})

function renderRegister() {
  render(
    <MemoryRouter initialEntries={['/register']}>
      <RegisterPage />
    </MemoryRouter>,
  )
}

// ---------------------------------------------------------------------------
// F-14-09: renders form fields
// ---------------------------------------------------------------------------

describe('RegisterPage — F-14-09: renders form fields', () => {
  it('renders email, password, confirm-password inputs and submit button', () => {
    renderRegister()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign up/i })).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-14-10: renders password strength bar
// ---------------------------------------------------------------------------

describe('RegisterPage — F-14-10: password strength indicator', () => {
  it('renders the password strength indicator', () => {
    renderRegister()
    expect(screen.getByLabelText(/password strength/i)).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-14-11: client-side confirm mismatch shows error without calling mutate
// ---------------------------------------------------------------------------

describe('RegisterPage — F-14-11: password mismatch shows client error', () => {
  it('shows "Passwords do not match" without calling mutate when confirm differs', async () => {
    const user = userEvent.setup()
    const mutateFn = vi.fn()
    mockUseRegister.mockReturnValue(makeRegister({ mutate: mutateFn }))

    renderRegister()

    await user.type(screen.getByLabelText(/email/i), 'a@b.com')
    await user.type(screen.getByLabelText(/^password$/i), 'Password1!')
    await user.type(screen.getByLabelText(/confirm password/i), 'Different1!')
    await user.click(screen.getByRole('button', { name: /sign up/i }))

    expect(screen.getByRole('alert')).toHaveTextContent(/passwords do not match/i)
    expect(mutateFn).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// F-14-12: successful submit calls mutate with email and password
// ---------------------------------------------------------------------------

describe('RegisterPage — F-14-12: submit calls mutate', () => {
  it('calls mutate with email and password when passwords match', async () => {
    const user = userEvent.setup()
    const mutateFn = vi.fn()
    mockUseRegister.mockReturnValue(makeRegister({ mutate: mutateFn }))

    renderRegister()

    await user.type(screen.getByLabelText(/email/i), 'user@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'Password1!')
    await user.type(screen.getByLabelText(/confirm password/i), 'Password1!')
    await user.click(screen.getByRole('button', { name: /sign up/i }))

    expect(mutateFn).toHaveBeenCalledWith(
      { email: 'user@example.com', password: 'Password1!' },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    )
  })
})

// ---------------------------------------------------------------------------
// F-14-13: submit button disabled while pending
// ---------------------------------------------------------------------------

describe('RegisterPage — F-14-13: button disabled while pending', () => {
  it('disables the submit button when isPending is true', () => {
    mockUseRegister.mockReturnValue(makeRegister({ isPending: true }))
    renderRegister()
    expect(screen.getByRole('button', { name: /creating account/i })).toBeDisabled()
  })
})

// ---------------------------------------------------------------------------
// F-14-14: API error renders alert
// ---------------------------------------------------------------------------

describe('RegisterPage — F-14-14: API error renders alert', () => {
  it('renders the API error message when mutation has an error', () => {
    mockUseRegister.mockReturnValue(
      makeRegister({ error: new ApiError(429, 'RATE_LIMITED'), isError: true }),
    )
    renderRegister()
    expect(screen.getByRole('alert')).toHaveTextContent(/too many registration attempts/i)
  })
})
