import { InsightsPage } from '@/pages/insights-page'
import { apiClient } from '@/lib/api-client'
import type { Insight } from '@/types/insight'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api-client', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api-client')>('@/lib/api-client')
  return { ...actual, apiClient: { get: vi.fn(), patch: vi.fn(), delete: vi.fn() } }
})

const INSIGHT: Insight = {
  id: 'ins-1',
  dataset_id: 'ds-1',
  dataset_filename: 'sales.csv',
  title: 'Revenue by region',
  question: 'What is revenue per region?',
  answer: 'North leads.',
  query_request: null,
  row_count: null,
  findings: [],
  tool_calls: [{ tool: 'group_by_aggregate', arguments: { group_by: ['region'] }, result: {} }],
  dataset_version: 1,
  current_dataset_version: 1,
  created_at: '2026-10-17T00:00:00Z',
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <InsightsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(apiClient.get).mockReset().mockResolvedValue([INSIGHT])
  vi.mocked(apiClient.patch).mockReset().mockResolvedValue({ ...INSIGHT, title: 'Renamed' })
  vi.mocked(apiClient.delete).mockReset().mockResolvedValue(undefined)
})

describe('InsightsPage', () => {
  it('shows the insight with its source, snapshot label, evidence and re-run link', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Revenue by region' })).toBeInTheDocument()
    expect(screen.getByText('Asked: What is revenue per region?')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /sales\.csv/ })).toHaveAttribute('href', '/workspace/datasets/ds-1')
    expect(screen.getByText('Snapshot')).toBeInTheDocument()
    expect(screen.getByText(/how this was calculated \(1 computation\)/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /re-run/i }).getAttribute('href')).toContain('dataset=ds-1')
  })

  it('renames inline', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole('button', { name: /rename insight/i }))
    const input = screen.getByRole('textbox', { name: /insight title/i })
    await user.clear(input)
    await user.type(input, 'Renamed{Enter}')
    expect(apiClient.patch).toHaveBeenCalledWith('/insights/ins-1', { title: 'Renamed' })
  })

  it('asks before deleting, and does nothing if cancelled', async () => {
    const user = userEvent.setup()
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    renderPage()
    const del = await screen.findByRole('button', { name: /delete revenue by region/i })
    await user.click(del)
    expect(apiClient.delete).not.toHaveBeenCalled()
    await user.click(del)
    expect(apiClient.delete).toHaveBeenCalledWith('/insights/ins-1')
    confirm.mockRestore()
  })

  it('warns when the insight was computed on an older version of the dataset', async () => {
    vi.mocked(apiClient.get).mockResolvedValue([{ ...INSIGHT, current_dataset_version: 3 }])
    renderPage()
    expect(await screen.findByText(/from version 1 · dataset now at version\s*3/i)).toBeInTheDocument()
    expect(screen.queryByText('Snapshot')).not.toBeInTheDocument()
  })
})
