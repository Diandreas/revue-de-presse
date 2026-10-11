import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../../api/client'

/** Préférences e-mail de l'utilisateur connecté (GET / PATCH /api/notifications/preferences/). */
export interface NotificationPreferences {
  /** E-mail quand une revue lancée par l'utilisateur est prête ou a échoué. */
  email_review_updates: boolean
}

const QUERY_KEY = ['notification-preferences']

export function useNotificationPreferences() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: async () => {
      const res = await apiClient.get<NotificationPreferences>('/notifications/preferences/')
      return res.data
    },
  })
}

export function useUpdateNotificationPreferences() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (input: Partial<NotificationPreferences>) => {
      const res = await apiClient.patch<NotificationPreferences>('/notifications/preferences/', input)
      return res.data
    },
    onSuccess: (data) => queryClient.setQueryData(QUERY_KEY, data),
  })
}
