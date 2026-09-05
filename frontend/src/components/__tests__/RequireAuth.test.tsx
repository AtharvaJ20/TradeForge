import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { RequireAuth } from '../RequireAuth'
import type { useAuth } from '@/features/auth/context/AuthContext'

// ---------------------------------------------------------------------------
// Mock useAuth — RequireAuth only reads user and isLoading
// ---------------------------------------------------------------------------

vi.mock('@/features/auth/context/AuthContext', () => ({
  useAuth: vi.fn(),
}))

import { useAuth as _useAuth } from '@/features/auth/context/AuthContext'

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

function renderWithRouter(initialPath: string) {
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<RequireAuth />}>
          <Route path="/analytics" element={<div>Analytics page</div>} />
        </Route>
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

// ---------------------------------------------------------------------------
// F-14-27: authenticated user sees the outlet
// ---------------------------------------------------------------------------

describe('RequireAuth — F-14-27: authenticated renders Outlet', () => {
  it('renders the outlet content when user is authenticated', () => {
    mockUseAuth.mockReturnValue(
      makeAuth({ user: { id: '1', email: 'a@b.com', is_email_verified: true, is_admin: false } }),
    )
    renderWithRouter('/analytics')
    expect(screen.getByText('Analytics page')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-14-28: unauthenticated user is redirected to /login?next=<pathname>
// ---------------------------------------------------------------------------

describe('RequireAuth — F-14-28: unauthenticated redirects to /login', () => {
  it('redirects to /login?next=/analytics when user is null', () => {
    mockUseAuth.mockReturnValue(makeAuth({ user: null, isLoading: false }))
    renderWithRouter('/analytics')
    expect(screen.getByText('Login page')).toBeInTheDocument()
    expect(screen.queryByText('Analytics page')).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-14-29: renders null while isLoading (no flash of login page)
// ---------------------------------------------------------------------------

describe('RequireAuth — F-14-29: renders null while loading', () => {
  it('renders nothing while isLoading is true', () => {
    mockUseAuth.mockReturnValue(makeAuth({ user: null, isLoading: true }))
    renderWithRouter('/analytics')
    expect(screen.queryByText('Login page')).not.toBeInTheDocument()
    expect(screen.queryByText('Analytics page')).not.toBeInTheDocument()
  })
})
