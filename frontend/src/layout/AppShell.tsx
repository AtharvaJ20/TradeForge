import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '@/features/auth/context/AuthContext'
import { useTheme } from '@/shared/hooks/useTheme'

// Heroicons mini (16×16 inline SVG, MIT licence)
function IconDashboard() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M2 3a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3Zm7 0a1 1 0 0 1 1-1h1a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1h-1a1 1 0 0 1-1-1V3Zm0 5a1 1 0 0 1 1-1h1a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1h-1a1 1 0 0 1-1-1V8ZM2 10a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-3Z" />
    </svg>
  )
}

function IconAnalytics() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M13 2a1 1 0 0 0-1 1v10a1 1 0 0 0 2 0V3a1 1 0 0 0-1-1ZM9 5a1 1 0 0 0-1 1v7a1 1 0 0 0 2 0V6a1 1 0 0 0-1-1ZM5 8a1 1 0 0 0-1 1v4a1 1 0 0 0 2 0V9a1 1 0 0 0-1-1ZM3 12a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z" />
    </svg>
  )
}

function IconRisk() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path fillRule="evenodd" d="M8 1a.75.75 0 0 1 .67.415l5.75 11.5A.75.75 0 0 1 13.75 14H2.25a.75.75 0 0 1-.67-1.085l5.75-11.5A.75.75 0 0 1 8 1Zm0 4a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 8 5Zm0 7.5a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Z" clipRule="evenodd" />
    </svg>
  )
}

function IconTrades() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path fillRule="evenodd" d="M2 3.5A1.5 1.5 0 0 1 3.5 2h9A1.5 1.5 0 0 1 14 3.5v9a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 2 12.5v-9Zm4.5 1a.75.75 0 0 0 0 1.5h3a.75.75 0 0 0 0-1.5h-3Zm0 3a.75.75 0 0 0 0 1.5h3a.75.75 0 0 0 0-1.5h-3Zm0 3a.75.75 0 0 0 0 1.5h1a.75.75 0 0 0 0-1.5h-1Z" clipRule="evenodd" />
    </svg>
  )
}

function IconImport() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M8.75 2.75a.75.75 0 0 0-1.5 0v5.69L5.03 6.22a.75.75 0 0 0-1.06 1.06l3.5 3.5a.75.75 0 0 0 1.06 0l3.5-3.5a.75.75 0 0 0-1.06-1.06L8.75 8.44V2.75Z" />
      <path d="M3.5 9.75a.75.75 0 0 0-1.5 0v1.5A2.75 2.75 0 0 0 4.75 14h6.5A2.75 2.75 0 0 0 14 11.25v-1.5a.75.75 0 0 0-1.5 0v1.5c0 .69-.56 1.25-1.25 1.25h-6.5c-.69 0-1.25-.56-1.25-1.25v-1.5Z" />
    </svg>
  )
}

function IconSettings() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path fillRule="evenodd" d="M6.955 1.45A.75.75 0 0 1 7.68.75h.642a.75.75 0 0 1 .727.7l.13 1.494a5.18 5.18 0 0 1 1.024.586l1.35-.674a.75.75 0 0 1 .92.208l.321.456.323.456a.75.75 0 0 1-.092.958l-1.093 1.037a5.37 5.37 0 0 1 0 1.178l1.093 1.037a.75.75 0 0 1 .092.958l-.323.456-.321.456a.75.75 0 0 1-.92.208l-1.35-.674a5.18 5.18 0 0 1-1.024.586l-.13 1.494a.75.75 0 0 1-.727.7H7.68a.75.75 0 0 1-.727-.7l-.13-1.494a5.18 5.18 0 0 1-1.024-.586l-1.35.674a.75.75 0 0 1-.92-.208l-.321-.456L2.887 11a.75.75 0 0 1 .092-.958l1.093-1.037a5.37 5.37 0 0 1 0-1.178L2.98 6.79a.75.75 0 0 1-.092-.958l.321-.456.321-.456a.75.75 0 0 1 .92-.208l1.35.674a5.18 5.18 0 0 1 1.024-.586l.13-1.494ZM8 10a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z" clipRule="evenodd" />
    </svg>
  )
}

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

const NAV_ITEMS = [
  { label: 'Dashboard', path: '/dashboard', icon: IconDashboard, end: false },
  { label: 'Analytics', path: '/analytics', icon: IconAnalytics, end: false },
  { label: 'Risk', path: '/risk', icon: IconRisk, end: false },
  { label: 'Trades', path: '/trades', icon: IconTrades, end: false },
  { label: 'Import', path: '/import', icon: IconImport, end: false },
  { label: 'Settings', path: '/settings', icon: IconSettings, end: false },
]

function navLinkClass({ isActive }: { isActive: boolean }) {
  const base =
    'flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-brand/50'
  return isActive
    ? `${base} bg-brand/10 text-brand`
    : `${base} text-text-secondary hover:bg-surface-subtle hover:text-text-primary`
}

export function AppShell() {
  const { logout } = useAuth()
  const { theme, toggle } = useTheme()
  const isDark = theme === 'dark'

  return (
    <div className="flex min-h-screen bg-surface-base">
      {/* Skip-link — first child, must remain here (F-14-30 group) */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-text-primary focus:shadow focus:outline-none focus:ring-2 focus:ring-brand"
      >
        Skip to content
      </a>

      <aside className="flex w-56 shrink-0 flex-col border-r border-border bg-surface-base">
        {/* Brand mark */}
        <div className="border-b border-border px-4 py-5">
          <span className="text-base font-extrabold tracking-tight text-brand">TradeForge</span>
        </div>

        {/* Nav */}
        <nav aria-label="Main navigation" className="flex-1 overflow-y-auto px-2 py-4">
          <ul className="flex flex-col gap-0.5">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon
              if (item.path === '/trades') {
                return (
                  <li key={item.path}>
                    <div className="flex items-center gap-1">
                      <NavLink to={item.path} end={item.end} className={navLinkClass}>
                        <Icon />
                        {item.label}
                      </NavLink>
                      <Link
                        to="/trades/new"
                        title="Add Trade"
                        aria-label="Add Trade"
                        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-text-secondary hover:bg-surface-subtle hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-brand/50"
                      >
                        +
                      </Link>
                    </div>
                  </li>
                )
              }
              return (
                <li key={item.path}>
                  <NavLink to={item.path} end={item.end} className={navLinkClass}>
                    <Icon />
                    {item.label}
                  </NavLink>
                </li>
              )
            })}
          </ul>
        </nav>

        {/* Footer — theme toggle + logout */}
        <div className="border-t border-border px-2 py-3">
          <button
            type="button"
            data-testid="theme-toggle"
            onClick={toggle}
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            className="mb-1 flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium text-text-secondary hover:bg-surface-subtle hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-brand/50"
          >
            <span className={isDark ? 'text-toggle-moon' : 'text-toggle-sun'}>
              {isDark ? <IconMoon /> : <IconSun />}
            </span>
            {isDark ? 'Dark mode' : 'Light mode'}
          </button>
          <button
            type="button"
            onClick={() => void logout()}
            className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium text-text-secondary hover:bg-surface-subtle hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-brand/50"
          >
            Log out
          </button>
        </div>
      </aside>

      <main id="main" className="flex flex-1 flex-col overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
