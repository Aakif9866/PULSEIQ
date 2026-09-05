import { Button } from '@/components/ui/button'
import { AlertTriangle } from 'lucide-react'
import { Component, type ErrorInfo, type ReactNode } from 'react'

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
}

/** Catches render errors anywhere below it so a bug in one page can't
 * white-screen the whole app. Must be a class component — React has no
 * hooks equivalent of getDerivedStateFromError/componentDidCatch. */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unhandled render error:', error, info.componentStack)
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-canvas)] px-4">
        <div className="w-full max-w-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6 text-center">
          <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-md bg-[var(--color-surface-raised)]">
            <AlertTriangle className="h-5 w-5 text-[var(--color-negative)]" strokeWidth={1.5} />
          </div>
          <h1 className="text-sm font-semibold text-[var(--color-fg)]">Something went wrong</h1>
          <p className="mt-1 text-xs text-[var(--color-fg-muted)]">
            An unexpected error occurred. Reloading usually fixes it.
          </p>
          <Button size="sm" className="mt-4" onClick={() => window.location.reload()}>
            Reload
          </Button>
        </div>
      </div>
    )
  }
}
