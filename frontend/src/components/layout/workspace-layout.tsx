import { Button } from '@/components/ui/button'
import { useLogout } from '@/features/auth/api'
import { useAuthStore } from '@/stores/auth-store'
import { cn } from '@/lib/utils'
import {
  Activity,
  Database,
  Gauge,
  LayoutDashboard,
  LogOut,
  Menu,
  Radar,
  Settings,
  Sparkles,
  SquareStack,
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/workspace', label: 'Workspace', icon: SquareStack, end: true },
  { to: '/workspace/datasets', label: 'Datasets', icon: Database },
  { to: '/workspace/dashboards', label: 'Dashboards', icon: LayoutDashboard },
  { to: '/workspace/ai-analyst', label: 'AI Analysis', icon: Sparkles },
  { to: '/workspace/insights', label: 'Saved Insights', icon: Activity },
  { to: '/workspace/monitors', label: 'Monitors', icon: Radar },
  { to: '/workspace/usage', label: 'Usage', icon: Gauge },
  { to: '/workspace/settings', label: 'Settings', icon: Settings },
]

function Brand() {
  return (
    <div className="flex items-center gap-2">
      <div className="flex h-6 w-6 items-center justify-center rounded-sm bg-[var(--color-accent)]">
        <Activity className="h-3.5 w-3.5 text-[var(--color-accent-fg)]" strokeWidth={2.5} />
      </div>
      <span className="text-sm font-semibold tracking-tight">PulseIQ</span>
    </div>
  )
}

export function WorkspaceLayout() {
  const user = useAuthStore((s) => s.user)
  const logout = useLogout()
  const navigate = useNavigate()
  // Below md the sidebar is a drawer; picking a link closes it.
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    if (!menuOpen) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setMenuOpen(false)
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [menuOpen])

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex h-dvh w-full bg-[var(--color-canvas)] text-[var(--color-fg)]">
      {menuOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          aria-hidden="true"
          onClick={() => setMenuOpen(false)}
        />
      )}

      <aside
        id="workspace-nav"
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-[var(--color-border)] bg-[var(--color-surface)] transition-transform md:static md:w-60 md:shrink-0 md:translate-x-0',
          menuOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-4">
          <Brand />
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setMenuOpen(false)}
            aria-label="Close menu"
          >
            <X className="h-4 w-4" strokeWidth={1.75} />
          </Button>
        </div>

        <nav aria-label="Workspace" className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2 py-3">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2.5 rounded-md px-2.5 py-2.5 text-sm transition-colors md:py-2',
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
          <Button variant="ghost" size="icon" onClick={handleLogout} aria-label="Log out" title="Log out">
            <LogOut className="h-4 w-4" strokeWidth={1.75} />
          </Button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 border-b border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 md:hidden">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setMenuOpen(true)}
            aria-label="Open menu"
            aria-expanded={menuOpen}
            aria-controls="workspace-nav"
          >
            <Menu className="h-5 w-5" strokeWidth={1.75} />
          </Button>
          <Brand />
        </header>

        <main id="main" className="min-w-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
