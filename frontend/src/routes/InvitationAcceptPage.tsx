import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { z } from 'zod'
import { apiClient, extractErrorMessage, setAccessToken } from '../api/client'
import type { Membership, User } from '../api/types'
import { useAuth } from '../auth/useAuth'

interface InvitationPreview {
  email: string
  role: string
  organization_name: string
}

const registerSchema = z.object({
  full_name: z.string().min(2, 'Votre nom est requis.'),
  password: z.string().min(10, 'Au moins 10 caractères.'),
})

type RegisterFormValues = z.infer<typeof registerSchema>

export default function InvitationAcceptPage() {
  const { token } = useParams<{ token: string }>()
  const { user, isLoading, refreshOrganization } = useAuth()
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
      const res = await apiClient.post(`/auth/invitations/${token}/accept/`)
      return res.data
    },
    onSuccess: async () => {
      await refreshOrganization()
      navigate('/dashboard', { replace: true })
    },
    onError: (error) => setActionError(extractErrorMessage(error, "Impossible d'accepter cette invitation.")),
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
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({ resolver: zodResolver(registerSchema) })

  if (isLoading || previewQuery.isLoading) {
    return <div className="flex min-h-screen items-center justify-center text-slate-500">Chargement…</div>
  }

  if (previewQuery.isError || !previewQuery.data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
        <div className="card max-w-sm text-center">
          <h1 className="text-lg font-semibold text-slate-900">Invitation introuvable</h1>
          <p className="mt-2 text-sm text-slate-600">
            Ce lien d&apos;invitation est invalide, expiré, ou a déjà été utilisé.
          </p>
          <Link to="/login" className="btn-primary mt-4 inline-flex">
            Se connecter
          </Link>
        </div>
      </div>
    )
  }

  const preview = previewQuery.data

  if (user) {
    const emailMatches = user.email.toLowerCase() === preview.email.toLowerCase()
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
        <div className="card max-w-sm text-center">
          <h1 className="text-lg font-semibold text-slate-900">Rejoindre {preview.organization_name}</h1>
          {emailMatches ? (
            <>
              <p className="mt-2 text-sm text-slate-600">Connecté en tant que {user.email}.</p>
              {actionError && <p className="mt-2 text-sm text-red-600">{actionError}</p>}
              <button
                type="button"
                className="btn-primary mt-4"
                disabled={acceptMutation.isPending}
                onClick={() => acceptMutation.mutate()}
              >
                {acceptMutation.isPending ? 'Validation…' : "Accepter l'invitation"}
              </button>
            </>
          ) : (
            <p className="mt-2 text-sm text-red-600">
              Cette invitation a été envoyée à {preview.email}, mais vous êtes connecté en tant que {user.email}.
              Déconnectez-vous puis réessayez avec le bon compte.
            </p>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
      <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-lg font-semibold text-slate-900">Rejoindre {preview.organization_name}</h1>
        <p className="mt-1 text-sm text-slate-500">Invitation envoyée à {preview.email}.</p>

        <form
          className="mt-6 space-y-4"
          onSubmit={(e) => void handleSubmit((values) => registerMutation.mutate(values))(e)}
        >
          <div>
            <label className="label">Votre nom complet</label>
            <input className="input" {...register('full_name')} />
            {errors.full_name && <p className="mt-1 text-xs text-red-600">{errors.full_name.message}</p>}
          </div>
          <div>
            <label className="label">Choisissez un mot de passe</label>
            <input type="password" autoComplete="new-password" className="input" {...register('password')} />
            {errors.password && <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>}
          </div>
          {actionError && <p className="text-sm text-red-600">{actionError}</p>}
          <button type="submit" disabled={isSubmitting || registerMutation.isPending} className="btn-primary w-full">
            {registerMutation.isPending ? 'Création…' : 'Créer mon compte et rejoindre'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          Vous avez déjà un compte ?{' '}
          <Link
            to="/login"
            state={{ from: { pathname: `/invitations/${token}/accept` } }}
            className="font-medium text-brand-600 hover:text-brand-700"
          >
            Se connecter
          </Link>
        </p>
      </div>
    </div>
  )
}
