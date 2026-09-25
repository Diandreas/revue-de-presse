import clsx from 'clsx'
import type { ComponentType, SVGProps } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import {
  CreditCardIcon,
  LogOutIcon,
  NewspaperIcon,
  SettingsIcon,
  TagIcon,
  UploadCloudIcon,
  UsersIcon,
} from './icons'

const NAV_ITEMS: { to: string; label: string; icon: ComponentType<SVGProps<SVGSVGElement>> }[] = [
  { to: '/dashboard', label: 'Revues de presse', icon: NewspaperIcon },
  { to: '/upload', label: 'Nouvelle revue', icon: UploadCloudIcon },
  { to: '/categories', label: 'Catégories de détection', icon: TagIcon },
  { to: '/team', label: 'Équipe', icon: UsersIcon },
  { to: '/billing', label: 'Abonnement', icon: CreditCardIcon },
  { to: '/settings', label: 'Paramètres', icon: SettingsIcon },
]

function initialsOf(text: string | undefined) {
  if (!text) return '?'
  return text.trim().slice(0, 2).toUpperCase()
}

export function AppLayout() {
  const { user, organization, logout } = useAuth()

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-64 shrink-0 flex-col border-r border-slate-200/70 bg-white/70 backdrop-blur-sm">
        <div className="flex items-center gap-2.5 border-b border-slate-200/70 px-5 py-5">
          <div className="brand-gradient flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-sm font-bold text-white shadow-[var(--shadow-soft)]">
            RP
          </div>
          <div className="min-w-0">
            <p className="font-display text-sm font-bold text-slate-900">Revue de Presse</p>
            <p className="truncate text-xs text-slate-500">{organization?.name}</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                clsx(
                  'group relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute -left-3 top-1/2 h-5 w-1 -translate-y-1/2 rounded-full bg-brand-600" />
                  )}
                  <item.icon
                    className={clsx('h-[18px] w-[18px] shrink-0', isActive ? 'text-brand-600' : 'text-slate-400 group-hover:text-slate-600')}
                  />
                  <span className="truncate">{item.label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-slate-200/70 p-3">
          <div className="flex items-center gap-2.5 rounded-lg px-2 py-2">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white">
              {initialsOf(user?.full_name || user?.email)}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium text-slate-700">{user?.full_name || user?.email}</p>
              <p className="truncate text-[11px] text-slate-400">{user?.email}</p>
            </div>
            <button
              type="button"
              onClick={() => void logout()}
              title="Se déconnecter"
              className="shrink-0 rounded-md p-1.5 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600"
            >
              <LogOutIcon className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      <main className="min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-5xl px-8 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
