import { Outlet } from 'react-router-dom'

interface AuthShellProps {
  title?: string
}

export function AuthShell({ title }: AuthShellProps) {
  return (
    <div data-testid="auth-shell" className="flex min-h-screen bg-surface-base">
      {/* Brand panel — 5fr */}
      <div
        data-testid="auth-shell-brand"
        className="hidden flex-col items-center justify-center bg-brand px-12 py-16 lg:flex"
        style={{ flex: '5' }}
      >
        <div className="max-w-xs text-center">
          <div className="mb-6 text-4xl font-extrabold tracking-tight text-white">TradeForge</div>
          <p className="text-base font-medium leading-relaxed text-white/80">
            Your edge is in the data. Track every trade. Understand every outcome.
          </p>
          {title && (
            <p className="mt-8 text-sm font-semibold uppercase tracking-widest text-white/60">
              {title}
            </p>
          )}
        </div>
      </div>

      {/* Form panel — 7fr */}
      <div
        data-testid="auth-shell-form"
        className="flex flex-1 flex-col items-center justify-center px-4 py-12"
        style={{ flex: '7' }}
      >
        <Outlet />
      </div>
    </div>
  )
}
