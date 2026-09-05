import { ProtectedRoute } from '@/components/layout/protected-route'
import { WorkspaceLayout } from '@/components/layout/workspace-layout'
import { AiAnalystPage } from '@/pages/ai-analyst-page'
import { DashboardDetailPage } from '@/pages/dashboard-detail-page'
import { DashboardsPage } from '@/pages/dashboards-page'
import { DatasetExplorerPage } from '@/pages/dataset-explorer-page'
import { DatasetsPage } from '@/pages/datasets-page'
import { InsightsPage } from '@/pages/insights-page'
import { LandingPage } from '@/pages/landing-page'
import { LoginPage } from '@/pages/login-page'
import { PlaceholderPage } from '@/pages/placeholder-page'
import { SignupPage } from '@/pages/signup-page'
import { WorkspaceHomePage } from '@/pages/workspace-home-page'
import { Settings } from 'lucide-react'
import { Navigate, Route, Routes } from 'react-router-dom'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<WorkspaceLayout />}>
          <Route path="/workspace" element={<WorkspaceHomePage />} />
          <Route path="/workspace/datasets" element={<DatasetsPage />} />
          <Route path="/workspace/datasets/:datasetId" element={<DatasetExplorerPage />} />
          <Route path="/workspace/dashboards" element={<DashboardsPage />} />
          <Route path="/workspace/dashboards/:dashboardId" element={<DashboardDetailPage />} />
          <Route path="/workspace/ai-analyst" element={<AiAnalystPage />} />
          <Route path="/workspace/insights" element={<InsightsPage />} />
          <Route
            path="/workspace/settings"
            element={
              <PlaceholderPage
                title="Settings"
                description="Account and workspace preferences."
                icon={Settings}
                emptyTitle="Nothing to configure yet"
                emptyDescription="Account and workspace settings will land here in a later phase."
              />
            }
          />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
