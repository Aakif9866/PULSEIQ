import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { useDatasetQueryResult } from '@/features/datasets/api'
import { buildChartOption } from '@/lib/chart-options'
import type { DashboardChart } from '@/types/dashboard'
import { ArrowDown, ArrowUp, Trash2 } from 'lucide-react'
import ReactECharts from 'echarts-for-react'

interface ChartCardProps {
  chart: DashboardChart
  onMoveUp: () => void
  onMoveDown: () => void
  onDelete: () => void
  isFirst: boolean
  isLast: boolean
}

export function ChartCard({ chart, onMoveUp, onMoveDown, onDelete, isFirst, isLast }: ChartCardProps) {
  const { data: result, isLoading, isError } = useDatasetQueryResult(
    chart.dataset_id,
    chart.query_request,
  )

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <div>
          <CardTitle>{chart.title}</CardTitle>
          <p className="mt-0.5 text-xs text-[var(--color-fg-subtle)]">{chart.dataset_filename}</p>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onMoveUp}
            disabled={isFirst}
            className="rounded p-1 text-[var(--color-fg-muted)] hover:bg-[var(--color-surface-raised)] disabled:opacity-30"
            aria-label="Move chart up"
          >
            <ArrowUp className="h-3.5 w-3.5" strokeWidth={1.75} />
          </button>
          <button
            type="button"
            onClick={onMoveDown}
            disabled={isLast}
            className="rounded p-1 text-[var(--color-fg-muted)] hover:bg-[var(--color-surface-raised)] disabled:opacity-30"
            aria-label="Move chart down"
          >
            <ArrowDown className="h-3.5 w-3.5" strokeWidth={1.75} />
          </button>
          <button
            type="button"
            onClick={onDelete}
            className="rounded p-1 text-[var(--color-fg-muted)] hover:bg-[var(--color-surface-raised)]"
            aria-label="Remove chart"
          >
            <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
          </button>
        </div>
      </CardHeader>
      <div className="px-2 pb-2">
        {isLoading && (
          <div className="flex h-64 items-center justify-center text-xs text-[var(--color-fg-muted)]">
            Loading chart…
          </div>
        )}
        {isError && (
          <div className="flex h-64 items-center justify-center text-xs text-[var(--color-negative)]">
            Couldn't load this chart's data.
          </div>
        )}
        {result && (
          <ReactECharts
            option={buildChartOption(result, chart.chart_type)}
            style={{ height: 260 }}
            opts={{ renderer: 'svg' }}
          />
        )}
      </div>
    </Card>
  )
}
