import { Brand } from '@/components/brand'
import { Button } from '@/components/ui/button'
import { useSlow } from '@/lib/use-slow'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useLogin } from '@/features/auth/api'
import { ApiError } from '@/lib/api-client'
import { type FormEvent, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const login = useLogin()
  const slow = useSlow(login.isPending)
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
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[var(--color-canvas)] px-4">
      <div className="hero-glow absolute inset-0" aria-hidden="true" />
      <div className="relative w-full max-w-sm">
        <Link to="/" className="mb-8 flex justify-center" aria-label="PulseIQ home">
          <Brand />
        </Link>

        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-[var(--shadow-card)] sm:p-8">
          <h1 className="text-xl font-semibold text-[var(--color-fg)]">Log in to your workspace</h1>
          <p className="mt-1 text-sm text-[var(--color-fg-muted)]">
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

            <Button type="submit" size="lg" className="w-full" disabled={login.isPending}>
              {login.isPending ? 'Logging in…' : 'Log in'}
            </Button>
            {slow && (
              <p role="status" className="text-center text-xs text-[var(--color-fg-muted)]">
                Waking up the server — on free hosting the first request can take up to a
                minute. Hang tight.
              </p>
            )}
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
