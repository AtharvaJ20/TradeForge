/**
 * AuthContext integration tests.
 *
 * Uses a real AuthProvider (not mocked) rendered inside a MemoryRouter so we
 * can exercise the actual hydration/login flow against MSW-intercepted network
 * requests.
 */
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from '@/__tests__/msw/server'
import { AuthProvider, useAuth } from '../AuthContext'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const BASE = 'http://localhost:8000'

const MOCK_USER = { id: '1', email: 'a@b.com', is_email_verified: true, is_admin: false }

function AuthConsumer() {
  const { user, isLoading, login } = useAuth()
  return (
    <div>
      <p data-testid="user">{user?.email ?? 'none'}</p>
      <p data-testid="loading">{isLoading ? 'true' : 'false'}</p>
      <button type="button" onClick={() => void login('a@b.com', 'pass123')}>
        Login
      </button>
    </div>
  )
}

function renderProvider() {
  render(
    <MemoryRouter initialEntries={['/login']}>
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>
    </MemoryRouter>,
  )
}

afterEach(() => {
  server.resetHandlers()
})

// ---------------------------------------------------------------------------
// F-14-30: Cold-start race — in-flight me() 401 after login must be ignored
// ---------------------------------------------------------------------------

describe('AuthContext — F-14-30: cold-start me() race', () => {
  it(
    'user stays authenticated when in-flight me() returns 401 after login() completes',
    async () => {
      const user = userEvent.setup()

      let releaseMeWith401!: () => void
      const meResolved = new Promise<void>((resolve) => {
        releaseMeWith401 = resolve
      })

      server.use(
        // me() hangs until we explicitly release it with 401 (simulates cold start)
        http.get(`${BASE}/v1/auth/me`, async () => {
          await meResolved
          return HttpResponse.json(
            { detail: 'NOT_AUTHENTICATED' },
            { status: 401 },
          )
        }),
        http.post(`${BASE}/v1/auth/login`, () =>
          HttpResponse.json(MOCK_USER),
        ),
      )

      renderProvider()

      // me() is in-flight (cold start); spinner is shown
      expect(screen.getByTestId('loading')).toHaveTextContent('true')

      // User submits the login form while me() is still pending
      await user.click(screen.getByRole('button', { name: /login/i }))

      // Login should succeed and user should be authenticated
      await waitFor(() => {
        expect(screen.getByTestId('user')).toHaveTextContent('a@b.com')
      })

      // Now simulate the cold-start me() finally returning 401
      await act(async () => {
        releaseMeWith401()
        // Allow the AbortError / promise chain to settle
        await new Promise((r) => setTimeout(r, 50))
      })

      // User must still be authenticated — the 401 from the aborted me() must
      // NOT have triggered setUser(null) or navigated to /login?expired=1
      expect(screen.getByTestId('user')).toHaveTextContent('a@b.com')
    },
    10_000,
  )
})
