import { apiClient } from '@/lib/api-client'
import { useAuthStore } from '@/stores/auth-store'
import type { AuthResponse } from '@/types/auth'
import { useMutation } from '@tanstack/react-query'

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
