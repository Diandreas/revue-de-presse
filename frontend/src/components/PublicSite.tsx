import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { WHATSAPP_DISPLAY, whatsappUrl } from '../lib/contact'
import { LEGAL, LEGAL_ROUTES, isPlaceholder } from '../lib/legal'
import { ArrowRightIcon, WhatsAppIcon } from './icons'
import { Logo, LogoMark } from './Logo'

/** Ancres de la page d'accueil (préfixées par « / » pour fonctionner depuis les pages légales). */
const HOME_SECTIONS = [
  { href: '/#fonctionnement', label: 'Fonctionnement' },
  { href: '/#format', label: 'Le format' },
  { href: '/#tarifs', label: 'Tarifs' },
  { href: '/#faq', label: 'FAQ' },
]

/** En-tête des pages publiques (accueil, pages légales) : marque, ancres et accès au compte. */
export function PublicHeader() {
  const { user } = useAuth()
  return (
    <>
      <a
        href="#contenu"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-slate-900 focus:shadow-lg"
      >
        Aller au contenu
      </a>
      <header className="sticky top-0 z-40 border-b border-slate-200/70 bg-white/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
          <Link to="/" className="shrink-0 rounded-xl" aria-label="Revue de Presse — accueil">
            <LogoMark className="h-9 w-9 drop-shadow-sm sm:hidden" />
            <Logo className="hidden sm:flex" />
          </Link>
          <nav aria-label="Sections de la page d’accueil" className="hidden md:block">
            <ul className="flex items-center gap-1">
              {HOME_SECTIONS.map((section) => (
                <li key={section.href}>
                  <Link to={section.href} className="btn-ghost !h-9 !font-medium">
                    {section.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
            {user ? (
              <Link to="/dashboard" className="btn-primary btn-sm !h-9">
                Mon espace
                <ArrowRightIcon className="h-4 w-4" />
              </Link>
            ) : (
              <>
                <Link to="/login" className="btn-ghost btn-sm !h-9">
                  Se connecter
                </Link>
                <Link to="/register" className="btn-primary btn-sm !h-9">
                  Essai gratuit
                </Link>
              </>
            )}
          </div>
        </div>
      </header>
    </>
  )
}

/** Pied de page des pages publiques : liens produit, légaux et contact WhatsApp. */
export function PublicFooter() {
  const email = LEGAL.publisher.email
  return (
    <footer className="ink-gradient text-slate-300">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
        <div>
          <Logo tone="light" subtitle="Veille média augmentée par l’IA" />
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-slate-400">
            La revue de presse des entreprises et institutions au Cameroun, préparée par l’IA et relue par vos équipes.
          </p>
        </div>
        <FooterColumn title="Produit">
          {HOME_SECTIONS.map((section) => (
            <li key={section.href}>
              <Link to={section.href} className="hover:text-white">
                {section.label}
              </Link>
            </li>
          ))}
        </FooterColumn>
        <FooterColumn title="Informations légales">
          {LEGAL_ROUTES.map((route) => (
            <li key={route.to}>
              <Link to={route.to} className="hover:text-white">
                {route.label}
              </Link>
            </li>
          ))}
        </FooterColumn>
        <FooterColumn title="Contact">
          <li>
            <a
              href={whatsappUrl('demo')}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 hover:text-white"
            >
              <WhatsAppIcon className="h-4 w-4 text-emerald-400" />
              {WHATSAPP_DISPLAY}
            </a>
          </li>
          {!isPlaceholder(email) && (
            <li>
              <a href={`mailto:${email}`} className="hover:text-white">
                {email}
              </a>
            </li>
          )}
          <li>
            <Link to="/login" className="hover:text-white">
              Se connecter
            </Link>
          </li>
          <li>
            <Link to="/register" className="hover:text-white">
              Essai gratuit 7 jours
            </Link>
          </li>
        </FooterColumn>
      </div>
      <div className="border-t border-white/10">
        <p className="mx-auto max-w-6xl px-4 py-5 text-xs text-slate-400 sm:px-6">
          © {new Date().getFullYear()} {LEGAL.brand} · service édité par {LEGAL.publisher.name}
        </p>
      </div>
    </footer>
  )
}

function FooterColumn({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <p className="text-[11px] font-semibold tracking-[0.12em] text-slate-400 uppercase">{title}</p>
      <ul className="mt-3 space-y-2 text-sm">{children}</ul>
    </div>
  )
}
