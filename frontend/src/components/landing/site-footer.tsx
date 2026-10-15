import { ContactButton } from '@/components/landing/contact-button'
import { Link } from 'react-router-dom'

export function SiteFooter() {
  return (
    <footer className="border-t border-[var(--color-border)] px-4 py-8 sm:px-6">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
        <p className="text-xs text-[var(--color-fg-subtle)]">
          PulseIQ — a self-service analytics workspace.
        </p>
        <nav aria-label="Legal" className="flex flex-wrap items-center gap-4 text-xs">
          <Link
            to="/privacy"
            className="text-[var(--color-fg-muted)] underline-offset-4 hover:text-[var(--color-fg)] hover:underline"
          >
            Privacy Policy
          </Link>
          <Link
            to="/terms"
            className="text-[var(--color-fg-muted)] underline-offset-4 hover:text-[var(--color-fg)] hover:underline"
          >
            Terms of Service
          </Link>
          <ContactButton side="top" />
        </nav>
      </div>
    </footer>
  )
}
