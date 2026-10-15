import { PageHeader } from '@/components/layout/page-header'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuthStore } from '@/stores/auth-store'
import { useNavigate } from 'react-router-dom'

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 text-sm">
      <span className="text-[var(--color-fg-muted)]">{label}</span>
      <span className="truncate text-[var(--color-fg)]">{value}</span>
    </div>
  )
}

export function SettingsPage() {
  const user = useAuthStore((s) => s.user)
  const clearSession = useAuthStore((s) => s.clearSession)
  const navigate = useNavigate()

  const handleLogout = () => {
    clearSession()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex flex-col">
      <PageHeader title="Settings" description="Your account on this workspace." />
      <div className="flex max-w-xl flex-col gap-4 px-6 py-5">
        <Card>
          <CardHeader>
            <CardTitle>Account</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Field label="Name" value={user?.full_name || '—'} />
            <Field label="Email" value={user?.email ?? '—'} />
            <Field label="Status" value={user?.is_active ? 'Active' : 'Inactive'} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Session</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between gap-4">
            <p className="text-sm text-[var(--color-fg-muted)]">
              Sign out of PulseIQ on this browser.
            </p>
            <Button variant="secondary" onClick={handleLogout}>
              Log out
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
