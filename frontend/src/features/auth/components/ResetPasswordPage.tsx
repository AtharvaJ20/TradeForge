import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ApiError } from '@/lib/api-client'
import { useConfirmPasswordReset } from '../hooks/usePasswordReset'

// Reuse the same inline strength scorer as RegisterPage
function scorePassword(pw: string): number {
  let score = 0
  if (pw.length >= 8) score++
  if (pw.length >= 12) score++
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++
  if (/[0-9]/.test(pw) || /[^a-zA-Z0-9]/.test(pw)) score++
  return score
}

const SEGMENT_COLORS = [
  'bg-surface-subtle',
  'bg-danger',
  'bg-warning',
  'bg-warning',
  'bg-success',
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

function mapError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.detail === 'INVALID_OR_EXPIRED_TOKEN')
      return 'This reset link is invalid or has expired. Request a new one.'
    if (err.detail === 'RATE_LIMITED') return 'Too many attempts. Please wait.'
    if (err.status === 422) return err.detail
  }
  return 'Something went wrong. Please try again.'
}

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token')
  const confirm = useConfirmPasswordReset()
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [confirmError, setConfirmError] = useState<string | null>(null)

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-base px-4">
        <div className="w-full max-w-sm rounded-xl border border-border bg-surface-base p-8 shadow-lg text-center">
          <h1 className="mb-3 text-xl font-bold text-text-primary">Invalid reset link</h1>
          <p className="mb-4 text-sm text-danger-emphasis">This reset link is missing a token.</p>
          <Link to="/forgot-password" className="text-sm text-primary hover:underline">
            Request a new reset link
          </Link>
        </div>
      </div>
    )
  }

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (password !== confirmPassword) {
      setConfirmError('Passwords do not match.')
      return
    }
    setConfirmError(null)
    confirm.mutate(
      { token: token!, newPassword: password },
      { onSuccess: () => navigate('/login?reset=1', { replace: true }) },
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-base px-4">
      <div className="w-full max-w-sm rounded-xl border border-border bg-surface-base p-8 shadow-lg">
        <h1 className="mb-6 text-2xl font-bold text-text-primary">Set new password</h1>

        {confirm.error && (
          <div role="alert" className="mb-4 rounded-lg bg-surface-danger px-4 py-3 text-sm text-danger-emphasis">
            {mapError(confirm.error)}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="mb-4">
            <label htmlFor="reset-password" className="mb-1.5 block text-sm font-medium text-text-primary">
              New password
            </label>
            <input
              id="reset-password"
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
            <label htmlFor="reset-confirm" className="mb-1.5 block text-sm font-medium text-text-primary">
              Confirm new password
            </label>
            <input
              id="reset-confirm"
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
            disabled={confirm.isPending}
            className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:bg-primary-emphasis focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {confirm.isPending ? 'Saving…' : 'Set new password'}
          </button>
        </form>
      </div>
    </div>
  )
}
