import { createContext, useContext } from 'react'
import type { Organization, User } from '../api/types'

export interface RegisterInput {
  email: string
  password: string
  full_name: string
  organization_name: string
}

export interface AuthContextValue {
  user: User | null
  organization: Organization | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (input: RegisterInput) => Promise<void>
  logout: () => Promise<void>
  refreshOrganization: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth doit être utilisé à l’intérieur de <AuthProvider>.')
  return ctx
}
