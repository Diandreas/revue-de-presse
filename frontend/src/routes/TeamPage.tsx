import clsx from 'clsx'
import { useState, type FormEvent } from 'react'
import { extractErrorMessage } from '../api/client'
import type { Invitation, Membership, MembershipRole, PasswordResetLink, SeatUsage } from '../api/types'
import { canManageRole, isAdminRole, useAuth } from '../auth/useAuth'
import { Modal } from '../components/Modal'
import { useToast } from '../components/Toast'
import {
  ClockIcon,
  LinkIcon,
  LockIcon,
  MailIcon,
  SettingsIcon,
  ShieldIcon,
  StarIcon,
  TrashIcon,
  UserIcon,
  UsersIcon,
  XIcon,
  type IconComponent,
} from '../components/icons'
import { Alert, Avatar, CopyButton, EmptyState, PageHeader, ProgressBar, Segmented, Skeleton, Spinner } from '../components/ui'
import { WhatsAppButton } from '../components/WhatsAppButton'
import {
  useChangeMemberRole,
  useInvitations,
  useInviteMember,
  useMemberResetLink,
  useMembers,
  useRemoveMember,
  useRevokeInvitation,
  useSeats,
  useTransferOwnership,
} from '../features/organization/useOrganization'
import { formatDate, formatDateTime, formatRelative, plural } from '../lib/format'

const ROLE_META: Record<MembershipRole, { label: string; className: string; icon: IconComponent; description: string }> = {
  owner: {
    label: 'Propriétaire',
    className: 'bg-amber-50 text-amber-800 ring-1 ring-amber-200',
    icon: StarIcon,
    description: 'Tous les droits : administrateurs, transfert de propriété, export et fermeture de l’organisation.',
  },
  admin: {
    label: 'Administrateur',
    className: 'bg-brand-50 text-brand-700 ring-1 ring-brand-200',
    icon: ShieldIcon,
    description: 'Invite et gère les membres, gère les catégories de détection et l’abonnement.',
  },
  member: {
    label: 'Membre',
    className: 'bg-slate-100 text-slate-700 ring-1 ring-slate-200',
    icon: UserIcon,
    description: 'Envoie des documents, consulte et exporte les revues de l’équipe.',
  },
}

function RoleChip({ role }: { role: MembershipRole }) {
  const meta = ROLE_META[role]
  return (
    <span className={clsx('chip', meta.className)}>
      <meta.icon className="h-3 w-3" />
      {meta.label}
    </span>
  )
}

/** « x / y places » : membres + invitations en attente (même calcul que le serveur). */
function SeatsMeter({ seats }: { seats: SeatUsage }) {
  if (seats.limit === null) return null
  return (
    <div className="w-full max-w-[240px]">
      <div className="mb-1.5 flex justify-between text-xs">
        <span className="font-medium text-slate-600">Places utilisées</span>
        <span className="text-slate-500 tabular-nums">
          {seats.used} / {seats.limit}
        </span>
      </div>
      <ProgressBar
        size="sm"
        percent={(seats.used / Math.max(1, seats.limit)) * 100}
        tone={seats.used >= seats.limit ? 'amber' : 'brand'}
      />
      {seats.pending_invitations > 0 && (
        <p className="mt-1 text-[11px] text-slate-400">
          dont {plural(seats.pending_invitations, 'invitation en attente', 'invitations en attente')}
        </p>
      )}
    </div>
  )
}

function InviteCard({ myRole, seats }: { myRole: MembershipRole | null | undefined; seats: SeatUsage | undefined }) {
  const toast = useToast()
  const { organization } = useAuth()
  const inviteMutation = useInviteMember()
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<'member' | 'admin'>('member')
  const [error, setError] = useState<string | null>(null)
  const [lastInvitation, setLastInvitation] = useState<Invitation | null>(null)
  // Seul un propriétaire peut inviter un administrateur (règle appliquée aussi par le serveur).
  const canInviteAdmins = myRole === 'owner'
  const seatsFull = seats?.available === 0

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) {
      setError('Saisissez une adresse e-mail valide.')
      return
    }
    try {
      const invitation = await inviteMutation.mutateAsync({
        email: email.trim(),
        role: canInviteAdmins ? role : 'member',
      })
      setLastInvitation(invitation)
      setEmail('')
      toast.success(`Invitation créée pour ${invitation.email}.`)
    } catch (err) {
      setError(extractErrorMessage(err, 'Impossible de créer l’invitation.'))
    }
  }

  return (
    <section className="card">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
          <MailIcon className="h-5 w-5" />
        </span>
        <div>
          <h2 className="section-title">Inviter un collègue</h2>
          <p className="text-xs text-slate-500">Il rejoindra votre espace en un clic.</p>
        </div>
      </div>

      {seatsFull && (
        <Alert
          tone="warning"
          title="Toutes les places sont utilisées"
          className="mt-5"
          action={
            <WhatsAppButton
              topic="billing"
              organizationName={organization?.name}
              label="Ajouter des places sur WhatsApp"
              className="w-full"
            />
          }
        >
          Votre formule compte {plural(seats?.limit ?? 0, 'place')}, invitations en attente comprises. Retirez un membre
          ou annulez une invitation, ou contactez-nous pour en ajouter.
        </Alert>
      )}

      <form className="mt-5 space-y-4" onSubmit={(e) => void handleSubmit(e)} noValidate>
        <div>
          <label className="label" htmlFor="invite-email">
            Adresse e-mail
          </label>
          <input
            id="invite-email"
            type="email"
            autoComplete="off"
            className="input"
            placeholder="prenom.nom@entreprise.cm"
            value={email}
            disabled={seatsFull}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        {canInviteAdmins ? (
          <div>
            <span className="label">Rôle</span>
            <Segmented
              className="w-full"
              value={role}
              onChange={setRole}
              options={[
                { value: 'member', label: 'Membre' },
                { value: 'admin', label: 'Administrateur' },
              ]}
            />
            <p className="field-hint">{ROLE_META[role].description}</p>
          </div>
        ) : (
          <p className="field-hint">
            Vous invitez en tant que <strong>membre</strong>. Seul un propriétaire peut inviter un administrateur.
          </p>
        )}
        {error && <Alert tone="danger">{error}</Alert>}
        <button type="submit" className="btn-primary w-full" disabled={inviteMutation.isPending || !email || seatsFull}>
          {inviteMutation.isPending ? <Spinner /> : <MailIcon className="h-4 w-4" />}
          Créer l’invitation
        </button>
      </form>

      {lastInvitation && (
        <div className="mt-5 rounded-2xl border border-emerald-200 bg-emerald-50/70 p-4 animate-fade-in">
          <p className="text-sm font-semibold text-emerald-900">Invitation prête pour {lastInvitation.email}</p>
          <p className="mt-1 text-xs leading-relaxed text-emerald-800">
            Un e-mail est envoyé si la messagerie est configurée. Dans tous les cas, partagez ce lien (WhatsApp,
            e-mail…) : il est valable jusqu’au {formatDate(lastInvitation.expires_at)}.
          </p>
          <div className="mt-3 flex items-center gap-2">
            <code className="min-w-0 flex-1 truncate rounded-lg bg-white px-2.5 py-1.5 text-xs text-slate-600 ring-1 ring-emerald-200">
              {lastInvitation.accept_url}
            </code>
            <CopyButton text={lastInvitation.accept_url} label="Copier" />
          </div>
        </div>
      )}
    </section>
  )
}

function PendingInvitations({ myRole }: { myRole: MembershipRole | null | undefined }) {
  const toast = useToast()
  const { data: invitations, isLoading } = useInvitations(true)
  const revokeMutation = useRevokeInvitation()

  const revoke = async (invitation: Invitation) => {
    try {
      await revokeMutation.mutateAsync(invitation.id)
      toast.info(`Invitation de ${invitation.email} annulée.`)
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Impossible d’annuler cette invitation.'))
    }
  }

  return (
    <section className="card !p-0">
      <div className="flex items-center justify-between gap-3 px-5 pt-5 pb-3 sm:px-6">
        <div>
          <h2 className="section-title">Invitations en attente</h2>
          <p className="text-xs text-slate-500">
            Copiez le lien pour le renvoyer, ou annulez l’invitation. Chaque invitation réserve une place.
          </p>
        </div>
        {invitations && invitations.length > 0 && (
          <span className="chip bg-amber-50 text-amber-800 ring-1 ring-amber-200">{invitations.length}</span>
        )}
      </div>
      {isLoading && (
        <div className="space-y-2 px-5 pb-5 sm:px-6">
          <Skeleton className="h-14 rounded-xl" />
        </div>
      )}
      {!isLoading && invitations?.length === 0 && (
        <p className="px-5 pb-5 text-sm text-slate-500 sm:px-6">Aucune invitation en attente.</p>
      )}
      {invitations && invitations.length > 0 && (
        <ul className="divide-y divide-slate-100 border-t border-slate-100">
          {invitations.map((invitation) => {
            const expired = new Date(invitation.expires_at).getTime() < Date.now()
            return (
              <li key={invitation.id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:px-6">
                <div className="flex min-w-0 flex-1 items-center gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-dashed border-slate-300 text-slate-400">
                    <MailIcon className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-900">{invitation.email}</p>
                    <p
                      className={clsx(
                        'mt-0.5 flex items-center gap-1 text-xs',
                        expired ? 'text-red-600' : 'text-slate-500',
                      )}
                    >
                      <ClockIcon className="h-3.5 w-3.5" />
                      {expired ? 'Expirée — réinvitez pour la renouveler' : `Expire ${formatRelative(invitation.expires_at)}`}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 pl-[52px] sm:pl-0">
                  <RoleChip role={invitation.role} />
                  <CopyButton text={invitation.accept_url} label="Lien" />
                  {canManageRole(myRole, invitation.role) && (
                    <button
                      type="button"
                      className="btn-icon text-slate-400 hover:bg-red-50 hover:text-red-600"
                      aria-label={`Annuler l’invitation de ${invitation.email}`}
                      title="Annuler l’invitation"
                      disabled={revokeMutation.isPending && revokeMutation.variables === invitation.id}
                      onClick={() => void revoke(invitation)}
                    >
                      <XIcon className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

type PendingConfirmation = 'transfer' | 'remove' | null

/** Gestion d'un membre : rôle (propriétaire), lien de réinitialisation du mot de passe,
 * transfert de propriété (propriétaire) et retrait de l'équipe. */
function ManageMemberModal({
  membership,
  myRole,
  onClose,
}: {
  membership: Membership
  myRole: MembershipRole | null | undefined
  onClose: () => void
}) {
  const toast = useToast()
  const { refreshOrganization } = useAuth()
  const changeRole = useChangeMemberRole()
  const resetLink = useMemberResetLink()
  const transfer = useTransferOwnership()
  const removeMember = useRemoveMember()
  const [role, setRole] = useState<MembershipRole>(membership.role)
  const [link, setLink] = useState<PasswordResetLink | null>(null)
  const [confirming, setConfirming] = useState<PendingConfirmation>(null)
  const [error, setError] = useState<string | null>(null)
  const name = membership.user.full_name || membership.user.email
  const isOwner = myRole === 'owner'

  const run = async (action: () => Promise<unknown>, success: string, closeAfter = true) => {
    setError(null)
    try {
      await action()
      toast.success(success)
      if (closeAfter) onClose()
    } catch (err) {
      setError(extractErrorMessage(err, 'Action impossible pour le moment.'))
      setConfirming(null)
    }
  }

  const saveRole = () =>
    run(
      () => changeRole.mutateAsync({ membershipId: membership.id, role }),
      `${name} est maintenant ${ROLE_META[role].label.toLowerCase()}.`,
    )

  const generateLink = () =>
    run(
      async () => setLink(await resetLink.mutateAsync(membership.id)),
      'Lien de réinitialisation prêt à être transmis.',
      false,
    )

  const transferOwnership = () =>
    run(async () => {
      await transfer.mutateAsync(membership.id)
      await refreshOrganization()
    }, `${name} est le nouveau propriétaire. Vous êtes désormais administrateur.`)

  const remove = () => run(() => removeMember.mutateAsync(membership.id), `${name} a été retiré de l’équipe.`)

  return (
    <Modal open onClose={onClose} title={`Gérer ${name}`} description={membership.user.email}>
      <div className="space-y-6">
        {error && <Alert tone="danger">{error}</Alert>}

        {isOwner && (
          <section>
            <h3 className="text-sm font-semibold text-slate-900">Rôle</h3>
            <Segmented
              className="mt-2 w-full"
              value={role}
              onChange={setRole}
              options={[
                { value: 'member', label: 'Membre' },
                { value: 'admin', label: 'Admin' },
                { value: 'owner', label: 'Propriétaire' },
              ]}
            />
            <p className="field-hint">{ROLE_META[role].description}</p>
            <button
              type="button"
              className="btn-primary btn-sm mt-3"
              disabled={role === membership.role || changeRole.isPending}
              onClick={() => void saveRole()}
            >
              {changeRole.isPending ? <Spinner /> : null}
              Enregistrer le rôle
            </button>
          </section>
        )}

        <section>
          <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <LockIcon className="h-4 w-4 text-slate-400" /> Mot de passe oublié
          </h3>
          <p className="mt-1 text-[13px] leading-relaxed text-slate-600">
            Générez un lien à usage unique et transmettez-le à {name} (WhatsApp, e-mail…) pour qu’il choisisse un
            nouveau mot de passe. Ne le partagez avec personne d’autre.
          </p>
          {link ? (
            <div className="mt-3 rounded-2xl border border-emerald-200 bg-emerald-50/70 p-3">
              <div className="flex items-center gap-2">
                <code className="min-w-0 flex-1 truncate rounded-lg bg-white px-2.5 py-1.5 text-xs text-slate-600 ring-1 ring-emerald-200">
                  {link.reset_url}
                </code>
                <CopyButton text={link.reset_url} label="Copier" />
              </div>
              <p className="mt-2 text-xs text-emerald-800">Valable jusqu’au {formatDateTime(link.expires_at)}.</p>
            </div>
          ) : (
            <button
              type="button"
              className="btn-secondary btn-sm mt-3"
              disabled={resetLink.isPending}
              onClick={() => void generateLink()}
            >
              {resetLink.isPending ? <Spinner /> : <LinkIcon className="h-4 w-4" />}
              Générer un lien de réinitialisation
            </button>
          )}
        </section>

        {isOwner && membership.role !== 'owner' && (
          <section>
            <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <StarIcon className="h-4 w-4 text-amber-500" /> Transférer la propriété
            </h3>
            <p className="mt-1 text-[13px] leading-relaxed text-slate-600">
              {name} deviendra propriétaire de l’organisation ; vous resterez administrateur.
            </p>
            <button
              type="button"
              className={clsx('btn-sm mt-3', confirming === 'transfer' ? 'btn-primary' : 'btn-secondary')}
              disabled={transfer.isPending}
              onClick={() => (confirming === 'transfer' ? void transferOwnership() : setConfirming('transfer'))}
            >
              {transfer.isPending ? <Spinner /> : <StarIcon className="h-4 w-4" />}
              {confirming === 'transfer' ? 'Confirmer le transfert' : 'Transférer la propriété'}
            </button>
          </section>
        )}

        <section className="border-t border-slate-100 pt-5">
          <h3 className="text-sm font-semibold text-slate-900">Retirer de l’équipe</h3>
          <p className="mt-1 text-[13px] leading-relaxed text-slate-600">
            {name} n’aura plus accès aux revues de l’organisation. Ses revues et documents restent disponibles pour
            l’équipe.
          </p>
          <button
            type="button"
            className="btn-danger btn-sm mt-3"
            disabled={removeMember.isPending}
            onClick={() => (confirming === 'remove' ? void remove() : setConfirming('remove'))}
          >
            {removeMember.isPending ? <Spinner /> : <TrashIcon className="h-4 w-4" />}
            {confirming === 'remove' ? 'Confirmer le retrait' : 'Retirer de l’équipe'}
          </button>
        </section>
      </div>
    </Modal>
  )
}

export default function TeamPage() {
  const { user, organization } = useAuth()
  const myRole = organization?.my_role
  const isAdmin = isAdminRole(myRole)
  const { data: members, isLoading } = useMembers()
  const { data: seats } = useSeats()
  const [managed, setManaged] = useState<Membership | null>(null)

  const memberCount = members?.length ?? 0

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Configuration"
        title="Équipe"
        subtitle="Toute l’équipe partage les mêmes revues, documents et catégories de détection."
      />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          <section className="card !p-0">
            <div className="flex flex-wrap items-end justify-between gap-4 px-5 pt-5 pb-4 sm:px-6">
              <div>
                <h2 className="section-title">Membres</h2>
                <p className="text-xs text-slate-500">
                  {isLoading ? 'Chargement…' : plural(memberCount, 'personne', 'personnes')} dans {organization?.name}
                </p>
              </div>
              {seats && <SeatsMeter seats={seats} />}
            </div>

            <ul className="divide-y divide-slate-100 border-t border-slate-100">
              {isLoading &&
                [0, 1, 2].map((i) => (
                  <li key={i} className="px-5 py-4 sm:px-6">
                    <Skeleton className="h-10 rounded-xl" />
                  </li>
                ))}
              {members?.map((membership) => {
                const isSelf = membership.user.id === user?.id
                const name = membership.user.full_name || membership.user.email
                return (
                  <li key={membership.id} className="flex items-center gap-3 px-5 py-4 sm:px-6">
                    <Avatar name={name} />
                    <div className="min-w-0 flex-1">
                      <p className="flex items-center gap-2 truncate text-sm font-semibold text-slate-900">
                        <span className="truncate">{name}</span>
                        {isSelf && <span className="chip bg-slate-900 text-white">Vous</span>}
                      </p>
                      <p className="truncate text-xs text-slate-500">
                        {membership.user.email}
                        <span className="hidden sm:inline"> · membre depuis le {formatDate(membership.created_at)}</span>
                      </p>
                    </div>
                    <RoleChip role={membership.role} />
                    {!isSelf && canManageRole(myRole, membership.role) && (
                      <button
                        type="button"
                        className="btn-icon text-slate-400"
                        aria-label={`Gérer ${name}`}
                        title="Rôle, mot de passe, retrait…"
                        onClick={() => setManaged(membership)}
                      >
                        <SettingsIcon className="h-4 w-4" />
                      </button>
                    )}
                  </li>
                )
              })}
            </ul>
            {!isLoading && memberCount <= 1 && (
              <div className="border-t border-slate-100">
                <EmptyState
                  icon={UsersIcon}
                  title="Travaillez à plusieurs"
                  description="Invitez les membres de votre cellule de communication : chacun pourra photographier les journaux et lancer des revues."
                  className="!py-8"
                />
              </div>
            )}
          </section>

          {isAdmin && <PendingInvitations myRole={myRole} />}
        </div>

        <aside className="space-y-6 lg:sticky lg:top-6">
          {isAdmin ? (
            <InviteCard myRole={myRole} seats={seats} />
          ) : (
            <Alert tone="info" title="Inviter un collègue">
              Seuls les propriétaires et administrateurs peuvent inviter de nouveaux membres. Demandez-leur un lien
              d’invitation.
            </Alert>
          )}

          <section className="card">
            <h2 className="flex items-center gap-2 section-title">
              <LinkIcon className="h-4 w-4 text-slate-400" /> Rôles
            </h2>
            <ul className="mt-4 space-y-4">
              {(Object.keys(ROLE_META) as MembershipRole[]).map((role) => (
                <li key={role}>
                  <RoleChip role={role} />
                  <p className="mt-1.5 text-[13px] leading-relaxed text-slate-600">{ROLE_META[role].description}</p>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>

      {managed && <ManageMemberModal membership={managed} myRole={myRole} onClose={() => setManaged(null)} />}
    </div>
  )
}
