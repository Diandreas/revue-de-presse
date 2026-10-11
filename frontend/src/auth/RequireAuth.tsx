import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { NoOrganizationScreen } from '../components/NoOrganizationScreen'
import { FullPageLoader } from '../components/ui'
import { useAuth } from './useAuth'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, organization, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <FullPageLoader label="Ouverture de votre espace…" />
      </div>
    )
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  if (!organization) {
    return <NoOrganizationScreen />
  }
  return <>{children}</>
}
