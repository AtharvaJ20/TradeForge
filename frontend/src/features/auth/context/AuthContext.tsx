import { createContext, useContext, useEffect, useState } from 'react'
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

  // Hydrate auth state on mount
  useEffect(() => {
    authApi
      .me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setIsLoading(false))
  }, [])

  // Session-expired event: any 401 from api-client dispatches this
  useEffect(() => {
    function handleExpired() {
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

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (ctx === null) {
    throw new Error('useAuth must be used inside <AuthProvider>')
  }
  return ctx
}
