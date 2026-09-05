import { PageHeader } from '@/components/layout/page-header'
import { AddToDashboardControl } from '@/components/dashboards/add-to-dashboard-control'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { useDataset, useRunDatasetQuery } from '@/features/datasets/api'
import { ApiError } from '@/lib/api-client'
import { formatBytes } from '@/lib/utils'
import type { AggregationOp, DatasetQueryRequest, FilterOp } from '@/types/dataset'
import { AlertTriangle, ArrowLeft } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

const AGGREGATION_OPS: AggregationOp[] = ['sum', 'avg', 'min', 'max', 'count']
const FILTER_OPS: FilterOp[] = ['eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'contains']

/** HTML inputs only give strings — send numeric-looking filter values as
 * numbers so they compare correctly against numeric columns. */
function coerceFilterValue(raw: string): string | number {
  const trimmed = raw.trim()
  if (trimmed !== '' && !Number.isNaN(Number(trimmed))) return Number(trimmed)
  return raw
}

export function DatasetExplorerPage() {
  const { datasetId } = useParams<{ datasetId: string }>()
  const { data: dataset, isLoading } = useDataset(datasetId ?? '')
  const runQuery = useRunDatasetQuery(datasetId ?? '')

  const [mode, setMode] = useState<'raw' | 'summary'>('raw')
  const [groupBy, setGroupBy] = useState('')
  const [aggOp, setAggOp] = useState<AggregationOp>('sum')
  const [aggColumn, setAggColumn] = useState('')
  const [filterColumn, setFilterColumn] = useState('')
  const [filterOp, setFilterOp] = useState<FilterOp>('eq')
  const [filterValue, setFilterValue] = useState('')
  const [sortBy, setSortBy] = useState('')
  const [sortDesc, setSortDesc] = useState(false)
  const [lastRequest, setLastRequest] = useState<DatasetQueryRequest | null>(null)

  const columnNames = useMemo(
    () => dataset?.columns_profile?.map((c) => c.name) ?? [],
    [dataset],
  )

  const canRun = mode === 'raw' || aggOp === 'count' || Boolean(aggColumn)

  const handleRun = () => {
    const request: DatasetQueryRequest = {
      group_by: mode === 'summary' && groupBy ? [groupBy] : [],
      aggregations:
        mode === 'summary'
          ? aggOp === 'count'
            ? [{ op: 'count', alias: 'count' }]
            : aggColumn
              ? [{ op: aggOp, column: aggColumn, alias: `${aggColumn}_${aggOp}` }]
              : []
          : [],
      filters:
        filterColumn && filterValue !== ''
          ? [{ column: filterColumn, op: filterOp, value: coerceFilterValue(filterValue) }]
          : [],
      sort_by: sortBy || undefined,
      sort_desc: sortDesc,
    }
    setLastRequest(request)
    runQuery.mutate(request)
  }

  if (isLoading) {
    return (
      <div className="flex flex-col">
        <PageHeader title="Loading…" />
      </div>
    )
  }

  if (!dataset) {
    return (
      <div className="flex flex-col">
        <PageHeader title="Dataset not found" />
        <div className="px-6 py-5">
          <EmptyState
            icon={AlertTriangle}
            title="Dataset not found"
            description="It may have been removed, or belongs to a different account."
          />
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col">
      <PageHeader
        title={dataset.original_filename}
        description={
          dataset.status === 'profiled'
            ? `${dataset.row_count?.toLocaleString()} rows · ${dataset.column_count} columns · ${formatBytes(dataset.size_bytes)}`
            : `${formatBytes(dataset.size_bytes)} · ${dataset.status}`
        }
        actions={
          <Button size="sm" variant="secondary" asChild>
            <Link to="/workspace/datasets">
              <ArrowLeft className="h-4 w-4" strokeWidth={1.75} />
              Back to datasets
            </Link>
          </Button>
        }
      />

      <div className="flex flex-col gap-4 px-6 py-5">
        {dataset.status === 'profiling_failed' && (
          <EmptyState
            icon={AlertTriangle}
            title="This file couldn't be analyzed"
            description="Legacy .xls files aren't supported yet — re-upload as .csv or .xlsx to explore this data."
          />
        )}

        {dataset.status === 'uploaded' && (
          <EmptyState
            icon={AlertTriangle}
            title="Still processing"
            description="This dataset hasn't finished profiling yet. Refresh in a moment."
          />
        )}

        {dataset.status === 'profiled' && (
          <>
            <Card>
              <CardHeader>
                <CardTitle>Columns</CardTitle>
              </CardHeader>
              <CardContent className="overflow-x-auto p-0">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-[var(--color-border)] text-xs text-[var(--color-fg-muted)]">
                      <th className="px-4 py-2 font-medium">Column</th>
                      <th className="px-4 py-2 font-medium">Type</th>
                      <th className="px-4 py-2 font-medium">Nulls</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dataset.columns_profile?.map((column) => (
                      <tr key={column.name} className="border-b border-[var(--color-border)] last:border-0">
                        <td className="px-4 py-2 font-medium text-[var(--color-fg)]">{column.name}</td>
                        <td className="px-4 py-2 text-[var(--color-fg-muted)]">{column.dtype}</td>
                        <td className="px-4 py-2 text-[var(--color-fg-muted)]">
                          {column.null_count} / {dataset.row_count}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Explore</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant={mode === 'raw' ? 'default' : 'secondary'}
                    onClick={() => setMode('raw')}
                  >
                    Raw rows
                  </Button>
                  <Button
                    size="sm"
                    variant={mode === 'summary' ? 'default' : 'secondary'}
                    onClick={() => setMode('summary')}
                  >
                    Summary
                  </Button>
                </div>

                {mode === 'summary' && (
                  <div className="grid grid-cols-3 gap-3">
                    <div className="space-y-1.5">
                      <Label>Group by</Label>
                      <Select value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
                        <option value="">(none)</option>
                        {columnNames.map((name) => (
                          <option key={name} value={name}>
                            {name}
                          </option>
                        ))}
                      </Select>
                    </div>
                    <div className="space-y-1.5">
                      <Label>Aggregate</Label>
                      <Select
                        value={aggOp}
                        onChange={(e) => setAggOp(e.target.value as AggregationOp)}
                      >
                        {AGGREGATION_OPS.map((op) => (
                          <option key={op} value={op}>
                            {op}
                          </option>
                        ))}
                      </Select>
                    </div>
                    <div className="space-y-1.5">
                      <Label>Of column</Label>
                      <Select
                        value={aggColumn}
                        onChange={(e) => setAggColumn(e.target.value)}
                        disabled={aggOp === 'count'}
                      >
                        <option value="">(select column)</option>
                        {columnNames.map((name) => (
                          <option key={name} value={name}>
                            {name}
                          </option>
                        ))}
                      </Select>
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-4 gap-3">
                  <div className="space-y-1.5">
                    <Label>Filter column</Label>
                    <Select value={filterColumn} onChange={(e) => setFilterColumn(e.target.value)}>
                      <option value="">(none)</option>
                      {columnNames.map((name) => (
                        <option key={name} value={name}>
                          {name}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label>Is</Label>
                    <Select value={filterOp} onChange={(e) => setFilterOp(e.target.value as FilterOp)}>
                      {FILTER_OPS.map((op) => (
                        <option key={op} value={op}>
                          {op}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label>Value</Label>
                    <Input value={filterValue} onChange={(e) => setFilterValue(e.target.value)} />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Sort by</Label>
                    <Select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                      <option value="">(none)</option>
                      {columnNames.map((name) => (
                        <option key={name} value={name}>
                          {name}
                        </option>
                      ))}
                    </Select>
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-2 text-xs text-[var(--color-fg-muted)]">
                    <input
                      type="checkbox"
                      checked={sortDesc}
                      onChange={(e) => setSortDesc(e.target.checked)}
                    />
                    Descending
                  </label>
                  <Button size="sm" onClick={handleRun} disabled={!canRun || runQuery.isPending}>
                    {runQuery.isPending ? 'Running…' : 'Run'}
                  </Button>
                </div>

                {runQuery.isError && (
                  <p className="text-xs text-[var(--color-negative)]">
                    {runQuery.error instanceof ApiError ? runQuery.error.message : 'Query failed.'}
                  </p>
                )}
              </CardContent>
            </Card>

            {runQuery.data && (
              <Card>
                <CardHeader>
                  <CardTitle>
                    Results — {runQuery.data.row_count} row{runQuery.data.row_count === 1 ? '' : 's'}
                    {runQuery.data.truncated ? ' (truncated)' : ''}
                  </CardTitle>
                </CardHeader>
                <CardContent className="overflow-x-auto p-0">
                  {runQuery.data.rows.length === 0 ? (
                    <EmptyState
                      icon={AlertTriangle}
                      title="No rows matched"
                      description="Try adjusting your filter."
                      className="border-none"
                    />
                  ) : (
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className="border-b border-[var(--color-border)] text-xs text-[var(--color-fg-muted)]">
                          {runQuery.data.columns.map((col) => (
                            <th key={col} className="px-4 py-2 font-medium">
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {runQuery.data.rows.map((row, i) => (
                          // Query results have no stable row id, so index is the key.
                          <tr key={i} className="border-b border-[var(--color-border)] last:border-0">
                            {row.map((value, j) => (
                              <td key={j} className="px-4 py-2 text-[var(--color-fg)]">
                                {String(value ?? '—')}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </CardContent>
              </Card>
            )}

            {runQuery.data &&
              runQuery.data.rows.length > 0 &&
              runQuery.data.columns.length >= 2 &&
              lastRequest &&
              datasetId && (
                <AddToDashboardControl
                  datasetId={datasetId}
                  query={lastRequest}
                  defaultTitle={`${dataset.original_filename} — ${mode === 'summary' ? 'Summary' : 'Preview'}`}
                />
              )}
          </>
        )}
      </div>
    </div>
  )
}
