import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { KpiCard } from '@/components/dashboards/kpi-card'
import { ResultTable } from '@/components/dashboards/result-table'
import { useDatasetQueryResult } from '@/features/datasets/api'
import { buildChartOption } from '@/lib/chart-options'
import { useTheme } from '@/lib/theme'
import type { DashboardChart } from '@/types/dashboard'
import { ArrowDown, ArrowUp, Check, Lightbulb, Pencil, Trash2, X } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'
import ReactECharts from 'echarts-for-react'

interface ChartCardProps {
  chart: DashboardChart
  onMoveUp: () => void
  onMoveDown: () => void
  onDelete: () => void
  onRename: (title: string) => void
  isFirst: boolean
  isLast: boolean
}

export function ChartCard({
  chart,
  onMoveUp,
  onMoveDown,
  onDelete,
  onRename,
  isFirst,
  isLast,
}: ChartCardProps) {
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(chart.title)
  const submitTitle = (e: FormEvent) => {
    e.preventDefault()
    const next = title.trim()
    if (next && next !== chart.title) onRename(next)
    setEditing(false)
  }
  const theme = useTheme()
  const { data: result, isLoading, isError } = useDatasetQueryResult(
    chart.dataset_id,
    chart.query_request,
  )

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <div className="min-w-0 flex-1">
          {editing ? (
            <form onSubmit={submitTitle} className="flex items-center gap-1">
              <input
                autoFocus
                aria-label="Chart title"
                value={title}
                maxLength={255}
                onChange={(e) => setTitle(e.target.value)}
                onKeyDown={(e) => e.key === 'Escape' && setEditing(false)}
                className="h-7 min-w-0 flex-1 rounded-md border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-2 text-sm outline-none focus-visible:border-[var(--color-accent)] focus-visible:ring-4 focus-visible:ring-[var(--color-focus)]"
              />
              <button type="submit" aria-label="Save title" className="rounded-md p-1.5 text-[var(--color-fg-muted)] hover:bg-[var(--color-surface-raised)]">
                <Check className="h-3.5 w-3.5" strokeWidth={2} />
              </button>
              <button type="button" aria-label="Cancel" onClick={() => setEditing(false)} className="rounded-md p-1.5 text-[var(--color-fg-muted)] hover:bg-[var(--color-surface-raised)]">
                <X className="h-3.5 w-3.5" strokeWidth={2} />
              </button>
            </form>
          ) : (
            <div className="flex items-center gap-1">
              <CardTitle className="truncate">{chart.title}</CardTitle>
              <button
                type="button"
                onClick={() => {
                  setTitle(chart.title)
                  setEditing(true)
                }}
                aria-label="Rename chart"
                className="rounded-md p-1 text-[var(--color-fg-subtle)] hover:bg-[var(--color-surface-raised)] hover:text-[var(--color-fg)]"
              >
                <Pencil className="h-3 w-3" strokeWidth={2} />
              </button>
            </div>
          )}
          <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-[var(--color-fg-subtle)]">
            {chart.dataset_filename}
            {chart.insight_id && (
              <Link
                to={`/workspace/insights?focus=${chart.insight_id}`}
                className="inline-flex items-center gap-1 text-[var(--color-accent)] hover:underline"
              >
                <Lightbulb className="h-3 w-3" strokeWidth={2} />
                View insight
              </Link>
            )}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onMoveUp}
            disabled={isFirst}
            className="rounded-md p-1.5 text-[var(--color-fg-muted)] hover:bg-[var(--color-surface-raised)] disabled:opacity-30"
            aria-label="Move chart up"
          >
            <ArrowUp className="h-3.5 w-3.5" strokeWidth={1.75} />
          </button>
          <button
            type="button"
            onClick={onMoveDown}
            disabled={isLast}
            className="rounded-md p-1.5 text-[var(--color-fg-muted)] hover:bg-[var(--color-surface-raised)] disabled:opacity-30"
            aria-label="Move chart down"
          >
            <ArrowDown className="h-3.5 w-3.5" strokeWidth={1.75} />
          </button>
          <button
            type="button"
            onClick={onDelete}
            className="rounded-md p-1.5 text-[var(--color-fg-muted)] hover:bg-[var(--color-surface-raised)]"
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
        {result && chart.chart_type === 'kpi' && <KpiCard label={chart.title} result={result} />}
        {result && chart.chart_type === 'table' && <ResultTable result={result} />}
        {result && chart.chart_type !== 'kpi' && chart.chart_type !== 'table' && (
          <ReactECharts
            option={buildChartOption(result, chart.chart_type, theme)}
            style={{ height: 260 }}
            opts={{ renderer: 'svg' }}
          />
        )}
      </div>
    </Card>
  )
}
