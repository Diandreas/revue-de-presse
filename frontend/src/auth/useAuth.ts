import { createContext, useContext } from 'react'
import type { MembershipRole, Organization, User, UserOrganization } from '../api/types'

/** Owner ou admin : peut inviter, gérer les catégories, payer… (mêmes règles que IsOrgAdmin). */
export function isAdminRole(role: MembershipRole | null | undefined) {
  return role === 'owner' || role === 'admin'
}

/** Mêmes règles que le backend (accounts.services.can_manage_role) : un owner gère tout le
 * monde, un admin seulement les membres. */
export function canManageRole(actorRole: MembershipRole | null | undefined, targetRole: MembershipRole) {
  if (actorRole === 'owner') return true
  return actorRole === 'admin' && targetRole === 'member'
}

export interface RegisterInput {
  email: string
  password: string
  full_name: string
  organization_name: string
  /** Numéro WhatsApp (un seul essai gratuit par numéro). */
  phone_number: string
  /** CGU/CGV et politique de confidentialité acceptées. */
  accept_terms: boolean
}

export interface RegisterResult {
  trialGranted: boolean
  /** Message à afficher si l'essai gratuit n'a pas été accordé. */
  trialNotice: string | null
}

export interface AuthContextValue {
  user: User | null
  organization: Organization | null
  /** Toutes les organisations (actives) de l'utilisateur, pour le sélecteur. */
  organizations: UserOrganization[]
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (input: RegisterInput) => Promise<RegisterResult>
  logout: () => Promise<void>
  /** Recharge les organisations de l'utilisateur et l'organisation courante. */
  refreshOrganization: () => Promise<void>
  /** Change d'organisation courante (les données affichées sont rechargées). */
  switchOrganization: (organizationId: string) => Promise<void>
  /** Met à jour l'utilisateur affiché (ex : après modification du nom). */
  setCurrentUser: (user: User) => void
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth doit être utilisé à l’intérieur de <AuthProvider>.')
  return ctx
}
