import { PageHeader } from '@/components/layout/page-header'
import { Button } from '@/components/ui/button'
import { IconChip } from '@/components/ui/icon-chip'
import { Card } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { useDataset, useDatasets, useStorageMode } from '@/features/datasets/api'
import { useCreateMonitor, useDeleteMonitor, useMonitors, useRunMonitor } from '@/features/monitors/api'
import { ApiError } from '@/lib/api-client'
import { formatDate } from '@/lib/utils'
import type { AggregationOp } from '@/types/dataset'
import type { BaselineStrategy, MonitorStatus } from '@/types/monitor'
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
  const [notifyEmail, setNotifyEmail] = useState(false)
  const emailEnabled = useStorageMode().data?.email_alerts_enabled ?? false

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
        // Uploaded files never change and no scheduler runs in production,
        // so a check only ever runs when the user clicks Run.
        check_frequency: 'manual',
        notify_email: notifyEmail,
      },
      {
        onSuccess: () => {
          resetForm()
          setCreating(false)
        },
        onError: (err) => {
          setFormError(err instanceof ApiError ? err.message : 'Could not create the check.')
        },
      },
    )
  }

  return (
    <div className="flex flex-col">
      <PageHeader
        title="Anomaly checks"
        description="Find unusual periods in a metric across your dataset's history."
        actions={
          !creating && (
            <Button size="sm" onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" strokeWidth={1.75} />
              New check
            </Button>
          )
        }
      />

      <div className="flex flex-col gap-4 px-4 py-5 sm:px-6">
        {creating && (
          <form
            className="flex flex-col gap-4 rounded-md border border-[var(--color-border)] p-4"
            onSubmit={handleCreate}
          >
            {formError && <p className="text-xs text-[var(--color-negative)]">{formError}</p>}

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="monitor-dataset">Dataset</Label>
                <Select
                  id="monitor-dataset"
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
                <Label htmlFor="monitor-monitor-name">Check name</Label>
                <Input
                  id="monitor-monitor-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Daily revenue"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="space-y-1.5">
                <Label htmlFor="monitor-time-column">Time column</Label>
                <Select
                  id="monitor-time-column"
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
                <Label htmlFor="monitor-metric-column">Metric column</Label>
                <Select
                  id="monitor-metric-column"
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
                <Label htmlFor="monitor-aggregation">Aggregation</Label>
                <Select
                  id="monitor-aggregation"
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

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="space-y-1.5">
                <Label htmlFor="monitor-baseline">Baseline</Label>
                <Select
                  id="monitor-baseline"
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
                  <Label htmlFor="monitor-sensitivity-z-score">Sensitivity (z-score)</Label>
                  <Input
                    id="monitor-sensitivity-z-score"
                    type="number"
                    step="0.1"
                    min="0.1"
                    value={zscoreThreshold}
                    onChange={(e) => setZscoreThreshold(e.target.value)}
                  />
                </div>
              ) : (
                <div className="space-y-1.5">
                  <Label htmlFor="monitor-threshold">Threshold (%)</Label>
                  <Input
                    id="monitor-threshold"
                    type="number"
                    step="1"
                    min="1"
                    value={thresholdPercent}
                    onChange={(e) => setThresholdPercent(e.target.value)}
                  />
                </div>
              )}
            </div>

            <p className="text-xs text-[var(--color-fg-muted)]">
              A check compares the latest period with the ones before it, across the history in
              your file. It runs when you click <strong className="font-medium">Run</strong>, and
              again automatically whenever you upload a new version of the dataset. Periods already
              reported are never reported twice.
            </p>

            {emailEnabled && (
            <label className="flex items-center gap-2 text-xs text-[var(--color-fg-muted)]">
              <input
                type="checkbox"
                checked={notifyEmail}
                onChange={(e) => setNotifyEmail(e.target.checked)}
                className="h-3.5 w-3.5"
              />
              Email me when an anomaly is detected
            </label>
            )}

            <div className="flex gap-2">
              <Button type="submit" size="sm" disabled={!canSubmit || createMonitor.isPending}>
                {createMonitor.isPending ? 'Creating…' : 'Create check'}
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
            title="No anomaly checks yet"
            description="Pick a metric and a time column, and PulseIQ flags periods that break from the trend, then explains them."
            action={
              <Button size="sm" variant="secondary" onClick={() => setCreating(true)}>
                <Plus className="h-4 w-4" strokeWidth={1.75} />
                New check
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
                    <IconChip icon={Radar} color="var(--color-orange)" className="h-8 w-8" />
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
