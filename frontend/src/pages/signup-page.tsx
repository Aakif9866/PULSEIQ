import { Brand } from '@/components/brand'
import { Button } from '@/components/ui/button'
import { useSlow } from '@/lib/use-slow'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useSignup } from '@/features/auth/api'
import { ApiError } from '@/lib/api-client'
import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

export function SignupPage() {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const signup = useSignup()
  const slow = useSlow(signup.isPending)
  const navigate = useNavigate()

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    signup.mutate(
      { email, password, full_name: fullName || undefined },
      { onSuccess: () => navigate('/workspace', { replace: true }) },
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
          <h1 className="text-xl font-semibold text-[var(--color-fg)]">Create your workspace</h1>
          <p className="mt-1 text-sm text-[var(--color-fg-muted)]">
            Start exploring datasets with AI-assisted analysis.
          </p>

          <form className="mt-5 space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-1.5">
              <Label htmlFor="full_name">Full name</Label>
              <Input
                id="full_name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Ana Lyst"
                autoComplete="name"
              />
            </div>
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
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
                autoComplete="new-password"
              />
            </div>

            {signup.isError && (
              <p className="text-xs text-[var(--color-negative)]">
                {signup.error instanceof ApiError ? signup.error.message : 'Something went wrong.'}
              </p>
            )}

            <Button type="submit" size="lg" className="w-full" disabled={signup.isPending}>
              {signup.isPending ? 'Creating account…' : 'Create account'}
            </Button>
            {slow && (
              <p role="status" className="text-center text-xs text-[var(--color-fg-muted)]">
                Waking up the server — on free hosting the first request can take up to a
                minute. Hang tight.
              </p>
            )}
            <p className="text-center text-xs text-[var(--color-fg-subtle)]">
              By signing up you agree to the{' '}
              <Link to="/terms" className="underline">
                Terms of Service
              </Link>{' '}
              and{' '}
              <Link to="/privacy" className="underline">
                Privacy Policy
              </Link>
              .
            </p>
          </form>
        </div>

        <p className="mt-4 text-center text-xs text-[var(--color-fg-muted)]">
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-[var(--color-accent)] hover:underline">
            Log in
          </Link>
        </p>
      </div>
    </div>
  )
}
