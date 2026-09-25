import type { ReactNode } from 'react'
import { ShieldIcon, SparkleIcon } from './icons'

interface AuthShellProps {
  title: string
  subtitle: string
  children: ReactNode
  footer: ReactNode
}

/** Écran plein-page partagé par connexion / inscription : panneau de marque à gauche
 * (masqué sur petit écran), formulaire centré à droite. */
export function AuthShell({ title, subtitle, children, footer }: AuthShellProps) {
  return (
    <div className="flex min-h-screen">
      <div className="brand-gradient relative hidden w-[44%] flex-col justify-between overflow-hidden p-10 text-white lg:flex">
        <div className="absolute -top-24 -right-20 h-72 w-72 rounded-full bg-white/10 blur-3xl" />
        <div className="absolute -bottom-32 -left-16 h-80 w-80 rounded-full bg-black/15 blur-3xl" />

        <div className="relative flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/15 text-sm font-bold backdrop-blur">
            RP
          </div>
          <span className="font-display text-sm font-bold">Revue de Presse</span>
        </div>

        <div className="relative">
          <SparkleIcon className="mb-5 h-8 w-8 text-white/70" />
          <h2 className="font-display text-3xl font-bold leading-tight">
            L&apos;IA au service de votre veille presse et juridique.
          </h2>
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-white/70">
            Déposez vos coupures de presse — PDF ou photos, une ou plusieurs — et laissez
            l&apos;IA repérer les risques juridiques, les points clés et les intox, en
            arrière-plan.
          </p>
          <div className="mt-6 flex items-center gap-2 text-xs text-white/60">
            <ShieldIcon className="h-4 w-4" />
            <span>Conçu pour les entreprises au Cameroun</span>
          </div>
        </div>

        <p className="relative text-xs text-white/40">© {new Date().getFullYear()} Revue de Presse</p>
      </div>

      <div className="flex flex-1 items-center justify-center px-4 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <div className="brand-gradient flex h-9 w-9 items-center justify-center rounded-xl text-sm font-bold text-white">
              RP
            </div>
            <span className="font-display text-sm font-bold text-slate-900">Revue de Presse</span>
          </div>

          <h1 className="page-title">{title}</h1>
          <p className="page-subtitle">{subtitle}</p>
          <div className="mt-7">{children}</div>
          <p className="mt-7 text-center text-sm text-slate-500">{footer}</p>
        </div>
      </div>
    </div>
  )
}
