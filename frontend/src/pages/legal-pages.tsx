import { SiteFooter } from '@/components/landing/site-footer'
import { Brand } from '@/components/brand'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

const EFFECTIVE_DATE = '15 October 2026'
const CONTACT = 'aakif9866@gmail.com'

function LegalLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[var(--color-canvas)] text-[var(--color-fg)]">
      <header className="mx-auto flex max-w-3xl items-center justify-between px-4 py-5 sm:px-6">
        <Link to="/" aria-label="PulseIQ home">
          <Brand />
        </Link>
        <nav aria-label="Legal" className="flex gap-4 text-sm text-[var(--color-fg-muted)]">
          <Link to="/privacy" className="hover:text-[var(--color-fg)]">
            Privacy
          </Link>
          <Link to="/terms" className="hover:text-[var(--color-fg)]">
            Terms
          </Link>
        </nav>
      </header>
      <main className="mx-auto max-w-3xl px-4 pb-16 sm:px-6">
        <article className="legal space-y-4 text-sm leading-relaxed text-[var(--color-fg-muted)] [&_h2]:mt-8 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:text-[var(--color-fg)] [&_li]:ml-5 [&_li]:list-disc [&_strong]:text-[var(--color-fg)]">
          <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-fg)]">{title}</h1>
          <p className="text-xs text-[var(--color-fg-subtle)]">Effective {EFFECTIVE_DATE}</p>
          {children}
        </article>
      </main>
      <SiteFooter />
    </div>
  )
}

export function PrivacyPage() {
  return (
    <LegalLayout title="Privacy Policy">
      <p>
        PulseIQ is a personal project run by an individual developer (“we”, “us”). This policy
        explains what we collect when you use PulseIQ, why, who processes it, and the choices you
        have. Questions: <strong>{CONTACT}</strong>.
      </p>

      <h2>What we collect</h2>
      <ul>
        <li>
          <strong>Account details</strong>: your email address, optional name, and a one-way
          (bcrypt) hash of your password. We never store your password itself.
        </li>
        <li>
          <strong>Files you upload</strong> (CSV or Excel) and the profile we compute from them
          (column names and types, row counts, data-quality statistics).
        </li>
        <li>
          <strong>What you create</strong>: questions you ask, generated SQL, query history, saved
          queries, insights, dashboards, and monitors.
        </li>
        <li>
          <strong>AI usage records</strong>: token counts, timing, and status for each AI request,
          used to enforce daily limits and shown to you on the Usage page.
        </li>
        <li>
          <strong>Technical logs</strong>: request method, path, status, duration, a request id, and
          your account id. Logs do not record your password, tokens, or file contents. Your IP
          address is held briefly in server memory for rate limiting and is not written to logs or
          the database.
        </li>
      </ul>

      <h2>Why we use it</h2>
      <ul>
        <li>To run the service: sign you in, store and analyze your files, and show results.</li>
        <li>To keep it safe and fair: rate limits, daily AI limits, and abuse prevention.</li>
        <li>To fix problems, using logs and, if enabled, error reports.</li>
      </ul>
      <p>
        We do not sell your data, show ads, use analytics or tracking tools, or use your data to
        train AI models.
      </p>

      <h2>AI processing</h2>
      <p>
        When you use AI Analysis, natural-language to SQL, or monitor explanations, we send your
        question, your dataset’s column names and types, and small, truncated results of
        calculations on your data (which can include individual cell values) to{' '}
        <strong>Groq, Inc.</strong>, which runs the language model. Your whole file is not sent.
        Groq processes this under its own terms and privacy policy. Avoid uploading sensitive
        personal data (see Terms). AI-written answers are labelled with the checks that produced
        them, and can still be wrong.
      </p>

      <h2>Who processes your data</h2>
      <ul>
        <li>
          <strong>Render</strong>: hosts the application.
        </li>
        <li>
          <strong>Neon</strong>: hosts the database (account details, history, dashboards, usage
          records).
        </li>
        <li>
          <strong>Cloudflare R2</strong>: stores your uploaded files privately; they are never
          publicly accessible.
        </li>
        <li>
          <strong>Groq</strong>: AI processing, as described above.
        </li>
        <li>
          <strong>Sentry</strong>, only if error tracking is enabled: receives error reports with
          personal data stripped.
        </li>
      </ul>
      <p>
        These providers may store and process data in the United States and other countries.
      </p>

      <h2>Cookies and browser storage</h2>
      <p>
        PulseIQ does not use cookies. It keeps your sign-in session in your browser’s local
        storage, which is strictly necessary for the service to work. There are no analytics,
        advertising, or tracking technologies, so no consent banner is needed.
      </p>

      <h2>How long we keep it</h2>
      <ul>
        <li>Files and everything you create: until you delete them, or your account.</li>
        <li>Sign-in sessions: refresh tokens expire after 14 days and are revoked when you log out.</li>
        <li>Technical logs: for the hosting provider’s limited log-retention period.</li>
        <li>
          Database backups kept by our provider may hold deleted data for a short period until
          they expire.
        </li>
      </ul>

      <h2>Your choices and rights</h2>
      <ul>
        <li>
          <strong>Access and export</strong>: Settings → Export my data downloads everything stored
          about your account.
        </li>
        <li>
          <strong>Deletion</strong>: delete individual datasets at any time, or Settings → Delete
          account to remove your account, files, and everything linked to it.
        </li>
        <li>
          <strong>Correction and other requests</strong>: email {CONTACT}. Depending on where you
          live, you may have further rights (for example under the GDPR or India’s DPDP Act), and
          you can complain to your local data-protection authority.
        </li>
      </ul>

      <h2>Shared demo account</h2>
      <p>
        The public demo account is shared by everyone who uses it. Anything uploaded or asked
        there is visible to other visitors and may be removed at any time, so don’t put anything
        private in it.
      </p>

      <h2>Security</h2>
      <p>
        Connections are encrypted (HTTPS), passwords are hashed, files are stored privately, and
        every request is checked against your account so other users can’t see your data. No
        system is perfectly secure; please use a password you don’t use elsewhere.
      </p>

      <h2>Children</h2>
      <p>PulseIQ is not intended for anyone under 18, and we don’t knowingly collect their data.</p>

      <h2>Changes</h2>
      <p>
        If this policy changes, we’ll update the date at the top. Significant changes will be
        shown in the app.
      </p>
    </LegalLayout>
  )
}

export function TermsPage() {
  return (
    <LegalLayout title="Terms of Service">
      <p>
        These terms apply when you use PulseIQ. By creating an account or using the demo, you agree
        to them. If you don’t agree, please don’t use the service. Contact:{' '}
        <strong>{CONTACT}</strong>.
      </p>

      <h2>The service</h2>
      <p>
        PulseIQ is a personal, non-commercial project offered free of charge for evaluation and
        learning. It may change, have downtime, or be discontinued at any time. On the free
        hosting plan, the server sleeps when idle, so the first request can take about a minute.
      </p>

      <h2>Your account</h2>
      <ul>
        <li>You must be at least 18 and give a valid email address.</li>
        <li>Keep your password private; you’re responsible for activity on your account.</li>
        <li>One person per account. Automated sign-ups are not allowed.</li>
      </ul>

      <h2>Your data</h2>
      <ul>
        <li>
          You keep all rights to the files you upload and what you create. You give us permission
          to store and process them only to provide the service to you, including sending parts of
          them to our AI provider as described in the Privacy Policy.
        </li>
        <li>
          Only upload data you have the right to use. Don’t upload special-category or highly
          sensitive personal data (for example health, financial account, government ID, or
          biometric data) or anyone else’s personal data without a lawful basis.
        </li>
      </ul>

      <h2>Acceptable use</h2>
      <p>You agree not to:</p>
      <ul>
        <li>break the law or infringe anyone’s rights;</li>
        <li>
          probe, attack, or overload the service, or try to get around its limits, security, or
          access controls;
        </li>
        <li>access other users’ data, or scrape or resell the service;</li>
        <li>
          use the AI features to produce harmful content or try to make them ignore their
          instructions.
        </li>
      </ul>

      <h2>Limits</h2>
      <p>
        To keep the free service available to everyone, accounts have limits on the number of
        datasets, file size, request rate, and daily AI usage. We may change these limits.
      </p>

      <h2>AI-generated content</h2>
      <p>
        Answers, SQL, and explanations are generated with the help of an AI model. Numbers are
        computed by code and checked, but results can still be incomplete or wrong. They are not
        professional, financial, legal, or medical advice. Verify anything important before
        relying on it.
      </p>

      <h2>Ending your use</h2>
      <p>
        You can delete your account at any time in Settings. We may suspend or delete accounts
        that break these terms or put the service at risk.
      </p>

      <h2>No warranty and limitation of liability</h2>
      <p>
        PulseIQ is provided “as is” and “as available”, without warranties of any kind. Keep your
        own copies of your files; don’t rely on PulseIQ as your only copy. To the extent the law
        allows, we are not liable for any indirect or consequential loss, or loss of data, profits,
        or business, arising from your use of the service. Nothing in these terms limits liability
        that cannot be limited by law.
      </p>

      <h2>Changes</h2>
      <p>
        We may update these terms. The date at the top shows the latest version. Continuing to use
        PulseIQ after a change means you accept the updated terms.
      </p>
    </LegalLayout>
  )
}
