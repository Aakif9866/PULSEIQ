import { PageHeader } from '@/components/layout/page-header'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import {
  useDatasets,
  useDeleteDataset,
  useStorageMode,
  useUploadDataset,
} from '@/features/datasets/api'
import { ApiError } from '@/lib/api-client'
import { formatBytes, formatDate } from '@/lib/utils'
import type { Dataset } from '@/types/dataset'
import { Database, FileSpreadsheet, Trash2, Upload } from 'lucide-react'
import { type ChangeEvent, useRef } from 'react'
import { Link } from 'react-router-dom'

const ACCEPTED_EXTENSIONS = '.csv,.xlsx,.xls'

export function DatasetsPage() {
  const { data: datasets, isLoading, isError } = useDatasets()
  const { data: storageMode } = useStorageMode()
  const upload = useUploadDataset()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = '' // allow re-selecting the same file after an error
    if (file) upload.mutate(file)
  }

  const triggerFilePicker = () => fileInputRef.current?.click()

  return (
    <div className="flex flex-col">
      <PageHeader
        title="Datasets"
        description="Upload and manage the datasets in your workspace."
        actions={
          <>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_EXTENSIONS}
              className="hidden"
              onChange={handleFileChange}
            />
            <Button size="sm" onClick={triggerFilePicker} disabled={upload.isPending}>
              <Upload className="h-4 w-4" strokeWidth={1.75} />
              {upload.isPending ? 'Uploading…' : 'Upload dataset'}
            </Button>
          </>
        }
      />

      <div className="px-6 py-5">
        {storageMode?.storage_provider === 'local' && (
          <p className="mb-3 text-xs text-[var(--color-fg-subtle)]">
            Datasets are stored on the server's local disk in this environment — they may not
            persist across a restart or redeploy. Cloudflare R2 can be enabled for persistent
            storage (see docs/STORAGE.md).
          </p>
        )}

        {upload.isError && (
          <p className="mb-3 text-xs text-[var(--color-negative)]">
            {upload.error instanceof ApiError ? upload.error.message : 'Upload failed. Please try again.'}
          </p>
        )}

        {isLoading && <p className="text-xs text-[var(--color-fg-muted)]">Loading datasets…</p>}

        {isError && (
          <p className="text-xs text-[var(--color-negative)]">
            Couldn't load your datasets. Please refresh the page.
          </p>
        )}

        {!isLoading && !isError && datasets?.length === 0 && (
          <EmptyState
            icon={Database}
            title="No datasets uploaded"
            description="Upload a CSV or Excel file to start profiling, exploring, and asking questions about your data."
            action={
              <Button size="sm" variant="secondary" onClick={triggerFilePicker}>
                <Upload className="h-4 w-4" strokeWidth={1.75} />
                Upload your first dataset
              </Button>
            }
          />
        )}

        {datasets && datasets.length > 0 && (
          <Card>
            <ul className="divide-y divide-[var(--color-border)]">
              {datasets.map((dataset) => (
                <DatasetRow key={dataset.id} dataset={dataset} />
              ))}
            </ul>
          </Card>
        )}
      </div>
    </div>
  )
}

function DatasetRow({ dataset }: { dataset: Dataset }) {
  const deleteDataset = useDeleteDataset()

  return (
    <li className="flex items-center gap-2 px-4 py-3 hover:bg-[var(--color-surface-raised)]">
      <Link to={`/workspace/datasets/${dataset.id}`} className="flex min-w-0 flex-1 items-center gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[var(--color-surface-raised)]">
            <FileSpreadsheet className="h-4 w-4 text-[var(--color-fg-muted)]" strokeWidth={1.5} />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-[var(--color-fg)]">
              {dataset.original_filename}
            </p>
            <p className="text-xs text-[var(--color-fg-muted)]">
              {formatBytes(dataset.size_bytes)} · Uploaded {formatDate(dataset.created_at)}
            </p>
          </div>
        </div>
        <span className="ml-auto shrink-0 rounded-full bg-[var(--color-surface-raised)] px-2.5 py-1 text-[11px] font-medium text-[var(--color-fg-muted)] capitalize">
          {dataset.status}
        </span>
      </Link>
      <button
        type="button"
        onClick={() => deleteDataset.mutate(dataset.id)}
        disabled={deleteDataset.isPending}
        className="shrink-0 rounded p-1.5 text-[var(--color-fg-muted)] hover:bg-[var(--color-border)] disabled:opacity-50"
        aria-label={`Delete ${dataset.original_filename}`}
      >
        <Trash2 className="h-4 w-4" strokeWidth={1.75} />
      </button>
    </li>
  )
}
