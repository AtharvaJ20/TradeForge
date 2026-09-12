import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { authApi } from '../api'
import type { User } from '../types'

interface AuthContextValue {
  user: User | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const navigate = useNavigate()
  const location = useLocation()
  // Tracks whether initial hydration is complete. The auth:session-expired
  // event must be ignored until then — the in-flight me() call started before
  // login will return 401 and would otherwise kick the user back to /login
  // even after a successful sign-in.
  const hydratedRef = useRef(false)
  // Holds the AbortController for the initial me() fetch so login() can cancel
  // it before it returns a 401, preventing handleExpired from firing post-login.
  const meControllerRef = useRef<AbortController | null>(null)

  // Hydrate auth state on mount
  useEffect(() => {
    const controller = new AbortController()
    meControllerRef.current = controller

    authApi
      .me(controller.signal)
      .then(setUser)
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === 'AbortError') return
        setUser(null)
      })
      .finally(() => {
        if (controller.signal.aborted) return
        hydratedRef.current = true
        setIsLoading(false)
      })

    return () => controller.abort()
  }, [])

  // Session-expired event: any 401 from api-client dispatches this
  useEffect(() => {
    function handleExpired() {
      if (!hydratedRef.current) return
      setUser(null)
      navigate('/login?expired=1', { replace: true })
    }
    window.addEventListener('auth:session-expired', handleExpired)
    return () => window.removeEventListener('auth:session-expired', handleExpired)
  }, [navigate])

  async function login(email: string, password: string): Promise<void> {
    // Cancel the initial me() fetch before credentials are submitted. If me()
    // is still in-flight (cold Railway start), aborting it prevents the 401
    // it would eventually return from passing through handleExpired and kicking
    // the user back to /login immediately after a successful sign-in.
    meControllerRef.current?.abort()
    const params = new URLSearchParams(location.search)
    const next = params.get('next')
    const userData = await authApi.login(email, password)
    setUser(userData)
    // Mark hydration complete so RequireAuth can render the protected route
    // immediately and any future 401s are handled by handleExpired.
    hydratedRef.current = true
    setIsLoading(false)
    navigate(next ?? '/analytics', { replace: true })
  }

  async function logout(): Promise<void> {
    await authApi.logout()
    setUser(null)
    navigate('/login')
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (ctx === null) {
    throw new Error('useAuth must be used inside <AuthProvider>')
  }
  return ctx
}
