import clsx from 'clsx'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Revues de presse' },
  { to: '/upload', label: 'Nouvelle revue' },
  { to: '/categories', label: 'Catégories de détection' },
  { to: '/team', label: 'Équipe' },
  { to: '/billing', label: 'Abonnement' },
  { to: '/settings', label: 'Paramètres' },
]

export function AppLayout() {
  const { user, organization, logout } = useAuth()

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="flex w-64 flex-col border-r border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-6 py-5">
          <p className="text-sm font-semibold text-slate-900">Revue de Presse</p>
          <p className="mt-0.5 truncate text-xs text-slate-500">{organization?.name}</p>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                clsx(
                  'block rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100',
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-200 px-4 py-4">
          <p className="truncate text-xs text-slate-500">{user?.email}</p>
          <button
            type="button"
            onClick={() => void logout()}
            className="mt-2 text-xs font-medium text-slate-500 hover:text-slate-800"
          >
            Se déconnecter
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-5xl px-8 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
