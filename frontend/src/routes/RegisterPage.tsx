import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { AuthShell } from '../components/AuthShell'

const schema = z.object({
  organization_name: z.string().min(2, "Le nom de l'entreprise est requis."),
  full_name: z.string().min(2, 'Votre nom est requis.'),
  email: z.string().email('Adresse email invalide.'),
  password: z.string().min(10, 'Au moins 10 caractères.'),
})

type FormValues = z.infer<typeof schema>

export default function RegisterPage() {
  const { register: registerAccount } = useAuth()
  const navigate = useNavigate()
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const onSubmit = async (values: FormValues) => {
    setServerError(null)
    try {
      await registerAccount(values)
      navigate('/dashboard', { replace: true })
    } catch (error) {
      setServerError(extractErrorMessage(error, 'Impossible de créer le compte.'))
    }
  }

  return (
    <AuthShell
      title="Créer votre entreprise"
      subtitle="Vous devenez propriétaire de l'organisation et pourrez inviter votre équipe ensuite."
      footer={
        <>
          Déjà inscrit ?{' '}
          <Link to="/login" className="font-medium text-brand-600 hover:text-brand-700">
            Se connecter
          </Link>
        </>
      }
    >
      <form className="space-y-4" onSubmit={(e) => void handleSubmit(onSubmit)(e)}>
        <div>
          <label className="label">Nom de l&apos;entreprise</label>
          <input className="input" {...register('organization_name')} />
          {errors.organization_name && (
            <p className="mt-1 text-xs text-red-600">{errors.organization_name.message}</p>
          )}
        </div>
        <div>
          <label className="label">Votre nom complet</label>
          <input className="input" {...register('full_name')} />
          {errors.full_name && <p className="mt-1 text-xs text-red-600">{errors.full_name.message}</p>}
        </div>
        <div>
          <label className="label">Email professionnel</label>
          <input type="email" autoComplete="email" className="input" {...register('email')} />
          {errors.email && <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>}
        </div>
        <div>
          <label className="label">Mot de passe</label>
          <input type="password" autoComplete="new-password" className="input" {...register('password')} />
          {errors.password && <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>}
        </div>
        {serverError && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{serverError}</p>
        )}
        <button type="submit" disabled={isSubmitting} className="btn-primary w-full">
          {isSubmitting ? 'Création…' : 'Créer mon compte'}
        </button>
      </form>
    </AuthShell>
  )
}
