import { Brand } from '@/components/brand'
import { ContactButton } from '@/components/landing/contact-button'
import { UserCount } from '@/components/landing/user-count'
import { ThemeToggle } from '@/components/theme-toggle'
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

// Each section keeps one color everywhere, so it's recognizable at a glance.
const NAV_ITEMS = [
  { to: '/workspace', label: 'Workspace', icon: SquareStack, color: 'var(--color-accent)', end: true },
  { to: '/workspace/datasets', label: 'Datasets', icon: Database, color: 'var(--color-teal)' },
  { to: '/workspace/dashboards', label: 'Dashboards', icon: LayoutDashboard, color: 'var(--color-indigo)' },
  { to: '/workspace/ai-analyst', label: 'AI Analysis', icon: Sparkles, color: 'var(--color-purple)' },
  { to: '/workspace/insights', label: 'Saved Insights', icon: Activity, color: 'var(--color-pink)' },
  { to: '/workspace/monitors', label: 'Monitors', icon: Radar, color: 'var(--color-orange)' },
  { to: '/workspace/usage', label: 'Usage', icon: Gauge, color: 'var(--color-positive)' },
  { to: '/workspace/settings', label: 'Settings', icon: Settings, color: 'var(--color-fg-muted)' },
]

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
      {/* Always mounted so the scrim fades both ways instead of popping. */}
      <div
        className={cn(
          'fixed inset-0 z-30 bg-black/40 transition-opacity duration-300 md:hidden',
          menuOpen ? 'opacity-100' : 'pointer-events-none opacity-0',
        )}
        aria-hidden="true"
        onClick={() => setMenuOpen(false)}
      />

      <aside
        id="workspace-nav"
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-[var(--color-border)] bg-[var(--color-canvas)] transition-transform duration-300 ease-apple md:static md:w-60 md:shrink-0 md:translate-x-0',
          menuOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex h-14 items-center justify-between px-4">
          <Brand size="sm" />
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
          {NAV_ITEMS.map(({ to, label, icon: Icon, color, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2.5 rounded-md px-2.5 py-2.5 text-sm transition-[background-color,color,transform] duration-100 active:scale-[0.98] md:py-2',
                  isActive
                    ? 'font-medium text-[var(--color-fg)]'
                    : 'text-[var(--color-fg-muted)] hover:bg-[var(--color-surface-raised)] hover:text-[var(--color-fg)]',
                )
              }
              style={({ isActive }) =>
                isActive ? { backgroundColor: `color-mix(in srgb, ${color} 15%, transparent)` } : undefined
              }
            >
              <Icon className="h-4 w-4" strokeWidth={2} style={{ color }} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center justify-between gap-2 border-t border-[var(--color-border)] px-3 py-3">
          <span
            aria-hidden="true"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[linear-gradient(135deg,var(--color-purple),var(--color-pink))] text-xs font-semibold text-white"
          >
            {(user?.full_name || user?.email || '?').charAt(0).toUpperCase()}
          </span>
          <div className="min-w-0 flex-1">
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

      <main id="main" className="min-w-0 flex-1 overflow-y-auto">
        {/* Translucent bar: page content scrolls underneath it. */}
        <header className="material sticky top-0 z-20 flex h-14 items-center gap-2 border-b border-[var(--color-border)] px-3 sm:px-6">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setMenuOpen(true)}
            aria-label="Open menu"
            aria-expanded={menuOpen}
            aria-controls="workspace-nav"
          >
            <Menu className="h-5 w-5" strokeWidth={1.75} />
          </Button>
          <span className="md:hidden">
            <Brand size="sm" />
          </span>
          <div className="ml-auto flex items-center gap-1 sm:gap-2">
            <UserCount />
            <ContactButton />
            <ThemeToggle />
          </div>
        </header>
        <Outlet />
      </main>
    </div>
  )
}
