import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { extractErrorMessage } from '../api/client'
import { isAdminRole, useAuth } from '../auth/useAuth'
import { AccountSettings } from '../components/AccountSettings'
import { OrganizationLifecycle } from '../components/OrganizationLifecycle'
import { useToast } from '../components/Toast'
import {
  BuildingIcon,
  CheckIcon,
  ChevronRightIcon,
  CreditCardIcon,
  LogOutIcon,
  ShieldIcon,
  SparkleIcon,
  TagIcon,
  UploadCloudIcon,
  UsersIcon,
  type IconComponent,
} from '../components/icons'
import { Alert, Avatar, PageHeader, Spinner } from '../components/ui'
import { useUpdateOrganization } from '../features/organization/useOrganization'
import { formatDate } from '../lib/format'

const ROLE_LABELS = { owner: 'Propriétaire', admin: 'Administrateur', member: 'Membre' } as const

/** « CM » -> « Cameroun », « fr » -> « français ». */
function displayName(type: 'region' | 'language', code: string | undefined) {
  if (!code) return '—'
  try {
    const label = new Intl.DisplayNames(['fr'], { type }).of(type === 'region' ? code.toUpperCase() : code) ?? code
    return label.charAt(0).toUpperCase() + label.slice(1)
  } catch {
    return code
  }
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3 text-sm">
      <dt className="text-slate-500">{label}</dt>
      <dd className="truncate text-right font-medium text-slate-800">{value}</dd>
    </div>
  )
}

function ShortcutLink({ to, icon: Icon, title, description }: { to: string; icon: IconComponent; title: string; description: string }) {
  return (
    <Link
      to={to}
      className="group flex items-center gap-3 rounded-2xl px-3 py-3 transition hover:bg-slate-50"
    >
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600 transition group-hover:bg-brand-50 group-hover:text-brand-600">
        <Icon className="h-5 w-5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold text-slate-900">{title}</span>
        <span className="block truncate text-xs text-slate-500">{description}</span>
      </span>
      <ChevronRightIcon className="h-4 w-4 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-slate-500" />
    </Link>
  )
}

export default function SettingsPage() {
  const toast = useToast()
  const { organization, user, refreshOrganization, logout } = useAuth()
  const canEdit = isAdminRole(organization?.my_role)
  const updateOrganization = useUpdateOrganization()
  const [name, setName] = useState(organization?.name ?? '')
  const [error, setError] = useState<string | null>(null)

  const trimmed = name.trim()
  const dirty = trimmed !== (organization?.name ?? '')

  const handleSave = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    if (trimmed.length < 2) {
      setError('Le nom de l’organisation est trop court.')
      return
    }
    try {
      await updateOrganization.mutateAsync({ name: trimmed })
      await refreshOrganization()
      toast.success('Organisation mise à jour.')
    } catch (err) {
      setError(extractErrorMessage(err, 'Impossible de mettre à jour l’organisation.'))
    }
  }

  const role = organization?.my_role ? ROLE_LABELS[organization.my_role] : '—'
  const userName = user?.full_name || user?.email || ''

  return (
    <div className="space-y-8">
      <PageHeader eyebrow="Compte" title="Paramètres" subtitle="Votre profil et les informations de votre organisation." />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          <section className="card">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                <BuildingIcon className="h-5 w-5" />
              </span>
              <div>
                <h2 className="section-title">Organisation</h2>
                <p className="text-xs text-slate-500">Affichée sur vos revues et vos exports PDF / Word.</p>
              </div>
            </div>

            <form className="mt-6" onSubmit={(e) => void handleSave(e)}>
              <label className="label" htmlFor="org-name">
                Nom de l’organisation
              </label>
              <div className="flex flex-col gap-3 sm:flex-row">
                <input
                  id="org-name"
                  className="input"
                  value={name}
                  disabled={!canEdit}
                  onChange={(e) => setName(e.target.value)}
                />
                {canEdit && (
                  <button type="submit" className="btn-primary shrink-0" disabled={!dirty || updateOrganization.isPending}>
                    {updateOrganization.isPending ? <Spinner /> : <CheckIcon className="h-4 w-4" />}
                    Enregistrer
                  </button>
                )}
              </div>
              {!canEdit && (
                <p className="field-hint">Seuls les propriétaires et administrateurs peuvent modifier ces informations.</p>
              )}
              {error && (
                <Alert tone="danger" className="mt-3">
                  {error}
                </Alert>
              )}
            </form>

            <dl className="mt-6 divide-y divide-slate-100 border-t border-slate-100">
              <InfoRow label="Pays" value={displayName('region', organization?.country)} />
              <InfoRow label="Langue des revues" value={displayName('language', organization?.default_locale)} />
              <InfoRow label="Créée le" value={formatDate(organization?.created_at)} />
            </dl>
          </section>

          <AccountSettings />

          <section className="card">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
                <ShieldIcon className="h-5 w-5" />
              </span>
              <div>
                <h2 className="section-title">Confidentialité et IA</h2>
                <p className="text-xs text-slate-500">Ce qu’il faut savoir sur le traitement de vos documents.</p>
              </div>
            </div>
            <ul className="mt-5 space-y-3 text-sm leading-relaxed text-slate-600">
              <li className="flex gap-2.5">
                <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                Vos documents, revues et catégories ne sont visibles que par les membres de votre organisation.
              </li>
              <li className="flex gap-2.5">
                <SparkleIcon className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />
                Les textes sont lus et résumés par un modèle d’intelligence artificielle (Mistral AI) pour produire la
                revue.
              </li>
              <li className="flex gap-2.5">
                <ShieldIcon className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
                L’IA peut se tromper : relisez les points sensibles (risques juridiques, intox) avant toute diffusion.
              </li>
            </ul>
            <p className="mt-5 border-t border-slate-100 pt-4 text-sm text-slate-500">
              Détails dans la{' '}
              <Link to="/confidentialite" className="font-semibold text-brand-600 hover:text-brand-700">
                politique de confidentialité
              </Link>{' '}
              et les{' '}
              <Link to="/cgu" className="font-semibold text-brand-600 hover:text-brand-700">
                conditions générales
              </Link>
              .
            </p>
          </section>

          <OrganizationLifecycle />
        </div>

        <aside className="space-y-6">
          <section className="card">
            <div className="flex items-center gap-4">
              <Avatar name={userName} size="lg" />
              <div className="min-w-0">
                <p className="truncate font-display text-lg font-semibold text-slate-900">{user?.full_name || 'Mon profil'}</p>
                <p className="truncate text-sm text-slate-500">{user?.email}</p>
              </div>
            </div>
            <dl className="mt-5 divide-y divide-slate-100 border-t border-slate-100">
              <InfoRow label="Rôle" value={role} />
              <InfoRow label="Inscrit le" value={formatDate(user?.date_joined)} />
            </dl>
            <button type="button" className="btn-secondary mt-5 w-full" onClick={() => void logout()}>
              <LogOutIcon className="h-4 w-4" />
              Se déconnecter
            </button>
          </section>

          <section className="card !p-3">
            <p className="px-3 pt-2 pb-1 text-[11px] font-semibold tracking-wide text-slate-400 uppercase">Raccourcis</p>
            <ShortcutLink to="/team" icon={UsersIcon} title="Équipe" description="Membres et invitations" />
            <ShortcutLink to="/categories" icon={TagIcon} title="Catégories" description="Ce que l’IA doit surligner" />
            <ShortcutLink to="/billing" icon={CreditCardIcon} title="Abonnement" description="Formule, quota et factures" />
            <ShortcutLink to="/upload" icon={UploadCloudIcon} title="Nouvelle revue" description="Envoyer des photos ou des PDF" />
          </section>
        </aside>
      </div>
    </div>
  )
}
