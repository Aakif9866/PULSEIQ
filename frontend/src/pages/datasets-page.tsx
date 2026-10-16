import { PageHeader } from '@/components/layout/page-header'
import { Button } from '@/components/ui/button'
import { IconChip } from '@/components/ui/icon-chip'
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
import { type ChangeEvent, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

const ACCEPTED_EXTENSIONS = '.csv,.xlsx,.xls'

export function DatasetsPage() {
  const { data: datasets, isLoading, isError } = useDatasets()
  const { data: storageMode } = useStorageMode()
  const upload = useUploadDataset()
  const fileInputRef = useRef<HTMLInputElement>(null)
  // Remembers the dataset count it was raised at, so a delete or a new
  // upload makes a stale message disappear without an effect.
  const [limitError, setLimitErrorState] = useState<{ text: string; count: number } | null>(null)
  const datasetCount = datasets?.length ?? 0
  const setLimitError = (text: string | null) =>
    setLimitErrorState(text === null ? null : { text, count: datasetCount })
  const visibleLimitError = limitError?.count === datasetCount ? limitError.text : null
  const maxMb = storageMode?.max_upload_size_mb
  const maxDatasets = storageMode?.max_datasets_per_user
  const atLimit = maxDatasets !== undefined && datasetCount >= maxDatasets

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = '' // allow re-selecting the same file after an error
    if (!file) return
    // Early, friendly check; the server enforces the same limit.
    if (maxMb !== undefined && file.size > maxMb * 1024 * 1024) {
      setLimitError(`Upload limit: each file can be at most ${maxMb} MB.`)
      return
    }
    setLimitError(null)
    upload.mutate(file)
  }

  // Same wording as the server's own 409/413, which still enforces both.
  const triggerFilePicker = () => {
    upload.reset()
    if (atLimit) {
      setLimitError(
        `Upload limit: you can keep up to ${maxDatasets} datasets. Delete one to upload another.`,
      )
      return
    }
    setLimitError(null)
    fileInputRef.current?.click()
  }

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

      <div className="px-4 py-5 sm:px-6">
        {visibleLimitError && (
          <p role="alert" className="mb-3 text-xs text-[var(--color-negative)]">
            {visibleLimitError}
          </p>
        )}

        {storageMode?.storage_provider === 'local' && (
          <p className="mb-3 text-xs text-[var(--color-fg-subtle)]">
            Datasets are stored on the server's local disk in this environment — they may not
            persist across a restart or redeploy. Cloudflare R2 can be enabled for persistent
            storage (see docs/STORAGE.md).
          </p>
        )}

        {upload.isError && (
          <p role="alert" className="mb-3 text-xs text-[var(--color-negative)]">
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
          <IconChip icon={FileSpreadsheet} color="var(--color-teal)" className="h-8 w-8" />
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
