import type { AuthResponse, User } from '@/types/auth'
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  setSession: (auth: AuthResponse) => void
  clearSession: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      setSession: (auth) =>
        set({
          user: auth.user,
          accessToken: auth.tokens.access_token,
          refreshToken: auth.tokens.refresh_token,
        }),
      clearSession: () => set({ user: null, accessToken: null, refreshToken: null }),
    }),
    {
      name: 'pulseiq-auth',
      // Persisting the refresh token in localStorage is a pragmatic default
      // for this project's scope; a stricter setup would keep it in an
      // httpOnly cookie instead.
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
    },
  ),
)

export const isAuthenticated = () => Boolean(useAuthStore.getState().accessToken)
