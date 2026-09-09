import { useEffect, useState, type ReactNode } from 'react'
import { apiClient, refreshAccessToken, setAccessToken, setUnauthorizedHandler } from '../api/client'
import type { Organization, User } from '../api/types'
import { AuthContext, type RegisterInput } from './useAuth'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [organization, setOrganization] = useState<Organization | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const loadSession = async () => {
    const me = await apiClient.get<User>('/auth/me/')
    setUser(me.data)
    const org = await apiClient.get<Organization>('/organizations/me/')
    setOrganization(org.data)
  }

  useEffect(() => {
    let cancelled = false

    setUnauthorizedHandler(() => {
      setUser(null)
      setOrganization(null)
    })

    void (async () => {
      const token = await refreshAccessToken()
      if (token && !cancelled) {
        try {
          await loadSession()
        } catch {
          setAccessToken(null)
        }
      }
      if (!cancelled) setIsLoading(false)
    })()

    return () => {
      cancelled = true
    }
  }, [])

  const login = async (email: string, password: string) => {
    const res = await apiClient.post<{ access: string }>('/auth/token/', { email, password })
    setAccessToken(res.data.access)
    await loadSession()
  }

  const register = async (input: RegisterInput) => {
    const res = await apiClient.post<{ access: string; user: User; organization: Organization }>(
      '/auth/register/',
      input,
    )
    setAccessToken(res.data.access)
    setUser(res.data.user)
    setOrganization(res.data.organization)
  }

  const logout = async () => {
    await apiClient.post('/auth/token/logout/').catch(() => undefined)
    setAccessToken(null)
    setUser(null)
    setOrganization(null)
  }

  const refreshOrganization = async () => {
    const org = await apiClient.get<Organization>('/organizations/me/')
    setOrganization(org.data)
  }

  return (
    <AuthContext.Provider value={{ user, organization, isLoading, login, register, logout, refreshOrganization }}>
      {children}
    </AuthContext.Provider>
  )
}
