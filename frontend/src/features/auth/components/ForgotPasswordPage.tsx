import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '@/lib/api-client'
import { useRequestPasswordReset } from '../hooks/usePasswordReset'

function mapError(err: unknown): string {
  if (err instanceof ApiError && err.detail === 'RATE_LIMITED') {
    return 'Too many requests. Please wait before trying again.'
  }
  return 'Something went wrong. Please try again.'
}

export function ForgotPasswordPage() {
  const reset = useRequestPasswordReset()
  const [email, setEmail] = useState('')

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    reset.mutate(email)
  }

  if (reset.isSuccess) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-base px-4">
        <div className="w-full max-w-sm rounded-xl border border-border bg-surface-base p-8 shadow-lg text-center">
          <h1 className="mb-4 text-2xl font-bold text-text-primary">Check your inbox</h1>
          <p className="text-sm text-text-secondary">
            If this email is registered, a password reset link has been sent. Check your inbox.
          </p>
          <Link to="/login" className="mt-4 inline-block text-sm text-primary hover:underline">
            Back to sign in
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-base px-4">
      <div className="w-full max-w-sm rounded-xl border border-border bg-surface-base p-8 shadow-lg">
        <h1 className="mb-2 text-2xl font-bold text-text-primary">Reset your password</h1>
        <p className="mb-6 text-sm text-text-secondary">
          Enter your email and we'll send a reset link.
        </p>

        {reset.error && (
          <div role="alert" className="mb-4 rounded-lg bg-surface-danger px-4 py-3 text-sm text-danger-emphasis">
            {mapError(reset.error)}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="mb-6">
            <label htmlFor="forgot-email" className="mb-1.5 block text-sm font-medium text-text-primary">
              Email
            </label>
            <input
              id="forgot-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-border bg-surface-base px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-focus focus:outline-none focus:ring-2 focus:ring-border-focus/20"
              placeholder="you@example.com"
            />
          </div>

          <button
            type="submit"
            disabled={reset.isPending}
            className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:bg-primary-emphasis focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {reset.isPending ? 'Sending…' : 'Send reset link'}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-text-secondary">
          <Link to="/login" className="text-primary hover:underline">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
