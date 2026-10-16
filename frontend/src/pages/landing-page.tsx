import { Brand } from '@/components/brand'
import { ThemeToggle } from '@/components/theme-toggle'
import { UserCount } from '@/components/landing/user-count'
import { Button } from '@/components/ui/button'
import { IconChip } from '@/components/ui/icon-chip'
import { ContactButton } from '@/components/landing/contact-button'
import { SiteFooter } from '@/components/landing/site-footer'
import { HeroPanel } from '@/components/landing/hero-panel'
import { motion } from 'framer-motion'
import { Database, MessageSquareText, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'

const FEATURES = [
  {
    icon: Database,
    color: 'var(--color-teal)',
    title: 'Automatic dataset profiling',
    description:
      'Upload a CSV or Excel file and get row counts, null rates, duplicates, and data-quality issues surfaced instantly.',
  },
  {
    icon: MessageSquareText,
    color: 'var(--color-purple)',
    title: 'Ask questions in plain language',
    description:
      'Natural-language questions are translated into validated, read-only analytical queries — grounded in your actual data.',
  },
  {
    icon: ShieldCheck,
    color: 'var(--color-positive)',
    title: 'Safe by construction',
    description:
      'Every AI-generated query is schema-validated and restricted to read-only analytical SELECTs before it ever runs.',
  },
]

export function LandingPage() {
  return (
    <div className="min-h-screen overflow-x-clip bg-[var(--color-canvas)] text-[var(--color-fg)]">
      <header className="material sticky top-0 z-30 border-b border-[var(--color-border)]">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link to="/" aria-label="PulseIQ home">
            <Brand />
          </Link>
          <div className="flex items-center gap-1 sm:gap-2">
            <span className="mr-1 hidden sm:block">
              <UserCount />
            </span>
            <ContactButton />
            <Button variant="ghost" size="sm" asChild>
              <Link to="/login">Log in</Link>
            </Button>
            <Button size="sm" className="rounded-full" asChild>
              <Link to="/signup">Sign up</Link>
            </Button>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main>
      <section className="relative mx-auto grid max-w-6xl grid-cols-1 items-center gap-12 px-4 py-14 sm:px-6 sm:py-20 lg:grid-cols-2">
        <div className="hero-glow absolute -inset-x-64 -top-24 h-[560px]" aria-hidden="true" />
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[420px] grid-backdrop" />

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: 'spring', bounce: 0, duration: 0.6 }}
          className="relative"
        >
          <p className="mb-3 text-sm font-semibold text-[var(--color-accent)]">
            AI-powered analytics workspace
          </p>
          <h1 className="text-4xl font-bold leading-[1.05] tracking-[-0.03em] text-[var(--color-fg)] sm:text-5xl lg:text-[3.25rem]">
            Ask your data questions.
            <br />
            <span className="text-gradient">Get grounded answers.</span>
          </h1>
          <p className="mt-6 max-w-lg text-lg leading-relaxed text-[var(--color-fg-muted)]">
            PulseIQ profiles your datasets, surfaces data quality issues, and lets you query them in
            plain language — with every AI-generated query validated against your schema before it
            runs. No spreadsheets. No guessing.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Button size="lg" className="rounded-full" asChild>
              <Link to="/signup">Start analyzing</Link>
            </Button>
            <Button size="lg" variant="secondary" className="rounded-full" asChild>
              <Link to="/login">View demo workspace</Link>
            </Button>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: 'spring', bounce: 0, duration: 0.6, delay: 0.1 }}
          className="relative flex justify-center lg:justify-end"
        >
          <HeroPanel />
        </motion.div>
      </section>

      <section className="mx-auto max-w-6xl px-4 pb-20 pt-4 sm:px-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {FEATURES.map(({ icon, color, title, description }) => (
            <div
              key={title}
              className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-[var(--shadow-card)]"
            >
              <IconChip icon={icon} color={color} className="mb-4" />
              <h3 className="text-base font-semibold text-[var(--color-fg)]">{title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-[var(--color-fg-muted)]">
                {description}
              </p>
            </div>
          ))}
        </div>
      </section>

      </main>

      <SiteFooter />
    </div>
  )
}
