import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import {
  apiClient,
  getOrganizationId,
  refreshAccessToken,
  setAccessToken,
  setOrganizationId,
  setOrganizationLostHandler,
  setUnauthorizedHandler,
} from '../api/client'
import type { Organization, RegisterResponse, User, UserOrganization } from '../api/types'
import { AuthContext, type RegisterInput } from './useAuth'

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<User | null>(null)
  const [organization, setOrganization] = useState<Organization | null>(null)
  const [organizations, setOrganizations] = useState<UserOrganization[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const reloadingRef = useRef<Promise<void> | null>(null)

  /** Organisations de l'utilisateur, puis l'organisation courante : celle mémorisée dans le
   * navigateur s'il en est toujours membre, sinon la première de la liste. */
  const loadOrganizations = useCallback(async () => {
    const res = await apiClient.get<UserOrganization[]>('/organizations/')
    const chosen = res.data.find((item) => item.id === getOrganizationId()) ?? res.data[0] ?? null
    setOrganizationId(chosen?.id ?? null)
    setOrganizations(res.data)
    if (!chosen) {
      setOrganization(null)
      return
    }
    const org = await apiClient.get<Organization>('/organizations/me/')
    setOrganization(org.data)
  }, [])

  /** Recharge les organisations (un seul rechargement à la fois : plusieurs requêtes peuvent
   * échouer ensemble). Si l'organisation courante change (départ, retrait, fermeture), les
   * données en cache de l'ancienne sont rechargées. */
  const refreshOrganization = useCallback(async () => {
    const previousId = getOrganizationId()
    reloadingRef.current ??= loadOrganizations().finally(() => {
      reloadingRef.current = null
    })
    await reloadingRef.current
    const currentId = getOrganizationId()
    if (currentId === previousId) return
    // Plus aucune organisation : l'écran dédié remplace l'appli, inutile de recharger.
    if (currentId) void queryClient.resetQueries()
    else void queryClient.cancelQueries()
  }, [loadOrganizations, queryClient])

  const loadSession = useCallback(async () => {
    const me = await apiClient.get<User>('/auth/me/')
    setUser(me.data)
    await loadOrganizations()
  }, [loadOrganizations])

  useEffect(() => {
    let cancelled = false

    setUnauthorizedHandler(() => {
      setUser(null)
      setOrganization(null)
      setOrganizations([])
    })
    // Membre retiré, organisation fermée, ou organisation à choisir : on recharge la liste
    // (bascule sur une autre organisation, ou écran « aucune organisation »).
    setOrganizationLostHandler(() => {
      refreshOrganization().catch(() => undefined)
    })

    void (async () => {
      const token = await refreshAccessToken()
      if (token && !cancelled) {
        try {
          await loadSession()
        } catch {
          setAccessToken(null)
          setUser(null)
        }
      }
      if (!cancelled) setIsLoading(false)
    })()

    return () => {
      cancelled = true
    }
  }, [loadSession, refreshOrganization])

  const login = async (email: string, password: string) => {
    const res = await apiClient.post<{ access: string }>('/auth/token/', { email, password })
    setAccessToken(res.data.access)
    await loadSession()
  }

  const register = async (input: RegisterInput) => {
    const res = await apiClient.post<RegisterResponse>('/auth/register/', input)
    queryClient.clear()
    setAccessToken(res.data.access)
    setUser(res.data.user)
    // Le créateur de l'entreprise en est par définition le propriétaire.
    const created: Organization = { ...res.data.organization, my_role: 'owner' }
    setOrganizationId(created.id)
    setOrganizations([{ id: created.id, name: created.name, slug: created.slug, my_role: 'owner' }])
    setOrganization(created)
    return { trialGranted: res.data.trial_granted, trialNotice: res.data.trial_notice }
  }

  const logout = async () => {
    await apiClient.post('/auth/token/logout/').catch(() => undefined)
    setAccessToken(null)
    setUser(null)
    setOrganization(null)
    setOrganizations([])
    // Les données de cette session ne doivent pas apparaître au compte suivant.
    queryClient.clear()
  }

  const switchOrganization = async (organizationId: string) => {
    setOrganizationId(organizationId)
    await loadOrganizations()
    void queryClient.resetQueries()
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        organization,
        organizations,
        isLoading,
        login,
        register,
        logout,
        refreshOrganization,
        switchOrganization,
        setCurrentUser: setUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
