import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { ErrorReference } from '@/components/ui/error-reference'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { AddToDashboardControl } from '@/components/dashboards/add-to-dashboard-control'
import { useAnalyzeDataset } from '@/features/ai/api'
import { useSaveInsight } from '@/features/insights/api'
import { useDatasets } from '@/features/datasets/api'
import { ApiError } from '@/lib/api-client'
import type { AnalyzeResponse, ConversationTurn, Finding, ToolCallRecord } from '@/types/analysis'
import { chartOptionsFromToolCalls, toolCallFailed } from '@/types/analysis'
import { AlertTriangle, Bookmark, Check, CheckCircle2, Database, HelpCircle, Sparkles, Wrench } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'

const CONFIDENCE_LABEL: Record<Finding['confidence'], string> = {
  high: 'High confidence',
  medium: 'Medium confidence',
  low: 'Low confidence',
}

export function FindingRow({ finding }: { finding: Finding }) {
  return (
    <li className="flex items-start gap-3 border-b border-[var(--color-border)] px-4 py-3 last:border-0">
      {finding.verified ? (
        <CheckCircle2
          className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-positive)]"
          strokeWidth={1.75}
          aria-label="Verified against tool evidence"
        />
      ) : (
        <AlertTriangle
          className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-warning)]"
          strokeWidth={1.75}
          aria-label="Unverified — could not confirm against tool evidence"
        />
      )}
      <div className="flex-1 space-y-1">
        <p className="text-sm text-[var(--color-fg)]">
          {finding.claim}
          {finding.value !== null && (
            <span className="text-[var(--color-fg-muted)]">
              {' — '}
              {finding.value}
              {finding.unit ? ` ${finding.unit}` : ''}
            </span>
          )}
        </p>
        <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--color-fg-muted)]">
          <span>{CONFIDENCE_LABEL[finding.confidence]}</span>
          {finding.classification && (
            <span className="rounded-full bg-[var(--color-accent-muted)] px-2 py-0.5 text-[var(--color-accent)]">
              {finding.classification.replaceAll('_', ' ')}
            </span>
          )}
          {finding.affected_rows !== null && finding.total_rows !== null && (
            <span>
              {finding.affected_rows} / {finding.total_rows} rows
            </span>
          )}
          {!finding.verified && (
            <span className="text-[var(--color-warning)]">
              not verified against tool evidence
            </span>
          )}
        </div>
      </div>
    </li>
  )
}

function ToolCallChip({ call }: { call: ToolCallRecord }) {
  const error = toolCallFailed(call)
  return (
    <li
      className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ${
        error
          ? 'border-[var(--color-negative)] text-[var(--color-negative)]'
          : 'border-[var(--color-border)] text-[var(--color-fg-muted)]'
      }`}
      title={error ?? undefined}
    >
      <Wrench className="h-3 w-3" strokeWidth={1.75} />
      {call.tool}
      {error && <AlertTriangle className="h-3 w-3" strokeWidth={1.75} />}
    </li>
  )
}

function EvidencePanel({ response }: { response: AnalyzeResponse }) {
  const failedCalls = response.tool_calls.filter((c) => toolCallFailed(c))

  return (
    <div className="space-y-4">
      {response.status === 'degraded' && (
        <div className="flex items-start gap-2 rounded-md border border-[var(--color-warning)] bg-[var(--color-warning)]/10 px-3 py-2 text-sm text-[var(--color-fg)]">
          <AlertTriangle
            className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-warning)]"
            strokeWidth={1.75}
          />
          <p>
            This analysis couldn't be completed reliably — the AI provider didn't return a
            usable response after retrying. Try rephrasing the question or asking again.
          </p>
        </div>
      )}

      {response.needs_clarification && (
        <div className="flex items-start gap-2 rounded-md border border-[var(--color-border)] bg-[var(--color-accent-muted)]/40 px-3 py-2 text-sm text-[var(--color-fg)]">
          <HelpCircle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-accent)]" strokeWidth={1.75} />
          <p>{response.needs_clarification}</p>
        </div>
      )}

      {response.warnings.length > 0 && (
        <ul className="space-y-1">
          {response.warnings.map((warning, i) => (
            <li
              key={i}
              className="flex items-start gap-2 rounded-md border border-[var(--color-negative)] bg-[var(--color-negative)]/10 px-3 py-2 text-sm text-[var(--color-negative)]"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.75} />
              {warning}
            </li>
          ))}
        </ul>
      )}

      <p className="text-sm text-[var(--color-fg)]">{response.answer}</p>

      {response.tool_calls.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-[var(--color-fg-muted)]">
            Evidence — tools run to answer this
          </p>
          <ul className="flex flex-wrap gap-1.5">
            {response.tool_calls.map((call, i) => (
              <ToolCallChip key={i} call={call} />
            ))}
          </ul>
          {failedCalls.length > 0 && (
            <p className="text-xs text-[var(--color-negative)]">
              {failedCalls.length} of {response.tool_calls.length} tool call
              {response.tool_calls.length === 1 ? '' : 's'} failed — the answer above accounts for
              this, but may be based on less evidence than usual.
            </p>
          )}
        </div>
      )}

      {response.findings.length > 0 && (
        <div className="overflow-hidden rounded-md border border-[var(--color-border)]">
          <p className="border-b border-[var(--color-border)] px-4 py-2 text-xs font-medium text-[var(--color-fg-muted)]">
            Findings ({response.findings.filter((f) => f.verified).length}/
            {response.findings.length} verified)
          </p>
          <ul>
            {response.findings.map((finding, i) => (
              <FindingRow key={i} finding={finding} />
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

/** Save / add-to-dashboard for one answer. Keyed by the answer, so a new
 * question starts with fresh "Save insight" state. */
function AnswerActions({ datasetId, response }: { datasetId: string; response: AnalyzeResponse }) {
  const save = useSaveInsight()
  const chartOptions = chartOptionsFromToolCalls(response.tool_calls, response.question)
  const [chartIndex, setChartIndex] = useState(0)
  const chart = chartOptions[chartIndex]

  // A degraded answer is an apology, not an insight worth keeping.
  if (response.status === 'degraded') return null

  return (
    <div className="mt-4 flex flex-wrap items-start gap-2 border-t border-[var(--color-border)] pt-4">
      <Button
        size="sm"
        variant="secondary"
        disabled={save.isPending || save.isSuccess}
        onClick={() =>
          save.mutate({
            datasetId,
            question: response.question,
            answer: response.answer,
            findings: response.findings,
          })
        }
      >
        {save.isSuccess ? (
          <Check className="h-4 w-4 text-[var(--color-positive)]" strokeWidth={2} />
        ) : (
          <Bookmark className="h-4 w-4" strokeWidth={1.75} />
        )}
        {save.isPending ? 'Saving…' : save.isSuccess ? 'Saved' : 'Save insight'}
      </Button>
      {save.isSuccess && (
        <Link
          to="/workspace/insights"
          className="self-center text-xs font-medium text-[var(--color-accent)] hover:underline"
        >
          View saved insights
        </Link>
      )}
      {chart && (
        <div className="flex flex-wrap items-start gap-2">
          {chartOptions.length > 1 && (
            <Select
              aria-label="Result to chart"
              className="h-8 w-auto text-xs"
              value={chartIndex}
              onChange={(e) => setChartIndex(Number(e.target.value))}
            >
              {chartOptions.map((option, i) => (
                <option key={option.label} value={i}>
                  Chart: {option.label}
                </option>
              ))}
            </Select>
          )}
          <AddToDashboardControl
            key={chartIndex}
            datasetId={datasetId}
            query={chart.query}
            defaultTitle={response.question.slice(0, 255)}
            suggestedChartType={chart.query.group_by?.length ? 'bar' : 'kpi'}
          />
        </div>
      )}
      {save.isError && (
        <p className="basis-full text-xs text-[var(--color-negative)]">
          {save.error instanceof ApiError ? save.error.message : "Couldn't save this insight."}
          <ErrorReference error={save.error} />
        </p>
      )}
    </div>
  )
}

export function AnalyzeAnalystView() {
  const { data: datasets } = useDatasets()
  const readyDatasets = datasets?.filter((d) => d.status === 'profiled') ?? []

  const [datasetId, setDatasetId] = useState('')
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState<ConversationTurn[]>([])
  const [lastResponse, setLastResponse] = useState<AnalyzeResponse | null>(null)
  const [answerCount, setAnswerCount] = useState(0)

  const analyze = useAnalyzeDataset(datasetId)

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!datasetId || !question.trim()) return
    const asked = question
    analyze.mutate(
      { question: asked, conversationHistory: history },
      {
        onSuccess: (response) => {
          setLastResponse(response)
          setAnswerCount((n) => n + 1)
          // The server caps each turn at 4,000 characters.
          setHistory((prev) => [...prev, { question: asked, answer: response.answer.slice(0, 4000) }])
        },
      },
    )
  }

  return (
    <div className="flex flex-col gap-4 px-4 py-5 sm:px-6">
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
                <Label htmlFor="analyze-dataset">Dataset</Label>
                <Select
                  id="analyze-dataset"
                  value={datasetId}
                  onChange={(e) => {
                    setDatasetId(e.target.value)
                    setHistory([])
                    setLastResponse(null)
                  }}
                >
                  <option value="">Select a dataset…</option>
                  {readyDatasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.original_filename}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="analyze-question">Question</Label>
                <Input
                  id="analyze-question"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="e.g. Are there any anomalies in this data?"
                />
              </div>
              <Button
                type="submit"
                className="self-start"
                disabled={!datasetId || !question.trim() || analyze.isPending}
              >
                <Sparkles className="h-4 w-4" strokeWidth={1.75} />
                {analyze.isPending ? 'Analyzing…' : 'Ask'}
              </Button>
              <p className="text-xs text-[var(--color-fg-subtle)]">
                Your question, column names, and small calculated results are sent to our AI
                provider (Groq). AI answers can be wrong; check the evidence below.{' '}
                <Link to="/privacy" className="underline">
                  Privacy
                </Link>
              </p>

              {analyze.isError &&
                (analyze.error instanceof ApiError && analyze.error.status === 429 ? (
                  <div className="flex items-start gap-2 rounded-md border border-[var(--color-warning)] bg-[var(--color-warning)]/10 px-3 py-2 text-sm text-[var(--color-fg)]">
                    <AlertTriangle
                      className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-warning)]"
                      strokeWidth={1.75}
                    />
                    <p>
                      {analyze.error.message}{' '}
                      <Link to="/workspace/usage" className="underline">
                        See your usage
                      </Link>
                      . Questions you've already asked today are still answered from cache.
                    </p>
                  </div>
                ) : (
                  <p className="text-xs text-[var(--color-negative)]">
                    {analyze.error instanceof ApiError
                      ? analyze.error.message
                      : 'Something went wrong.'}
                    <ErrorReference error={analyze.error} />
                  </p>
                ))}
            </form>
          </CardContent>
        </Card>
      )}

      {lastResponse && (
        <Card>
          <CardHeader>
            <CardTitle>Answer</CardTitle>
          </CardHeader>
          <CardContent>
            <EvidencePanel response={lastResponse} />
            <AnswerActions key={answerCount} datasetId={datasetId} response={lastResponse} />
          </CardContent>
        </Card>
      )}
    </div>
  )
}
