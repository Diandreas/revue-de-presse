import clsx from 'clsx'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { usageStateOf } from '../features/billing/usage'
import { useSubscription } from '../features/billing/useBilling'
import { plural } from '../lib/format'
import { AlertTriangleIcon, GiftIcon, ZapIcon } from './icons'
import { ProgressBar } from './ui'
import { WhatsAppButton } from './WhatsAppButton'

/** Encart « formule & consommation » de la barre latérale (fond sombre). */
export function SidebarUsageCard({ onNavigate }: { onNavigate?: () => void }) {
  const { data: subscription, isLoading } = useSubscription()
  const state = usageStateOf(subscription, isLoading)

  if (state.kind === 'loading') {
    return <div className="h-[104px] animate-pulse rounded-2xl bg-white/5" />
  }

  const box = 'block rounded-2xl border border-white/10 bg-white/[0.04] p-4 transition hover:bg-white/[0.07]'

  if (state.kind === 'trial' || state.kind === 'active') {
    const ratio = state.limit ? (state.used / state.limit) * 100 : 0
    return (
      <Link to="/billing" onClick={onNavigate} className={box}>
        <div className="flex items-center gap-2 text-xs font-semibold text-white">
          {state.kind === 'trial' ? (
            <GiftIcon className="h-4 w-4 text-amber-300" />
          ) : (
            <ZapIcon className="h-4 w-4 text-brand-300" />
          )}
          {state.kind === 'trial' ? 'Essai gratuit' : `Formule ${state.planName}`}
          {state.kind === 'trial' && (
            <span className="ml-auto rounded-full bg-amber-300/15 px-2 py-0.5 text-[10px] font-semibold text-amber-200">
              {state.daysLeft > 0 ? `${plural(state.daysLeft, 'jour')}` : 'dernier jour'}
            </span>
          )}
        </div>
        <ProgressBar percent={ratio} tone="light" size="sm" className="mt-3" />
        <p className="mt-2 text-[11px] text-slate-400 tabular-nums">
          {state.used} / {state.limit} revues utilisées
        </p>
      </Link>
    )
  }

  return (
    <Link to="/billing" onClick={onNavigate} className={clsx(box, 'border-amber-300/20')}>
      <div className="flex items-center gap-2 text-xs font-semibold text-amber-200">
        <AlertTriangleIcon className="h-4 w-4" />
        {state.kind === 'trial-expired' ? 'Essai terminé' : 'Aucun abonnement actif'}
      </div>
      <p className="mt-1.5 text-[11px] leading-relaxed text-slate-400">
        Choisissez une formule pour continuer à générer des revues.
      </p>
    </Link>
  )
}

/** Bandeau du tableau de bord quand l'essai touche à sa fin ou que le quota est presque atteint. */
export function UsageBanner() {
  const { data: subscription, isLoading } = useSubscription()
  const state = usageStateOf(subscription, isLoading)

  if (state.kind === 'trial' && state.daysLeft <= 3) {
    return (
      <BannerShell tone="amber">
        Votre essai gratuit se termine {state.daysLeft <= 1 ? 'très bientôt' : `dans ${state.daysLeft} jours`}. Choisissez
        une formule pour ne pas interrompre votre veille.
      </BannerShell>
    )
  }
  if ((state.kind === 'trial' || state.kind === 'active') && state.limit > 0 && state.used / state.limit >= 0.8) {
    return (
      <BannerShell tone={state.used >= state.limit ? 'red' : 'amber'}>
        {state.used >= state.limit
          ? `Quota atteint : ${state.limit} revues sur la période.`
          : `${state.used} revues sur ${state.limit} utilisées sur la période.`}{' '}
        Passez à une formule supérieure pour plus de revues.
      </BannerShell>
    )
  }
  if (state.kind === 'trial-expired' || state.kind === 'none' || state.kind === 'inactive') {
    return (
      <BannerShell tone="red">
        {state.kind === 'trial-expired'
          ? 'Votre essai gratuit est terminé.'
          : 'Votre organisation n’a pas d’abonnement actif.'}{' '}
        Choisissez une formule pour lancer de nouvelles revues.
      </BannerShell>
    )
  }
  return null
}

function BannerShell({ tone, children }: { tone: 'amber' | 'red'; children: ReactNode }) {
  const { organization } = useAuth()
  return (
    <div
      className={clsx(
        'flex flex-col gap-3 rounded-2xl border px-4 py-3.5 text-sm sm:flex-row sm:items-center sm:justify-between animate-fade-in',
        tone === 'amber' ? 'border-amber-200 bg-amber-50 text-amber-900' : 'border-red-200 bg-red-50 text-red-900',
      )}
    >
      <p className="flex items-start gap-2.5">
        <AlertTriangleIcon className={clsx('mt-0.5 h-4 w-4 shrink-0', tone === 'amber' ? 'text-amber-500' : 'text-red-500')} />
        <span>{children}</span>
      </p>
      <div className="flex shrink-0 flex-wrap items-center gap-3">
        <WhatsAppButton topic="billing" organizationName={organization?.name} variant="link" label="Nous écrire" />
        <Link to="/billing" className="btn-secondary btn-sm">
          Voir les formules
        </Link>
      </div>
    </div>
  )
}
