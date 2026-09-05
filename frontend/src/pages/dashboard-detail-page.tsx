import { PageHeader } from '@/components/layout/page-header'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { ChartCard } from '@/components/dashboards/chart-card'
import { useDashboard, useDeleteChart, useMoveChart } from '@/features/dashboards/api'
import { LayoutDashboard, Sparkles } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

export function DashboardDetailPage() {
  const { dashboardId } = useParams<{ dashboardId: string }>()
  const { data: dashboard, isLoading } = useDashboard(dashboardId ?? '')
  const deleteChart = useDeleteChart(dashboardId ?? '')
  const moveChart = useMoveChart(dashboardId ?? '')

  if (isLoading) {
    return (
      <div className="flex flex-col">
        <PageHeader title="Loading…" />
      </div>
    )
  }

  if (!dashboard) {
    return (
      <div className="flex flex-col">
        <PageHeader title="Dashboard not found" />
        <div className="px-6 py-5">
          <EmptyState
            icon={LayoutDashboard}
            title="Dashboard not found"
            description="It may have been removed, or belongs to a different account."
          />
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col">
      <PageHeader
        title={dashboard.name}
        description={`${dashboard.charts.length} chart${dashboard.charts.length === 1 ? '' : 's'}`}
        actions={
          <Button size="sm" variant="secondary" asChild>
            <Link to="/workspace/dashboards">Back to dashboards</Link>
          </Button>
        }
      />

      <div className="px-6 py-5">
        {dashboard.charts.length === 0 ? (
          <EmptyState
            icon={Sparkles}
            title="No charts yet"
            description="Run a query in the dataset explorer or ask a question in the AI analyst, then add it to this dashboard."
            action={
              <Button size="sm" variant="secondary" asChild>
                <Link to="/workspace/ai-analyst">Go to AI Analyst</Link>
              </Button>
            }
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {dashboard.charts.map((chart, index) => (
              <ChartCard
                key={chart.id}
                chart={chart}
                isFirst={index === 0}
                isLast={index === dashboard.charts.length - 1}
                onMoveUp={() => moveChart.mutate({ chartId: chart.id, direction: 'up' })}
                onMoveDown={() => moveChart.mutate({ chartId: chart.id, direction: 'down' })}
                onDelete={() => deleteChart.mutate(chart.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
