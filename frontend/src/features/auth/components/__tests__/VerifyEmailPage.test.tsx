import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { VerifyEmailPage } from '../VerifyEmailPage'
import { ApiError } from '@/lib/api-client'

// ---------------------------------------------------------------------------
// Mock authApi — VerifyEmailPage calls authApi.verifyEmail directly
// ---------------------------------------------------------------------------

vi.mock('../../api', () => ({
  authApi: {
    verifyEmail: vi.fn(),
  },
}))

import { authApi } from '../../api'

const mockVerifyEmail = vi.mocked(authApi.verifyEmail)

beforeEach(() => {
  vi.clearAllMocks()
})

function renderVerify(search = '') {
  render(
    <MemoryRouter initialEntries={[`/verify-email${search}`]}>
      <VerifyEmailPage />
    </MemoryRouter>,
  )
}

// ---------------------------------------------------------------------------
// F-14-15: no token → "Invalid verification link" immediately
// ---------------------------------------------------------------------------

describe('VerifyEmailPage — F-14-15: no-token state', () => {
  it('shows invalid verification link when no token is present', () => {
    renderVerify()
    expect(screen.getByRole('heading', { name: /invalid verification link/i })).toBeInTheDocument()
    expect(mockVerifyEmail).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// F-14-16: valid token → loading → success and calls verifyEmail
// ---------------------------------------------------------------------------

describe('VerifyEmailPage — F-14-16: success state after verifyEmail resolves', () => {
  it('shows loading then success after verifyEmail resolves', async () => {
    mockVerifyEmail.mockResolvedValue({ message: 'ok' })
    renderVerify('?token=valid-token-abc')

    expect(screen.getByText(/verifying your email/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /email verified/i })).toBeInTheDocument()
    })

    expect(mockVerifyEmail).toHaveBeenCalledWith('valid-token-abc')
  })
})

// ---------------------------------------------------------------------------
// F-14-17: invalid token → error heading shown
// ---------------------------------------------------------------------------

describe('VerifyEmailPage — F-14-17: error state for invalid token', () => {
  it('shows verification failed heading when verifyEmail rejects with INVALID_OR_EXPIRED_TOKEN', async () => {
    mockVerifyEmail.mockRejectedValue(new ApiError(400, 'INVALID_OR_EXPIRED_TOKEN'))
    renderVerify('?token=bad-token')

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /verification failed/i })).toBeInTheDocument()
    })

    expect(screen.getByText(/invalid or has expired/i)).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-14-18: generic error → "Something went wrong" message
// ---------------------------------------------------------------------------

describe('VerifyEmailPage — F-14-18: generic error fallback', () => {
  it('shows "Something went wrong" for non-ApiError rejections', async () => {
    mockVerifyEmail.mockRejectedValue(new Error('Network error'))
    renderVerify('?token=any-token')

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /verification failed/i })).toBeInTheDocument()
    })

    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// plan F-14-16 (timer): redirects to /login?verified=1 after 2 seconds
// ---------------------------------------------------------------------------

describe('VerifyEmailPage — F-14-16b: redirect to /login?verified=1 after 2s', () => {
  it('navigates to /login?verified=1 two seconds after successful verification', async () => {
    vi.useFakeTimers()
    mockVerifyEmail.mockResolvedValue({ message: 'ok' })

    render(
      <MemoryRouter initialEntries={['/verify-email?token=valid-token']}>
        <Routes>
          <Route path="/verify-email" element={<VerifyEmailPage />} />
          <Route path="/login" element={<div>Login page</div>} />
        </Routes>
      </MemoryRouter>,
    )

    // flush microtasks so the Promise .then() fires and state updates
    await act(async () => {})

    expect(screen.getByRole('heading', { name: /email verified/i })).toBeInTheDocument()

    act(() => { vi.advanceTimersByTime(2001) })

    expect(screen.getByText('Login page')).toBeInTheDocument()
    vi.useRealTimers()
  })
})
