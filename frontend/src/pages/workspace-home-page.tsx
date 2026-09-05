import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { PageHeader } from '@/components/layout/page-header'
import { useDashboards } from '@/features/dashboards/api'
import { useDatasets } from '@/features/datasets/api'
import { useInsights } from '@/features/insights/api'
import { formatBytes, formatDate } from '@/lib/utils'
import { Activity, Database, LayoutDashboard, Star, Upload } from 'lucide-react'
import { Link } from 'react-router-dom'

export function WorkspaceHomePage() {
  const { data: datasets } = useDatasets()
  const { data: dashboards } = useDashboards()
  const { data: insights } = useInsights()
  const recentDatasets = datasets?.slice(0, 5) ?? []

  const statTiles = [
    { label: 'Datasets', value: String(datasets?.length ?? 0), icon: Database },
    { label: 'Dashboards', value: String(dashboards?.length ?? 0), icon: LayoutDashboard },
    { label: 'Insights saved', value: String(insights?.length ?? 0), icon: Star },
  ]

  return (
    <div className="flex flex-col">
      <PageHeader
        title="Workspace"
        description="An overview of your datasets, dashboards, and recent activity."
        actions={
          <Button size="sm" asChild>
            <Link to="/workspace/datasets">
              <Upload className="h-4 w-4" strokeWidth={1.75} />
              Upload dataset
            </Link>
          </Button>
        }
      />

      <div className="grid grid-cols-3 gap-3 px-6 py-5">
        {statTiles.map(({ label, value, icon: Icon }) => (
          <Card key={label}>
            <CardContent className="flex items-center justify-between py-4">
              <div>
                <p className="text-[11px] uppercase tracking-wide text-[var(--color-fg-subtle)]">
                  {label}
                </p>
                <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
              </div>
              <Icon className="h-5 w-5 text-[var(--color-fg-subtle)]" strokeWidth={1.5} />
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-3 px-6 pb-6">
        <Card>
          <CardHeader>
            <CardTitle>Recent datasets</CardTitle>
          </CardHeader>
          <CardContent>
            {recentDatasets.length === 0 ? (
              <EmptyState
                icon={Database}
                title="No datasets yet"
                description="Upload a CSV or Excel file to start profiling, exploring, and asking questions about your data."
                action={
                  <Button size="sm" variant="secondary" asChild>
                    <Link to="/workspace/datasets">
                      <Upload className="h-4 w-4" strokeWidth={1.75} />
                      Upload your first dataset
                    </Link>
                  </Button>
                }
              />
            ) : (
              <ul className="divide-y divide-[var(--color-border)]">
                {recentDatasets.map((dataset) => (
                  <li
                    key={dataset.id}
                    className="flex items-center justify-between gap-3 py-2 text-sm first:pt-0 last:pb-0"
                  >
                    <span className="truncate text-[var(--color-fg)]">{dataset.original_filename}</span>
                    <span className="shrink-0 text-xs text-[var(--color-fg-muted)]">
                      {formatBytes(dataset.size_bytes)} · {formatDate(dataset.created_at)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
          </CardHeader>
          <CardContent>
            <EmptyState
              icon={Activity}
              title="Nothing to show yet"
              description="Once you upload a dataset and start asking questions, your activity will appear here."
            />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
