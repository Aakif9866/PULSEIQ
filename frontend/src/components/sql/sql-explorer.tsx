import { ResultTable } from '@/components/dashboards/result-table'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ErrorReference } from '@/components/ui/error-reference'
import { Input } from '@/components/ui/input'
import {
  useAskSql,
  useDeleteSavedQuery,
  useQueryHistory,
  useRunSql,
  useSaveQuery,
  useSavedQueries,
  useSuggestedQueries,
} from '@/features/history/api'
import { ApiError } from '@/lib/api-client'
import type { DatasetQueryResult } from '@/types/dataset'
import { Trash2 } from 'lucide-react'
import { useState } from 'react'

function errorText(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback
}

/** SQL Explorer (docs/V2_IMPLEMENTATION_PLAN.md Phase 2): hand-written SQL
 * and NL-to-SQL both go through the backend's one validator — the table is
 * always called `dataset`, read-only, row-capped. Generated SQL lands in the
 * editor so it's visible and editable, never hidden. */
export function SqlExplorer({ datasetId }: { datasetId: string }) {
  const [sql, setSql] = useState('SELECT * FROM dataset LIMIT 20')
  const [question, setQuestion] = useState('')
  const [saveName, setSaveName] = useState('')
  const [answer, setAnswer] = useState<string | null>(null)
  const [result, setResult] = useState<DatasetQueryResult | null>(null)

  const suggested = useSuggestedQueries(datasetId)
  const history = useQueryHistory(datasetId)
  const saved = useSavedQueries(datasetId)
  const runSql = useRunSql(datasetId)
  const askSql = useAskSql(datasetId)
  const saveQuery = useSaveQuery(datasetId)
  const deleteSaved = useDeleteSavedQuery(datasetId)

  const handleRun = () => {
    setAnswer(null)
    runSql.mutate(sql, {
      onSuccess: (data) => {
        setSql(data.sql)
        setResult(data.result)
      },
    })
  }

  const handleAsk = () => {
    askSql.mutate(question, {
      onSuccess: (data) => {
        setSql(data.generated_sql)
        setAnswer(data.answer)
        setResult(data.result)
      },
    })
  }

  const handleSave = () => {
    saveQuery.mutate({ name: saveName, sql_text: sql }, { onSuccess: () => setSaveName('') })
  }

  const error = runSql.error ?? askSql.error
  const sqlHistory = (history.data ?? []).filter((h) => h.sql_text).slice(0, 8)

  return (
    <Card>
      <CardHeader>
        <CardTitle>SQL Explorer</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Input
            aria-label="Ask in plain English"
            placeholder="Ask in plain English, e.g. total revenue by region"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && question.trim() && handleAsk()}
          />
          <Button
            size="sm"
            className="h-9"
            onClick={handleAsk}
            disabled={!question.trim() || askSql.isPending}
          >
            {askSql.isPending ? 'Generating…' : 'Generate SQL'}
          </Button>
        </div>

        {suggested.data && suggested.data.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {suggested.data.map((s) => (
              <Button key={s.label} size="sm" variant="secondary" onClick={() => setSql(s.sql)}>
                {s.label}
              </Button>
            ))}
          </div>
        )}

        <textarea
          aria-label="SQL query"
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          spellCheck={false}
          rows={5}
          className="w-full rounded-md border border-[var(--color-border-strong)] bg-[var(--color-surface)] p-3 font-mono text-xs text-[var(--color-fg)] outline-none focus-visible:border-[var(--color-accent)]"
        />
        <p className="text-[11px] text-[var(--color-fg-muted)]">
          Read-only. Query the table <code>dataset</code>; results are capped.
        </p>

        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex gap-2">
            <Input
              aria-label="Saved query name"
              placeholder="Name to save as"
              value={saveName}
              onChange={(e) => setSaveName(e.target.value)}
              className="h-8 w-48"
            />
            <Button
              size="sm"
              variant="secondary"
              onClick={handleSave}
              disabled={!saveName.trim() || !sql.trim() || saveQuery.isPending}
            >
              Save
            </Button>
          </div>
          <Button size="sm" onClick={handleRun} disabled={!sql.trim() || runSql.isPending}>
            {runSql.isPending ? 'Running…' : 'Run SQL'}
          </Button>
        </div>

        {error && (
          <p role="alert" className="text-xs text-[var(--color-negative)]">
            {errorText(error, 'Query failed.')}
            <ErrorReference error={error} />
          </p>
        )}
        {saveQuery.isError && (
          <p className="text-xs text-[var(--color-negative)]">
            {errorText(saveQuery.error, 'Could not save the query.')}
          </p>
        )}

        {answer && <p className="text-sm text-[var(--color-fg)]">{answer}</p>}

        {result && (
          <div className="space-y-1.5">
            <p className="text-xs text-[var(--color-fg-muted)]">
              {result.row_count} row{result.row_count === 1 ? '' : 's'}
              {result.truncated ? ' (truncated)' : ''}
            </p>
            <ResultTable result={result} />
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-1.5">
            <h3 className="text-xs font-medium text-[var(--color-fg-muted)]">Saved queries</h3>
            {saved.data?.length ? (
              <ul className="space-y-1">
                {saved.data.map((q) => (
                  <li key={q.id} className="flex items-center justify-between gap-2">
                    <button
                      type="button"
                      className="truncate text-left text-xs text-[var(--color-fg)] hover:underline"
                      onClick={() => setSql(q.sql_text)}
                      title={q.sql_text}
                    >
                      {q.name}
                    </button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-6 w-6"
                      aria-label={`Delete saved query ${q.name}`}
                      onClick={() => deleteSaved.mutate(q.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
                    </Button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-[var(--color-fg-subtle)]">None yet.</p>
            )}
          </div>
          <div className="space-y-1.5">
            <h3 className="text-xs font-medium text-[var(--color-fg-muted)]">Recent</h3>
            {sqlHistory.length ? (
              <ul className="space-y-1">
                {sqlHistory.map((h) => (
                  <li key={h.id}>
                    <button
                      type="button"
                      className="block w-full truncate text-left font-mono text-[11px] text-[var(--color-fg)] hover:underline"
                      onClick={() => setSql(h.sql_text ?? '')}
                      title={h.question ?? h.sql_text ?? ''}
                    >
                      {h.sql_text}
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-[var(--color-fg-subtle)]">No queries run yet.</p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
