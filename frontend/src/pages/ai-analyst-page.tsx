import { PageHeader } from '@/components/layout/page-header'
import { AddToDashboardControl } from '@/components/dashboards/add-to-dashboard-control'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { useAskDataset } from '@/features/ai/api'
import { useDatasets } from '@/features/datasets/api'
import { useSaveInsight } from '@/features/insights/api'
import { ApiError } from '@/lib/api-client'
import type { AskResponse } from '@/types/insight'
import { Database, Sparkles } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'

export function AiAnalystPage() {
  const { data: datasets } = useDatasets()
  const readyDatasets = datasets?.filter((d) => d.status === 'profiled') ?? []

  const [datasetId, setDatasetId] = useState('')
  const [question, setQuestion] = useState('')
  const [lastAsk, setLastAsk] = useState<AskResponse | null>(null)

  const ask = useAskDataset(datasetId)
  const save = useSaveInsight()

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!datasetId || !question.trim()) return
    setLastAsk(null)
    ask.mutate(question, { onSuccess: setLastAsk })
  }

  const handleSave = () => {
    if (!lastAsk) return
    save.mutate({ datasetId, ask: lastAsk })
  }

  return (
    <div className="flex flex-col">
      <PageHeader
        title="AI Analysis"
        description="Ask questions about your data in plain language."
      />

      <div className="flex flex-col gap-4 px-6 py-5">
        {readyDatasets.length === 0 ? (
          <EmptyState
            icon={Database}
            title="No datasets ready yet"
            description="Upload a CSV or Excel file and wait for it to finish profiling before asking questions about it."
            action={
              <Button size="sm" variant="secondary" asChild>
                <Link to="/workspace/datasets">Go to datasets</Link>
              </Button>
            }
          />
        ) : (
          <Card>
            <CardContent>
              <form className="flex flex-col gap-3" onSubmit={handleSubmit}>
                <div className="space-y-1.5">
                  <Label>Dataset</Label>
                  <Select value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
                    <option value="">Select a dataset…</option>
                    {readyDatasets.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.original_filename}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label>Question</Label>
                  <Input
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder="e.g. What's the total amount per region?"
                  />
                </div>
                <Button
                  type="submit"
                  className="self-start"
                  disabled={!datasetId || !question.trim() || ask.isPending}
                >
                  <Sparkles className="h-4 w-4" strokeWidth={1.75} />
                  {ask.isPending ? 'Thinking…' : 'Ask'}
                </Button>

                {ask.isError && (
                  <p className="text-xs text-[var(--color-negative)]">
                    {ask.error instanceof ApiError ? ask.error.message : 'Something went wrong.'}
                  </p>
                )}
              </form>
            </CardContent>
          </Card>
        )}

        {lastAsk && (
          <Card>
            <CardHeader>
              <CardTitle>Answer</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-[var(--color-fg)]">{lastAsk.answer}</p>

              <div className="overflow-x-auto rounded-md border border-[var(--color-border)]">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-[var(--color-border)] text-xs text-[var(--color-fg-muted)]">
                      {lastAsk.result.columns.map((col) => (
                        <th key={col} className="px-4 py-2 font-medium">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {lastAsk.result.rows.map((row, i) => (
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
              </div>

              <div className="flex items-center gap-3">
                <Button size="sm" variant="secondary" onClick={handleSave} disabled={save.isPending}>
                  {save.isPending ? 'Saving…' : save.isSuccess ? 'Saved' : 'Save insight'}
                </Button>
                {save.isError && (
                  <p className="text-xs text-[var(--color-negative)]">Couldn't save this insight.</p>
                )}
              </div>

              {lastAsk.result.rows.length > 0 && lastAsk.result.columns.length >= 2 && (
                <AddToDashboardControl
                  datasetId={datasetId}
                  query={lastAsk.query}
                  defaultTitle={lastAsk.question}
                />
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
