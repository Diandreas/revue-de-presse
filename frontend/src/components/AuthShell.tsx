import type { ReactNode } from 'react'
import { CheckIcon, HighlighterIcon, ScaleIcon, ShieldIcon, SparkleIcon } from './icons'
import { Logo, LogoMark } from './Logo'

interface AuthShellProps {
  title: string
  subtitle: ReactNode
  children: ReactNode
  footer?: ReactNode
  badge?: ReactNode
}

/** Illustration : une coupure de presse dont l'IA a surligné les passages sensibles. */
function ClippingIllustration() {
  return (
    <div className="relative mx-auto w-full max-w-md">
      <div className="absolute -inset-6 rounded-[2rem] bg-brand-500/10 blur-2xl" />
      <div className="relative rotate-[-1.5deg] rounded-2xl bg-paper p-6 text-slate-800 shadow-2xl ring-1 ring-black/5">
        <div className="flex items-center justify-between border-b-2 border-slate-900 pb-2">
          <p className="font-display text-sm font-bold tracking-tight">Le Quotidien</p>
          <p className="text-[10px] tracking-widest text-slate-500 uppercase">Économie · Société</p>
        </div>
        <p className="mt-3 font-display text-xl leading-snug font-semibold">
          Nouvelle réglementation des télécommunications : ce qui change pour les entreprises
        </p>
        <div className="mt-3 space-y-2 text-[12.5px] leading-relaxed text-slate-600">
          <p>
            Le texte adopté mardi prévoit{' '}
            <mark className="rounded-sm bg-blue-200/70 px-0.5 text-slate-900">un délai de mise en conformité de six mois</mark>{' '}
            pour les opérateurs concernés.
          </p>
          <p>
            Selon un message relayé sur les réseaux sociaux,{' '}
            <mark className="rounded-sm bg-amber-200/80 px-0.5 text-slate-900">
              les sanctions atteindraient des milliards
            </mark>
            , une information démentie par le ministère.
          </p>
          <p>
            L’article cite nommément{' '}
            <mark className="rounded-sm bg-red-200/70 px-0.5 text-slate-900">un dirigeant accusé sans preuve</mark>.
          </p>
        </div>
      </div>

      <div className="absolute -top-4 -right-3 rotate-[3deg] rounded-xl bg-white px-3 py-2 text-xs font-semibold text-red-700 shadow-xl ring-1 ring-black/5">
        <span className="flex items-center gap-1.5">
          <ScaleIcon className="h-3.5 w-3.5" /> Risque juridique
        </span>
      </div>
      <div className="absolute -bottom-5 -left-4 rotate-[-3deg] rounded-xl bg-white px-3 py-2 text-xs font-semibold text-amber-700 shadow-xl ring-1 ring-black/5">
        <span className="flex items-center gap-1.5">
          <HighlighterIcon className="h-3.5 w-3.5" /> Intox potentielle
        </span>
      </div>
    </div>
  )
}

const SELLING_POINTS = [
  'PDF ou photos de journaux, une ou plusieurs à la fois',
  'Risques juridiques, points clés et intox repérés par l’IA',
  'Analyse en arrière-plan, export PDF et Word',
]

/** Écran plein-page partagé par connexion / inscription / invitation : panneau de marque à
 * gauche (masqué sur petit écran), formulaire à droite. */
export function AuthShell({ title, subtitle, children, footer, badge }: AuthShellProps) {
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
        <Logo tone="light" subtitle="Veille média augmentée par l’IA" className="relative" />

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
          <Logo />
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
          </div>
        </div>
        <p className="flex items-center justify-center gap-1.5 pb-6 text-xs text-slate-400">
          <SparkleIcon className="h-3.5 w-3.5" />
          Analyse propulsée par l’IA · © {new Date().getFullYear()} Revue de Presse
        </p>
      </main>
    </div>
  )
}
