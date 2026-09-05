import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '@/features/auth/context/AuthContext'

// Renders <Outlet /> when authenticated; redirects to /login?next=<pathname> when not.
// Renders null while isLoading (initial auth check) to avoid flash of login screen.
export function RequireAuth() {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) return null

  if (!user) {
    return <Navigate to={`/login?next=${location.pathname}`} replace />
  }

  return <Outlet />
}
