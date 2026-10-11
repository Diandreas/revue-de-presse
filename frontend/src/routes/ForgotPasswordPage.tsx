import { zodResolver } from '@hookform/resolvers/zod'
import clsx from 'clsx'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { z } from 'zod'
import { extractErrorMessage } from '../api/client'
import { AuthShell } from '../components/AuthShell'
import { ArrowRightIcon, MailIcon } from '../components/icons'
import { Alert, Spinner } from '../components/ui'
import { WhatsAppButton } from '../components/WhatsAppButton'
import { useRequestPasswordReset } from '../features/account/useAccount'

const schema = z.object({
  email: z.string().trim().toLowerCase().email('Adresse email invalide.'),
})

type FormValues = z.infer<typeof schema>

/** « Mot de passe oublié » : lien de réinitialisation envoyé par e-mail. Tant que la
 * messagerie n'est pas configurée, l'administrateur de l'organisation (page Équipe) ou
 * l'équipe Revue de Presse peut générer ce lien et le transmettre sur WhatsApp. */
export default function ForgotPasswordPage() {
  const requestReset = useRequestPasswordReset()
  const [sentTo, setSentTo] = useState<string | null>(null)
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const onSubmit = async (values: FormValues) => {
    setServerError(null)
    try {
      await requestReset.mutateAsync(values.email)
      setSentTo(values.email)
    } catch (error) {
      setServerError(extractErrorMessage(error, 'Impossible d’envoyer le lien pour le moment. Réessayez plus tard.'))
    }
  }

  return (
    <AuthShell
      title="Mot de passe oublié"
      subtitle="Indiquez l’adresse e-mail de votre compte : nous vous envoyons un lien pour choisir un nouveau mot de passe."
      footer={
        <>
          Vous l’avez retrouvé ?{' '}
          <Link to="/login" className="font-semibold text-brand-600 hover:text-brand-700">
            Se connecter
          </Link>
        </>
      }
    >
      {sentTo ? (
        <div className="space-y-4">
          <Alert tone="success" title="Vérifiez votre messagerie">
            Si un compte existe pour <strong>{sentTo}</strong>, un e-mail avec un lien de réinitialisation vient de lui
            être envoyé (pensez aux courriers indésirables). Le lien ne fonctionne qu’une fois.
          </Alert>
          <Alert tone="info" title="Rien reçu ?">
            Demandez à l’administrateur de votre organisation de générer un lien de réinitialisation depuis la page
            Équipe, ou écrivez-nous sur WhatsApp.
          </Alert>
          <WhatsAppButton topic="help" label="Obtenir de l’aide sur WhatsApp" className="w-full" />
        </div>
      ) : (
        <form className="space-y-5" noValidate onSubmit={(e) => void handleSubmit(onSubmit)(e)}>
          <div>
            <label className="label" htmlFor="forgot-email">
              Email professionnel
            </label>
            <input
              id="forgot-email"
              type="email"
              autoComplete="email"
              inputMode="email"
              placeholder="vous@entreprise.cm"
              className={clsx('input', errors.email && 'input-error')}
              {...register('email')}
            />
            {errors.email && <p className="field-error">{errors.email.message}</p>}
          </div>
          {serverError && <Alert tone="danger">{serverError}</Alert>}
          <button type="submit" disabled={isSubmitting} className="btn-primary btn-lg w-full">
            {isSubmitting ? <Spinner /> : <MailIcon className="h-4 w-4" />}
            {isSubmitting ? 'Envoi…' : 'Recevoir le lien'}
            {!isSubmitting && <ArrowRightIcon className="h-4 w-4" />}
          </button>
        </form>
      )}
    </AuthShell>
  )
}
