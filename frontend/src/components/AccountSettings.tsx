import { useState, type FormEvent } from 'react'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { useChangePassword, useUpdateProfile } from '../features/account/useAccount'
import { CheckIcon, LockIcon, UserIcon } from './icons'
import { PasswordInput } from './PasswordInput'
import { useToast } from './Toast'
import { Alert, Spinner } from './ui'

function ProfileForm() {
  const toast = useToast()
  const { user, setCurrentUser } = useAuth()
  const updateProfile = useUpdateProfile()
  const [fullName, setFullName] = useState(user?.full_name ?? '')
  const [error, setError] = useState<string | null>(null)
  const trimmed = fullName.trim()

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    if (trimmed.length < 2) {
      setError('Votre nom est trop court.')
      return
    }
    try {
      setCurrentUser(await updateProfile.mutateAsync({ full_name: trimmed }))
      toast.success('Votre nom a été mis à jour.')
    } catch (err) {
      setError(extractErrorMessage(err, 'Impossible de mettre à jour votre nom.'))
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)}>
      <label className="label" htmlFor="account-name">
        Nom complet
      </label>
      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          id="account-name"
          className="input"
          autoComplete="name"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
        />
        <button
          type="submit"
          className="btn-primary shrink-0"
          disabled={trimmed === (user?.full_name ?? '') || updateProfile.isPending}
        >
          {updateProfile.isPending ? <Spinner /> : <CheckIcon className="h-4 w-4" />}
          Enregistrer
        </button>
      </div>
      <p className="field-hint">Votre adresse e-mail ({user?.email}) sert d’identifiant et ne peut pas être modifiée ici.</p>
      {error && (
        <Alert tone="danger" className="mt-3">
          {error}
        </Alert>
      )}
    </form>
  )
}

function PasswordForm() {
  const toast = useToast()
  const changePassword = useChangePassword()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    if (next.length < 10) {
      setError('Le nouveau mot de passe doit contenir au moins 10 caractères.')
      return
    }
    if (next !== confirm) {
      setError('Les deux nouveaux mots de passe ne correspondent pas.')
      return
    }
    try {
      await changePassword.mutateAsync({ current_password: current, new_password: next })
      setCurrent('')
      setNext('')
      setConfirm('')
      toast.success('Mot de passe modifié. Vos autres appareils ont été déconnectés.')
    } catch (err) {
      setError(extractErrorMessage(err, 'Impossible de modifier le mot de passe.'))
    }
  }

  return (
    <form className="space-y-4" onSubmit={(e) => void handleSubmit(e)} noValidate>
      <div>
        <label className="label" htmlFor="password-current">
          Mot de passe actuel
        </label>
        <PasswordInput
          id="password-current"
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="label" htmlFor="password-new">
            Nouveau mot de passe
          </label>
          <PasswordInput id="password-new" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="password-confirm">
            Confirmation
          </label>
          <PasswordInput
            id="password-confirm"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </div>
      </div>
      <p className="field-hint">10 caractères minimum. Vos autres appareils seront déconnectés.</p>
      {error && <Alert tone="danger">{error}</Alert>}
      <button
        type="submit"
        className="btn-secondary"
        disabled={!current || !next || !confirm || changePassword.isPending}
      >
        {changePassword.isPending ? <Spinner /> : <LockIcon className="h-4 w-4" />}
        Changer le mot de passe
      </button>
    </form>
  )
}

/** « Mon compte » : nom affiché et mot de passe. */
export function AccountSettings() {
  return (
    <section className="card">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-sky-600">
          <UserIcon className="h-5 w-5" />
        </span>
        <div>
          <h2 className="section-title">Mon compte</h2>
          <p className="text-xs text-slate-500">Votre nom et votre mot de passe.</p>
        </div>
      </div>
      <div className="mt-6 space-y-6">
        <ProfileForm />
        <div className="border-t border-slate-100 pt-6">
          <PasswordForm />
        </div>
      </div>
    </section>
  )
}
