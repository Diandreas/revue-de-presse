import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { RequireAuth } from './auth/RequireAuth'
import { AppLayout } from './components/AppLayout'
import { FullPageLoader } from './components/ui'

// Une page = un fichier JS chargé à la demande : la page de connexion (première visite,
// souvent sur mobile) n'embarque ni l'éditeur d'envoi ni le rendu Markdown des revues.
const BillingPage = lazy(() => import('./routes/BillingPage'))
const CategoriesPage = lazy(() => import('./routes/CategoriesPage'))
const DashboardPage = lazy(() => import('./routes/DashboardPage'))
const InvitationAcceptPage = lazy(() => import('./routes/InvitationAcceptPage'))
const JobDetailPage = lazy(() => import('./routes/JobDetailPage'))
const LoginPage = lazy(() => import('./routes/LoginPage'))
const RegisterPage = lazy(() => import('./routes/RegisterPage'))
const SettingsPage = lazy(() => import('./routes/SettingsPage'))
const TeamPage = lazy(() => import('./routes/TeamPage'))
const UploadPage = lazy(() => import('./routes/UploadPage'))

export default function App() {
  return (
    <Suspense fallback={<FullPageLoader />}>
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
          {/* Retour de la page de paiement Stripe (success_url / cancel_url). */}
          <Route path="/billing/:outcome" element={<BillingPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}
