import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AuthShell } from '../AuthShell'

function renderAuthShell(title?: string) {
  render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route element={<AuthShell title={title} />}>
          <Route path="/login" element={<div>Login form content</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('AuthShell — structural layout', () => {
  it('renders brand panel and form panel with correct data-testid attributes', () => {
    renderAuthShell()
    expect(screen.getByTestId('auth-shell')).toBeInTheDocument()
    expect(screen.getByTestId('auth-shell-brand')).toBeInTheDocument()
    expect(screen.getByTestId('auth-shell-form')).toBeInTheDocument()
  })

  it('renders outlet content inside the form panel', () => {
    renderAuthShell()
    const formPanel = screen.getByTestId('auth-shell-form')
    expect(formPanel).toHaveTextContent('Login form content')
  })

  it('renders the TradeForge brand mark in the brand panel', () => {
    renderAuthShell()
    const brandPanel = screen.getByTestId('auth-shell-brand')
    expect(brandPanel).toHaveTextContent('TradeForge')
  })

  it('renders optional title prop in the brand panel when provided', () => {
    renderAuthShell('Sign in')
    const brandPanel = screen.getByTestId('auth-shell-brand')
    expect(brandPanel).toHaveTextContent('Sign in')
  })
})
