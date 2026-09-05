import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useLogin } from '@/features/auth/api'
import { ApiError } from '@/lib/api-client'
import { Activity } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const login = useLogin()
  const navigate = useNavigate()
  const location = useLocation()

  const from = (location.state as { from?: Location })?.from?.pathname ?? '/workspace'

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    login.mutate(
      { email, password },
      { onSuccess: () => navigate(from, { replace: true }) },
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-canvas)] px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center justify-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-sm bg-[var(--color-accent)]">
            <Activity className="h-4 w-4 text-[var(--color-accent-fg)]" strokeWidth={2.5} />
          </div>
          <span className="text-base font-semibold tracking-tight">PulseIQ</span>
        </div>

        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
          <h1 className="text-sm font-semibold text-[var(--color-fg)]">Log in to your workspace</h1>
          <p className="mt-1 text-xs text-[var(--color-fg-muted)]">
            Analyze your datasets and pick up where you left off.
          </p>

          <form className="mt-5 space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                autoComplete="email"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </div>

            {login.isError && (
              <p className="text-xs text-[var(--color-negative)]">
                {login.error instanceof ApiError ? login.error.message : 'Something went wrong.'}
              </p>
            )}

            <Button type="submit" className="w-full" disabled={login.isPending}>
              {login.isPending ? 'Logging in…' : 'Log in'}
            </Button>
          </form>
        </div>

        <p className="mt-4 text-center text-xs text-[var(--color-fg-muted)]">
          Don't have an account?{' '}
          <Link to="/signup" className="font-medium text-[var(--color-accent)] hover:underline">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  )
}
