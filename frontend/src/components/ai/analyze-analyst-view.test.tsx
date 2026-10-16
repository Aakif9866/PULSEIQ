import { AnalyzeAnalystView } from '@/components/ai/analyze-analyst-view'
import { apiClient } from '@/lib/api-client'
import type { AnalyzeResponse } from '@/types/analysis'
import type { Dataset } from '@/types/dataset'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api-client', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api-client')>('@/lib/api-client')
  return {
    ...actual,
    apiClient: {
      get: vi.fn(),
      post: vi.fn(),
    },
  }
})

const PROFILED_DATASET: Dataset = {
  id: 'ds-1',
  original_filename: 'sales.csv',
  content_type: 'text/csv',
  size_bytes: 123,
  status: 'profiled',
  created_at: '2026-01-01T00:00:00Z',
  row_count: 8,
  column_count: 3,
  columns_profile: null,
  duplicate_row_count: 2,
  data_quality_score: 90,
  correlations: null,
  version: 1,
}

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AnalyzeAnalystView />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

async function askQuestion(question: string) {
  const user = userEvent.setup()
  // useDatasets() resolves asynchronously — the empty state renders until
  // it does, so the dropdown must be waited for, not queried synchronously.
  const datasetSelect = await screen.findByRole('combobox')
  await user.selectOptions(datasetSelect, 'ds-1')
  await user.type(screen.getByRole('textbox'), question)
  await user.click(screen.getByRole('button', { name: /ask/i }))
  return user
}

beforeEach(() => {
  vi.mocked(apiClient.get).mockReset().mockResolvedValue([PROFILED_DATASET])
  vi.mocked(apiClient.post).mockReset()
})

describe('AnalyzeAnalystView', () => {
  it('shows an empty state when no dataset has finished profiling', async () => {
    vi.mocked(apiClient.get).mockResolvedValue([{ ...PROFILED_DATASET, status: 'uploaded' }])
    renderWithProviders()
    expect(await screen.findByText(/no datasets ready yet/i)).toBeInTheDocument()
  })

  it('renders a verified finding, its evidence tools, and the answer text', async () => {
    const response: AnalyzeResponse = {
      question: 'Find duplicates',
      answer: 'There are 2 duplicate rows.',
      status: 'ok',
      needs_clarification: null,
      warnings: [],
      tool_calls: [{ tool: 'get_duplicates', arguments: {}, result: { duplicate_rows: 2 } }],
      findings: [
        {
          claim: 'duplicate rows',
          value: 2,
          unit: null,
          affected_rows: 2,
          total_rows: 8,
          calculation: null,
          classification: 'duplicate',
          confidence: 'high',
          evidence: [],
          verified: true,
        },
      ],
    }
    vi.mocked(apiClient.post).mockResolvedValue(response)

    renderWithProviders()
    await askQuestion('Any duplicates?')

    expect(await screen.findByText('There are 2 duplicate rows.')).toBeInTheDocument()
    expect(screen.getByText('get_duplicates')).toBeInTheDocument()
    expect(screen.getByText(/1\/1 verified/)).toBeInTheDocument()
    expect(screen.queryByText(/not verified against tool evidence/)).not.toBeInTheDocument()
  })

  it('flags an unverified finding instead of hiding it', async () => {
    const response: AnalyzeResponse = {
      question: 'Any anomalies?',
      answer: 'There are 42 missing values.',
      status: 'ok',
      needs_clarification: null,
      warnings: [],
      tool_calls: [{ tool: 'get_missing_values', arguments: {}, result: { row_count: 8 } }],
      findings: [
        {
          claim: 'missing values',
          value: 42,
          unit: null,
          affected_rows: null,
          total_rows: null,
          calculation: null,
          classification: 'missing_data',
          confidence: 'medium',
          evidence: [],
          verified: false,
        },
      ],
    }
    vi.mocked(apiClient.post).mockResolvedValue(response)

    renderWithProviders()
    await askQuestion('Any anomalies?')

    expect(await screen.findByText(/not verified against tool evidence/)).toBeInTheDocument()
    expect(screen.getByText(/0\/1 verified/)).toBeInTheDocument()
  })

  it('shows the degraded banner when the provider fell back', async () => {
    const response: AnalyzeResponse = {
      question: 'Give me a full analysis',
      answer: 'The AI provider did not return a usable response after retrying.',
      status: 'degraded',
      needs_clarification: null,
      warnings: [],
      tool_calls: [],
      findings: [],
    }
    vi.mocked(apiClient.post).mockResolvedValue(response)

    renderWithProviders()
    await askQuestion('Give me a full analysis')

    expect(await screen.findByText(/couldn't be completed reliably/i)).toBeInTheDocument()
  })

  it('surfaces a failed tool call instead of silently continuing', async () => {
    const response: AnalyzeResponse = {
      question: 'Correlate age and revenue',
      answer: 'Could not compute that correlation.',
      status: 'ok',
      needs_clarification: null,
      warnings: [],
      tool_calls: [
        {
          tool: 'calculate_correlation',
          arguments: { column_a: 'age', column_b: 'revenue' },
          result: { error: "Unknown tool: calculate_correlation" },
        },
      ],
      findings: [],
    }
    vi.mocked(apiClient.post).mockResolvedValue(response)

    renderWithProviders()
    await askQuestion('Correlate age and revenue')

    expect(
      await screen.findByText(/1 of 1 tool call failed/i),
    ).toBeInTheDocument()
  })

  it('shows the API error message when the request itself fails', async () => {
    const { ApiError } = await vi.importActual<typeof import('@/lib/api-client')>(
      '@/lib/api-client',
    )
    vi.mocked(apiClient.post).mockRejectedValue(
      new ApiError(503, 'AI features are not configured.'),
    )

    renderWithProviders()
    await askQuestion('Anything?')

    expect(await screen.findByText('AI features are not configured.')).toBeInTheDocument()
  })

  it('shows the request id as a quotable reference on a server error', async () => {
    const { ApiError } = await vi.importActual<typeof import('@/lib/api-client')>(
      '@/lib/api-client',
    )
    vi.mocked(apiClient.post).mockRejectedValue(
      new ApiError(500, 'Something went wrong on our end.', undefined, 'req-abc-123'),
    )

    renderWithProviders()
    await askQuestion('Anything?')

    expect(await screen.findByText('req-abc-123')).toBeInTheDocument()
    expect(screen.getByText(/Reference:/)).toBeInTheDocument()
  })

  it('shows a distinct quota message with a link to usage on a 429', async () => {
    const { ApiError } = await vi.importActual<typeof import('@/lib/api-client')>(
      '@/lib/api-client',
    )
    vi.mocked(apiClient.post).mockRejectedValue(
      new ApiError(
        429,
        'Daily AI usage limit reached (2,500 of 2,000 tokens). Resets at 2026-09-26T00:00:00+00:00.',
      ),
    )

    renderWithProviders()
    await askQuestion('Anything?')

    expect(await screen.findByText(/Daily AI usage limit reached/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'See your usage' })).toHaveAttribute(
      'href',
      '/workspace/usage',
    )
  })

  it('sends conversation history from a prior answer on the next question', async () => {
    const first: AnalyzeResponse = {
      question: 'Which category is best?',
      answer: 'Electronics, by revenue.',
      status: 'ok',
      needs_clarification: null,
      warnings: [],
      tool_calls: [],
      findings: [],
    }
    vi.mocked(apiClient.post).mockResolvedValueOnce(first)
    renderWithProviders()
    await askQuestion('Which category is best?')
    await screen.findByText('Electronics, by revenue.')

    const second: AnalyzeResponse = { ...first, question: 'Why?', answer: 'Because volume.' }
    vi.mocked(apiClient.post).mockResolvedValueOnce(second)
    const user = userEvent.setup()
    await user.clear(screen.getByRole('textbox'))
    await user.type(screen.getByRole('textbox'), 'Why?')
    await user.click(screen.getByRole('button', { name: /ask/i }))
    await screen.findByText('Because volume.')

    const [, body] = vi.mocked(apiClient.post).mock.calls[1]!
    expect(body).toMatchObject({
      question: 'Why?',
      conversation_history: [{ question: 'Which category is best?', answer: 'Electronics, by revenue.' }],
    })
  })

  it('saves an answer as an insight with its findings', async () => {
    const response: AnalyzeResponse = {
      question: 'Total amount?',
      answer: 'The total is 45.',
      status: 'ok',
      needs_clarification: null,
      warnings: [],
      tool_calls: [],
      findings: [{ claim: 'Total amount', value: 45, unit: null, affected_rows: null, total_rows: null, calculation: null, classification: null, confidence: 'high', evidence: [], verified: true }],
    }
    vi.mocked(apiClient.post).mockResolvedValueOnce(response).mockResolvedValueOnce({ id: 'ins-1' })
    renderWithProviders()
    const user = await askQuestion('Total amount?')
    await user.click(await screen.findByRole('button', { name: /save insight/i }))

    expect(apiClient.post).toHaveBeenLastCalledWith('/insights', {
      dataset_id: 'ds-1',
      question: 'Total amount?',
      answer: 'The total is 45.',
      query: undefined,
      row_count: undefined,
      findings: response.findings,
      title: undefined,
      tool_calls: [], // the evidence is stored with the insight
    })
    // Once saved, the report and the saved insight are one click away.
    expect(await screen.findByRole('button', { name: /download report/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /view saved insight/i })).toHaveAttribute(
      'href',
      '/workspace/insights?focus=ins-1',
    )
    expect(await screen.findByRole('button', { name: /saved/i })).toBeDisabled()
  })

  it('offers "Add to dashboard" only when a group-by result can be re-run as a chart', async () => {
    const base: AnalyzeResponse = {
      question: 'Revenue by region?',
      answer: 'North leads.',
      status: 'ok',
      needs_clarification: null,
      warnings: [],
      findings: [],
      tool_calls: [{ tool: 'get_dataset_profile', arguments: {}, result: {} }],
    }
    vi.mocked(apiClient.post).mockResolvedValueOnce(base)
    renderWithProviders()
    const user = await askQuestion('Revenue by region?')
    await screen.findByRole('button', { name: /save insight/i })
    expect(screen.queryByRole('button', { name: /add to dashboard/i })).not.toBeInTheDocument()

    vi.mocked(apiClient.post).mockResolvedValueOnce({
      ...base,
      tool_calls: [
        {
          tool: 'group_by_aggregate',
          arguments: { group_by: ['region'], column: 'revenue', op: 'sum' },
          result: { columns: ['region', 'value'], rows: [['North', 10]] },
        },
      ],
    })
    await user.type(screen.getByRole('textbox'), ' again')
    await user.click(screen.getByRole('button', { name: /^ask follow-up$/i }))
    expect(await screen.findByRole('button', { name: /add to dashboard/i })).toBeInTheDocument()
    // One chartable result: nothing to choose between.
    expect(screen.queryByRole('combobox', { name: /result to chart/i })).not.toBeInTheDocument()
  })

  it('lets the user pick which result to chart when the AI computed several', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      question: 'Revenue per region?', answer: 'North leads.', status: 'ok',
      needs_clarification: null, warnings: [], findings: [],
      tool_calls: [
        { tool: 'group_by_aggregate', arguments: { group_by: ['region'], column: 'revenue', op: 'sum' }, result: {} },
        { tool: 'group_by_aggregate', arguments: { group_by: ['region'], column: 'order_id', op: 'count' }, result: {} },
      ],
    })
    renderWithProviders()
    await askQuestion('Revenue per region?')
    const picker = await screen.findByRole('combobox', { name: /result to chart/i })
    expect(picker).toHaveDisplayValue('Chart: sum of revenue by region')
  })

  it('hides save actions on a degraded answer', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      question: 'q', answer: 'Analysis could not be completed.', status: 'degraded',
      needs_clarification: null, warnings: [], findings: [], tool_calls: [],
    })
    renderWithProviders()
    await askQuestion('q')
    await screen.findByText(/analysis could not be completed/i)
    expect(screen.queryByRole('button', { name: /save insight/i })).not.toBeInTheDocument()
  })

  it('fills (but does not send) a suggested next question, and keeps the thread', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      question: 'Revenue by region?', answer: 'North leads.', status: 'ok',
      needs_clarification: null, warnings: [], findings: [], tool_calls: [],
      suggested_questions: ['Break revenue down by channel.'],
    })
    renderWithProviders()
    const user = await askQuestion('Revenue by region?')
    await user.click(await screen.findByRole('button', { name: /break revenue down by channel/i }))

    expect(screen.getByRole('textbox')).toHaveValue('Break revenue down by channel.')
    expect(apiClient.post).toHaveBeenCalledTimes(1) // picking never spends quota
    expect(screen.getByRole('button', { name: /ask follow-up/i })).toBeEnabled()
    expect(screen.getByRole('button', { name: /new conversation/i })).toBeInTheDocument()
  })
})
