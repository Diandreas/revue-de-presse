import { useState } from 'react'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { useUpdateOrganization } from '../features/organization/useOrganization'

export default function SettingsPage() {
  const { organization, user, refreshOrganization } = useAuth()
  const updateOrganization = useUpdateOrganization()
  const [name, setName] = useState(organization?.name ?? '')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const handleSave = async () => {
    setError(null)
    setSuccess(false)
    try {
      await updateOrganization.mutateAsync({ name })
      await refreshOrganization()
      setSuccess(true)
    } catch (err) {
      setError(extractErrorMessage(err, 'Impossible de mettre à jour l’organisation.'))
    }
  }

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900">Paramètres</h1>
      <p className="mt-1 text-sm text-slate-500">Informations de votre compte et de votre organisation.</p>

      <div className="card mt-6">
        <h2 className="text-sm font-semibold text-slate-900">Votre compte</h2>
        <dl className="mt-3 space-y-2 text-sm">
          <div className="flex justify-between">
            <dt className="text-slate-500">Email</dt>
            <dd className="text-slate-800">{user?.email}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Nom</dt>
            <dd className="text-slate-800">{user?.full_name || '—'}</dd>
          </div>
        </dl>
      </div>

      <div className="card mt-6">
        <h2 className="text-sm font-semibold text-slate-900">Organisation</h2>
        <div className="mt-3">
          <label className="label">Nom de l&apos;organisation</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        {success && <p className="mt-2 text-sm text-green-700">Organisation mise à jour.</p>}
        <button
          type="button"
          className="btn-primary mt-4"
          disabled={updateOrganization.isPending || !name}
          onClick={() => void handleSave()}
        >
          {updateOrganization.isPending ? 'Enregistrement…' : 'Enregistrer'}
        </button>
        <p className="mt-3 text-xs text-slate-400">
          Seuls les propriétaires et administrateurs peuvent modifier ces informations.
        </p>
      </div>
    </div>
  )
}
