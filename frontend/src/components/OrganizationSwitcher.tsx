import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { extractErrorMessage } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { BuildingIcon, ChevronDownIcon } from './icons'
import { useToast } from './Toast'

/** Sélecteur d'organisation (barre latérale), affiché seulement si le compte appartient à
 * plusieurs organisations (ex : essai personnel puis invitation de l'employeur). */
export function OrganizationSwitcher({ onSwitched }: { onSwitched?: () => void }) {
  const { organization, organizations, switchOrganization } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const [switching, setSwitching] = useState(false)

  if (organizations.length < 2) return null

  const handleChange = async (organizationId: string) => {
    setSwitching(true)
    try {
      await switchOrganization(organizationId)
      const name = organizations.find((item) => item.id === organizationId)?.name
      toast.info(`Vous travaillez maintenant dans ${name ?? 'cette organisation'}.`)
      onSwitched?.()
      navigate('/dashboard')
    } catch (error) {
      toast.error(extractErrorMessage(error, 'Impossible de changer d’organisation.'))
    } finally {
      setSwitching(false)
    }
  }

  return (
    <div className="px-4 pb-4">
      <label htmlFor="organization-switcher" className="px-1 text-[11px] font-semibold tracking-[0.12em] text-slate-500 uppercase">
        Organisation
      </label>
      <div className="relative mt-1.5">
        <BuildingIcon className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <select
          id="organization-switcher"
          value={organization?.id ?? ''}
          disabled={switching}
          onChange={(event) => void handleChange(event.target.value)}
          className="w-full appearance-none truncate rounded-xl border border-white/10 bg-white/5 py-2 pr-9 pl-9 text-sm font-medium text-slate-100 transition hover:bg-white/10 focus:border-brand-400 focus:outline-none disabled:opacity-60"
        >
          {organizations.map((item) => (
            <option key={item.id} value={item.id} className="text-slate-900">
              {item.name}
            </option>
          ))}
        </select>
        <ChevronDownIcon className="pointer-events-none absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
      </div>
    </div>
  )
}
