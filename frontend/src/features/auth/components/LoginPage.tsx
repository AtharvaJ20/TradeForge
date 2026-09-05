import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ApiError } from '@/lib/api-client'
import { useAuth } from '../context/AuthContext'

function mapLoginError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.detail === 'INVALID_CREDENTIALS') return 'Incorrect email or password.'
    if (err.detail === 'ACCOUNT_LOCKED')
      return 'Account locked due to too many failed attempts. Contact support.'
    if (err.detail === 'EMAIL_NOT_VERIFIED')
      return 'Please verify your email before logging in.'
    if (err.detail === 'RATE_LIMITED') return 'Too many attempts. Please wait before trying again.'
  }
  return 'Something went wrong. Please try again.'
}

export function LoginPage() {
  const { login } = useAuth()
  const [searchParams] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const expired = searchParams.get('expired') === '1'
  const verified = searchParams.get('verified') === '1'
  const reset = searchParams.get('reset') === '1'

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setIsSubmitting(true)
    setError(null)
    try {
      await login(email, password)
    } catch (err) {
      setError(mapLoginError(err))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-base px-4">
      <div className="w-full max-w-sm rounded-xl border border-border bg-surface-base p-8 shadow-lg">
        <h1 className="mb-6 text-2xl font-bold text-text-primary">Sign in</h1>

        {expired && (
          <div
            role="alert"
            className="mb-4 rounded-lg bg-surface-warning px-4 py-3 text-sm text-warning-emphasis"
          >
            Your session expired. Please log in again.
          </div>
        )}
        {verified && (
          <div
            role="alert"
            className="mb-4 rounded-lg bg-surface-success px-4 py-3 text-sm text-success-emphasis"
          >
            Email verified. You can now log in.
          </div>
        )}
        {reset && (
          <div
            role="alert"
            className="mb-4 rounded-lg bg-surface-success px-4 py-3 text-sm text-success-emphasis"
          >
            Password reset successful. Please log in.
          </div>
        )}

        {error && (
          <div role="alert" className="mb-4 rounded-lg bg-surface-danger px-4 py-3 text-sm text-danger-emphasis">
            {error}
          </div>
        )}

        <form onSubmit={(e) => void handleSubmit(e)} noValidate>
          <div className="mb-4">
            <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-text-primary">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-border bg-surface-base px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-focus focus:outline-none focus:ring-2 focus:ring-border-focus/20"
              placeholder="you@example.com"
            />
          </div>

          <div className="mb-6">
            <label
              htmlFor="password"
              className="mb-1.5 block text-sm font-medium text-text-primary"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-border bg-surface-base px-3 py-2 text-sm text-text-primary focus:border-border-focus focus:outline-none focus:ring-2 focus:ring-border-focus/20"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:bg-primary-emphasis focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-text-secondary">
          <Link to="/forgot-password" className="text-primary hover:underline">
            Forgot password?
          </Link>
        </p>
        <p className="mt-2 text-center text-sm text-text-secondary">
          No account?{' '}
          <Link to="/register" className="text-primary hover:underline">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  )
}
