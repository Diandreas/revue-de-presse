import { zodResolver } from '@hookform/resolvers/zod'
import clsx from 'clsx'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { AuthShell } from '../components/AuthShell'
import { ArrowRightIcon, GiftIcon } from '../components/icons'
import { PasswordInput } from '../components/PasswordInput'
import { Alert, Spinner } from '../components/ui'

const schema = z.object({
  organization_name: z.string().trim().min(2, 'Le nom de l’entreprise est requis.'),
  full_name: z.string().trim().min(2, 'Votre nom est requis.'),
  email: z.string().trim().email('Adresse email invalide.'),
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
      demo
      title="Créez l’espace de votre entreprise"
      subtitle="Vous en devenez le propriétaire et pourrez inviter votre équipe ensuite."
      badge={
        <span className="chip bg-amber-50 py-1 text-amber-800 ring-1 ring-amber-200">
          <GiftIcon className="h-3.5 w-3.5" />
          7 jours d’essai gratuit · sans carte bancaire
        </span>
      }
      footer={
        <>
          Déjà inscrit ?{' '}
          <Link to="/login" className="font-semibold text-brand-600 hover:text-brand-700">
            Se connecter
          </Link>
        </>
      }
    >
      <form className="space-y-4" noValidate onSubmit={(e) => void handleSubmit(onSubmit)(e)}>
        <div>
          <label className="label" htmlFor="reg-org">
            Nom de l’entreprise
          </label>
          <input
            id="reg-org"
            autoComplete="organization"
            placeholder="Ex : Cabinet Ndjock & Associés"
            className={clsx('input', errors.organization_name && 'input-error')}
            {...register('organization_name')}
          />
          {errors.organization_name && <p className="field-error">{errors.organization_name.message}</p>}
        </div>
        <div>
          <label className="label" htmlFor="reg-name">
            Votre nom complet
          </label>
          <input
            id="reg-name"
            autoComplete="name"
            className={clsx('input', errors.full_name && 'input-error')}
            {...register('full_name')}
          />
          {errors.full_name && <p className="field-error">{errors.full_name.message}</p>}
        </div>
        <div>
          <label className="label" htmlFor="reg-email">
            Email professionnel
          </label>
          <input
            id="reg-email"
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
          <label className="label" htmlFor="reg-password">
            Mot de passe
          </label>
          <PasswordInput
            id="reg-password"
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
        {serverError && <Alert tone="danger">{serverError}</Alert>}
        <button type="submit" disabled={isSubmitting} className="btn-primary btn-lg w-full">
          {isSubmitting ? <Spinner /> : null}
          {isSubmitting ? 'Création de votre espace…' : 'Démarrer mon essai gratuit'}
          {!isSubmitting && <ArrowRightIcon className="h-4 w-4" />}
        </button>
      </form>
    </AuthShell>
  )
}
