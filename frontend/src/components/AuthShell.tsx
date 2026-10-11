import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ClippingIllustration } from './ClippingIllustration'
import { CheckIcon, ShieldIcon, SparkleIcon } from './icons'
import { LegalLinks } from './LegalLinks'
import { Logo, LogoMark } from './Logo'
import { WhatsAppButton } from './WhatsAppButton'
import { WHATSAPP_DISPLAY } from '../lib/contact'

interface AuthShellProps {
  title: string
  subtitle: ReactNode
  children: ReactNode
  footer?: ReactNode
  badge?: ReactNode
  /** Propose une démo guidée sur WhatsApp sous le formulaire (connexion, inscription). */
  demo?: boolean
}

const SELLING_POINTS = [
  'PDF ou photos de journaux, une ou plusieurs à la fois',
  'Risques juridiques, points clés et intox repérés par l’IA',
  'Analyse en arrière-plan, export PDF et Word',
]

/** Écran plein-page partagé par connexion / inscription / invitation : panneau de marque à
 * gauche (masqué sur petit écran), formulaire à droite. */
export function AuthShell({ title, subtitle, children, footer, badge, demo = false }: AuthShellProps) {
  return (
    <div className="flex min-h-screen bg-white">
      <aside className="ink-gradient relative hidden w-[46%] max-w-[680px] flex-col justify-between overflow-hidden p-10 text-white lg:flex xl:p-14">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage:
              'linear-gradient(rgb(255 255 255 / 0.6) 1px, transparent 1px), linear-gradient(90deg, rgb(255 255 255 / 0.6) 1px, transparent 1px)',
            backgroundSize: '44px 44px',
          }}
        />
        <Link to="/" className="relative w-fit rounded-xl" aria-label="Revue de Presse — accueil">
          <Logo tone="light" subtitle="Veille média augmentée par l’IA" />
        </Link>

        <div className="relative space-y-10">
          <div>
            <h2 className="text-balance font-display text-[34px] leading-[1.15] font-semibold xl:text-[40px]">
              Votre revue de presse, <span className="text-amber-300">analysée</span> en quelques minutes.
            </h2>
            <ul className="mt-6 space-y-2.5">
              {SELLING_POINTS.map((point) => (
                <li key={point} className="flex items-start gap-2.5 text-[15px] text-slate-300">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-300/15 text-amber-300">
                    <CheckIcon className="h-3.5 w-3.5" />
                  </span>
                  {point}
                </li>
              ))}
            </ul>
          </div>
          <ClippingIllustration />
        </div>

        <div className="relative flex items-center gap-2 text-xs text-slate-400">
          <ShieldIcon className="h-4 w-4" />
          <span>Conçu pour les entreprises au Cameroun · données hébergées de façon sécurisée</span>
        </div>
      </aside>

      <main className="flex flex-1 flex-col">
        <div className="flex items-center justify-between px-5 py-5 lg:hidden">
          <Link to="/" className="rounded-xl" aria-label="Revue de Presse — accueil">
            <Logo />
          </Link>
        </div>
        <div className="flex flex-1 items-center justify-center px-5 pt-4 pb-12 sm:px-8">
          <div className="w-full max-w-[400px] animate-slide-up">
            <div className="mb-6 hidden lg:block">
              <LogoMark className="h-10 w-10" />
            </div>
            {badge && <div className="mb-4">{badge}</div>}
            <h1 className="font-display text-[28px] leading-tight font-semibold text-slate-900">{title}</h1>
            <p className="mt-2 text-[15px] leading-relaxed text-slate-500">{subtitle}</p>
            <div className="mt-8">{children}</div>
            {footer && <p className="mt-8 text-center text-sm text-slate-500">{footer}</p>}
            {demo && (
              <div className="mt-8 border-t border-slate-100 pt-6 text-center">
                <p className="text-sm text-slate-500">Vous préférez une présentation guidée ?</p>
                <WhatsAppButton topic="demo" className="mt-3 w-full" />
                <p className="mt-2 text-xs text-slate-400">WhatsApp : {WHATSAPP_DISPLAY}</p>
              </div>
            )}
          </div>
        </div>
        <footer className="space-y-2 px-5 pb-6">
          <LegalLinks />
          <p className="flex items-center justify-center gap-1.5 text-xs text-slate-400">
            <SparkleIcon className="h-3.5 w-3.5" />
            Analyse propulsée par l’IA · © {new Date().getFullYear()} Revue de Presse
          </p>
        </footer>
      </main>
    </div>
  )
}
