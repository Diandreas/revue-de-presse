import { useMutation } from '@tanstack/react-query'
import { apiClient, setAccessToken } from '../../api/client'
import type { User } from '../../api/types'

/** « Mon compte » : seul le nom est modifiable (l'e-mail sert d'identifiant). */
export function useUpdateProfile() {
  return useMutation({
    mutationFn: async (input: { full_name: string }) => {
      const res = await apiClient.patch<User>('/auth/me/', input)
      return res.data
    },
  })
}

/** Change le mot de passe : les autres appareils sont déconnectés, cette session reçoit un
 * nouveau jeton (le cookie de session est renouvelé par le serveur). */
export function useChangePassword() {
  return useMutation({
    mutationFn: async (input: { current_password: string; new_password: string }) => {
      const res = await apiClient.post<{ access: string }>('/auth/password/change/', input)
      setAccessToken(res.data.access)
    },
  })
}

export function useRequestPasswordReset() {
  return useMutation({
    mutationFn: async (email: string) => {
      const res = await apiClient.post<{ detail: string }>('/auth/password/reset/', { email })
      return res.data.detail
    },
  })
}

export function useConfirmPasswordReset() {
  return useMutation({
    mutationFn: async (input: { uid: string; token: string; new_password: string }) => {
      const res = await apiClient.post<{ detail: string }>('/auth/password/reset/confirm/', input)
      return res.data.detail
    },
  })
}

export function useLeaveOrganization() {
  return useMutation({
    mutationFn: async () => {
      await apiClient.post('/organizations/me/leave/')
    },
  })
}

export function useCloseOrganization() {
  return useMutation({
    mutationFn: async (input: { confirm_name: string; reason: string }) => {
      const res = await apiClient.post<{ detail: string }>('/organizations/me/close/', input)
      return res.data.detail
    },
  })
}

/** Télécharge l'export JSON des données de l'organisation (propriétaires). */
export function useExportOrganization() {
  return useMutation({
    mutationFn: async () => {
      const res = await apiClient.get<Blob>('/organizations/me/export/', { responseType: 'blob' })
      const disposition = String(res.headers['content-disposition'] ?? '')
      const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? 'revue-de-presse-export.json'
      const url = URL.createObjectURL(res.data)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    },
  })
}
