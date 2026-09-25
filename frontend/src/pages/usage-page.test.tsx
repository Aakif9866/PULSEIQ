import { apiClient } from '@/lib/api-client'
import { UsagePage } from '@/pages/usage-page'
import type { UsageSummary } from '@/types/usage'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api-client', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api-client')>('@/lib/api-client')
  return { ...actual, apiClient: { get: vi.fn(), post: vi.fn() } }
})

const BASE: UsageSummary = {
  day_start: '2026-09-25T00:00:00Z',
  resets_at: '2026-09-26T00:00:00Z',
  requests: 4,
  cache_hits: 1,
  prompt_tokens: 9000,
  completion_tokens: 1000,
  total_tokens: 10000,
  estimated_cost_usd: null,
  quota_tokens: null,
  remaining_tokens: null,
  cost_tracking_configured: false,
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <UsagePage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(apiClient.get).mockReset()
})

describe('UsagePage', () => {
  it('shows real token totals and requests', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(BASE)
    renderPage()
    expect(await screen.findByText((10000).toLocaleString())).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
  })

  it('says cost is not tracked rather than showing $0 when pricing is unset', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(BASE)
    renderPage()
    expect(await screen.findByText('Not tracked')).toBeInTheDocument()
    expect(screen.queryByText('$0.0000')).not.toBeInTheDocument()
  })

  it('shows the dollar estimate when pricing is configured', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      ...BASE,
      estimated_cost_usd: 0.0123,
      cost_tracking_configured: true,
    })
    renderPage()
    expect(await screen.findByText('$0.0123')).toBeInTheDocument()
  })

  it('explains there is no limit when no quota is configured', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(BASE)
    renderPage()
    expect(await screen.findByText(/No daily limit is configured/)).toBeInTheDocument()
  })

  it('shows remaining tokens under a quota', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      ...BASE,
      quota_tokens: 50000,
      remaining_tokens: 40000,
    })
    renderPage()
    expect(await screen.findByText(/left\./)).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '20')
  })

  it('says the limit is reached when nothing remains', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      ...BASE,
      total_tokens: 50000,
      quota_tokens: 50000,
      remaining_tokens: 0,
    })
    renderPage()
    expect(await screen.findByText(/limit reached/)).toBeInTheDocument()
  })
})
