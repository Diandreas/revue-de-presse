import { Navigate, Route, Routes } from 'react-router-dom'
import { RequireAuth } from './auth/RequireAuth'
import { AppLayout } from './components/AppLayout'
import BillingPage from './routes/BillingPage'
import CategoriesPage from './routes/CategoriesPage'
import DashboardPage from './routes/DashboardPage'
import InvitationAcceptPage from './routes/InvitationAcceptPage'
import JobDetailPage from './routes/JobDetailPage'
import LoginPage from './routes/LoginPage'
import RegisterPage from './routes/RegisterPage'
import SettingsPage from './routes/SettingsPage'
import TeamPage from './routes/TeamPage'
import UploadPage from './routes/UploadPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/invitations/:token/accept" element={<InvitationAcceptPage />} />

      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/jobs/:jobId" element={<JobDetailPage />} />
        <Route path="/categories" element={<CategoriesPage />} />
        <Route path="/team" element={<TeamPage />} />
        <Route path="/billing" element={<BillingPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
