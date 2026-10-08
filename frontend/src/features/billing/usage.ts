import type { Subscription } from '../../api/types'
import { daysUntil } from '../../lib/format'

export type UsageState =
  | { kind: 'loading' }
  | { kind: 'none' }
  | { kind: 'trial'; daysLeft: number; used: number; limit: number; planName: string }
  | { kind: 'trial-expired'; used: number; limit: number }
  | { kind: 'active'; used: number; limit: number; planName: string; renewsOn: string | null }
  | { kind: 'inactive'; status: Subscription['status']; planName: string }

/** Lecture unique de l'état d'abonnement, partagée par la barre latérale, le tableau de
 * bord, la page d'envoi et la page Abonnement (mêmes règles que le serveur). */
export function usageStateOf(subscription: Subscription | null | undefined, isLoading = false): UsageState {
  if (isLoading || subscription === undefined) return { kind: 'loading' }
  if (subscription === null) return { kind: 'none' }
  const used = subscription.reviews_used
  const limit = subscription.reviews_limit
  if (subscription.status === 'trialing') {
    const daysLeft = daysUntil(subscription.current_period_end)
    if (subscription.current_period_end && new Date(subscription.current_period_end).getTime() < Date.now()) {
      return { kind: 'trial-expired', used, limit }
    }
    return { kind: 'trial', daysLeft, used, limit, planName: subscription.plan.name }
  }
  if (subscription.status === 'active') {
    return { kind: 'active', used, limit, planName: subscription.plan.name, renewsOn: subscription.current_period_end }
  }
  return { kind: 'inactive', status: subscription.status, planName: subscription.plan.name }
}

/** Message bloquant si une nouvelle revue sera refusée par le serveur, sinon null. */
export function blockingReason(state: UsageState): string | null {
  switch (state.kind) {
    case 'none':
    case 'inactive':
      return 'Aucun abonnement actif : choisissez une formule pour lancer de nouvelles revues.'
    case 'trial-expired':
      return 'Votre essai gratuit est terminé : choisissez une formule pour continuer.'
    case 'trial':
    case 'active':
      return state.used >= state.limit
        ? `Quota atteint (${state.limit} revues sur la période) : passez à une formule supérieure pour continuer.`
        : null
    default:
      return null
  }
}
