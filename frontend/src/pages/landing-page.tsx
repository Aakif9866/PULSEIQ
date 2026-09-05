import { Button } from '@/components/ui/button'
import { HeroPanel } from '@/components/landing/hero-panel'
import { motion } from 'framer-motion'
import { Activity, Database, MessageSquareText, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'

const FEATURES = [
  {
    icon: Database,
    title: 'Automatic dataset profiling',
    description:
      'Upload a CSV or Excel file and get row counts, null rates, duplicates, and data-quality issues surfaced instantly.',
  },
  {
    icon: MessageSquareText,
    title: 'Ask questions in plain language',
    description:
      'Natural-language questions are translated into validated, read-only analytical queries — grounded in your actual data.',
  },
  {
    icon: ShieldCheck,
    title: 'Safe by construction',
    description:
      'Every AI-generated query is schema-validated and restricted to read-only analytical SELECTs before it ever runs.',
  },
]

export function LandingPage() {
  return (
    <div className="min-h-screen bg-[var(--color-canvas)] text-[var(--color-fg)]">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-sm bg-[var(--color-accent)]">
            <Activity className="h-4 w-4 text-[var(--color-accent-fg)]" strokeWidth={2.5} />
          </div>
          <span className="text-base font-semibold tracking-tight">PulseIQ</span>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" asChild>
            <Link to="/login">Log in</Link>
          </Button>
          <Button size="sm" asChild>
            <Link to="/signup">Sign up</Link>
          </Button>
        </div>
      </header>

      <section className="relative mx-auto grid max-w-6xl grid-cols-1 items-center gap-12 px-6 py-20 lg:grid-cols-2">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[420px] grid-backdrop" />

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="relative"
        >
          <p className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--color-accent)]">
            AI-powered analytics workspace
          </p>
          <h1 className="text-4xl font-semibold leading-tight tracking-tight text-[var(--color-fg)] lg:text-5xl">
            Ask your data questions.
            <br />
            Get grounded answers.
          </h1>
          <p className="mt-5 max-w-lg text-sm leading-relaxed text-[var(--color-fg-muted)]">
            PulseIQ profiles your datasets, surfaces data quality issues, and lets you query them in
            plain language — with every AI-generated query validated against your schema before it
            runs. No spreadsheets. No guessing.
          </p>
          <div className="mt-8 flex items-center gap-3">
            <Button size="lg" asChild>
              <Link to="/signup">Start analyzing</Link>
            </Button>
            <Button size="lg" variant="secondary" asChild>
              <Link to="/login">View demo workspace</Link>
            </Button>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.15 }}
          className="relative flex justify-center lg:justify-end"
        >
          <HeroPanel />
        </motion.div>
      </section>

      <section className="mx-auto max-w-6xl border-t border-[var(--color-border)] px-6 py-16">
        <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, description }) => (
            <div key={title}>
              <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-md bg-[var(--color-surface-raised)] border border-[var(--color-border)]">
                <Icon className="h-4 w-4 text-[var(--color-fg-muted)]" strokeWidth={1.5} />
              </div>
              <h3 className="text-sm font-semibold text-[var(--color-fg)]">{title}</h3>
              <p className="mt-1.5 text-xs leading-relaxed text-[var(--color-fg-muted)]">
                {description}
              </p>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-[var(--color-border)] px-6 py-8">
        <p className="mx-auto max-w-6xl text-xs text-[var(--color-fg-subtle)]">
          PulseIQ — a self-service analytics workspace.
        </p>
      </footer>
    </div>
  )
}
