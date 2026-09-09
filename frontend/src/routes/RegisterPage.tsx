import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../auth/useAuth'

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
      setServerError(extractErrorMessage(error, "Impossible de créer le compte."))
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
      <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-lg font-semibold text-slate-900">Créer votre entreprise</h1>
        <p className="mt-1 text-sm text-slate-500">
          Vous devenez propriétaire de l&apos;organisation et pourrez inviter votre équipe ensuite.
        </p>

        <form className="mt-6 space-y-4" onSubmit={(e) => void handleSubmit(onSubmit)(e)}>
          <div>
            <label className="label">Nom de l&apos;entreprise</label>
            <input className="input" {...register('organization_name')} />
            {errors.organization_name && <p className="mt-1 text-xs text-red-600">{errors.organization_name.message}</p>}
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
          {serverError && <p className="text-sm text-red-600">{serverError}</p>}
          <button type="submit" disabled={isSubmitting} className="btn-primary w-full">
            {isSubmitting ? 'Création…' : 'Créer mon compte'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          Déjà inscrit ?{' '}
          <Link to="/login" className="font-medium text-brand-600 hover:text-brand-700">
            Se connecter
          </Link>
        </p>
      </div>
    </div>
  )
}
