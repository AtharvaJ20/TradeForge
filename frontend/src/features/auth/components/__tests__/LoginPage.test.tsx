import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { LoginPage } from '../LoginPage'
import { ApiError } from '@/lib/api-client'
import type { useAuth } from '../../context/AuthContext'

// ---------------------------------------------------------------------------
// Mock useAuth — isolate LoginPage from real AuthContext / network
// ---------------------------------------------------------------------------

vi.mock('../../context/AuthContext', () => ({
  useAuth: vi.fn(),
}))

import { useAuth as _useAuth } from '../../context/AuthContext'

const mockUseAuth = vi.mocked(_useAuth)

function makeAuth(overrides: Partial<ReturnType<typeof useAuth>> = {}): ReturnType<typeof useAuth> {
  return {
    user: null,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    ...overrides,
  }
}

function renderLogin(search = '') {
  mockUseAuth.mockReturnValue(makeAuth())
  render(
    <MemoryRouter initialEntries={[`/login${search}`]}>
      <LoginPage />
    </MemoryRouter>,
  )
}

// ---------------------------------------------------------------------------
// F-14-01: email input, password input, and submit button are rendered
// ---------------------------------------------------------------------------

describe('LoginPage — F-14-01: renders form fields', () => {
  it('renders email input, password input, and submit button', () => {
    renderLogin()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-14-02: shows session-expired banner when ?expired=1
// ---------------------------------------------------------------------------

describe('LoginPage — F-14-02: session-expired banner', () => {
  it('shows session-expired banner when ?expired=1 is present', () => {
    renderLogin('?expired=1')
    expect(screen.getByRole('alert')).toHaveTextContent(/session expired/i)
  })
})

// ---------------------------------------------------------------------------
// F-14-03: shows email-verified banner when ?verified=1
// ---------------------------------------------------------------------------

describe('LoginPage — F-14-03: email-verified banner', () => {
  it('shows email-verified banner when ?verified=1 is present', () => {
    renderLogin('?verified=1')
    expect(screen.getByRole('alert')).toHaveTextContent(/email verified/i)
  })
})

// ---------------------------------------------------------------------------
// F-14-04: shows password-reset banner when ?reset=1
// ---------------------------------------------------------------------------

describe('LoginPage — F-14-04: password-reset banner', () => {
  it('shows password-reset banner when ?reset=1 is present', () => {
    renderLogin('?reset=1')
    expect(screen.getByRole('alert')).toHaveTextContent(/password reset successful/i)
  })
})

// ---------------------------------------------------------------------------
// F-14-05: submit calls login(email, password)
// ---------------------------------------------------------------------------

describe('LoginPage — F-14-05: submit calls login', () => {
  it('calls login with the entered email and password on submit', async () => {
    const user = userEvent.setup()
    const loginFn = vi.fn().mockResolvedValue(undefined)
    mockUseAuth.mockReturnValue(makeAuth({ login: loginFn }))

    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>,
    )

    await user.type(screen.getByLabelText(/email/i), 'user@example.com')
    await user.type(screen.getByLabelText(/password/i), 'secret123')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(loginFn).toHaveBeenCalledWith('user@example.com', 'secret123')
    })
  })
})

// ---------------------------------------------------------------------------
// F-14-06: submit button disabled while submitting
// ---------------------------------------------------------------------------

describe('LoginPage — F-14-06: button disabled while submitting', () => {
  it('disables the submit button while login is in progress', async () => {
    const user = userEvent.setup()
    let resolve!: () => void
    const loginFn = vi.fn().mockReturnValue(new Promise<void>((r) => { resolve = r }))
    mockUseAuth.mockReturnValue(makeAuth({ login: loginFn }))

    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>,
    )

    await user.type(screen.getByLabelText(/email/i), 'a@b.com')
    await user.type(screen.getByLabelText(/password/i), 'pw')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(screen.getByRole('button', { name: /signing in/i })).toBeDisabled()
    resolve()
  })
})

// ---------------------------------------------------------------------------
// F-14-07: shows error for INVALID_CREDENTIALS
// ---------------------------------------------------------------------------

describe('LoginPage — F-14-07: INVALID_CREDENTIALS error', () => {
  it('shows "Incorrect email or password" for INVALID_CREDENTIALS detail', async () => {
    const user = userEvent.setup()
    const loginFn = vi.fn().mockRejectedValue(new ApiError(401, 'INVALID_CREDENTIALS'))
    mockUseAuth.mockReturnValue(makeAuth({ login: loginFn }))

    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>,
    )

    await user.type(screen.getByLabelText(/email/i), 'a@b.com')
    await user.type(screen.getByLabelText(/password/i), 'wrong')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/incorrect email or password/i)
    })
  })
})

// ---------------------------------------------------------------------------
// F-14-08: shows error for ACCOUNT_LOCKED
// ---------------------------------------------------------------------------

describe('LoginPage — F-14-08: ACCOUNT_LOCKED error', () => {
  it('shows "Account locked" for ACCOUNT_LOCKED detail', async () => {
    const user = userEvent.setup()
    const loginFn = vi.fn().mockRejectedValue(new ApiError(423, 'ACCOUNT_LOCKED'))
    mockUseAuth.mockReturnValue(makeAuth({ login: loginFn }))

    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>,
    )

    await user.type(screen.getByLabelText(/email/i), 'a@b.com')
    await user.type(screen.getByLabelText(/password/i), 'pw')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/account locked/i)
    })
  })
})
