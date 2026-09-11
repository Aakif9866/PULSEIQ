import { PageHeader } from '@/components/layout/page-header'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { useAnomalies, useMonitor, useRunMonitor } from '@/features/monitors/api'
import { formatDate } from '@/lib/utils'
import type { Severity } from '@/types/monitor'
import { ArrowLeft, History } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

const SEVERITY_CLASS: Record<Severity, string> = {
  low: 'text-[var(--color-fg-muted)]',
  medium: 'text-[var(--color-fg)]',
  high: 'text-[var(--color-negative)]',
}

function formatChange(changePercent: number | null, direction: 'increase' | 'decrease'): string {
  if (changePercent === null) return direction === 'increase' ? 'Moved up' : 'Moved down'
  const sign = direction === 'increase' ? '+' : '-'
  return `${sign}${Math.abs(changePercent).toFixed(1)}%`
}

export function MonitorDetailPage() {
  const { monitorId } = useParams<{ monitorId: string }>()
  const { data: monitor, isLoading } = useMonitor(monitorId ?? '')
  const { data: anomalies } = useAnomalies(monitorId)
  const runMonitor = useRunMonitor()

  if (isLoading) {
    return (
      <div className="flex flex-col">
        <PageHeader title="Loading…" />
      </div>
    )
  }

  if (!monitor) {
    return (
      <div className="flex flex-col">
        <PageHeader title="Monitor not found" />
        <div className="px-6 py-5">
          <EmptyState
            icon={History}
            title="Monitor not found"
            description="It may have been removed, or belongs to a different account."
          />
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col">
      <PageHeader
        title={monitor.name}
        description={`${monitor.dataset_filename} · ${monitor.aggregation}(${monitor.metric_column}) by ${monitor.time_column}`}
        actions={
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" asChild>
              <Link to="/workspace/monitors">
                <ArrowLeft className="h-4 w-4" strokeWidth={1.75} />
                Back to monitors
              </Link>
            </Button>
            <Button
              size="sm"
              disabled={runMonitor.isPending}
              onClick={() => monitorId && runMonitor.mutate(monitorId)}
            >
              {runMonitor.isPending ? 'Running…' : 'Run now'}
            </Button>
          </div>
        }
      />

      <div className="flex flex-col gap-4 px-6 py-5">
        <Card>
          <CardHeader>
            <CardTitle>Configuration</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs text-[var(--color-fg-muted)] sm:grid-cols-4">
            <div>
              <p className="text-[var(--color-fg-subtle)]">Baseline</p>
              <p className="text-[var(--color-fg)]">{monitor.baseline_strategy.replace('_', ' ')}</p>
            </div>
            <div>
              <p className="text-[var(--color-fg-subtle)]">Sensitivity</p>
              <p className="text-[var(--color-fg)]">
                {monitor.baseline_strategy === 'zscore'
                  ? `z ≥ ${monitor.zscore_threshold}`
                  : `${monitor.threshold_percent}%`}
              </p>
            </div>
            <div>
              <p className="text-[var(--color-fg-subtle)]">Frequency</p>
              <p className="text-[var(--color-fg)]">{monitor.check_frequency}</p>
            </div>
            <div>
              <p className="text-[var(--color-fg-subtle)]">Email alerts</p>
              <p className="text-[var(--color-fg)]">{monitor.notify_email ? 'On' : 'Off'}</p>
            </div>
            <div>
              <p className="text-[var(--color-fg-subtle)]">Last checked</p>
              <p className="text-[var(--color-fg)]">
                {monitor.last_checked_at ? formatDate(monitor.last_checked_at) : 'Never'}
              </p>
            </div>
            <div>
              <p className="text-[var(--color-fg-subtle)]">Last result</p>
              <p className="text-[var(--color-fg)]">{monitor.last_status ?? 'n/a'}</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Anomaly history</CardTitle>
          </CardHeader>
          {anomalies && anomalies.length > 0 ? (
            <ul className="divide-y divide-[var(--color-border)]">
              {anomalies.map((anomaly) => (
                <li key={anomaly.id} className="flex flex-col gap-1 px-4 py-3">
                  <div className="flex items-center justify-between gap-4">
                    <p className="text-sm font-medium text-[var(--color-fg)]">
                      {anomaly.period_label} ·{' '}
                      <span className={SEVERITY_CLASS[anomaly.severity]}>
                        {formatChange(anomaly.change_percent, anomaly.direction)}
                      </span>
                    </p>
                    <span className="shrink-0 text-xs text-[var(--color-fg-subtle)]">
                      {anomaly.alert_sent
                        ? 'Alert sent'
                        : anomaly.alert_error
                          ? 'Alert failed'
                          : 'Not alerted'}
                    </span>
                  </div>
                  <p className="text-xs text-[var(--color-fg-muted)]">
                    Observed {anomaly.observed_value}
                    {anomaly.baseline_value !== null && ` · baseline ${anomaly.baseline_value}`} ·
                    {' '}
                    {anomaly.severity} severity
                  </p>
                  {anomaly.explanation && (
                    <p className="text-xs text-[var(--color-fg-muted)]">{anomaly.explanation}</p>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <div className="px-4 py-6">
              <EmptyState
                icon={History}
                title="No anomalies yet"
                description="Nothing unusual has been detected for this monitor so far."
              />
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
