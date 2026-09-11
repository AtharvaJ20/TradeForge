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

  // Hydrate auth state on mount
  useEffect(() => {
    authApi
      .me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => {
        hydratedRef.current = true
        setIsLoading(false)
      })
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
    const params = new URLSearchParams(location.search)
    const next = params.get('next')
    const userData = await authApi.login(email, password)
    setUser(userData)
    // Mark hydration complete so that (a) RequireAuth can render immediately
    // and (b) any 401 from the still-in-flight initial me() call does not
    // redirect back to /login. The in-flight me() will settle harmlessly.
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
