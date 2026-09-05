import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '@/lib/api-client'
import { useRegister } from '../hooks/useRegister'

// Inline strength scorer — no external library (R-14-4)
// Returns 0–4. Segments: red(1) → amber(2) → amber(3) → green(4)
function scorePassword(pw: string): number {
  let score = 0
  if (pw.length >= 8) score++
  if (pw.length >= 12) score++
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++
  if (/[0-9]/.test(pw) || /[^a-zA-Z0-9]/.test(pw)) score++
  return score
}

const SEGMENT_COLORS = [
  'bg-surface-subtle', // 0 - empty
  'bg-danger',         // 1 - weak
  'bg-warning',        // 2 - fair
  'bg-warning',        // 3 - good
  'bg-success',        // 4 - strong
]

function PasswordStrengthBar({ password }: { password: string }) {
  const score = password.length === 0 ? 0 : scorePassword(password)
  return (
    <div aria-label="Password strength indicator" className="mt-1.5 flex gap-1">
      {[1, 2, 3, 4].map((seg) => (
        <div
          key={seg}
          className={`h-1.5 flex-1 rounded-full transition-colors ${
            score >= seg ? (SEGMENT_COLORS[score] ?? 'bg-surface-subtle') : 'bg-surface-subtle'
          }`}
        />
      ))}
    </div>
  )
}

function mapRegisterError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 429) return 'Too many registration attempts. Please wait.'
    if (err.status === 422) return err.detail
  }
  return 'Something went wrong. Please try again.'
}

export function RegisterPage() {
  const navigate = useNavigate()
  const register = useRegister()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [confirmError, setConfirmError] = useState<string | null>(null)

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (password !== confirmPassword) {
      setConfirmError('Passwords do not match.')
      return
    }
    setConfirmError(null)
    register.mutate(
      { email, password },
      { onSuccess: () => navigate('/register-success') },
    )
  }

  const apiError = register.error ? mapRegisterError(register.error) : null

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-base px-4">
      <div className="w-full max-w-sm rounded-xl border border-border bg-surface-base p-8 shadow-lg">
        <h1 className="mb-6 text-2xl font-bold text-text-primary">Create account</h1>

        {apiError && (
          <div role="alert" className="mb-4 rounded-lg bg-surface-danger px-4 py-3 text-sm text-danger-emphasis">
            {apiError}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="mb-4">
            <label htmlFor="reg-email" className="mb-1.5 block text-sm font-medium text-text-primary">
              Email
            </label>
            <input
              id="reg-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-border bg-surface-base px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-focus focus:outline-none focus:ring-2 focus:ring-border-focus/20"
              placeholder="you@example.com"
            />
          </div>

          <div className="mb-4">
            <label htmlFor="reg-password" className="mb-1.5 block text-sm font-medium text-text-primary">
              Password
            </label>
            <input
              id="reg-password"
              type="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-border bg-surface-base px-3 py-2 text-sm text-text-primary focus:border-border-focus focus:outline-none focus:ring-2 focus:ring-border-focus/20"
            />
            <PasswordStrengthBar password={password} />
          </div>

          <div className="mb-6">
            <label htmlFor="reg-confirm" className="mb-1.5 block text-sm font-medium text-text-primary">
              Confirm password
            </label>
            <input
              id="reg-confirm"
              type="password"
              autoComplete="new-password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full rounded-lg border border-border bg-surface-base px-3 py-2 text-sm text-text-primary focus:border-border-focus focus:outline-none focus:ring-2 focus:ring-border-focus/20"
            />
            {confirmError && (
              <p role="alert" className="mt-1.5 text-xs text-danger-emphasis">
                {confirmError}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={register.isPending}
            className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:bg-primary-emphasis focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {register.isPending ? 'Creating account…' : 'Sign up'}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-text-secondary">
          Already have an account?{' '}
          <Link to="/login" className="text-primary hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
