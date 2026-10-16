import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useDatasetVersions, useUploadVersion } from '@/features/datasets/api'
import { ApiError } from '@/lib/api-client'
import { formatBytes, formatDate } from '@/lib/utils'
import type { SchemaChanges, VersionUploadResult } from '@/types/dataset'
import { CheckCircle2, History, Upload } from 'lucide-react'
import { useRef } from 'react'
import { Link } from 'react-router-dom'

function describeChanges(c: SchemaChanges): string[] {
  const out: string[] = []
  if (c.added.length) out.push(`added ${c.added.join(', ')}`)
  if (c.removed.length) out.push(`removed ${c.removed.join(', ')}`)
  for (const t of c.type_changed) out.push(`${t.column}: ${t.from} → ${t.to}`)
  if (c.row_count_change) out.push(`${c.row_count_change > 0 ? '+' : ''}${c.row_count_change.toLocaleString()} rows`)
  return out.length ? out : ['same columns']
}

/** "Upload new version" for the dataset page header. */
export function UploadVersionButton({ datasetId }: { datasetId: string }) {
  const upload = useUploadVersion(datasetId)
  const input = useRef<HTMLInputElement>(null)
  return (
    <>
      <input
        ref={input}
        type="file"
        accept=".csv,.xlsx,.xls"
        className="hidden"
        aria-label="New version file"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) upload.mutate(file)
          e.target.value = ''
        }}
      />
      <Button size="sm" variant="secondary" onClick={() => input.current?.click()} disabled={upload.isPending}>
        <Upload className="h-4 w-4" strokeWidth={1.75} />
        {upload.isPending ? 'Uploading…' : 'Upload new version'}
      </Button>
      {upload.data && <VersionUploaded result={upload.data} />}
      {upload.isError && (
        <p role="alert" className="basis-full text-xs text-[var(--color-negative)]">
          {upload.error instanceof ApiError ? upload.error.message : "The new version couldn't be uploaded."}
        </p>
      )}
    </>
  )
}

function VersionUploaded({ result }: { result: VersionUploadResult }) {
  const changes = result.version.schema_changes
  return (
    <p role="status" className="flex basis-full items-start gap-1.5 text-xs text-[var(--color-fg-muted)]">
      <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--color-positive)]" strokeWidth={2} />
      <span>
        Version {result.version.version} is live
        {changes && ` (${describeChanges(changes).join('; ')})`}. Saved insights from earlier versions
        are now marked as such.
        {result.checks_run > 0 && (
          <>
            {' '}
            Re-ran {result.checks_run} anomaly {result.checks_run === 1 ? 'check' : 'checks'}:{' '}
            <Link to="/workspace/monitors" className="font-medium text-[var(--color-accent)] hover:underline">
              {result.new_anomalies} new {result.new_anomalies === 1 ? 'anomaly' : 'anomalies'}
            </Link>
            .
          </>
        )}
      </span>
    </p>
  )
}

/** The dataset's version history, newest first. */
export function DatasetVersions({ datasetId }: { datasetId: string }) {
  const { data: versions } = useDatasetVersions(datasetId)
  if (!versions || versions.length < 2) return null
  return (
    <Card>
      <CardHeader className="flex-row items-center gap-2">
        <History className="h-4 w-4 text-[var(--color-fg-muted)]" strokeWidth={1.75} />
        <CardTitle>Versions</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <ol>
          {versions.map((v, i) => (
            <li
              key={v.version}
              className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5 border-b border-[var(--color-border)] px-4 py-2.5 text-sm last:border-0"
            >
              <span className="font-medium">
                v{v.version}
                {i === 0 && (
                  <span className="ml-2 rounded-full bg-[var(--color-accent-muted)] px-2 py-0.5 text-xs font-normal text-[var(--color-accent)]">
                    current
                  </span>
                )}
                <span className="ml-2 font-normal text-[var(--color-fg-muted)]">{v.original_filename}</span>
              </span>
              <span className="text-xs text-[var(--color-fg-muted)] tabular-nums">
                {v.row_count?.toLocaleString() ?? '—'} rows · {formatBytes(v.size_bytes)} ·{' '}
                {formatDate(v.created_at)}
                {!v.file_kept && ' · file no longer stored'}
              </span>
              {v.schema_changes && (
                <span className="basis-full text-xs text-[var(--color-fg-subtle)]">
                  vs v{v.schema_changes.previous_version}: {describeChanges(v.schema_changes).join('; ')}
                </span>
              )}
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  )
}
