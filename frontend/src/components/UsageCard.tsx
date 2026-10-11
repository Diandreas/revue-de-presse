import clsx from 'clsx'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { usageStateOf, type UsageState } from '../features/billing/usage'
import { useSubscription } from '../features/billing/useBilling'
import { formatDate, plural } from '../lib/format'
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
    const renewSoon = state.kind === 'active' && (state.overdue || (state.daysLeft !== null && state.daysLeft <= 7))
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
          {renewSoon && (
            <span className="ml-auto rounded-full bg-amber-300/15 px-2 py-0.5 text-[10px] font-semibold text-amber-200">
              À renouveler
            </span>
          )}
        </div>
        <ProgressBar percent={ratio} tone="light" size="sm" className="mt-3" />
        <p className="mt-2 text-[11px] text-slate-400 tabular-nums">
          {state.used} / {state.limit} revues ce mois-ci
        </p>
      </Link>
    )
  }

  return (
    <Link to="/billing" onClick={onNavigate} className={clsx(box, 'border-amber-300/20')}>
      <div className="flex items-center gap-2 text-xs font-semibold text-amber-200">
        <AlertTriangleIcon className="h-4 w-4" />
        {state.kind === 'trial-expired'
          ? 'Essai terminé'
          : state.kind === 'expired'
            ? 'Abonnement échu'
            : 'Aucun abonnement actif'}
      </div>
      <p className="mt-1.5 text-[11px] leading-relaxed text-slate-400">
        {state.kind === 'expired'
          ? 'Contactez-nous pour renouveler et continuer à générer des revues.'
          : 'Contactez-nous pour souscrire et continuer à générer des revues.'}
      </p>
    </Link>
  )
}

/** Message du bandeau de tableau de bord (fin d'essai, échéance à J-7 / J-3, période
 * échue, quota presque atteint), ou null si tout va bien. */
function bannerFor(state: UsageState): { tone: 'amber' | 'red'; message: string } | null {
  switch (state.kind) {
    case 'trial-expired':
      return { tone: 'red', message: 'Votre essai gratuit est terminé. Contactez-nous pour souscrire une formule.' }
    case 'expired':
      return {
        tone: 'red',
        message: `Votre abonnement a pris fin${state.endedOn ? ` le ${formatDate(state.endedOn)}` : ''}. Contactez-nous pour le renouveler.`,
      }
    case 'none':
    case 'inactive':
      return { tone: 'red', message: 'Votre organisation n’a pas d’abonnement actif. Contactez-nous pour souscrire.' }
    case 'trial':
      if (state.daysLeft <= 3) {
        return {
          tone: 'amber',
          message: `Votre essai gratuit se termine ${state.daysLeft <= 1 ? 'très bientôt' : `dans ${state.daysLeft} jours`}. Contactez-nous pour souscrire sans interrompre votre veille.`,
        }
      }
      break
    case 'active':
      if (state.overdue) {
        return {
          tone: 'red',
          message: `Votre période d’abonnement est terminée : accès maintenu jusqu’au ${formatDate(state.accessUntil)}. Contactez-nous pour renouveler.`,
        }
      }
      if (state.daysLeft !== null && state.daysLeft <= 7) {
        return state.endsAtPeriodEnd
          ? { tone: 'amber', message: `Votre abonnement résilié prend fin le ${formatDate(state.renewsOn)}.` }
          : {
              tone: state.daysLeft <= 3 ? 'red' : 'amber',
              message: `Votre abonnement arrive à échéance ${state.daysLeft <= 1 ? 'demain' : `dans ${state.daysLeft} jours`} (le ${formatDate(state.renewsOn)}). Contactez-nous pour le renouveler.`,
            }
      }
      break
    default:
      return null
  }
  if (state.limit > 0 && state.used / state.limit >= 0.8) {
    const reached = state.used >= state.limit
    return {
      tone: reached ? 'red' : 'amber',
      message: `${reached ? `Quota atteint : ${state.limit} revues ce mois-ci.` : `${state.used} revues sur ${state.limit} utilisées ce mois-ci.`} Contactez-nous pour passer à une formule supérieure.`,
    }
  }
  return null
}

/** Bandeau du tableau de bord : renouvellement, fin d'essai ou quota presque atteint. */
export function UsageBanner() {
  const { data: subscription, isLoading } = useSubscription()
  const banner = bannerFor(usageStateOf(subscription, isLoading))
  return banner ? <BannerShell tone={banner.tone}>{banner.message}</BannerShell> : null
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
        <WhatsAppButton topic="billing" organizationName={organization?.name} variant="link" label="Nous contacter" />
        <Link to="/billing" className="btn-secondary btn-sm">
          Voir l’abonnement
        </Link>
      </div>
    </div>
  )
}
