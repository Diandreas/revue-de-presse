import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../../api/client'
import type {
  Invitation,
  Membership,
  MembershipRole,
  Organization,
  Paginated,
  PasswordResetLink,
  SeatUsage,
} from '../../api/types'

/** Après un changement dans l'équipe : membres, invitations et places à jour. */
function invalidateTeam(queryClient: ReturnType<typeof useQueryClient>) {
  void queryClient.invalidateQueries({ queryKey: ['members'] })
  void queryClient.invalidateQueries({ queryKey: ['invitations'] })
  void queryClient.invalidateQueries({ queryKey: ['seats'] })
}

export function useMembers() {
  return useQuery({
    queryKey: ['members'],
    queryFn: async () => {
      const res = await apiClient.get<Paginated<Membership>>('/organizations/me/members/')
      return res.data.results
    },
  })
}

export function useInvitations(enabled: boolean) {
  return useQuery({
    queryKey: ['invitations'],
    queryFn: async () => {
      const res = await apiClient.get<Invitation[]>('/organizations/me/invitations/')
      return res.data
    },
    enabled,
  })
}

/** Places de la formule : membres + invitations en attente (cf. backend seat_usage). */
export function useSeats() {
  return useQuery({
    queryKey: ['seats'],
    queryFn: async () => {
      const res = await apiClient.get<SeatUsage>('/organizations/me/seats/')
      return res.data
    },
  })
}

export function useInviteMember() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (input: { email: string; role: MembershipRole }) => {
      const res = await apiClient.post<Invitation>('/organizations/me/invite/', input)
      return res.data
    },
    onSuccess: () => invalidateTeam(queryClient),
  })
}

export function useRevokeInvitation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (invitationId: string) => {
      await apiClient.delete(`/organizations/me/invitations/${invitationId}/`)
    },
    onSuccess: () => invalidateTeam(queryClient),
  })
}

export function useRemoveMember() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (membershipId: string) => {
      await apiClient.delete(`/organizations/me/members/${membershipId}/`)
    },
    onSuccess: () => invalidateTeam(queryClient),
  })
}

export function useChangeMemberRole() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (input: { membershipId: string; role: MembershipRole }) => {
      const res = await apiClient.patch<Membership>(`/organizations/me/members/${input.membershipId}/`, {
        role: input.role,
      })
      return res.data
    },
    onSuccess: () => invalidateTeam(queryClient),
  })
}

export function useTransferOwnership() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (membershipId: string) => {
      const res = await apiClient.post<Membership>('/organizations/me/transfer-ownership/', {
        membership_id: membershipId,
      })
      return res.data
    },
    onSuccess: () => invalidateTeam(queryClient),
  })
}

/** Lien de réinitialisation du mot de passe d'un membre, à lui transmettre (WhatsApp…). */
export function useMemberResetLink() {
  return useMutation({
    mutationFn: async (membershipId: string) => {
      const res = await apiClient.post<PasswordResetLink>(`/organizations/me/members/${membershipId}/password-reset-link/`)
      return res.data
    },
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
