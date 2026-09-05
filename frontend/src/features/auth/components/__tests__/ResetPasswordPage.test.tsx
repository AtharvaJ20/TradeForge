import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ResetPasswordPage } from '../ResetPasswordPage'
import { ApiError } from '@/lib/api-client'
import type { useConfirmPasswordReset } from '../../hooks/usePasswordReset'

// ---------------------------------------------------------------------------
// Mock useConfirmPasswordReset
// ---------------------------------------------------------------------------

vi.mock('../../hooks/usePasswordReset', () => ({
  useRequestPasswordReset: vi.fn(),
  useConfirmPasswordReset: vi.fn(),
}))

import { useConfirmPasswordReset as _useConfirmPasswordReset } from '../../hooks/usePasswordReset'

const mockUseConfirmPasswordReset = vi.mocked(_useConfirmPasswordReset)

function makeConfirm(
  overrides: Partial<ReturnType<typeof useConfirmPasswordReset>> = {},
): ReturnType<typeof useConfirmPasswordReset> {
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
  } as ReturnType<typeof useConfirmPasswordReset>
}

beforeEach(() => {
  mockUseConfirmPasswordReset.mockReturnValue(makeConfirm())
})

function renderReset(search = '?token=valid-token') {
  render(
    <MemoryRouter initialEntries={[`/reset-password${search}`]}>
      <ResetPasswordPage />
    </MemoryRouter>,
  )
}

// ---------------------------------------------------------------------------
// F-14-22: no token → "Invalid reset link" immediately
// ---------------------------------------------------------------------------

describe('ResetPasswordPage — F-14-22: no-token state', () => {
  it('shows "Invalid reset link" when no token is in the URL', () => {
    renderReset('')
    expect(screen.getByRole('heading', { name: /invalid reset link/i })).toBeInTheDocument()
    expect(screen.queryByLabelText(/new password/i)).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-14-23: with token renders the form
// ---------------------------------------------------------------------------

describe('ResetPasswordPage — F-14-23: renders form when token present', () => {
  it('renders new password and confirm password fields', () => {
    renderReset()
    expect(screen.getByLabelText('New password')).toBeInTheDocument()
    expect(screen.getByLabelText('Confirm new password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /set new password/i })).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-14-24: password mismatch shows error without calling mutate
// ---------------------------------------------------------------------------

describe('ResetPasswordPage — F-14-24: password mismatch client error', () => {
  it('shows "Passwords do not match" and does not call mutate when passwords differ', async () => {
    const user = userEvent.setup()
    const mutateFn = vi.fn()
    mockUseConfirmPasswordReset.mockReturnValue(makeConfirm({ mutate: mutateFn }))

    renderReset()

    await user.type(screen.getByLabelText('New password'), 'Password1!')
    await user.type(screen.getByLabelText('Confirm new password'), 'Different1!')
    await user.click(screen.getByRole('button', { name: /set new password/i }))

    expect(screen.getByRole('alert')).toHaveTextContent(/passwords do not match/i)
    expect(mutateFn).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// F-14-25: matching passwords calls mutate with token and newPassword
// ---------------------------------------------------------------------------

describe('ResetPasswordPage — F-14-25: submit calls mutate', () => {
  it('calls mutate with token and newPassword when passwords match', async () => {
    const user = userEvent.setup()
    const mutateFn = vi.fn()
    mockUseConfirmPasswordReset.mockReturnValue(makeConfirm({ mutate: mutateFn }))

    renderReset('?token=my-reset-token')

    await user.type(screen.getByLabelText('New password'), 'Password1!')
    await user.type(screen.getByLabelText('Confirm new password'), 'Password1!')
    await user.click(screen.getByRole('button', { name: /set new password/i }))

    expect(mutateFn).toHaveBeenCalledWith(
      { token: 'my-reset-token', newPassword: 'Password1!' },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    )
  })
})

// ---------------------------------------------------------------------------
// F-14-26: API error renders alert
// ---------------------------------------------------------------------------

describe('ResetPasswordPage — F-14-26: API error renders alert', () => {
  it('shows "reset link is invalid or has expired" for INVALID_OR_EXPIRED_TOKEN error', () => {
    mockUseConfirmPasswordReset.mockReturnValue(
      makeConfirm({
        error: new ApiError(400, 'INVALID_OR_EXPIRED_TOKEN'),
        isError: true,
      }),
    )
    renderReset()
    expect(screen.getByRole('alert')).toHaveTextContent(/reset link is invalid or has expired/i)
  })
})

// ---------------------------------------------------------------------------
// plan F-14-25: 422 policy message rendered verbatim
// ---------------------------------------------------------------------------

describe('ResetPasswordPage — 422 policy message verbatim', () => {
  it('shows the exact policy detail string for 422 errors', () => {
    mockUseConfirmPasswordReset.mockReturnValue(
      makeConfirm({
        error: new ApiError(422, 'Password must be at least 8 characters.'),
        isError: true,
      }),
    )
    renderReset()
    expect(screen.getByRole('alert')).toHaveTextContent('Password must be at least 8 characters.')
  })
})

// ---------------------------------------------------------------------------
// plan F-14-24 (navigation): navigates to /login?reset=1 on success
// ---------------------------------------------------------------------------

describe('ResetPasswordPage — navigation to /login?reset=1', () => {
  it('navigates to /login?reset=1 when password reset succeeds', async () => {
    const user = userEvent.setup()
    const mutateFn = vi.fn().mockImplementation(
      (_vars: unknown, options?: { onSuccess?: (data: unknown) => void }) => {
        options?.onSuccess?.({ message: 'ok' })
      },
    )
    mockUseConfirmPasswordReset.mockReturnValue(makeConfirm({ mutate: mutateFn }))

    render(
      <MemoryRouter initialEntries={['/reset-password?token=valid-token']}>
        <Routes>
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/login" element={<div>Login page</div>} />
        </Routes>
      </MemoryRouter>,
    )

    await user.type(screen.getByLabelText('New password'), 'Password1!')
    await user.type(screen.getByLabelText('Confirm new password'), 'Password1!')
    await user.click(screen.getByRole('button', { name: /set new password/i }))

    expect(screen.getByText('Login page')).toBeInTheDocument()
  })
})
