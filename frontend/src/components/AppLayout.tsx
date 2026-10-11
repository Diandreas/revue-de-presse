import clsx from 'clsx'
import { Suspense, useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import {
  CreditCardIcon,
  LogOutIcon,
  MenuIcon,
  NewspaperIcon,
  PlusIcon,
  SettingsIcon,
  TagIcon,
  UsersIcon,
  XIcon,
  type IconComponent,
} from './icons'
import { Logo, LogoMark } from './Logo'
import { OrganizationSwitcher } from './OrganizationSwitcher'
import { SidebarUsageCard } from './UsageCard'
import { WhatsAppButton } from './WhatsAppButton'
import { Avatar, FullPageLoader } from './ui'

const NAV_SECTIONS: { title: string; items: { to: string; label: string; icon: IconComponent }[] }[] = [
  {
    title: 'Veille',
    items: [{ to: '/dashboard', label: 'Revues de presse', icon: NewspaperIcon }],
  },
  {
    title: 'Configuration',
    items: [
      { to: '/categories', label: 'Catégories de détection', icon: TagIcon },
      { to: '/team', label: 'Équipe', icon: UsersIcon },
    ],
  },
  {
    title: 'Compte',
    items: [
      { to: '/billing', label: 'Abonnement', icon: CreditCardIcon },
      { to: '/settings', label: 'Paramètres', icon: SettingsIcon },
    ],
  },
]

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { user, organization, logout } = useAuth()
  const location = useLocation()
  // « Revues de presse » reste actif sur le détail d'une revue (/jobs/:id).
  const isReviewsActive = (to: string) => to === '/dashboard' && location.pathname.startsWith('/jobs/')

  return (
    <div className="flex h-full flex-col">
      <div className="px-5 pt-6 pb-5">
        <Link to="/dashboard" onClick={onNavigate} className="block rounded-xl">
          <Logo tone="light" subtitle={organization?.name} />
        </Link>
      </div>

      <OrganizationSwitcher onSwitched={onNavigate} />

      <div className="px-4">
        <Link
          to="/upload"
          onClick={onNavigate}
          className="btn-primary w-full !h-11 shadow-[var(--shadow-glow)] hover:!shadow-[0_10px_30px_-6px_rgb(99_102_241/0.6)]"
        >
          <PlusIcon className="h-[18px] w-[18px]" />
          Nouvelle revue
        </Link>
      </div>

      <nav className="scrollbar-thin mt-6 flex-1 space-y-6 overflow-y-auto px-3" aria-label="Navigation principale">
        {NAV_SECTIONS.map((section) => (
          <div key={section.title}>
            <p className="px-3 pb-2 text-[11px] font-semibold tracking-[0.12em] text-slate-500 uppercase">
              {section.title}
            </p>
            <div className="space-y-0.5">
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    clsx(
                      'group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition',
                      isActive || isReviewsActive(item.to)
                        ? 'bg-white/10 text-white'
                        : 'text-slate-400 hover:bg-white/5 hover:text-slate-100',
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      {(isActive || isReviewsActive(item.to)) && (
                        <span className="absolute top-1/2 left-0 h-5 w-1 -translate-y-1/2 rounded-r-full bg-amber-300" />
                      )}
                      <item.icon
                        className={clsx(
                          'h-[18px] w-[18px] shrink-0 transition',
                          isActive || isReviewsActive(item.to) ? 'text-amber-300' : 'text-slate-500 group-hover:text-slate-300',
                        )}
                      />
                      <span className="truncate">{item.label}</span>
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="space-y-3 p-4">
        <WhatsAppButton topic="help" organizationName={organization?.name} variant="dark" label="Aide sur WhatsApp" />
        <SidebarUsageCard onNavigate={onNavigate} />
        <div className="flex items-center gap-3 rounded-2xl px-2 py-2">
          <Avatar name={user?.full_name || user?.email || '?'} size="sm" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-slate-100">{user?.full_name || user?.email}</p>
            <p className="truncate text-xs text-slate-500">{user?.email}</p>
          </div>
          <button
            type="button"
            onClick={() => void logout()}
            title="Se déconnecter"
            aria-label="Se déconnecter"
            className="shrink-0 rounded-lg p-2 text-slate-500 transition hover:bg-white/10 hover:text-white"
          >
            <LogOutIcon className="h-[18px] w-[18px]" />
          </button>
        </div>
      </div>
    </div>
  )
}

export function AppLayout() {
  const { organization } = useAuth()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const location = useLocation()

  // Fermer le menu mobile à chaque changement de page, et avec Échap.
  useEffect(() => {
    setDrawerOpen(false)
    // Changement de page : on repart du haut (sinon la revue s'ouvre à la hauteur de
    // défilement de la page d'envoi).
    window.scrollTo({ top: 0 })
  }, [location.pathname])

  useEffect(() => {
    if (!drawerOpen) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setDrawerOpen(false)
    }
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = previousOverflow
    }
  }, [drawerOpen])

  return (
    <div className="min-h-screen">
      {/* Barre latérale (desktop) */}
      <aside className="ink-gradient fixed inset-y-0 left-0 z-30 hidden w-72 border-r border-white/5 lg:block">
        <SidebarContent />
      </aside>

      {/* Barre supérieure (mobile / tablette) */}
      <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-slate-200/70 bg-white/85 px-4 backdrop-blur-md lg:hidden">
        <Link to="/dashboard" className="flex min-w-0 items-center gap-2.5">
          <LogoMark className="h-8 w-8" />
          <div className="min-w-0 leading-tight">
            <p className="font-display text-[15px] font-semibold text-slate-900">Revue de Presse</p>
            <p className="truncate text-[11px] text-slate-500">{organization?.name}</p>
          </div>
        </Link>
        <div className="flex items-center gap-1">
          <Link to="/upload" className="btn-primary btn-sm !h-9 !px-3" aria-label="Nouvelle revue">
            <PlusIcon className="h-4 w-4" />
            <span className="hidden sm:inline">Nouvelle revue</span>
          </Link>
          <button
            type="button"
            className="btn-icon"
            aria-label="Ouvrir le menu"
            aria-expanded={drawerOpen}
            onClick={() => setDrawerOpen(true)}
          >
            <MenuIcon className="h-5 w-5" />
          </button>
        </div>
      </header>

      {/* Menu coulissant (mobile) */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-[2px] animate-fade-in" onClick={() => setDrawerOpen(false)} />
          <div className="ink-gradient absolute inset-y-0 left-0 w-[86%] max-w-xs shadow-2xl animate-slide-in-left">
            <button
              type="button"
              aria-label="Fermer le menu"
              onClick={() => setDrawerOpen(false)}
              className="absolute top-5 right-4 rounded-lg p-2 text-slate-400 transition hover:bg-white/10 hover:text-white"
            >
              <XIcon className="h-5 w-5" />
            </button>
            <SidebarContent onNavigate={() => setDrawerOpen(false)} />
          </div>
        </div>
      )}

      <main className="min-w-0 lg:pl-72">
        <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
          {/* Suspense local : la barre latérale reste affichée pendant le chargement d'une page. */}
          <Suspense fallback={<FullPageLoader />}>
            <Outlet />
          </Suspense>
        </div>
      </main>
    </div>
  )
}
