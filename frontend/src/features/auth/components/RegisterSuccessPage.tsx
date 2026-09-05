import { Link } from 'react-router-dom'

export function RegisterSuccessPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-base px-4">
      <div className="w-full max-w-sm rounded-xl border border-border bg-surface-base p-8 shadow-lg text-center">
        <h1 className="mb-4 text-2xl font-bold text-text-primary">Check your email</h1>
        <p className="mb-6 text-sm text-text-secondary">
          Registration successful — a verification link has been sent to your inbox. Click it to
          activate your account.
        </p>
        <Link to="/login" className="text-sm text-primary hover:underline">
          Back to sign in
        </Link>
      </div>
    </div>
  )
}
