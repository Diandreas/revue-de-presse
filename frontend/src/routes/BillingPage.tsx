import clsx from 'clsx'
import { useRef, useState, type FormEvent } from 'react'
import { useParams } from 'react-router-dom'
import { extractErrorMessage } from '../api/client'
import type { Invoice, Plan, Subscription, SubscriptionProviderName } from '../api/types'
import { isAdminRole, useAuth } from '../auth/useAuth'
import { Modal } from '../components/Modal'
import { InvoiceStatusBadge, SubscriptionStatusBadge } from '../components/StatusBadge'
import { useToast } from '../components/Toast'
import {
  CheckIcon,
  ClockIcon,
  CreditCardIcon,
  FileTextIcon,
  GiftIcon,
  LandmarkIcon,
  RefreshIcon,
  SmartphoneIcon,
  SparkleIcon,
  UploadCloudIcon,
  UsersIcon,
  ZapIcon,
  type IconComponent,
} from '../components/icons'
import { Alert, EmptyState, PageHeader, ProgressBar, Segmented, Skeleton, Spinner } from '../components/ui'
import {
  useCancelSubscription,
  useCheckoutBankTransfer,
  useCheckoutMobileMoney,
  useCheckoutStripe,
  useInvoices,
  usePlans,
  useSubscription,
  useUploadInvoiceProof,
} from '../features/billing/useBilling'
import { daysUntil, formatAmount, formatDate, formatNumber, plural } from '../lib/format'

const COMMON_FEATURES = [
  'Photos de journaux et fichiers PDF',
  'Détection des risques juridiques et des intox',
  'Catégories de détection personnalisées',
  'Export PDF et Word',
]

const PROVIDER_META: Record<SubscriptionProviderName, { label: string; icon: IconComponent }> = {
  mobile_money: { label: 'Mobile Money', icon: SmartphoneIcon },
  stripe: { label: 'Carte bancaire', icon: CreditCardIcon },
  bank_transfer: { label: 'Virement', icon: LandmarkIcon },
}

function currencyLabel(currency: string) {
  return currency === 'XAF' ? 'FCFA' : currency
}

/* ---------------------------------------------------------------------------
 * Formule en cours
 * ------------------------------------------------------------------------- */

function periodLine(subscription: Subscription) {
  const end = subscription.current_period_end
  switch (subscription.status) {
    case 'trialing': {
      const days = daysUntil(end)
      if (end && new Date(end).getTime() < Date.now()) return `Essai terminé le ${formatDate(end)}`
      return `Essai gratuit jusqu’au ${formatDate(end)} · ${days > 0 ? `${plural(days, 'jour')} restant${days > 1 ? 's' : ''}` : 'dernier jour'}`
    }
    case 'active':
      if (end && new Date(end).getTime() < Date.now()) return `Période terminée le ${formatDate(end)} : renouvellement en attente.`
      return subscription.cancel_at_period_end ? `Prend fin le ${formatDate(end)}` : `Prochain renouvellement le ${formatDate(end)}`
    case 'past_due':
      return 'Paiement en retard : régularisez pour continuer à lancer des revues.'
    case 'canceled':
      return 'Abonnement résilié.'
    default:
      return 'En attente de paiement.'
  }
}

function CurrentPlanCard({
  subscription,
  pendingPlan,
  canManage,
  onCancel,
}: {
  subscription: Subscription
  pendingPlan: Plan | null
  canManage: boolean
  onCancel: () => void
}) {
  const ratio = subscription.reviews_limit ? (subscription.reviews_used / subscription.reviews_limit) * 100 : 0
  const isTrial = subscription.status === 'trialing'
  return (
    <section className="ink-gradient relative overflow-hidden rounded-3xl p-6 text-white shadow-[var(--shadow-lifted)] sm:p-8">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-24 -right-24 h-64 w-64 rounded-full bg-brand-500/30 blur-3xl"
      />
      <div className="relative grid gap-8 md:grid-cols-[minmax(0,1fr)_280px] md:items-end">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <SubscriptionStatusBadge status={subscription.status} />
            {pendingPlan && (
              <span className="chip bg-amber-300/15 text-amber-200 ring-1 ring-amber-300/30">
                <ClockIcon className="h-3 w-3" /> Passage à {pendingPlan.name} dès réception du paiement
              </span>
            )}
          </div>
          <p className="mt-4 flex items-center gap-2 text-sm font-medium text-slate-300">
            {isTrial ? <GiftIcon className="h-4 w-4 text-amber-300" /> : <ZapIcon className="h-4 w-4 text-brand-300" />}
            {isTrial ? 'Vous découvrez la formule' : 'Votre formule'}
          </p>
          <h2 className="mt-1 font-display text-4xl font-semibold tracking-tight">{subscription.plan.name}</h2>
          <p className="mt-2 text-sm text-slate-300">
            {isTrial ? 'Puis ' : ''}
            {formatAmount(subscription.plan.price_amount, subscription.plan.currency)} / mois
          </p>
          <p className="mt-4 text-sm text-slate-200">{periodLine(subscription)}</p>
          {canManage && subscription.status === 'active' && !subscription.cancel_at_period_end && (
            <button
              type="button"
              onClick={onCancel}
              className="mt-5 text-xs font-medium text-slate-400 underline-offset-4 transition hover:text-white hover:underline"
            >
              Résilier l’abonnement
            </button>
          )}
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/[0.06] p-5 backdrop-blur">
          <p className="text-xs font-semibold tracking-wide text-slate-300 uppercase">Revues sur la période</p>
          <p className="mt-2 font-display text-3xl font-semibold tabular-nums">
            {formatNumber(subscription.reviews_used)}
            <span className="text-lg text-slate-400"> / {formatNumber(subscription.reviews_limit)}</span>
          </p>
          <ProgressBar percent={ratio} tone="light" className="mt-3" />
          <p className="mt-4 flex items-center gap-2 text-xs text-slate-300">
            <UsersIcon className="h-3.5 w-3.5" />
            Jusqu’à {plural(subscription.plan.max_seats, 'membre')} dans l’équipe
          </p>
        </div>
      </div>
    </section>
  )
}

/* ---------------------------------------------------------------------------
 * Formules
 * ------------------------------------------------------------------------- */

function PlanCard({
  plan,
  subscription,
  recommended,
  canPurchase,
  onChoose,
}: {
  plan: Plan
  subscription: Subscription | null | undefined
  recommended: boolean
  canPurchase: boolean
  onChoose: () => void
}) {
  const isCurrentPlan = subscription?.plan.code === plan.code
  const isActiveCurrent = isCurrentPlan && subscription?.status === 'active'
  const isPending = subscription?.pending_plan_code === plan.code

  let label = `Choisir ${plan.name}`
  if (isActiveCurrent) label = 'Formule actuelle'
  else if (isPending) label = 'Finaliser le paiement'
  else if (isCurrentPlan && subscription?.status === 'trialing') label = `Activer ${plan.name}`

  return (
    <article
      className={clsx(
        'relative flex flex-col rounded-3xl border bg-white p-6 transition',
        recommended
          ? 'border-brand-300 shadow-[var(--shadow-glow)] ring-1 ring-brand-500/20'
          : 'border-slate-200 shadow-[var(--shadow-card)]',
      )}
    >
      {recommended && (
        <span className="brand-gradient absolute -top-3 left-6 inline-flex items-center gap-1 rounded-full px-3 py-1 text-[11px] font-semibold text-white shadow-md">
          <SparkleIcon className="h-3 w-3" /> Recommandé
        </span>
      )}
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-display text-xl font-semibold text-slate-900">{plan.name}</h3>
        {isCurrentPlan && <span className="chip bg-slate-900 text-white">Votre formule</span>}
      </div>
      <p className="mt-4 flex items-baseline gap-1.5">
        <span className="font-display text-4xl font-semibold tracking-tight text-slate-900 tabular-nums">
          {formatNumber(Number(plan.price_amount))}
        </span>
        <span className="text-sm font-medium text-slate-500">{currencyLabel(plan.currency)} / mois</span>
      </p>

      <ul className="mt-6 space-y-3 text-sm text-slate-700">
        <li className="flex items-start gap-2.5">
          <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />
          <span>
            <strong className="font-semibold text-slate-900">{plural(plan.max_reviews_per_month, 'revue')}</strong> de
            presse par mois
          </span>
        </li>
        <li className="flex items-start gap-2.5">
          <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />
          <span>
            Jusqu’à <strong className="font-semibold text-slate-900">{plural(plan.max_seats, 'membre')}</strong>
          </span>
        </li>
        {COMMON_FEATURES.map((feature) => (
          <li key={feature} className="flex items-start gap-2.5">
            <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
            <span>{feature}</span>
          </li>
        ))}
      </ul>

      <div className="mt-auto pt-7">
        <button
          type="button"
          className={clsx('w-full', recommended && !isActiveCurrent ? 'btn-primary' : 'btn-secondary')}
          disabled={isActiveCurrent || !canPurchase}
          onClick={onChoose}
          title={canPurchase ? undefined : 'Réservé aux propriétaires et administrateurs'}
        >
          {isActiveCurrent && <CheckIcon className="h-4 w-4" />}
          {label}
        </button>
      </div>
    </article>
  )
}

/* ---------------------------------------------------------------------------
 * Paiement
 * ------------------------------------------------------------------------- */

type PaymentMethod = 'mobile_money' | 'card' | 'bank_transfer'

function normalizeCameroonPhone(value: string) {
  const digits = value.replace(/\D/g, '').replace(/^00/, '')
  const local = digits.startsWith('237') ? digits.slice(3) : digits
  return /^6\d{8}$/.test(local) ? `237${local}` : null
}

function PaymentModal({ plan, onClose, onInvoiceCreated }: { plan: Plan | null; onClose: () => void; onInvoiceCreated: () => void }) {
  const toast = useToast()
  const checkoutStripe = useCheckoutStripe()
  const checkoutMobileMoney = useCheckoutMobileMoney()
  const checkoutBankTransfer = useCheckoutBankTransfer()
  const [method, setMethod] = useState<PaymentMethod>('mobile_money')
  const [phone, setPhone] = useState('')
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'warning' | 'danger'; message: string } | null>(null)

  const busy = checkoutStripe.isPending || checkoutMobileMoney.isPending || checkoutBankTransfer.isPending
  const price = plan ? formatAmount(plan.price_amount, plan.currency) : ''

  const close = () => {
    setFeedback(null)
    onClose()
  }

  const payByMobileMoney = async (event: FormEvent) => {
    event.preventDefault()
    if (!plan) return
    const phoneNumber = normalizeCameroonPhone(phone)
    if (!phoneNumber) {
      setFeedback({ tone: 'danger', message: 'Numéro invalide : 9 chiffres commençant par 6 (ex : 6 71 23 45 67).' })
      return
    }
    setFeedback(null)
    try {
      const result = await checkoutMobileMoney.mutateAsync({ planCode: plan.code, phoneNumber })
      setFeedback(
        result.mock
          ? {
              tone: 'warning',
              message:
                'Le paiement Mobile Money n’est pas encore activé sur la plateforme. Utilisez le virement bancaire en attendant.',
            }
          : {
              tone: 'success',
              message: `Demande de ${price} envoyée au +${phoneNumber}. Validez-la sur votre téléphone : la formule s’active dès confirmation.`,
            },
      )
    } catch (error) {
      setFeedback({ tone: 'danger', message: extractErrorMessage(error, 'Échec de la demande Mobile Money.') })
    }
  }

  const payByCard = async () => {
    if (!plan) return
    setFeedback(null)
    try {
      const result = await checkoutStripe.mutateAsync(plan.code)
      if (result.checkout_url) {
        window.location.assign(result.checkout_url)
        return
      }
      setFeedback({
        tone: 'warning',
        message: 'Le paiement par carte n’est pas encore activé sur la plateforme. Utilisez le virement bancaire en attendant.',
      })
    } catch (error) {
      setFeedback({ tone: 'danger', message: extractErrorMessage(error, 'Échec du paiement par carte.') })
    }
  }

  const payByTransfer = async () => {
    if (!plan) return
    setFeedback(null)
    try {
      await checkoutBankTransfer.mutateAsync(plan.code)
      toast.success('Facture créée : effectuez le virement puis envoyez le justificatif.')
      close()
      onInvoiceCreated()
    } catch (error) {
      setFeedback({ tone: 'danger', message: extractErrorMessage(error, 'Impossible de générer la facture.') })
    }
  }

  return (
    <Modal
      open={plan !== null}
      onClose={close}
      title={plan ? `Formule ${plan.name}` : ''}
      description={plan ? `${price} / mois · ${plural(plan.max_reviews_per_month, 'revue')} par mois` : undefined}
    >
      <Segmented
        className="w-full"
        value={method}
        onChange={(value) => {
          setMethod(value)
          setFeedback(null)
        }}
        options={[
          {
            value: 'mobile_money',
            label: (
              <>
                <SmartphoneIcon className="h-4 w-4" /> <span className="hidden sm:inline">Mobile</span> Money
              </>
            ),
          },
          {
            value: 'card',
            label: (
              <>
                <CreditCardIcon className="h-4 w-4" /> Carte
              </>
            ),
          },
          {
            value: 'bank_transfer',
            label: (
              <>
                <LandmarkIcon className="h-4 w-4" /> Virement
              </>
            ),
          },
        ]}
      />

      <div className="mt-6">
        {method === 'mobile_money' && (
          <form className="space-y-4" onSubmit={(e) => void payByMobileMoney(e)} noValidate>
            <p className="text-sm leading-relaxed text-slate-600">
              MTN Mobile Money ou Orange Money : vous recevez une demande de paiement à valider sur votre téléphone.
            </p>
            <div>
              <label className="label" htmlFor="momo-phone">
                Numéro Mobile Money
              </label>
              <div className="flex">
                <span className="inline-flex items-center rounded-l-xl border border-r-0 border-slate-200 bg-slate-50 px-3 text-sm font-medium text-slate-500">
                  +237
                </span>
                <input
                  id="momo-phone"
                  type="tel"
                  inputMode="tel"
                  autoComplete="tel-national"
                  className="input rounded-l-none"
                  placeholder="6 71 23 45 67"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                />
              </div>
            </div>
            <button type="submit" className="btn-primary w-full" disabled={busy || !phone}>
              {checkoutMobileMoney.isPending ? <Spinner /> : <SmartphoneIcon className="h-4 w-4" />}
              Payer {price}
            </button>
          </form>
        )}

        {method === 'card' && (
          <div className="space-y-4">
            <p className="text-sm leading-relaxed text-slate-600">
              Vous êtes redirigé vers la page de paiement sécurisée de notre prestataire (Stripe), puis ramené ici.
            </p>
            <button type="button" className="btn-primary w-full" disabled={busy} onClick={() => void payByCard()}>
              {checkoutStripe.isPending ? <Spinner /> : <CreditCardIcon className="h-4 w-4" />}
              Payer {price} par carte
            </button>
          </div>
        )}

        {method === 'bank_transfer' && (
          <div className="space-y-4">
            <ol className="space-y-3">
              {[
                'Générez la facture du montant de la formule.',
                'Effectuez le virement du montant exact.',
                'Envoyez le justificatif depuis la liste des factures : nous validons et activons la formule.',
              ].map((step, index) => (
                <li key={step} className="flex gap-3 text-sm text-slate-600">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-semibold text-brand-700">
                    {index + 1}
                  </span>
                  <span className="pt-0.5">{step}</span>
                </li>
              ))}
            </ol>
            <button type="button" className="btn-primary w-full" disabled={busy} onClick={() => void payByTransfer()}>
              {checkoutBankTransfer.isPending ? <Spinner /> : <FileTextIcon className="h-4 w-4" />}
              Générer la facture
            </button>
          </div>
        )}

        {feedback && (
          <Alert tone={feedback.tone} className="mt-4">
            {feedback.message}
          </Alert>
        )}
      </div>
    </Modal>
  )
}

/* ---------------------------------------------------------------------------
 * Factures
 * ------------------------------------------------------------------------- */

function InvoicesSection({ canManage, highlight }: { canManage: boolean; highlight: boolean }) {
  const toast = useToast()
  const { data: invoices, isLoading } = useInvoices()
  const uploadProof = useUploadInvoiceProof()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [targetInvoice, setTargetInvoice] = useState<string | null>(null)

  const upload = async (invoiceId: string, file: File) => {
    try {
      await uploadProof.mutateAsync({ invoiceId, file })
      toast.success('Justificatif envoyé : nous le vérifions et activons votre formule.')
    } catch (error) {
      toast.error(extractErrorMessage(error, 'Échec de l’envoi du justificatif.'))
    }
  }

  const uploadingId = uploadProof.isPending ? uploadProof.variables?.invoiceId : null

  return (
    <section
      id="factures"
      className={clsx('card !p-0 scroll-mt-6 transition', highlight && 'ring-2 ring-brand-400 ring-offset-2')}
    >
      <div className="px-5 pt-5 pb-4 sm:px-6">
        <h2 className="section-title">Factures</h2>
        <p className="text-xs text-slate-500">Historique des paiements de votre organisation.</p>
      </div>
      {isLoading && (
        <div className="space-y-2 px-5 pb-5 sm:px-6">
          <Skeleton className="h-14 rounded-xl" />
          <Skeleton className="h-14 rounded-xl" />
        </div>
      )}
      {!isLoading && invoices?.length === 0 && (
        <div className="border-t border-slate-100">
          <EmptyState icon={FileTextIcon} title="Aucune facture pour l’instant" className="!py-8" />
        </div>
      )}
      {invoices && invoices.length > 0 && (
        <ul className="divide-y divide-slate-100 border-t border-slate-100">
          {invoices.map((invoice: Invoice) => {
            const provider = PROVIDER_META[invoice.provider]
            const needsProof = invoice.provider === 'bank_transfer' && invoice.status === 'pending'
            return (
              <li key={invoice.id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:px-6">
                <div className="flex min-w-0 flex-1 items-center gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
                    <provider.icon className="h-5 w-5" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-900 tabular-nums">
                      {formatAmount(invoice.amount, invoice.currency)}
                    </p>
                    <p className="truncate text-xs text-slate-500">
                      {provider.label} · {formatDate(invoice.created_at)}
                      {invoice.paid_at && ` · payée le ${formatDate(invoice.paid_at)}`}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 pl-[52px] sm:pl-0">
                  <InvoiceStatusBadge status={invoice.status} />
                  {needsProof && canManage && (
                    <button
                      type="button"
                      className="btn-secondary btn-sm"
                      disabled={uploadingId === invoice.id}
                      onClick={() => {
                        setTargetInvoice(invoice.id)
                        fileInputRef.current?.click()
                      }}
                    >
                      {uploadingId === invoice.id ? <Spinner /> : <UploadCloudIcon className="h-4 w-4" />}
                      Envoyer le justificatif
                    </button>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}
      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf,image/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file && targetInvoice) void upload(targetInvoice, file)
          e.target.value = ''
        }}
      />
    </section>
  )
}

/* ---------------------------------------------------------------------------
 * Page
 * ------------------------------------------------------------------------- */

export default function BillingPage() {
  const toast = useToast()
  const { outcome } = useParams<{ outcome?: string }>()
  const { organization } = useAuth()
  const canManage = isAdminRole(organization?.my_role)
  const { data: subscription, isLoading: subscriptionLoading } = useSubscription()
  const { data: plans, isLoading: plansLoading } = usePlans()
  const cancelSubscription = useCancelSubscription()

  const [selectedPlan, setSelectedPlan] = useState<Plan | null>(null)
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [highlightInvoices, setHighlightInvoices] = useState(false)

  const sortedPlans = [...(plans ?? [])].sort((a, b) => Number(a.price_amount) - Number(b.price_amount))
  const recommendedCode = sortedPlans.find((p) => p.code === 'pro')?.code ?? sortedPlans[1]?.code
  const pendingPlan = subscription?.pending_plan_code
    ? (sortedPlans.find((p) => p.code === subscription.pending_plan_code) ?? null)
    : null

  const showInvoices = () => {
    document.getElementById('factures')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    setHighlightInvoices(true)
    window.setTimeout(() => setHighlightInvoices(false), 2400)
  }

  const handleCancel = async () => {
    try {
      await cancelSubscription.mutateAsync()
      toast.info('Abonnement résilié.')
    } catch (error) {
      toast.error(extractErrorMessage(error, 'Impossible de résilier l’abonnement.'))
    }
    setConfirmCancel(false)
  }

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Compte"
        title="Abonnement"
        subtitle="Votre formule, votre consommation et vos factures. Paiement par Mobile Money, carte ou virement."
      />

      {outcome === 'success' && (
        <Alert tone="success" title="Paiement reçu">
          Merci ! Votre formule est activée dès que notre prestataire confirme le paiement (généralement en quelques
          secondes). Actualisez la page si besoin.
        </Alert>
      )}
      {outcome === 'cancel' && (
        <Alert tone="warning" title="Paiement interrompu">
          Aucun montant n’a été débité. Vous pouvez choisir un autre moyen de paiement ci-dessous.
        </Alert>
      )}

      {subscriptionLoading ? (
        <Skeleton className="h-60 rounded-3xl" />
      ) : subscription ? (
        <CurrentPlanCard
          subscription={subscription}
          pendingPlan={pendingPlan}
          canManage={canManage}
          onCancel={() => setConfirmCancel(true)}
        />
      ) : (
        <Alert tone="warning" title="Aucun abonnement actif">
          Choisissez une formule ci-dessous pour lancer vos revues de presse.
        </Alert>
      )}

      <section>
        <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="section-title text-lg">Formules</h2>
            <p className="text-sm text-slate-500">Sans engagement, résiliable à tout moment.</p>
          </div>
          {!canManage && (
            <p className="text-xs text-slate-500">Seuls les propriétaires et administrateurs peuvent changer de formule.</p>
          )}
        </div>
        <div className="mt-6 grid gap-6 md:grid-cols-3">
          {plansLoading && [0, 1, 2].map((i) => <Skeleton key={i} className="h-[440px] rounded-3xl" />)}
          {sortedPlans.map((plan) => (
            <PlanCard
              key={plan.id}
              plan={plan}
              subscription={subscription}
              recommended={plan.code === recommendedCode}
              canPurchase={canManage}
              onChoose={() => setSelectedPlan(plan)}
            />
          ))}
        </div>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1.5">
            <SmartphoneIcon className="h-3.5 w-3.5" /> MTN MoMo & Orange Money
          </span>
          <span className="inline-flex items-center gap-1.5">
            <CreditCardIcon className="h-3.5 w-3.5" /> Carte bancaire
          </span>
          <span className="inline-flex items-center gap-1.5">
            <LandmarkIcon className="h-3.5 w-3.5" /> Virement avec facture
          </span>
          <span className="inline-flex items-center gap-1.5">
            <RefreshIcon className="h-3.5 w-3.5" /> Renouvellement mensuel
          </span>
        </div>
      </section>

      <InvoicesSection canManage={canManage} highlight={highlightInvoices} />

      <PaymentModal plan={selectedPlan} onClose={() => setSelectedPlan(null)} onInvoiceCreated={showInvoices} />

      <Modal
        open={confirmCancel}
        onClose={() => setConfirmCancel(false)}
        title="Résilier l’abonnement ?"
        description="Vous ne pourrez plus lancer de nouvelles revues. Les revues existantes restent consultables."
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setConfirmCancel(false)}>
              Garder ma formule
            </button>
            <button type="button" className="btn-danger" disabled={cancelSubscription.isPending} onClick={() => void handleCancel()}>
              {cancelSubscription.isPending && <Spinner />}
              Résilier
            </button>
          </>
        }
      >
        <p className="text-sm leading-relaxed text-slate-600">
          Vous pourrez souscrire à nouveau à tout moment depuis cette page.
        </p>
      </Modal>
    </div>
  )
}
