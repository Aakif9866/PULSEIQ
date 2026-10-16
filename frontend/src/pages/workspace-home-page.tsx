import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { IconChip } from '@/components/ui/icon-chip'
import { PageHeader } from '@/components/layout/page-header'
import { useDashboards } from '@/features/dashboards/api'
import { useDatasets } from '@/features/datasets/api'
import { useRecentActivity } from '@/features/history/api'
import { useInsights } from '@/features/insights/api'
import { formatBytes, formatDate } from '@/lib/utils'
import { Activity, Code2, Database, LayoutDashboard, Sparkles, Star, Upload } from 'lucide-react'
import type { QuerySource } from '@/types/history'
import { Link } from 'react-router-dom'

const SOURCE_META: Record<QuerySource, { label: string; icon: typeof Sparkles; color: string }> = {
  ai_deep_analysis: { label: 'AI analysis', icon: Sparkles, color: 'var(--color-purple)' },
  ai_structured: { label: 'AI question', icon: Sparkles, color: 'var(--color-purple)' },
  ai_sql: { label: 'AI → SQL', icon: Code2, color: 'var(--color-indigo)' },
  sql_explorer: { label: 'SQL query', icon: Code2, color: 'var(--color-teal)' },
}

export function WorkspaceHomePage() {
  const { data: datasets } = useDatasets()
  const { data: dashboards } = useDashboards()
  const { data: insights } = useInsights()
  const { data: activity } = useRecentActivity()
  const recentDatasets = datasets?.slice(0, 5) ?? []
  const recentActivity = activity?.slice(0, 6) ?? []
  const filenames = new Map(datasets?.map((d) => [d.id, d.original_filename]))

  const statTiles = [
    { label: 'Datasets', value: String(datasets?.length ?? 0), icon: Database, color: 'var(--color-teal)' },
    { label: 'Dashboards', value: String(dashboards?.length ?? 0), icon: LayoutDashboard, color: 'var(--color-indigo)' },
    { label: 'Insights saved', value: String(insights?.length ?? 0), icon: Star, color: 'var(--color-pink)' },
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

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 px-4 py-5 sm:px-6">
        {statTiles.map(({ label, value, icon, color }) => (
          <Card key={label}>
            <CardContent className="flex items-center justify-between py-4">
              <div>
                <p className="text-[11px] uppercase tracking-wide text-[var(--color-fg-subtle)]">
                  {label}
                </p>
                <p className="mt-1 text-3xl font-semibold tracking-tight tabular-nums">{value}</p>
              </div>
              <IconChip icon={icon} color={color} />
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-3 px-4 pb-6 sm:px-6 lg:grid-cols-2">
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
                  <li key={dataset.id}>
                    <Link
                      to={`/workspace/datasets/${dataset.id}`}
                      className="-mx-2 flex items-center justify-between gap-3 rounded-md px-2 py-2 text-sm transition-colors hover:bg-[var(--color-surface-raised)]"
                    >
                      <span className="truncate text-[var(--color-fg)]">{dataset.original_filename}</span>
                      <span className="shrink-0 text-xs text-[var(--color-fg-muted)]">
                        {formatBytes(dataset.size_bytes)} · {formatDate(dataset.created_at)}
                      </span>
                    </Link>
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
            {recentActivity.length === 0 ? (
              <EmptyState
                icon={Activity}
                title="Nothing to show yet"
                description="Questions you ask the AI and queries you run in the SQL Explorer will appear here."
                action={
                  <Button size="sm" variant="secondary" asChild>
                    <Link to="/workspace/ai-analyst">
                      <Sparkles className="h-4 w-4" strokeWidth={1.75} />
                      Ask a question
                    </Link>
                  </Button>
                }
              />
            ) : (
              <ul className="space-y-0.5">
                {recentActivity.map((item) => {
                  const { label, icon: Icon, color } = SOURCE_META[item.source]
                  return (
                    <li key={item.id}>
                      <Link
                        to={`/workspace/datasets/${item.dataset_id}`}
                        className="-mx-2 flex items-start gap-3 rounded-md px-2 py-2 transition-colors hover:bg-[var(--color-surface-raised)]"
                      >
                        <Icon className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.75} style={{ color }} />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm text-[var(--color-fg)]">
                            {item.question || item.sql_text}
                          </span>
                          <span className="block truncate text-xs text-[var(--color-fg-muted)]">
                            {label} · {filenames.get(item.dataset_id) ?? 'Deleted dataset'} ·{' '}
                            {formatDate(item.created_at)}
                          </span>
                        </span>
                      </Link>
                    </li>
                  )
                })}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
