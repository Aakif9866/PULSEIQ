import { ProtectedRoute } from '@/components/layout/protected-route'
import { LandingPage } from '@/pages/landing-page'
import { type ComponentType, lazy, Suspense, useEffect } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'

// The landing page is eager (it's the first paint for most visitors);
// everything else loads on demand, so charts and the workspace don't
// weigh down the first visit.
function page<K extends string>(load: () => Promise<Record<K, ComponentType>>, name: K) {
  return lazy(() => load().then((m) => ({ default: m[name] })))
}

const LoginPage = page(() => import('@/pages/login-page'), 'LoginPage')
const SignupPage = page(() => import('@/pages/signup-page'), 'SignupPage')
const PrivacyPage = page(() => import('@/pages/legal-pages'), 'PrivacyPage')
const TermsPage = page(() => import('@/pages/legal-pages'), 'TermsPage')
const NotFoundPage = page(() => import('@/pages/not-found-page'), 'NotFoundPage')
const WorkspaceLayout = page(
  () => import('@/components/layout/workspace-layout'),
  'WorkspaceLayout',
)
const WorkspaceHomePage = page(() => import('@/pages/workspace-home-page'), 'WorkspaceHomePage')
const DatasetsPage = page(() => import('@/pages/datasets-page'), 'DatasetsPage')
const DatasetExplorerPage = page(
  () => import('@/pages/dataset-explorer-page'),
  'DatasetExplorerPage',
)
const DashboardsPage = page(() => import('@/pages/dashboards-page'), 'DashboardsPage')
const DashboardDetailPage = page(
  () => import('@/pages/dashboard-detail-page'),
  'DashboardDetailPage',
)
const AiAnalystPage = page(() => import('@/pages/ai-analyst-page'), 'AiAnalystPage')
const InsightsPage = page(() => import('@/pages/insights-page'), 'InsightsPage')
const MonitorsPage = page(() => import('@/pages/monitors-page'), 'MonitorsPage')
const MonitorDetailPage = page(() => import('@/pages/monitor-detail-page'), 'MonitorDetailPage')
const UsagePage = page(() => import('@/pages/usage-page'), 'UsagePage')
const SettingsPage = page(() => import('@/pages/settings-page'), 'SettingsPage')

const SITE = 'PulseIQ'
const TITLES: [RegExp, string][] = [
  [/^\/$/, `${SITE} — AI data analyst with verified answers`],
  [/^\/login$/, `Log in · ${SITE}`],
  [/^\/signup$/, `Sign up · ${SITE}`],
  [/^\/privacy$/, `Privacy Policy · ${SITE}`],
  [/^\/terms$/, `Terms of Service · ${SITE}`],
  [/^\/workspace$/, `Workspace · ${SITE}`],
  [/^\/workspace\/datasets\/.+/, `Dataset · ${SITE}`],
  [/^\/workspace\/datasets$/, `Datasets · ${SITE}`],
  [/^\/workspace\/dashboards\/.+/, `Dashboard · ${SITE}`],
  [/^\/workspace\/dashboards$/, `Dashboards · ${SITE}`],
  [/^\/workspace\/ai-analyst$/, `AI Analysis · ${SITE}`],
  [/^\/workspace\/insights$/, `Saved Insights · ${SITE}`],
  [/^\/workspace\/monitors\/.+/, `Monitor · ${SITE}`],
  [/^\/workspace\/monitors$/, `Monitors · ${SITE}`],
  [/^\/workspace\/usage$/, `Usage · ${SITE}`],
  [/^\/workspace\/settings$/, `Settings · ${SITE}`],
]

function DocumentTitle() {
  const { pathname } = useLocation()
  useEffect(() => {
    const title = TITLES.find(([re]) => re.test(pathname))?.[1]
    document.title = title ?? `Page not found · ${SITE}`
    // The static host answers unknown paths with 200 (SPA rewrite), so
    // the not-found page tells crawlers itself not to index it.
    document.querySelector('meta[name="robots"]')?.remove()
    if (!title) {
      const robots = document.createElement('meta')
      robots.name = 'robots'
      robots.content = 'noindex'
      document.head.append(robots)
    }
    document
      .querySelector('link[rel="canonical"]')
      ?.setAttribute('href', `${window.location.origin}${pathname}`)
  }, [pathname])
  return null
}

function PageFallback() {
  return (
    <div role="status" className="p-6 text-xs text-[var(--color-fg-muted)]">
      Loading…
    </div>
  )
}

export default function App() {
  return (
    <>
      <DocumentTitle />
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/terms" element={<TermsPage />} />

          <Route element={<ProtectedRoute />}>
            <Route element={<WorkspaceLayout />}>
              <Route path="/workspace" element={<WorkspaceHomePage />} />
              <Route path="/workspace/datasets" element={<DatasetsPage />} />
              <Route path="/workspace/datasets/:datasetId" element={<DatasetExplorerPage />} />
              <Route path="/workspace/dashboards" element={<DashboardsPage />} />
              <Route path="/workspace/dashboards/:dashboardId" element={<DashboardDetailPage />} />
              <Route path="/workspace/ai-analyst" element={<AiAnalystPage />} />
              <Route path="/workspace/insights" element={<InsightsPage />} />
              <Route path="/workspace/monitors" element={<MonitorsPage />} />
              <Route path="/workspace/monitors/:monitorId" element={<MonitorDetailPage />} />
              <Route path="/workspace/usage" element={<UsagePage />} />
              <Route path="/workspace/settings" element={<SettingsPage />} />
            </Route>
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </>
  )
}
