import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/layout/AppShell'
import type { useAuth } from '@/features/auth/context/AuthContext'

// ---------------------------------------------------------------------------
// Mock useAuth — AppShell only calls logout and reads nothing else
// ---------------------------------------------------------------------------

vi.mock('@/features/auth/context/AuthContext', () => ({
  useAuth: vi.fn(),
}))

import { useAuth as _useAuth } from '@/features/auth/context/AuthContext'

const mockUseAuth = vi.mocked(_useAuth)

function makeAuth(overrides: Partial<ReturnType<typeof useAuth>> = {}): ReturnType<typeof useAuth> {
  return {
    user: { id: '1', email: 'a@b.com', is_email_verified: true, is_admin: false },
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    ...overrides,
  }
}

function renderShell(initialPath = '/analytics') {
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/analytics" element={<div>Analytics content</div>} />
          <Route path="/risk" element={<div>Risk content</div>} />
          <Route path="/trades" element={<div>Trades content</div>} />
          <Route path="/import" element={<div>Import content</div>} />
          <Route path="/settings" element={<div>Settings content</div>} />
        </Route>
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockUseAuth.mockReturnValue(makeAuth())
})

// ---------------------------------------------------------------------------
// F-14-30: sidebar renders the app logo and nav landmark
// ---------------------------------------------------------------------------

describe('AppShell — F-14-30: logo and nav landmark', () => {
  it('renders the TradeForge logo and main navigation landmark', () => {
    renderShell()
    expect(screen.getByText('TradeForge')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: /main navigation/i })).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// F-14-31: all 6 nav links are present
// ---------------------------------------------------------------------------

describe('AppShell — F-14-31: six nav links', () => {
  it('renders NavLinks for Dashboard, Analytics, Risk, Trades, Import, Settings', () => {
    renderShell()
    const nav = screen.getByRole('navigation', { name: /main navigation/i })
    expect(nav).toBeInTheDocument()

    const links = ['Dashboard', 'Analytics', 'Risk', 'Trades', 'Import', 'Settings']
    links.forEach((label) => {
      expect(screen.getByRole('link', { name: label })).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// F-14-32: outlet content is rendered inside <main>
// ---------------------------------------------------------------------------

describe('AppShell — F-14-32: outlet renders inside <main>', () => {
  it('renders outlet content inside the main landmark', () => {
    renderShell('/analytics')
    const main = screen.getByRole('main')
    expect(main).toBeInTheDocument()
    expect(main).toHaveTextContent('Analytics content')
  })
})

// ---------------------------------------------------------------------------
// F-14-33: logout button calls logout()
// ---------------------------------------------------------------------------

describe('AppShell — F-14-33: logout button calls logout', () => {
  it('calls logout when the logout button is clicked', async () => {
    const user = userEvent.setup()
    const logoutFn = vi.fn().mockResolvedValue(undefined)
    mockUseAuth.mockReturnValue(makeAuth({ logout: logoutFn }))

    renderShell()

    await user.click(screen.getByRole('button', { name: /log out/i }))

    expect(logoutFn).toHaveBeenCalledTimes(1)
  })
})

// ---------------------------------------------------------------------------
// F-14-31b: active nav link carries aria-current="page"
// ---------------------------------------------------------------------------

describe('AppShell — F-14-31b: active link has aria-current="page"', () => {
  it('applies aria-current="page" to the active link and not to inactive links', () => {
    renderShell('/analytics')
    expect(screen.getByRole('link', { name: 'Analytics' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Dashboard' })).not.toHaveAttribute('aria-current', 'page')
  })
})

// ---------------------------------------------------------------------------
// Task B: skip-link present with href="#main" (WCAG 2.1 SC 2.4.1)
// ---------------------------------------------------------------------------

describe('AppShell — skip-link for keyboard navigation', () => {
  it('renders a skip-link with href="#main" before the sidebar', () => {
    renderShell()
    const skipLink = screen.getByRole('link', { name: /skip to content/i })
    expect(skipLink).toBeInTheDocument()
    expect(skipLink).toHaveAttribute('href', '#main')
  })

  it('main landmark has id="main" so the skip-link target exists', () => {
    renderShell()
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main')
  })
})
