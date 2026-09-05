import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/auth-store'
import { cn } from '@/lib/utils'
import {
  Activity,
  Database,
  LayoutDashboard,
  LogOut,
  Settings,
  Sparkles,
  SquareStack,
} from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/workspace', label: 'Workspace', icon: SquareStack, end: true },
  { to: '/workspace/datasets', label: 'Datasets', icon: Database },
  { to: '/workspace/dashboards', label: 'Dashboards', icon: LayoutDashboard },
  { to: '/workspace/ai-analyst', label: 'AI Analysis', icon: Sparkles },
  { to: '/workspace/insights', label: 'Saved Insights', icon: Activity },
  { to: '/workspace/settings', label: 'Settings', icon: Settings },
]

export function WorkspaceLayout() {
  const user = useAuthStore((s) => s.user)
  const clearSession = useAuthStore((s) => s.clearSession)
  const navigate = useNavigate()

  const handleLogout = () => {
    clearSession()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex h-screen w-full bg-[var(--color-canvas)] text-[var(--color-fg)]">
      <aside className="flex w-60 shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-surface)]">
        <div className="flex items-center gap-2 border-b border-[var(--color-border)] px-4 py-4">
          <div className="flex h-6 w-6 items-center justify-center rounded-sm bg-[var(--color-accent)]">
            <Activity className="h-3.5 w-3.5 text-[var(--color-accent-fg)]" strokeWidth={2.5} />
          </div>
          <span className="text-sm font-semibold tracking-tight">PulseIQ</span>
        </div>

        <nav className="flex flex-1 flex-col gap-0.5 px-2 py-3">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors',
                  isActive
                    ? 'bg-[var(--color-accent-muted)] text-[var(--color-fg)]'
                    : 'text-[var(--color-fg-muted)] hover:bg-[var(--color-surface-raised)] hover:text-[var(--color-fg)]',
                )
              }
            >
              <Icon className="h-4 w-4" strokeWidth={1.75} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center justify-between gap-2 border-t border-[var(--color-border)] px-3 py-3">
          <div className="min-w-0">
            <p className="truncate text-xs font-medium text-[var(--color-fg)]">
              {user?.full_name || user?.email}
            </p>
            <p className="truncate text-[11px] text-[var(--color-fg-subtle)]">{user?.email}</p>
          </div>
          <Button variant="ghost" size="icon" onClick={handleLogout} title="Log out">
            <LogOut className="h-4 w-4" strokeWidth={1.75} />
          </Button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
