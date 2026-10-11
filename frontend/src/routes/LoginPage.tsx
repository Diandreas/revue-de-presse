import { zodResolver } from '@hookform/resolvers/zod'
import clsx from 'clsx'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { AuthShell } from '../components/AuthShell'
import { ArrowRightIcon } from '../components/icons'
import { PasswordInput } from '../components/PasswordInput'
import { Alert, Spinner } from '../components/ui'

const schema = z.object({
  // Les comptes sont enregistrés en minuscules : « Jean.Ndjock@… » doit aussi fonctionner.
  email: z.string().trim().toLowerCase().email('Adresse email invalide.'),
  password: z.string().min(1, 'Mot de passe requis.'),
})

type FormValues = z.infer<typeof schema>

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [serverError, setServerError] = useState<string | null>(null)
  // Message transmis par une autre page (ex : « mot de passe modifié »).
  const notice = (location.state as { notice?: string } | null)?.notice

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
    <AuthShell
      demo
      title="Bon retour parmi nous"
      subtitle="Connectez-vous à l’espace de votre entreprise."
      footer={
        <>
          Pas encore de compte ?{' '}
          <Link to="/register" className="font-semibold text-brand-600 hover:text-brand-700">
            Créer votre entreprise
          </Link>
        </>
      }
    >
      <form className="space-y-5" noValidate onSubmit={(e) => void handleSubmit(onSubmit)(e)}>
        {notice && <Alert tone="success">{notice}</Alert>}
        <div>
          <label className="label" htmlFor="login-email">
            Email professionnel
          </label>
          <input
            id="login-email"
            type="email"
            autoComplete="email"
            inputMode="email"
            placeholder="vous@entreprise.cm"
            className={clsx('input', errors.email && 'input-error')}
            {...register('email')}
          />
          {errors.email && <p className="field-error">{errors.email.message}</p>}
        </div>
        <div>
          <div className="flex items-baseline justify-between gap-3">
            <label className="label" htmlFor="login-password">
              Mot de passe
            </label>
            <Link to="/mot-de-passe-oublie" className="mb-1.5 text-[13px] font-medium text-brand-600 hover:text-brand-700">
              Mot de passe oublié ?
            </Link>
          </div>
          <PasswordInput
            id="login-password"
            autoComplete="current-password"
            invalid={Boolean(errors.password)}
            {...register('password')}
          />
          {errors.password && <p className="field-error">{errors.password.message}</p>}
        </div>
        {serverError && <Alert tone="danger">{serverError}</Alert>}
        <button type="submit" disabled={isSubmitting} className="btn-primary btn-lg w-full">
          {isSubmitting ? <Spinner /> : null}
          {isSubmitting ? 'Connexion…' : 'Se connecter'}
          {!isSubmitting && <ArrowRightIcon className="h-4 w-4" />}
        </button>
      </form>
    </AuthShell>
  )
}
