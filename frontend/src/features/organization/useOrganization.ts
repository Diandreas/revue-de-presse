import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../../api/client'
import type { Membership, MembershipRole, Organization, Paginated } from '../../api/types'

export function useMembers() {
  return useQuery({
    queryKey: ['members'],
    queryFn: async () => {
      const res = await apiClient.get<Paginated<Membership>>('/organizations/me/members/')
      return res.data.results
    },
  })
}

export function useInviteMember() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (input: { email: string; role: MembershipRole }) => {
      const res = await apiClient.post('/organizations/me/invite/', input)
      return res.data
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['members'] }),
  })
}

export function useRemoveMember() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (membershipId: string) => {
      await apiClient.delete(`/organizations/me/members/${membershipId}/`)
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['members'] }),
  })
}

export function useUpdateOrganization() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (input: Partial<Pick<Organization, 'name'>>) => {
      const res = await apiClient.patch<Organization>('/organizations/me/', input)
      return res.data
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['organization'] }),
  })
}
