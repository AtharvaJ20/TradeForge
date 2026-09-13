import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { LandingPage } from '../LandingPage'

vi.mock('@/shared/hooks/useTheme', () => ({
  useTheme: () => ({ theme: 'light' as const, toggle: vi.fn() }),
}))

function renderAtRoot() {
  render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('LandingPage — route tests', () => {
  it('renders LandingPage at the root path /', () => {
    renderAtRoot()
    expect(screen.getByTestId('landing-hero')).toBeInTheDocument()
    expect(screen.getByTestId('landing-nav')).toBeInTheDocument()
  })

  it('root path / renders LandingPage, not a redirect to /dashboard', () => {
    renderAtRoot()
    // Landing page content is visible — not a dashboard redirect
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.queryByText('Dashboard')).not.toBeInTheDocument()
  })
})
