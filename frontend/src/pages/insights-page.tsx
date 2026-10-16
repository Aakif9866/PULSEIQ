import { PageHeader } from '@/components/layout/page-header'
import { FindingRow } from '@/components/ai/analyze-analyst-view'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { Input } from '@/components/ui/input'
import {
  downloadInsightReport,
  useDeleteInsight,
  useInsights,
  useRenameInsight,
} from '@/features/insights/api'
import { cn, formatDate } from '@/lib/utils'
import type { Insight } from '@/types/insight'
import { Check, Database, FileDown, Pencil, RotateCw, Star, Trash2, Wrench, X } from 'lucide-react'
import { type FormEvent, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

export function InsightsPage() {
  const { data: insights, isLoading } = useInsights()
  const deleteInsight = useDeleteInsight()
  // ?focus=<id> (from "View saved insight" links) scrolls to and highlights one.
  const [params] = useSearchParams()
  const focusId = params.get('focus')

  return (
    <div className="flex flex-col">
      <PageHeader
        title="Saved Insights"
        description="Answers you've kept from the AI Analyst, with the evidence behind them."
      />

      <div className="px-4 py-5 sm:px-6">
        {isLoading && (
          <div className="space-y-3" aria-busy="true">
            {[0, 1].map((i) => (
              <div key={i} className="h-28 animate-pulse rounded-lg bg-[var(--color-surface-raised)]" />
            ))}
          </div>
        )}

        {!isLoading && insights?.length === 0 && (
          <EmptyState
            icon={Star}
            title="No saved insights"
            description="Ask a question in the AI Analyst, then press “Save insight” on an answer to keep it here."
            action={
              <Button size="sm" variant="secondary" asChild>
                <Link to="/workspace/ai-analyst">Go to AI Analyst</Link>
              </Button>
            }
          />
        )}

        {insights && insights.length > 0 && (
          <div className="flex flex-col gap-3">
            {insights.map((insight) => (
              <InsightCard
                key={insight.id}
                insight={insight}
                focused={insight.id === focusId}
                onDelete={() => {
                  if (window.confirm(`Delete “${insight.title}”? This can't be undone.`)) {
                    deleteInsight.mutate(insight.id)
                  }
                }}
                deleting={deleteInsight.isPending && deleteInsight.variables === insight.id}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function InsightCard({
  insight,
  focused,
  onDelete,
  deleting,
}: {
  insight: Insight
  focused: boolean
  onDelete: () => void
  deleting: boolean
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [reportError, setReportError] = useState(false)

  useEffect(() => {
    if (focused) ref.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [focused])

  const rerun = `/workspace/ai-analyst?dataset=${insight.dataset_id}&q=${encodeURIComponent(insight.question)}`

  return (
    <div ref={ref}>
      <Card className={cn(focused && 'ring-4 ring-[var(--color-focus)]')}>
        <CardContent className="space-y-3 py-4">
          <div className="space-y-1">
            <EditableTitle insight={insight} />
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-[var(--color-fg-muted)]">
              <Link
                to={`/workspace/datasets/${insight.dataset_id}`}
                className="inline-flex items-center gap-1 hover:text-[var(--color-accent)]"
              >
                <Database className="h-3 w-3" strokeWidth={2} />
                {insight.dataset_filename}
              </Link>
              <span aria-hidden="true">·</span>
              <span>Saved {formatDate(insight.created_at)}</span>
              {insight.dataset_version !== null &&
              insight.dataset_version < insight.current_dataset_version ? (
                <span
                  className="rounded-full bg-[var(--color-warning)]/15 px-2 py-0.5 font-medium text-[var(--color-warning)]"
                  title="The dataset has a newer version. Re-run to compute this on the current data."
                >
                  From version {insight.dataset_version} · dataset now at version{' '}
                  {insight.current_dataset_version}
                </span>
              ) : (
                <span
                  className="rounded-full bg-[var(--color-surface-raised)] px-2 py-0.5"
                  title="A saved result. Re-run it for a fresh computation."
                >
                  Snapshot
                </span>
              )}
            </p>
            {insight.title !== insight.question && (
              <p className="text-xs text-[var(--color-fg-subtle)]">Asked: {insight.question}</p>
            )}
          </div>

          <p className="text-sm text-[var(--color-fg)]">{insight.answer}</p>

          {insight.findings.length > 0 && (
            <ul className="-mx-4 border-y border-[var(--color-border)]">
              {insight.findings.map((finding, i) => (
                <FindingRow key={i} finding={finding} />
              ))}
            </ul>
          )}

          {insight.tool_calls.length > 0 && (
            <details className="group text-sm">
              <summary className="cursor-pointer select-none text-xs font-medium text-[var(--color-fg-muted)] hover:text-[var(--color-fg)]">
                How this was calculated ({insight.tool_calls.length}{' '}
                {insight.tool_calls.length === 1 ? 'computation' : 'computations'})
              </summary>
              <ul className="mt-2 space-y-1.5">
                {insight.tool_calls.map((call, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-[var(--color-fg-muted)]">
                    <Wrench className="mt-0.5 h-3 w-3 shrink-0" strokeWidth={2} />
                    <code className="break-all font-mono">
                      {call.tool}(
                      {Object.entries(call.arguments)
                        .filter(([, v]) => v !== null && v !== undefined)
                        .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
                        .join(', ')}
                      )
                    </code>
                  </li>
                ))}
              </ul>
            </details>
          )}

          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Button size="sm" variant="secondary" asChild>
              <Link to={rerun}>
                <RotateCw className="h-4 w-4" strokeWidth={1.75} />
                Re-run
              </Link>
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => downloadInsightReport(insight).catch(() => setReportError(true))}
            >
              <FileDown className="h-4 w-4" strokeWidth={1.75} />
              Download report
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={onDelete}
              disabled={deleting}
              className="ml-auto"
              aria-label={`Delete ${insight.title}`}
            >
              <Trash2 className="h-4 w-4" strokeWidth={1.75} />
              Delete
            </Button>
          </div>
          {reportError && (
            <p className="text-xs text-[var(--color-negative)]">
              The report couldn&apos;t be generated. Please try again.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function EditableTitle({ insight }: { insight: Insight }) {
  const rename = useRenameInsight()
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(insight.title)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const title = value.trim()
    if (!title || title === insight.title) return setEditing(false)
    rename.mutate({ id: insight.id, title }, { onSuccess: () => setEditing(false) })
  }

  if (!editing) {
    return (
      <div className="flex items-start gap-1">
        <h2 className="text-base font-semibold text-[var(--color-fg)]">{insight.title}</h2>
        <Button
          size="icon"
          variant="ghost"
          className="h-7 w-7 shrink-0"
          onClick={() => {
            setValue(insight.title)
            setEditing(true)
          }}
          aria-label="Rename insight"
        >
          <Pencil className="h-3.5 w-3.5" strokeWidth={1.75} />
        </Button>
      </div>
    )
  }
  return (
    <form onSubmit={submit} className="flex items-center gap-1">
      <Input
        autoFocus
        aria-label="Insight title"
        value={value}
        maxLength={255}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === 'Escape' && setEditing(false)}
        className="h-8"
      />
      <Button size="icon" variant="ghost" type="submit" aria-label="Save title" disabled={rename.isPending}>
        <Check className="h-4 w-4" strokeWidth={2} />
      </Button>
      <Button size="icon" variant="ghost" type="button" onClick={() => setEditing(false)} aria-label="Cancel">
        <X className="h-4 w-4" strokeWidth={2} />
      </Button>
    </form>
  )
}
