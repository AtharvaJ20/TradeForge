import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { authApi } from '../api'
import { ApiError } from '@/lib/api-client'

type VerifyState = 'loading' | 'success' | 'error' | 'no-token'

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token')
  const [state, setState] = useState<VerifyState>(token ? 'loading' : 'no-token')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  useEffect(() => {
    if (!token) return

    authApi
      .verifyEmail(token)
      .then(() => {
        setState('success')
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.detail === 'INVALID_OR_EXPIRED_TOKEN') {
          setErrorMsg('This verification link is invalid or has expired. Request a new one from the login page.')
        } else {
          setErrorMsg('Something went wrong. Please try again.')
        }
        setState('error')
      })
  }, [token])

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-base px-4">
      <div className="w-full max-w-sm rounded-xl border border-border bg-surface-base p-8 shadow-lg text-center">
        {state === 'loading' && (
          <p className="text-sm text-text-secondary">Verifying your email…</p>
        )}
        {state === 'success' && (
          <>
            <h1 className="mb-3 text-xl font-bold text-text-primary">Email verified!</h1>
            <p className="mb-4 text-sm text-text-secondary">Your account is ready. Sign in to get started.</p>
            <button
              type="button"
              onClick={() => navigate('/login?verified=1', { replace: true })}
              className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary/50"
            >
              Continue to sign in
            </button>
          </>
        )}
        {state === 'error' && (
          <>
            <h1 className="mb-3 text-xl font-bold text-text-primary">Verification failed</h1>
            <p className="text-sm text-danger-emphasis">{errorMsg}</p>
            <Link to="/login" className="mt-4 inline-block text-sm text-primary hover:underline">
              Back to sign in
            </Link>
          </>
        )}
        {state === 'no-token' && (
          <>
            <h1 className="mb-3 text-xl font-bold text-text-primary">Invalid verification link</h1>
            <p className="text-sm text-danger-emphasis">
              This link is missing a verification token.
            </p>
            <Link to="/login" className="mt-4 inline-block text-sm text-primary hover:underline">
              Back to sign in
            </Link>
          </>
        )}
      </div>
    </div>
  )
}
