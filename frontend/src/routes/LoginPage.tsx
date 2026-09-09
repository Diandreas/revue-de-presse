import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../auth/useAuth'

const schema = z.object({
  email: z.string().email('Adresse email invalide.'),
  password: z.string().min(1, 'Mot de passe requis.'),
})

type FormValues = z.infer<typeof schema>

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const onSubmit = async (values: FormValues) => {
    setServerError(null)
    try {
      await login(values.email, values.password)
      const from = (location.state as { from?: { pathname?: string } } | null)?.from
      navigate(from?.pathname ?? '/dashboard', { replace: true })
    } catch (error) {
      setServerError(extractErrorMessage(error, 'Email ou mot de passe incorrect.'))
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-lg font-semibold text-slate-900">Connexion</h1>
        <p className="mt-1 text-sm text-slate-500">Revue de Presse — accès entreprise</p>

        <form className="mt-6 space-y-4" onSubmit={(e) => void handleSubmit(onSubmit)(e)}>
          <div>
            <label className="label">Email professionnel</label>
            <input type="email" autoComplete="email" className="input" {...register('email')} />
            {errors.email && <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>}
          </div>
          <div>
            <label className="label">Mot de passe</label>
            <input type="password" autoComplete="current-password" className="input" {...register('password')} />
            {errors.password && <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>}
          </div>
          {serverError && <p className="text-sm text-red-600">{serverError}</p>}
          <button type="submit" disabled={isSubmitting} className="btn-primary w-full">
            {isSubmitting ? 'Connexion…' : 'Se connecter'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          Pas encore de compte ?{' '}
          <Link to="/register" className="font-medium text-brand-600 hover:text-brand-700">
            Créer votre entreprise
          </Link>
        </p>
      </div>
    </div>
  )
}
