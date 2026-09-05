import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '@/features/auth/context/AuthContext'

const NAV_ITEMS = [
  { label: 'Dashboard', path: '/', end: true },
  { label: 'Analytics', path: '/analytics', end: false },
  { label: 'Risk', path: '/risk', end: false },
  { label: 'Trades', path: '/trades', end: false },
  { label: 'Import', path: '/import', end: false },
  { label: 'Settings', path: '/settings', end: false },
]

function navLinkClass({ isActive }: { isActive: boolean }) {
  const base =
    'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50'
  return isActive
    ? `${base} bg-surface-info text-primary`
    : `${base} text-text-secondary hover:bg-surface-subtle hover:text-text-primary`
}

export function AppShell() {
  const { logout } = useAuth()

  return (
    <div className="flex min-h-screen bg-surface-base">
      <aside className="flex w-56 shrink-0 flex-col border-r border-border bg-surface-base">
        <div className="border-b border-border px-4 py-5">
          <span className="text-lg font-bold text-text-primary">TradeForge</span>
        </div>

        <nav aria-label="Main navigation" className="flex-1 overflow-y-auto px-2 py-4">
          <ul className="flex flex-col gap-1">
            {NAV_ITEMS.map((item) => (
              <li key={item.path}>
                <NavLink to={item.path} end={item.end} className={navLinkClass}>
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <div className="border-t border-border px-2 py-4">
          <button
            type="button"
            onClick={() => void logout()}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-text-secondary hover:bg-surface-subtle hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/50"
          >
            Log out
          </button>
        </div>
      </aside>

      <main className="flex flex-1 flex-col overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
