import { apiClient } from '@/lib/api-client'
import type { AskResponse } from '@/types/insight'
import { useMutation } from '@tanstack/react-query'

export function useAskDataset(datasetId: string) {
  return useMutation({
    mutationFn: (question: string) =>
      apiClient.post<AskResponse>(`/datasets/${datasetId}/ask`, { question }),
  })
}
