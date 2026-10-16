import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { ErrorReference } from '@/components/ui/error-reference'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { AddToDashboardControl } from '@/components/dashboards/add-to-dashboard-control'
import { useAnalyzeDataset } from '@/features/ai/api'
import { downloadInsightReport, useSaveInsight } from '@/features/insights/api'
import { useDatasetBriefing, useDatasets } from '@/features/datasets/api'
import { ApiError } from '@/lib/api-client'
import type { AnalyzeResponse, ConversationTurn, Finding, ToolCallRecord } from '@/types/analysis'
import { analysisContext, chartOptionsFromToolCalls, toolCallFailed } from '@/types/analysis'
import { AlertTriangle, Bookmark, Check, CheckCircle2, Database, FileDown, HelpCircle, MessageSquarePlus, Sparkles, Wrench } from 'lucide-react'
import { type FormEvent, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

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
            {/* Rephrasing only helps when the model's reply was unusable —
                not for a rate limit, an outage or a server misconfiguration,
                whose specific explanation is the answer text below. */}
            {!response.failure_reason || response.failure_reason === 'invalid_response'
              ? "This analysis couldn't be completed reliably — the AI provider didn't return a usable response after retrying. Try rephrasing the question or asking again."
              : "This analysis couldn't be completed. The reason is explained below."}
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

function QuestionChips({
  label,
  questions,
  onPick,
}: {
  label: string
  questions: string[]
  onPick: (q: string) => void
}) {
  if (questions.length === 0) return null
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium text-[var(--color-fg-muted)]">{label}</p>
      <div className="flex flex-wrap gap-2">
        {questions.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onPick(q)}
            className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border-strong)] px-3 py-1.5 text-left text-xs text-[var(--color-fg)] transition-colors hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[var(--color-focus)] active:scale-[0.98]"
          >
            <Sparkles className="h-3 w-3 shrink-0 text-[var(--color-purple)]" strokeWidth={2} />
            {q}
          </button>
        ))}
      </div>
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
            toolCalls: response.tool_calls,
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
      {save.data && (
        <>
          <Button size="sm" variant="secondary" onClick={() => downloadInsightReport(save.data)}>
            <FileDown className="h-4 w-4" strokeWidth={1.75} />
            Download report
          </Button>
          <Link
            to={`/workspace/insights?focus=${save.data.id}`}
            className="self-center text-xs font-medium text-[var(--color-accent)] hover:underline"
          >
            View saved insight
          </Link>
        </>
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
            insightId={save.data?.id}
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

  // Deep links from a dataset's briefing pre-fill (never auto-send) a
  // question, so following a link never spends AI quota on its own.
  const [params] = useSearchParams()
  const [datasetId, setDatasetId] = useState(params.get('dataset') ?? '')
  const [question, setQuestion] = useState(params.get('q') ?? '')
  const [history, setHistory] = useState<ConversationTurn[]>([])
  const [lastResponse, setLastResponse] = useState<AnalyzeResponse | null>(null)
  const [answerCount, setAnswerCount] = useState(0)

  const analyze = useAnalyzeDataset(datasetId)
  const briefing = useDatasetBriefing(datasetId, history.length === 0)
  const questionRef = useRef<HTMLInputElement>(null)
  // Fills (never sends) the question: asking always stays the user's click.
  const pick = (q: string) => {
    setQuestion(q)
    questionRef.current?.focus()
  }
  const resetConversation = () => {
    setHistory([])
    setLastResponse(null)
  }

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
          setQuestion('')
          // The server caps each turn at 4,000 characters. `context` is a
          // compact record of what was computed (tools + arguments, never
          // data values), so a follow-up like "break that down by region"
          // knows which metric and period "that" was.
          setHistory((prev) => [
            ...prev,
            {
              question: asked,
              answer: response.answer.slice(0, 4000),
              context: analysisContext(response.tool_calls),
            },
          ])
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
                    resetConversation()
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
                  ref={questionRef}
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
                {analyze.isPending ? 'Analyzing…' : history.length ? 'Ask follow-up' : 'Ask'}
              </Button>
              {datasetId && history.length === 0 && (
                <QuestionChips
                  label="Suggested starting points for this dataset"
                  questions={briefing.data?.suggested_questions ?? []}
                  onPick={pick}
                />
              )}
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

      {history.length > 1 && (
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Earlier in this conversation</CardTitle>
            <Button size="sm" variant="ghost" onClick={resetConversation}>
              <MessageSquarePlus className="h-4 w-4" strokeWidth={1.75} />
              New conversation
            </Button>
          </CardHeader>
          <CardContent>
            <ol className="space-y-3">
              {history.slice(0, -1).map((turn, i) => (
                <li key={i} className="space-y-0.5">
                  <p className="text-sm font-medium text-[var(--color-fg)]">{turn.question}</p>
                  <p className="line-clamp-2 text-sm text-[var(--color-fg-muted)]">{turn.answer}</p>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}

      {lastResponse && (
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Answer</CardTitle>
            {history.length === 1 && (
              <Button size="sm" variant="ghost" onClick={resetConversation}>
                <MessageSquarePlus className="h-4 w-4" strokeWidth={1.75} />
                New conversation
              </Button>
            )}
          </CardHeader>
          <CardContent>
            <p className="mb-3 text-xs text-[var(--color-fg-subtle)]">{lastResponse.question}</p>
            <EvidencePanel response={lastResponse} />
            <AnswerActions key={answerCount} datasetId={datasetId} response={lastResponse} />
            {lastResponse.status === 'ok' && (
              <div className="mt-4">
                <QuestionChips
                  label="Suggested next questions"
                  questions={lastResponse.suggested_questions ?? []}
                  onPick={pick}
                />
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
