import { useState } from 'react'
import { extractErrorMessage } from '../api/client'
import type { MembershipRole } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { useInviteMember, useMembers, useRemoveMember } from '../features/organization/useOrganization'

const ROLE_LABELS: Record<MembershipRole, string> = {
  owner: 'Propriétaire',
  admin: 'Administrateur',
  member: 'Membre',
}

export default function TeamPage() {
  const { user } = useAuth()
  const { data: members, isLoading } = useMembers()
  const inviteMutation = useInviteMember()
  const removeMutation = useRemoveMember()

  const [email, setEmail] = useState('')
  const [role, setRole] = useState<MembershipRole>('member')
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [inviteSuccess, setInviteSuccess] = useState<string | null>(null)

  const handleInvite = async () => {
    setInviteError(null)
    setInviteSuccess(null)
    try {
      await inviteMutation.mutateAsync({ email, role })
      setInviteSuccess(`Invitation envoyée à ${email}.`)
      setEmail('')
    } catch (error) {
      setInviteError(extractErrorMessage(error, "Impossible d'envoyer l'invitation."))
    }
  }

  const handleRemove = async (membershipId: string) => {
    if (!window.confirm('Retirer ce membre de l’organisation ?')) return
    await removeMutation.mutateAsync(membershipId)
  }

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900">Équipe</h1>
      <p className="mt-1 text-sm text-slate-500">Gérez les membres de votre organisation et leurs rôles.</p>

      <div className="card mt-6">
        <h2 className="text-sm font-semibold text-slate-900">Inviter un membre</h2>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <div className="min-w-[220px] flex-1">
            <label className="label">Email</label>
            <input type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div>
            <label className="label">Rôle</label>
            <select className="input" value={role} onChange={(e) => setRole(e.target.value as MembershipRole)}>
              <option value="member">Membre</option>
              <option value="admin">Administrateur</option>
            </select>
          </div>
          <button
            type="button"
            className="btn-primary"
            disabled={!email || inviteMutation.isPending}
            onClick={() => void handleInvite()}
          >
            {inviteMutation.isPending ? 'Envoi…' : 'Inviter'}
          </button>
        </div>
        {inviteError && <p className="mt-2 text-sm text-red-600">{inviteError}</p>}
        {inviteSuccess && <p className="mt-2 text-sm text-green-700">{inviteSuccess}</p>}
      </div>

      <div className="mt-6 space-y-2">
        {isLoading && <p className="text-sm text-slate-500">Chargement…</p>}
        {members?.map((membership) => (
          <div key={membership.id} className="card flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-900">{membership.user.full_name || membership.user.email}</p>
              <p className="text-xs text-slate-500">{membership.user.email}</p>
            </div>
            <div className="flex items-center gap-3">
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700">
                {ROLE_LABELS[membership.role]}
              </span>
              {membership.user.email !== user?.email && (
                <button type="button" className="btn-danger" onClick={() => void handleRemove(membership.id)}>
                  Retirer
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
