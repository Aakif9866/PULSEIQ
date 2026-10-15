import { PageHeader } from '@/components/layout/page-header'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ErrorReference } from '@/components/ui/error-reference'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useDeleteAccount, useExportData, useLogout } from '@/features/auth/api'
import { ApiError } from '@/lib/api-client'
import { useAuthStore } from '@/stores/auth-store'
import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

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
  const logout = useLogout()
  const exportData = useExportData()
  const deleteAccount = useDeleteAccount()
  const navigate = useNavigate()
  const [confirming, setConfirming] = useState(false)
  const [password, setPassword] = useState('')

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  const handleDelete = (event: FormEvent) => {
    event.preventDefault()
    deleteAccount.mutate(password, { onSuccess: () => navigate('/', { replace: true }) })
  }

  return (
    <div className="flex flex-col">
      <PageHeader title="Settings" description="Your account on this workspace." />
      <div className="flex max-w-xl flex-col gap-4 px-4 py-5 sm:px-6">
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

        <Card>
          <CardHeader>
            <CardTitle>Your data</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between gap-4">
              <p className="text-sm text-[var(--color-fg-muted)]">
                Download everything stored about your account as JSON.
              </p>
              <Button
                variant="secondary"
                onClick={() => exportData.mutate()}
                disabled={exportData.isPending}
              >
                {exportData.isPending ? 'Preparing…' : 'Export my data'}
              </Button>
            </div>
            {exportData.isError && (
              <p role="alert" className="text-xs text-[var(--color-negative)]">
                {exportData.error instanceof ApiError ? exportData.error.message : 'Export failed.'}
                <ErrorReference error={exportData.error} />
              </p>
            )}
            <p className="text-xs text-[var(--color-fg-subtle)]">
              How your data is used:{' '}
              <Link className="underline" to="/privacy">
                Privacy Policy
              </Link>{' '}
              ·{' '}
              <Link className="underline" to="/terms">
                Terms
              </Link>
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Delete account</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-[var(--color-fg-muted)]">
              Permanently deletes your account, uploaded files, dashboards, insights, queries, and
              monitors. This can't be undone.
            </p>
            {!confirming ? (
              <Button variant="destructive" onClick={() => setConfirming(true)}>
                Delete my account
              </Button>
            ) : (
              <form onSubmit={handleDelete} className="space-y-2">
                <Label htmlFor="delete-password">Enter your password to confirm</Label>
                <Input
                  id="delete-password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <div className="flex gap-2">
                  <Button
                    type="submit"
                    variant="destructive"
                    disabled={!password || deleteAccount.isPending}
                  >
                    {deleteAccount.isPending ? 'Deleting…' : 'Permanently delete'}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setConfirming(false)
                      setPassword('')
                      deleteAccount.reset()
                    }}
                  >
                    Cancel
                  </Button>
                </div>
                {deleteAccount.isError && (
                  <p role="alert" className="text-xs text-[var(--color-negative)]">
                    {deleteAccount.error instanceof ApiError
                      ? deleteAccount.error.message
                      : 'Deletion failed.'}
                    <ErrorReference error={deleteAccount.error} />
                  </p>
                )}
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
