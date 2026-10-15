import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/auth-store'
import { Link } from 'react-router-dom'

export function NotFoundPage() {
  const signedIn = useAuthStore((s) => Boolean(s.accessToken))
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[var(--color-canvas)] px-4 text-center text-[var(--color-fg)]">
      <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-accent)]">404</p>
      <h1 className="text-2xl font-semibold tracking-tight">Page not found</h1>
      <p className="max-w-sm text-sm text-[var(--color-fg-muted)]">
        The page you’re looking for doesn’t exist or has moved.
      </p>
      <Button asChild>
        <Link to={signedIn ? '/workspace' : '/'}>
          {signedIn ? 'Back to your workspace' : 'Go to the home page'}
        </Link>
      </Button>
    </main>
  )
}
