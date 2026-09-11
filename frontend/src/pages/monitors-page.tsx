import { PageHeader } from '@/components/layout/page-header'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { useDataset, useDatasets } from '@/features/datasets/api'
import { useCreateMonitor, useDeleteMonitor, useMonitors, useRunMonitor } from '@/features/monitors/api'
import { ApiError } from '@/lib/api-client'
import { formatDate } from '@/lib/utils'
import type { AggregationOp } from '@/types/dataset'
import type { BaselineStrategy, CheckFrequency, MonitorStatus } from '@/types/monitor'
import { Plus, Radar, Trash2 } from 'lucide-react'
import { type FormEvent, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

const AGGREGATIONS: AggregationOp[] = ['sum', 'avg', 'min', 'max', 'count']

const STATUS_LABEL: Record<MonitorStatus, string> = {
  NO_ANOMALY: 'Normal',
  ANOMALY_DETECTED: 'Anomaly detected',
  INSUFFICIENT_DATA: 'Not enough history',
  ERROR: 'Check failed',
}

const STATUS_CLASS: Record<MonitorStatus, string> = {
  NO_ANOMALY: 'text-[var(--color-fg-muted)]',
  ANOMALY_DETECTED: 'text-[var(--color-negative)]',
  INSUFFICIENT_DATA: 'text-[var(--color-fg-subtle)]',
  ERROR: 'text-[var(--color-negative)]',
}

export function MonitorsPage() {
  const { data: monitors, isLoading } = useMonitors()
  const { data: datasets } = useDatasets()
  const createMonitor = useCreateMonitor()
  const deleteMonitor = useDeleteMonitor()
  const runMonitor = useRunMonitor()

  const [creating, setCreating] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const [datasetId, setDatasetId] = useState('')
  const [name, setName] = useState('')
  const [metricColumn, setMetricColumn] = useState('')
  const [timeColumn, setTimeColumn] = useState('')
  const [aggregation, setAggregation] = useState<AggregationOp>('sum')
  const [baselineStrategy, setBaselineStrategy] = useState<BaselineStrategy>('moving_average')
  const [thresholdPercent, setThresholdPercent] = useState('20')
  const [zscoreThreshold, setZscoreThreshold] = useState('3')
  const [checkFrequency, setCheckFrequency] = useState<CheckFrequency>('daily')
  const [notifyEmail, setNotifyEmail] = useState(false)

  const { data: selectedDataset } = useDataset(datasetId)
  const columnNames = useMemo(
    () => selectedDataset?.columns_profile?.map((c) => c.name) ?? [],
    [selectedDataset],
  )
  const profiledDatasets = useMemo(
    () => (datasets ?? []).filter((d) => d.status === 'profiled'),
    [datasets],
  )

  const resetForm = () => {
    setDatasetId('')
    setName('')
    setMetricColumn('')
    setTimeColumn('')
    setAggregation('sum')
    setBaselineStrategy('moving_average')
    setThresholdPercent('20')
    setZscoreThreshold('3')
    setCheckFrequency('daily')
    setNotifyEmail(false)
    setFormError(null)
  }

  const canSubmit = Boolean(datasetId && name.trim() && metricColumn && timeColumn)

  const handleCreate = (event: FormEvent) => {
    event.preventDefault()
    if (!canSubmit) return
    setFormError(null)
    createMonitor.mutate(
      {
        dataset_id: datasetId,
        name: name.trim(),
        metric_column: metricColumn,
        time_column: timeColumn,
        aggregation,
        baseline_strategy: baselineStrategy,
        threshold_percent: baselineStrategy === 'zscore' ? null : Number(thresholdPercent),
        zscore_threshold: baselineStrategy === 'zscore' ? Number(zscoreThreshold) : null,
        check_frequency: checkFrequency,
        notify_email: notifyEmail,
      },
      {
        onSuccess: () => {
          resetForm()
          setCreating(false)
        },
        onError: (err) => {
          setFormError(err instanceof ApiError ? err.message : 'Could not create the monitor.')
        },
      },
    )
  }

  return (
    <div className="flex flex-col">
      <PageHeader
        title="Monitors"
        description="Watch a metric and get alerted when it moves unexpectedly."
        actions={
          !creating && (
            <Button size="sm" onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" strokeWidth={1.75} />
              New monitor
            </Button>
          )
        }
      />

      <div className="flex flex-col gap-4 px-6 py-5">
        {creating && (
          <form
            className="flex flex-col gap-4 rounded-md border border-[var(--color-border)] p-4"
            onSubmit={handleCreate}
          >
            {formError && <p className="text-xs text-[var(--color-negative)]">{formError}</p>}

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Dataset</Label>
                <Select
                  value={datasetId}
                  onChange={(e) => {
                    setDatasetId(e.target.value)
                    setMetricColumn('')
                    setTimeColumn('')
                  }}
                >
                  <option value="">Select a dataset…</option>
                  {profiledDatasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.original_filename}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Monitor name</Label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Daily revenue"
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <Label>Time column</Label>
                <Select
                  value={timeColumn}
                  onChange={(e) => setTimeColumn(e.target.value)}
                  disabled={!datasetId}
                >
                  <option value="">Select…</option>
                  {columnNames.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Metric column</Label>
                <Select
                  value={metricColumn}
                  onChange={(e) => setMetricColumn(e.target.value)}
                  disabled={!datasetId}
                >
                  <option value="">Select…</option>
                  {columnNames.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Aggregation</Label>
                <Select
                  value={aggregation}
                  onChange={(e) => setAggregation(e.target.value as AggregationOp)}
                >
                  {AGGREGATIONS.map((a) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <Label>Baseline</Label>
                <Select
                  value={baselineStrategy}
                  onChange={(e) => setBaselineStrategy(e.target.value as BaselineStrategy)}
                >
                  <option value="previous_period">Previous period</option>
                  <option value="moving_average">Moving average</option>
                  <option value="zscore">Z-score (statistical)</option>
                </Select>
              </div>
              {baselineStrategy === 'zscore' ? (
                <div className="space-y-1.5">
                  <Label>Sensitivity (z-score)</Label>
                  <Input
                    type="number"
                    step="0.1"
                    min="0.1"
                    value={zscoreThreshold}
                    onChange={(e) => setZscoreThreshold(e.target.value)}
                  />
                </div>
              ) : (
                <div className="space-y-1.5">
                  <Label>Threshold (%)</Label>
                  <Input
                    type="number"
                    step="1"
                    min="1"
                    value={thresholdPercent}
                    onChange={(e) => setThresholdPercent(e.target.value)}
                  />
                </div>
              )}
              <div className="space-y-1.5">
                <Label>Check frequency</Label>
                <Select
                  value={checkFrequency}
                  onChange={(e) => setCheckFrequency(e.target.value as CheckFrequency)}
                >
                  <option value="manual">Manual only</option>
                  <option value="daily">Daily</option>
                  <option value="hourly">Hourly</option>
                </Select>
              </div>
            </div>

            <label className="flex items-center gap-2 text-xs text-[var(--color-fg-muted)]">
              <input
                type="checkbox"
                checked={notifyEmail}
                onChange={(e) => setNotifyEmail(e.target.checked)}
                className="h-3.5 w-3.5"
              />
              Email me when an anomaly is detected
            </label>

            <div className="flex gap-2">
              <Button type="submit" size="sm" disabled={!canSubmit || createMonitor.isPending}>
                {createMonitor.isPending ? 'Creating…' : 'Create monitor'}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => {
                  resetForm()
                  setCreating(false)
                }}
              >
                Cancel
              </Button>
            </div>
          </form>
        )}

        {!isLoading && monitors?.length === 0 && !creating && (
          <EmptyState
            icon={Radar}
            title="No monitors yet"
            description="Create a monitor to watch a metric and get alerted when it moves unexpectedly."
            action={
              <Button size="sm" variant="secondary" onClick={() => setCreating(true)}>
                <Plus className="h-4 w-4" strokeWidth={1.75} />
                New monitor
              </Button>
            }
          />
        )}

        {monitors && monitors.length > 0 && (
          <Card>
            <ul className="divide-y divide-[var(--color-border)]">
              {monitors.map((monitor) => (
                <li key={monitor.id} className="flex items-center justify-between gap-4 px-4 py-3">
                  <Link
                    to={`/workspace/monitors/${monitor.id}`}
                    className="flex min-w-0 flex-1 items-center gap-3"
                  >
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[var(--color-surface-raised)]">
                      <Radar className="h-4 w-4 text-[var(--color-fg-muted)]" strokeWidth={1.5} />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-[var(--color-fg)]">
                        {monitor.name}
                      </p>
                      <p className="text-xs text-[var(--color-fg-muted)]">
                        {monitor.dataset_filename} · {monitor.metric_column} ·{' '}
                        {monitor.last_checked_at
                          ? `Checked ${formatDate(monitor.last_checked_at)}`
                          : 'Never checked'}
                      </p>
                    </div>
                  </Link>
                  <span
                    className={`shrink-0 text-xs font-medium ${
                      monitor.last_status
                        ? STATUS_CLASS[monitor.last_status]
                        : 'text-[var(--color-fg-subtle)]'
                    }`}
                  >
                    {monitor.last_status ? STATUS_LABEL[monitor.last_status] : 'Not checked yet'}
                  </span>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={runMonitor.isPending}
                    onClick={() => runMonitor.mutate(monitor.id)}
                  >
                    Run now
                  </Button>
                  <button
                    type="button"
                    onClick={() => deleteMonitor.mutate(monitor.id)}
                    className="shrink-0 rounded p-1.5 text-[var(--color-fg-muted)] hover:bg-[var(--color-surface-raised)]"
                    aria-label="Delete monitor"
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
