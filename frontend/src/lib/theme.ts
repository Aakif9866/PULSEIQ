import { create } from 'zustand'

export type Theme = 'light' | 'dark'

// Must match the key public/theme-init.js reads before first paint.
const THEME_KEY = 'pulseiq-theme'

const root = document.documentElement

interface ThemeState {
  theme: Theme
  toggle: () => void
}

export const useThemeStore = create<ThemeState>()((set, get) => ({
  // theme-init.js has already resolved stored choice vs. system preference.
  theme: root.dataset.theme === 'dark' ? 'dark' : 'light',
  toggle: () => {
    const theme: Theme = get().theme === 'dark' ? 'light' : 'dark'
    root.classList.add('theme-transition')
    root.dataset.theme = theme
    window.setTimeout(() => root.classList.remove('theme-transition'), 250)
    try {
      localStorage.setItem(THEME_KEY, theme)
    } catch {
      // Storage blocked: the theme still applies for this visit.
    }
    set({ theme })
  },
}))

export const useTheme = () => useThemeStore((s) => s.theme)
