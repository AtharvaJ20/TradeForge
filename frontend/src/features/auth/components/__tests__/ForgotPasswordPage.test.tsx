import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ForgotPasswordPage } from '../ForgotPasswordPage'
import { ApiError } from '@/lib/api-client'
import type { useRequestPasswordReset } from '../../hooks/usePasswordReset'

// ---------------------------------------------------------------------------
// Mock useRequestPasswordReset
// ---------------------------------------------------------------------------

vi.mock('../../hooks/usePasswordReset', () => ({
  useRequestPasswordReset: vi.fn(),
  useConfirmPasswordReset: vi.fn(),
}))

import { useRequestPasswordReset as _useRequestPasswordReset } from '../../hooks/usePasswordReset'

const mockUseRequestPasswordReset = vi.mocked(_useRequestPasswordReset)

function makeReset(
  overrides: Partial<ReturnType<typeof useRequestPasswordReset>> = {},
): ReturnType<typeof useRequestPasswordReset> {
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
  } as ReturnType<typeof useRequestPasswordReset>
}

beforeEach(() => {
  mockUseRequestPasswordReset.mockReturnValue(makeReset())
})

function renderForgot() {
  render(
    <MemoryRouter initialEntries={['/forgot-password']}>
      <ForgotPasswordPage />
    </MemoryRouter>,
  )
}

// ---------------------------------------------------------------------------
// F-14-19: renders email input and submit button
// ---------------------------------------------------------------------------

describe('ForgotPasswordPage — F-14-19: renders form', () => {
  it('renders email input and submit button', () => {
    renderForgot()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /send reset link/i })).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-14-20: submit calls mutate with the entered email
// ---------------------------------------------------------------------------

describe('ForgotPasswordPage — F-14-20: submit calls mutate with email', () => {
  it('calls mutate with the email entered by the user', async () => {
    const user = userEvent.setup()
    const mutateFn = vi.fn()
    mockUseRequestPasswordReset.mockReturnValue(makeReset({ mutate: mutateFn }))

    renderForgot()

    await user.type(screen.getByLabelText(/email/i), 'user@example.com')
    await user.click(screen.getByRole('button', { name: /send reset link/i }))

    expect(mutateFn).toHaveBeenCalledWith('user@example.com')
  })
})

// ---------------------------------------------------------------------------
// F-14-21: isSuccess → "Check your inbox" view replaces the form
// ---------------------------------------------------------------------------

describe('ForgotPasswordPage — F-14-21: success view replaces form', () => {
  it('shows "Check your inbox" heading and hides the form when isSuccess is true', () => {
    mockUseRequestPasswordReset.mockReturnValue(makeReset({ isSuccess: true }))
    renderForgot()

    expect(screen.getByRole('heading', { name: /check your inbox/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /send reset link/i })).not.toBeInTheDocument()
  })
})
