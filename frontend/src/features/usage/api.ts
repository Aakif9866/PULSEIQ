import { apiClient } from '@/lib/api-client'
import type { UsageSummary } from '@/types/usage'
import { useQuery } from '@tanstack/react-query'

export const USAGE_KEY = ['usage', 'me'] as const

export function useMyUsage() {
  return useQuery({
    queryKey: USAGE_KEY,
    queryFn: () => apiClient.get<UsageSummary>('/usage/me'),
  })
}
