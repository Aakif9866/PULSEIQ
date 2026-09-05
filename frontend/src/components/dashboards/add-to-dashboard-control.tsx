import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { useAddChart, useCreateDashboard, useDashboards } from '@/features/dashboards/api'
import type { ChartType } from '@/types/dashboard'
import type { DatasetQueryRequest } from '@/types/dataset'
import { LayoutDashboard } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

interface AddToDashboardControlProps {
  datasetId: string
  query: DatasetQueryRequest
  defaultTitle: string
}

const NEW_DASHBOARD = '__new__'

/** Saves the query that produced the caller's current result as a chart on
 * a dashboard — new or existing. Shared by the dataset explorer and the AI
 * analyst, so "add to dashboard" behaves identically from either place. */
export function AddToDashboardControl({ datasetId, query, defaultTitle }: AddToDashboardControlProps) {
  const { data: dashboards } = useDashboards()
  const createDashboard = useCreateDashboard()
  const addChart = useAddChart()

  const [open, setOpen] = useState(false)
  const [dashboardId, setDashboardId] = useState('')
  const [newDashboardName, setNewDashboardName] = useState('')
  const [title, setTitle] = useState(defaultTitle)
  const [chartType, setChartType] = useState<ChartType>('bar')

  const handleAdd = async () => {
    let targetDashboardId = dashboardId
    if (dashboardId === NEW_DASHBOARD) {
      if (!newDashboardName.trim()) return
      const created = await createDashboard.mutateAsync(newDashboardName.trim())
      targetDashboardId = created.id
    }
    if (!targetDashboardId) return

    addChart.mutate(
      { dashboardId: targetDashboardId, datasetId, title, chartType, query },
      { onSuccess: () => setOpen(false) },
    )
  }

  if (!open) {
    return (
      <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>
        <LayoutDashboard className="h-4 w-4" strokeWidth={1.75} />
        Add to dashboard
      </Button>
    )
  }

  return (
    <div className="flex flex-wrap items-end gap-2 rounded-md border border-[var(--color-border)] p-3">
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-[var(--color-fg-muted)]">Dashboard</label>
        <Select value={dashboardId} onChange={(e) => setDashboardId(e.target.value)}>
          <option value="">Select…</option>
          {dashboards?.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
          <option value={NEW_DASHBOARD}>+ New dashboard…</option>
        </Select>
      </div>
      {dashboardId === NEW_DASHBOARD && (
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-[var(--color-fg-muted)]">Dashboard name</label>
          <Input value={newDashboardName} onChange={(e) => setNewDashboardName(e.target.value)} />
        </div>
      )}
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-[var(--color-fg-muted)]">Chart title</label>
        <Input value={title} onChange={(e) => setTitle(e.target.value)} />
      </div>
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-[var(--color-fg-muted)]">Chart type</label>
        <Select value={chartType} onChange={(e) => setChartType(e.target.value as ChartType)}>
          <option value="bar">Bar</option>
          <option value="line">Line</option>
        </Select>
      </div>
      <Button
        size="sm"
        onClick={handleAdd}
        disabled={!dashboardId || addChart.isPending || createDashboard.isPending}
      >
        {addChart.isPending || createDashboard.isPending ? 'Adding…' : 'Add'}
      </Button>
      <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
        Cancel
      </Button>

      {addChart.isSuccess && (
        <p className="w-full text-xs text-[var(--color-positive)]">
          Added.{' '}
          <Link to="/workspace/dashboards" className="underline">
            View dashboards
          </Link>
        </p>
      )}
      {(addChart.isError || createDashboard.isError) && (
        <p className="w-full text-xs text-[var(--color-negative)]">Couldn't add this chart.</p>
      )}
    </div>
  )
}
