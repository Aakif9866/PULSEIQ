import { SqlExplorer } from '@/components/sql/sql-explorer'
import { ApiError, apiClient } from '@/lib/api-client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api-client', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api-client')>('@/lib/api-client')
  return { ...actual, apiClient: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }
})

function renderExplorer() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <SqlExplorer datasetId="ds-1" />
    </QueryClientProvider>,
  )
}

describe('SqlExplorer', () => {
  beforeEach(() => {
    vi.mocked(apiClient.get).mockResolvedValue([])
    vi.mocked(apiClient.post).mockReset()
  })

  it('puts generated SQL in the editor and shows the answer and rows', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      question: 'revenue by region',
      answer: 'North leads with 503,471.',
      generated_sql: 'SELECT region, SUM(revenue) FROM dataset GROUP BY region LIMIT 10000',
      result: { columns: ['region', 'sum'], rows: [['North', 503471]], row_count: 1, truncated: false },
    })
    const user = userEvent.setup()
    renderExplorer()

    await user.type(screen.getByLabelText('Ask in plain English'), 'revenue by region')
    await user.click(screen.getByRole('button', { name: 'Generate SQL' }))

    expect(apiClient.post).toHaveBeenCalledWith('/datasets/ds-1/ask-sql', {
      question: 'revenue by region',
    })
    expect(await screen.findByText('North leads with 503,471.')).toBeInTheDocument()
    expect(screen.getByLabelText('SQL query')).toHaveValue(
      'SELECT region, SUM(revenue) FROM dataset GROUP BY region LIMIT 10000',
    )
    expect(screen.getByText('North')).toBeInTheDocument()
  })

  it("shows the validator's rejection instead of results", async () => {
    vi.mocked(apiClient.post).mockRejectedValue(
      new ApiError(422, 'Only SELECT statements are allowed', undefined, 'req-123'),
    )
    const user = userEvent.setup()
    renderExplorer()

    await user.click(screen.getByRole('button', { name: 'Run SQL' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Only SELECT statements are allowed')
    expect(alert).toHaveTextContent('req-123')
  })
})
