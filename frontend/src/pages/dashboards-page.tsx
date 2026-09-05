import { PageHeader } from '@/components/layout/page-header'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { Input } from '@/components/ui/input'
import { useCreateDashboard, useDashboards, useDeleteDashboard } from '@/features/dashboards/api'
import { formatDate } from '@/lib/utils'
import { LayoutDashboard, Plus, Trash2 } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'

export function DashboardsPage() {
  const { data: dashboards, isLoading } = useDashboards()
  const createDashboard = useCreateDashboard()
  const deleteDashboard = useDeleteDashboard()

  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')

  const handleCreate = (event: FormEvent) => {
    event.preventDefault()
    if (!name.trim()) return
    createDashboard.mutate(name.trim(), {
      onSuccess: () => {
        setName('')
        setCreating(false)
      },
    })
  }

  return (
    <div className="flex flex-col">
      <PageHeader
        title="Dashboards"
        description="Saved analyses and dashboard canvases."
        actions={
          !creating && (
            <Button size="sm" onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" strokeWidth={1.75} />
              New dashboard
            </Button>
          )
        }
      />

      <div className="flex flex-col gap-4 px-6 py-5">
        {creating && (
          <form
            className="flex items-end gap-2 rounded-md border border-[var(--color-border)] p-3"
            onSubmit={handleCreate}
          >
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-[var(--color-fg-muted)]">Name</label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Sales overview"
                autoFocus
              />
            </div>
            <Button type="submit" size="sm" disabled={!name.trim() || createDashboard.isPending}>
              {createDashboard.isPending ? 'Creating…' : 'Create'}
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setCreating(false)}>
              Cancel
            </Button>
          </form>
        )}

        {!isLoading && dashboards?.length === 0 && !creating && (
          <EmptyState
            icon={LayoutDashboard}
            title="No dashboards yet"
            description="Create a dashboard, then add charts to it from the dataset explorer or AI analyst."
            action={
              <Button size="sm" variant="secondary" onClick={() => setCreating(true)}>
                <Plus className="h-4 w-4" strokeWidth={1.75} />
                New dashboard
              </Button>
            }
          />
        )}

        {dashboards && dashboards.length > 0 && (
          <Card>
            <ul className="divide-y divide-[var(--color-border)]">
              {dashboards.map((dashboard) => (
                <li key={dashboard.id} className="flex items-center justify-between gap-4 px-4 py-3">
                  <Link
                    to={`/workspace/dashboards/${dashboard.id}`}
                    className="flex min-w-0 flex-1 items-center gap-3"
                  >
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[var(--color-surface-raised)]">
                      <LayoutDashboard
                        className="h-4 w-4 text-[var(--color-fg-muted)]"
                        strokeWidth={1.5}
                      />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-[var(--color-fg)]">
                        {dashboard.name}
                      </p>
                      <p className="text-xs text-[var(--color-fg-muted)]">
                        {dashboard.chart_count} chart{dashboard.chart_count === 1 ? '' : 's'} ·
                        Created {formatDate(dashboard.created_at)}
                      </p>
                    </div>
                  </Link>
                  <button
                    type="button"
                    onClick={() => deleteDashboard.mutate(dashboard.id)}
                    className="shrink-0 rounded p-1.5 text-[var(--color-fg-muted)] hover:bg-[var(--color-surface-raised)]"
                    aria-label="Delete dashboard"
                  >
                    <Trash2 className="h-4 w-4" strokeWidth={1.75} />
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </div>
  )
}
