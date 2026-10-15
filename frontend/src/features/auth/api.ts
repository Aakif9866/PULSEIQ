import { apiClient } from '@/lib/api-client'
import { useAuthStore } from '@/stores/auth-store'
import type { AuthResponse } from '@/types/auth'
import { useMutation, useQueryClient } from '@tanstack/react-query'

export interface SignupPayload {
  email: string
  password: string
  full_name?: string
}

export interface LoginPayload {
  email: string
  password: string
}

export function useSignup() {
  const setSession = useAuthStore((s) => s.setSession)
  return useMutation({
    mutationFn: (payload: SignupPayload) =>
      apiClient.post<AuthResponse>('/auth/signup', payload, { auth: false }),
    onSuccess: setSession,
  })
}

export function useLogin() {
  const setSession = useAuthStore((s) => s.setSession)
  return useMutation({
    mutationFn: (payload: LoginPayload) =>
      apiClient.post<AuthResponse>('/auth/login', payload, { auth: false }),
    onSuccess: setSession,
  })
}

/** Revokes the refresh token server-side (best effort), then forgets the
 * session and every cached query so the next user sees nothing of this one. */
export function useLogout() {
  const queryClient = useQueryClient()
  return async () => {
    const { refreshToken, clearSession } = useAuthStore.getState()
    if (refreshToken) {
      await apiClient
        .post('/auth/logout', { refresh_token: refreshToken }, { auth: false })
        .catch(() => undefined)
    }
    clearSession()
    queryClient.clear()
  }
}

export function useExportData() {
  return useMutation({
    mutationFn: async () => {
      const data = await apiClient.get<unknown>('/auth/me/export')
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }),
      )
      const link = document.createElement('a')
      link.href = url
      link.download = 'pulseiq-export.json'
      link.click()
      URL.revokeObjectURL(url)
    },
  })
}

export function useDeleteAccount() {
  const queryClient = useQueryClient()
  const clearSession = useAuthStore((s) => s.clearSession)
  return useMutation({
    mutationFn: (password: string) => apiClient.delete<void>('/auth/me', { body: { password } }),
    onSuccess: () => {
      clearSession()
      queryClient.clear()
    },
  })
}
