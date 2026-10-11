import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { z } from 'zod'
import { apiClient, extractErrorMessage, setAccessToken } from '../api/client'
import type { Membership, User } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { AuthShell } from '../components/AuthShell'
import { ArrowRightIcon, MailIcon, UsersIcon } from '../components/icons'
import { PasswordInput } from '../components/PasswordInput'
import { TermsCheckbox } from '../components/TermsCheckbox'
import { Alert, FullPageLoader, Spinner } from '../components/ui'

interface InvitationPreview {
  email: string
  role: string
  organization_name: string
}

const ROLE_LABELS: Record<string, string> = { owner: 'propriétaire', admin: 'administrateur', member: 'membre' }

const registerSchema = z.object({
  full_name: z.string().trim().min(2, 'Votre nom est requis.'),
  password: z.string().min(10, 'Au moins 10 caractères.'),
  accept_terms: z.boolean().refine((value) => value, 'Vous devez accepter les conditions pour créer votre compte.'),
})

type RegisterFormValues = z.infer<typeof registerSchema>

export default function InvitationAcceptPage() {
  const { token } = useParams<{ token: string }>()
  const { user, isLoading, refreshOrganization, switchOrganization } = useAuth()
  const navigate = useNavigate()
  const [actionError, setActionError] = useState<string | null>(null)

  const previewQuery = useQuery({
    queryKey: ['invitation-preview', token],
    queryFn: async () => {
      const res = await apiClient.get<InvitationPreview>(`/auth/invitations/${token}/`)
      return res.data
    },
    enabled: Boolean(token),
    retry: false,
  })

  const acceptMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<Membership>(`/auth/invitations/${token}/accept/`)
      return res.data
    },
    onSuccess: async (membership) => {
      // Le compte peut déjà appartenir à une autre organisation : on bascule sur celle rejointe.
      if (membership.organization) await switchOrganization(membership.organization)
      else await refreshOrganization()
      navigate('/dashboard', { replace: true })
    },
    onError: (error) => setActionError(extractErrorMessage(error, 'Impossible d’accepter cette invitation.')),
  })

  const registerMutation = useMutation({
    mutationFn: async (values: RegisterFormValues) => {
      const res = await apiClient.post<{ access: string; user: User; membership: Membership }>(
        `/auth/invitations/${token}/register/`,
        values,
      )
      return res.data
    },
    onSuccess: (data) => {
      setAccessToken(data.access)
      window.location.href = '/dashboard'
    },
    onError: (error) => setActionError(extractErrorMessage(error, 'Impossible de créer le compte.')),
  })

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormValues>({ resolver: zodResolver(registerSchema), defaultValues: { accept_terms: false } })

  if (isLoading || previewQuery.isLoading) {
    return <FullPageLoader />
  }

  if (previewQuery.isError || !previewQuery.data) {
    return (
      <AuthShell
        title="Invitation introuvable"
        subtitle="Ce lien d’invitation est invalide, a expiré (7 jours) ou a déjà été utilisé. Demandez un nouveau lien à l’administrateur de votre organisation."
      >
        <Link to="/login" className="btn-primary btn-lg w-full">
          Se connecter
        </Link>
      </AuthShell>
    )
  }

  const preview = previewQuery.data
  const roleLabel = ROLE_LABELS[preview.role] ?? preview.role
  const badge = (
    <span className="chip bg-brand-50 py-1 text-brand-700 ring-1 ring-brand-200">
      <UsersIcon className="h-3.5 w-3.5" />
      Invitation en tant que {roleLabel}
    </span>
  )

  if (user) {
    const emailMatches = user.email.toLowerCase() === preview.email.toLowerCase()
    return (
      <AuthShell title={`Rejoindre ${preview.organization_name}`} subtitle={`Connecté en tant que ${user.email}.`} badge={badge}>
        {emailMatches ? (
          <div className="space-y-4">
            {actionError && <Alert tone="danger">{actionError}</Alert>}
            <button
              type="button"
              className="btn-primary btn-lg w-full"
              disabled={acceptMutation.isPending}
              onClick={() => acceptMutation.mutate()}
            >
              {acceptMutation.isPending ? <Spinner /> : null}
              {acceptMutation.isPending ? 'Validation…' : 'Accepter l’invitation'}
            </button>
          </div>
        ) : (
          <Alert tone="warning" title="Ce n’est pas le bon compte">
            Cette invitation a été envoyée à <strong>{preview.email}</strong>. Déconnectez-vous puis reconnectez-vous
            avec ce compte.
          </Alert>
        )}
      </AuthShell>
    )
  }

  return (
    <AuthShell
      title={`Rejoindre ${preview.organization_name}`}
      subtitle={
        <span className="inline-flex items-center gap-1.5">
          <MailIcon className="h-4 w-4" /> Invitation envoyée à {preview.email}
        </span>
      }
      badge={badge}
      footer={
        <>
          Vous avez déjà un compte ?{' '}
          <Link
            to="/login"
            state={{ from: { pathname: `/invitations/${token}/accept` } }}
            className="font-semibold text-brand-600 hover:text-brand-700"
          >
            Se connecter
          </Link>
        </>
      }
    >
      <form
        className="space-y-4"
        noValidate
        onSubmit={(e) => void handleSubmit((values) => registerMutation.mutate(values))(e)}
      >
        <div>
          <label className="label" htmlFor="inv-name">
            Votre nom complet
          </label>
          <input
            id="inv-name"
            autoComplete="name"
            className={clsx('input', errors.full_name && 'input-error')}
            {...register('full_name')}
          />
          {errors.full_name && <p className="field-error">{errors.full_name.message}</p>}
        </div>
        <div>
          <label className="label" htmlFor="inv-password">
            Choisissez un mot de passe
          </label>
          <PasswordInput
            id="inv-password"
            autoComplete="new-password"
            invalid={Boolean(errors.password)}
            {...register('password')}
          />
          {errors.password ? (
            <p className="field-error">{errors.password.message}</p>
          ) : (
            <p className="field-hint">10 caractères minimum.</p>
          )}
        </div>
        <TermsCheckbox id="inv-terms" error={errors.accept_terms?.message} {...register('accept_terms')} />
        {actionError && <Alert tone="danger">{actionError}</Alert>}
        <button type="submit" disabled={registerMutation.isPending} className="btn-primary btn-lg w-full">
          {registerMutation.isPending ? <Spinner /> : null}
          {registerMutation.isPending ? 'Création…' : 'Créer mon compte et rejoindre'}
          {!registerMutation.isPending && <ArrowRightIcon className="h-4 w-4" />}
        </button>
      </form>
    </AuthShell>
  )
}
