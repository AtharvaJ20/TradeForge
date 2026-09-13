import { Link } from 'react-router-dom'
import { useTheme } from '@/shared/hooks/useTheme'

function IconSun() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M8 10.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z" />
      <path d="M8 .75a.75.75 0 0 1 .75.75v1a.75.75 0 0 1-1.5 0v-1A.75.75 0 0 1 8 .75ZM1.17 4.285a.75.75 0 0 1 1.03-.265l.866.5a.75.75 0 1 1-.75 1.3l-.866-.5a.75.75 0 0 1-.28-1.035ZM4.285 14.83a.75.75 0 0 1-.265-1.03l.5-.866a.75.75 0 0 1 1.3.75l-.5.866a.75.75 0 0 1-1.035.28ZM.75 8a.75.75 0 0 1 .75-.75h1a.75.75 0 0 1 0 1.5h-1A.75.75 0 0 1 .75 8ZM14.83 11.715a.75.75 0 0 1-1.03.265l-.866-.5a.75.75 0 0 1 .75-1.3l.866.5a.75.75 0 0 1 .28 1.035ZM11.715 1.17a.75.75 0 0 1 .265 1.03l-.5.866a.75.75 0 1 1-1.3-.75l.5-.866a.75.75 0 0 1 1.035-.28ZM8 13.5a.75.75 0 0 1 .75.75v1a.75.75 0 0 1-1.5 0v-1A.75.75 0 0 1 8 13.5ZM13.48 4.517a.75.75 0 1 0-.75-1.3l-.866.5a.75.75 0 0 0 .75 1.3l.866-.5Z" />
    </svg>
  )
}

function IconMoon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M14.438 10.148c.19-.425-.321-.787-.748-.601A5.5 5.5 0 0 1 6.453 2.31c.186-.427-.176-.938-.6-.748a6.501 6.501 0 1 0 8.585 8.586Z" />
    </svg>
  )
}

const FEATURES = [
  {
    title: 'Trade Journal',
    description:
      'Log every trade with notes, emotions, and discipline scores. Build the habit of reflection.',
  },
  {
    title: 'Performance Analytics',
    description:
      'Win rate, expectancy, profit factor, drawdown — every metric that matters, updated in real time.',
  },
  {
    title: 'Risk Management',
    description:
      'Track position sizing, portfolio heat, and drawdown tiers to protect your capital.',
  },
  {
    title: 'Broker Import',
    description:
      'Import trades from Zerodha, Upstox, and Angel One. No manual entry required.',
  },
]

export function LandingPage() {
  const { theme, toggle } = useTheme()
  const isDark = theme === 'dark'

  return (
    <div className="flex min-h-screen flex-col bg-surface-base">
      {/* Nav */}
      <header>
        <nav
          data-testid="landing-nav"
          className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4"
          aria-label="Landing page navigation"
        >
          <span className="text-lg font-extrabold tracking-tight text-brand">TradeForge</span>
          <div className="flex items-center gap-3">
            <button
              type="button"
              data-testid="theme-toggle"
              onClick={toggle}
              aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              className="flex items-center justify-center rounded-lg p-2 text-text-secondary hover:bg-surface-subtle hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-brand/50"
            >
              <span className={isDark ? 'text-toggle-moon' : 'text-toggle-sun'}>
                {isDark ? <IconMoon /> : <IconSun />}
              </span>
            </button>
            <Link
              to="/login"
              className="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-brand/50"
            >
              Sign in
            </Link>
            <Link
              to="/register"
              className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-emphasis focus:outline-none focus:ring-2 focus:ring-brand/50"
            >
              Get started
            </Link>
          </div>
        </nav>
      </header>

      {/* Hero */}
      <section
        data-testid="landing-hero"
        className="mx-auto flex max-w-4xl flex-col items-center px-6 py-24 text-center"
        aria-label="Hero"
      >
        <h1 className="mb-6 text-5xl font-extrabold leading-tight tracking-tight text-text-primary">
          Your edge is in <span className="text-brand">the data</span>
        </h1>
        <p className="mb-10 max-w-xl text-lg text-text-secondary">
          TradeForge helps you track every trade, understand your patterns, and improve your
          process — so you stop guessing and start compounding.
        </p>
        <div className="flex gap-4">
          <Link
            to="/register"
            className="rounded-xl bg-brand px-6 py-3 text-base font-semibold text-white hover:bg-brand-emphasis focus:outline-none focus:ring-2 focus:ring-brand/50"
          >
            Start for free
          </Link>
          <Link
            to="/login"
            className="rounded-xl border border-border px-6 py-3 text-base font-medium text-text-secondary hover:border-brand hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-brand/50"
          >
            Sign in
          </Link>
        </div>
      </section>

      {/* Features */}
      <section
        data-testid="landing-features"
        className="bg-surface-subtle py-20"
        aria-label="Features"
      >
        <div className="mx-auto max-w-6xl px-6">
          <h2 className="mb-12 text-center text-3xl font-bold text-text-primary">
            Everything a serious trader needs
          </h2>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="rounded-xl border border-border bg-surface-base p-6"
              >
                <h3 className="mb-2 text-base font-semibold text-text-primary">{f.title}</h3>
                <p className="text-sm text-text-secondary">{f.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA band */}
      <section
        data-testid="landing-cta-band"
        className="bg-brand py-16 text-center"
        aria-label="Call to action"
      >
        <h2 className="mb-4 text-3xl font-bold text-white">Ready to sharpen your edge?</h2>
        <p className="mb-8 text-base text-white/80">
          Join traders who use data — not instinct — to improve.
        </p>
        <Link
          to="/register"
          className="inline-block rounded-xl bg-white px-8 py-3 text-base font-semibold text-brand hover:bg-white/90 focus:outline-none focus:ring-2 focus:ring-white/50"
        >
          Create your free account
        </Link>
      </section>

      <footer className="border-t border-border py-8 text-center text-sm text-text-muted">
        © {new Date().getFullYear()} TradeForge. All rights reserved.
      </footer>
    </div>
  )
}
