import { Button } from '@/components/ui/button'
import { useThemeStore } from '@/lib/theme'
import { Moon, Sun } from 'lucide-react'

export function ThemeToggle() {
  const { theme, toggle } = useThemeStore()
  const label = theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'
  const Icon = theme === 'dark' ? Sun : Moon
  return (
    <Button variant="ghost" size="icon" onClick={toggle} aria-label={label} title={label}>
      <Icon className="h-4 w-4" strokeWidth={1.75} />
    </Button>
  )
}
