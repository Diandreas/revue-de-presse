import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { z } from 'zod'
import { extractErrorMessage } from '../api/client'
import { AuthShell } from '../components/AuthShell'
import { CheckIcon, LockIcon } from '../components/icons'
import { PasswordInput } from '../components/PasswordInput'
import { Alert, Spinner } from '../components/ui'
import { useConfirmPasswordReset } from '../features/account/useAccount'

const schema = z
  .object({
    new_password: z.string().min(10, 'Au moins 10 caractères.'),
    confirm: z.string(),
  })
  .refine((values) => values.new_password === values.confirm, {
    message: 'Les deux mots de passe ne correspondent pas.',
    path: ['confirm'],
  })

type FormValues = z.infer<typeof schema>

/** Nouveau mot de passe depuis le lien reçu par e-mail ou transmis par un administrateur. */
export default function ResetPasswordPage() {
  const { uid = '', token = '' } = useParams<{ uid: string; token: string }>()
  const navigate = useNavigate()
  const confirmReset = useConfirmPasswordReset()
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const onSubmit = async (values: FormValues) => {
    setServerError(null)
    try {
      const detail = await confirmReset.mutateAsync({ uid, token, new_password: values.new_password })
      navigate('/login', { replace: true, state: { notice: detail } })
    } catch (error) {
      setServerError(extractErrorMessage(error, 'Impossible de modifier le mot de passe.'))
    }
  }

  return (
    <AuthShell
      title="Choisissez un nouveau mot de passe"
      subtitle="Ce lien ne fonctionne qu’une fois. Vos autres appareils seront déconnectés."
      footer={
        <>
          Lien expiré ?{' '}
          <Link to="/mot-de-passe-oublie" className="font-semibold text-brand-600 hover:text-brand-700">
            Demander un nouveau lien
          </Link>
        </>
      }
    >
      <form className="space-y-5" noValidate onSubmit={(e) => void handleSubmit(onSubmit)(e)}>
        <div>
          <label className="label" htmlFor="reset-password">
            Nouveau mot de passe
          </label>
          <PasswordInput
            id="reset-password"
            autoComplete="new-password"
            invalid={Boolean(errors.new_password)}
            {...register('new_password')}
          />
          {errors.new_password ? (
            <p className="field-error">{errors.new_password.message}</p>
          ) : (
            <p className="field-hint">10 caractères minimum, évitez les mots de passe trop courants.</p>
          )}
        </div>
        <div>
          <label className="label" htmlFor="reset-confirm">
            Confirmez le mot de passe
          </label>
          <PasswordInput
            id="reset-confirm"
            autoComplete="new-password"
            invalid={Boolean(errors.confirm)}
            {...register('confirm')}
          />
          {errors.confirm && <p className="field-error">{errors.confirm.message}</p>}
        </div>
        {serverError && <Alert tone="danger">{serverError}</Alert>}
        <button type="submit" disabled={isSubmitting} className="btn-primary btn-lg w-full">
          {isSubmitting ? <Spinner /> : <LockIcon className="h-4 w-4" />}
          {isSubmitting ? 'Enregistrement…' : 'Enregistrer le mot de passe'}
          {!isSubmitting && <CheckIcon className="h-4 w-4" />}
        </button>
      </form>
    </AuthShell>
  )
}
