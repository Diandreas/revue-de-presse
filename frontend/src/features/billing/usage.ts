import type { Subscription } from '../../api/types'
import { daysUntil } from '../../lib/format'

export type UsageState =
  | { kind: 'loading' }
  | { kind: 'none' }
  | { kind: 'trial'; daysLeft: number; used: number; limit: number; planName: string }
  | { kind: 'trial-expired'; used: number; limit: number }
  | {
      kind: 'active'
      used: number
      limit: number
      planName: string
      renewsOn: string | null
      /** Jours avant la fin de la période payée (null : pas d'échéance connue). */
      daysLeft: number | null
      /** Période terminée : accès maintenu pendant le délai de grâce, jusqu'à `accessUntil`. */
      overdue: boolean
      accessUntil: string | null
      endsAtPeriodEnd: boolean
    }
  | { kind: 'expired'; planName: string; endedOn: string | null }
  | { kind: 'inactive'; status: Subscription['status']; planName: string }

/** Lecture unique de l'état d'abonnement, partagée par la barre latérale, le tableau de
 * bord, la page d'envoi et la page Abonnement. L'accès vient du serveur (`has_access`,
 * délai de grâce compris) : l'interface ne recalcule pas les règles. */
export function usageStateOf(subscription: Subscription | null | undefined, isLoading = false): UsageState {
  if (isLoading || subscription === undefined) return { kind: 'loading' }
  if (subscription === null) return { kind: 'none' }
  const used = subscription.reviews_used
  const limit = subscription.reviews_limit
  const end = subscription.current_period_end
  if (subscription.status === 'trialing') {
    if (!subscription.has_access) return { kind: 'trial-expired', used, limit }
    return { kind: 'trial', daysLeft: daysUntil(end), used, limit, planName: subscription.plan.name }
  }
  if (subscription.status === 'active' || subscription.status === 'past_due') {
    if (!subscription.has_access) return { kind: 'expired', planName: subscription.plan.name, endedOn: end }
    return {
      kind: 'active',
      used,
      limit,
      planName: subscription.plan.name,
      renewsOn: end,
      daysLeft: end ? daysUntil(end) : null,
      overdue: end !== null && new Date(end).getTime() < Date.now(),
      accessUntil: subscription.access_until,
      endsAtPeriodEnd: subscription.cancel_at_period_end,
    }
  }
  return { kind: 'inactive', status: subscription.status, planName: subscription.plan.name }
}

/** Message bloquant si une nouvelle revue sera refusée par le serveur, sinon null. */
export function blockingReason(state: UsageState): string | null {
  switch (state.kind) {
    case 'none':
    case 'inactive':
      return 'Aucun abonnement actif : contactez notre équipe pour souscrire une formule.'
    case 'trial-expired':
      return 'Votre essai gratuit est terminé : contactez notre équipe pour souscrire une formule.'
    case 'expired':
      return 'Votre abonnement est arrivé à échéance : contactez notre équipe pour le renouveler.'
    case 'trial':
    case 'active':
      return state.used >= state.limit
        ? `Quota atteint (${state.limit} revues ce mois-ci) : contactez notre équipe pour passer à une formule supérieure.`
        : null
    default:
      return null
  }
}
