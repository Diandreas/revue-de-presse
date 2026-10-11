import clsx from 'clsx'
import { HighlighterIcon, ScaleIcon } from './icons'

/** Illustration : une coupure de presse dont l'IA a surligné les passages sensibles
 * (journal et texte fictifs). Partagée par l'écran de connexion et la page d'accueil. */
export function ClippingIllustration({ className }: { className?: string }) {
  return (
    <div className={clsx('relative mx-auto w-full max-w-md', className)} aria-hidden="true">
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
