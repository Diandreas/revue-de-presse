import clsx from 'clsx'
import { useState, type FormEvent } from 'react'
import { extractErrorMessage } from '../api/client'
import type { BillingProfile, Invoice, Plan, Subscription } from '../api/types'
import { isAdminRole, useAuth } from '../auth/useAuth'
import { Modal } from '../components/Modal'
import { InvoiceStatusBadge, SubscriptionStatusBadge } from '../components/StatusBadge'
import { useToast } from '../components/Toast'
import { WhatsAppButton } from '../components/WhatsAppButton'
import {
  BuildingIcon,
  CheckIcon,
  ClockIcon,
  DownloadIcon,
  FileTextIcon,
  GiftIcon,
  SparkleIcon,
  UsersIcon,
  ZapIcon,
} from '../components/icons'
import { Alert, EmptyState, PageHeader, ProgressBar, Skeleton, Spinner } from '../components/ui'
import { usageStateOf } from '../features/billing/usage'
import {
  useBillingProfile,
  useCancelSubscription,
  useDownloadInvoicePdf,
  useInvoices,
  usePlans,
  useResumeSubscription,
  useSubscription,
  useUpdateBillingProfile,
} from '../features/billing/useBilling'
import { daysUntil, formatAmount, formatDate, formatNumber, plural } from '../lib/format'

const COMMON_FEATURES = [
  'Photos de journaux et fichiers PDF',
  'Détection des risques juridiques et des intox',
  'Catégories de détection personnalisées',
  'Export PDF et Word',
]

const SUBSCRIBE_LABEL = 'Souscrire / renouveler avec notre équipe'

/* ---------------------------------------------------------------------------
 * Formule en cours
 * ------------------------------------------------------------------------- */

function periodLine(subscription: Subscription) {
  const end = subscription.current_period_end
  const state = usageStateOf(subscription)
  switch (state.kind) {
    case 'trial': {
      const days = daysUntil(end)
      return `Essai gratuit jusqu’au ${formatDate(end)} · ${days > 0 ? `${plural(days, 'jour')} restant${days > 1 ? 's' : ''}` : 'dernier jour'}`
    }
    case 'trial-expired':
      return `Essai terminé le ${formatDate(end)}.`
    case 'active':
      if (!end) return 'Abonnement actif.'
      if (state.overdue) return `Période terminée le ${formatDate(end)} : accès maintenu jusqu’au ${formatDate(state.accessUntil)}.`
      return state.endsAtPeriodEnd ? `Résilié : prend fin le ${formatDate(end)}.` : `Payé jusqu’au ${formatDate(end)}.`
    case 'expired':
      return `Abonnement échu le ${formatDate(end)}.`
    default:
      return subscription.status === 'canceled' ? 'Abonnement résilié.' : 'En attente d’activation par notre équipe.'
  }
}

function CurrentPlanCard({
  subscription,
  organizationName,
  canManage,
  onCancel,
  onResume,
  resuming,
}: {
  subscription: Subscription
  organizationName?: string | null
  canManage: boolean
  onCancel: () => void
  onResume: () => void
  resuming: boolean
}) {
  const ratio = subscription.reviews_limit ? (subscription.reviews_used / subscription.reviews_limit) * 100 : 0
  const isTrial = subscription.status === 'trialing'
  const isRunning = subscription.status === 'active' && subscription.has_access
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
            {subscription.cancel_at_period_end && (
              <span className="chip bg-amber-300/15 text-amber-200 ring-1 ring-amber-300/30">
                <ClockIcon className="h-3 w-3" /> Résiliation programmée
              </span>
            )}
          </div>
          <p className="mt-4 flex items-center gap-2 text-sm font-medium text-slate-300">
            {isTrial ? <GiftIcon className="h-4 w-4 text-amber-300" /> : <ZapIcon className="h-4 w-4 text-brand-300" />}
            {isTrial ? 'Vous découvrez la formule' : 'Votre formule'}
          </p>
          <h2 className="mt-1 font-display text-4xl font-semibold tracking-tight">{subscription.plan.name}</h2>
          <p className="mt-2 text-sm text-slate-300">Tarif sur devis · renouvellement avec notre équipe</p>
          <p className="mt-4 text-sm text-slate-200">{periodLine(subscription)}</p>
          <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-3">
            <WhatsAppButton
              topic="billing"
              organizationName={organizationName}
              variant="primary"
              label={SUBSCRIBE_LABEL}
              className="btn-lg"
            />
            {canManage && isRunning && !subscription.cancel_at_period_end && (
              <button
                type="button"
                onClick={onCancel}
                className="text-xs font-medium text-slate-400 underline-offset-4 transition hover:text-white hover:underline"
              >
                Résilier l’abonnement
              </button>
            )}
            {canManage && subscription.cancel_at_period_end && (
              <button
                type="button"
                onClick={onResume}
                disabled={resuming}
                className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-200 underline underline-offset-4 transition hover:text-white"
              >
                {resuming && <Spinner />}
                Annuler la résiliation
              </button>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/[0.06] p-5 backdrop-blur">
          <p className="text-xs font-semibold tracking-wide text-slate-300 uppercase">
            {subscription.status === 'trialing' ? 'Revues de l’essai' : 'Revues ce mois-ci'}
          </p>
          <p className="mt-2 font-display text-3xl font-semibold tabular-nums">
            {formatNumber(subscription.reviews_used)}
            <span className="text-lg text-slate-400"> / {formatNumber(subscription.reviews_limit)}</span>
          </p>
          <ProgressBar percent={ratio} tone="light" className="mt-3" />
          <p className="mt-4 flex items-center gap-2 text-xs text-slate-300">
            <UsersIcon className="h-3.5 w-3.5" />
            {formatNumber(subscription.seats_used)} / {plural(subscription.seats_limit, 'membre')} (invitations comprises)
          </p>
        </div>
      </div>
    </section>
  )
}

/** Alerte en tête de page quand l'accès est menacé ou coupé. */
function AccessAlert({ subscription, organizationName }: { subscription: Subscription | null; organizationName?: string | null }) {
  const state = usageStateOf(subscription)
  const action = (
    <WhatsAppButton topic="billing" organizationName={organizationName} variant="link" label="Contactez-nous sur WhatsApp" showNumber />
  )
  if (state.kind === 'none' || state.kind === 'inactive') {
    return (
      <Alert tone="warning" title="Aucun abonnement actif" action={action}>
        Contactez-nous pour souscrire une formule : notre équipe l’active dès réception de votre règlement.
      </Alert>
    )
  }
  if (state.kind === 'trial-expired' || state.kind === 'expired') {
    return (
      <Alert tone="danger" title={state.kind === 'expired' ? 'Abonnement échu' : 'Essai terminé'} action={action}>
        Vous ne pouvez plus lancer de nouvelles revues. Contactez-nous pour{' '}
        {state.kind === 'expired' ? 'renouveler votre abonnement' : 'souscrire une formule'} : vos revues restent consultables.
      </Alert>
    )
  }
  if (state.kind === 'active' && state.overdue) {
    return (
      <Alert tone="warning" title="Renouvellement en attente" action={action}>
        Votre période d’abonnement est terminée. L’accès est maintenu jusqu’au {formatDate(state.accessUntil)} :
        contactez-nous pour renouveler sans interruption.
      </Alert>
    )
  }
  return null
}

/* ---------------------------------------------------------------------------
 * Formules (limites uniquement : tarifs sur devis)
 * ------------------------------------------------------------------------- */

function PlanCard({
  plan,
  isCurrentPlan,
  recommended,
  organizationName,
}: {
  plan: Plan
  isCurrentPlan: boolean
  recommended: boolean
  organizationName?: string | null
}) {
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
      <p className="mt-4">
        <span className="font-display text-2xl font-semibold tracking-tight text-slate-900">Sur devis</span>
        <span className="block text-sm font-medium text-slate-500">Contactez-nous pour un tarif adapté</span>
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
        <WhatsAppButton
          topic="billing"
          organizationName={organizationName}
          variant={recommended ? 'primary' : 'light'}
          label={isCurrentPlan ? 'Renouveler' : 'Demander un devis'}
          className="w-full"
        />
      </div>
    </article>
  )
}

const HOW_IT_WORKS = [
  'Écrivez-nous sur WhatsApp : nous établissons votre devis selon la formule et la durée choisies (1, 3 ou 12 mois).',
  'Réglez par Mobile Money ou virement, selon les modalités convenues avec notre équipe.',
  'Nous activons votre formule aussitôt : la facture acquittée apparaît ci-dessous, en PDF.',
]

/* ---------------------------------------------------------------------------
 * Factures
 * ------------------------------------------------------------------------- */

function invoiceTitle(invoice: Invoice) {
  const what = invoice.plan_name ? `${invoice.plan_name} · ${plural(invoice.months, 'mois', 'mois')}` : 'Abonnement'
  return `${invoice.number ?? 'Facture'} — ${what}`
}

function InvoicesSection() {
  const toast = useToast()
  const { data: invoices, isLoading } = useInvoices()
  const download = useDownloadInvoicePdf()
  const downloadingId = download.isPending ? download.variables?.id : null

  const downloadPdf = async (invoice: Invoice) => {
    try {
      await download.mutateAsync(invoice)
    } catch (error) {
      toast.error(extractErrorMessage(error, 'Impossible de télécharger la facture.'))
    }
  }

  return (
    <section id="factures" className="card !p-0 scroll-mt-6">
      <div className="px-5 pt-5 pb-4 sm:px-6">
        <h2 className="section-title">Factures</h2>
        <p className="text-xs text-slate-500">Factures de votre organisation, téléchargeables en PDF (montants TTC).</p>
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
          {invoices.map((invoice) => (
            <li key={invoice.id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:px-6">
              <div className="flex min-w-0 flex-1 items-center gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
                  <FileTextIcon className="h-5 w-5" />
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-slate-900">{invoiceTitle(invoice)}</p>
                  <p className="truncate text-xs text-slate-500 tabular-nums">
                    {formatAmount(invoice.amount, invoice.currency)} TTC · du {formatDate(invoice.period_start)} au{' '}
                    {formatDate(invoice.period_end)}
                    {invoice.paid_at && ` · payée le ${formatDate(invoice.paid_at)}`}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 pl-[52px] sm:pl-0">
                <InvoiceStatusBadge status={invoice.status} />
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  disabled={downloadingId === invoice.id}
                  onClick={() => void downloadPdf(invoice)}
                >
                  {downloadingId === invoice.id ? <Spinner /> : <DownloadIcon className="h-4 w-4" />}
                  PDF
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/* ---------------------------------------------------------------------------
 * Informations de facturation
 * ------------------------------------------------------------------------- */

type ProfileForm = Omit<BillingProfile, 'updated_at'>

const PROFILE_FIELDS: { key: keyof ProfileForm; label: string; placeholder?: string; multiline?: boolean }[] = [
  { key: 'legal_name', label: 'Raison sociale' },
  { key: 'niu', label: 'NIU', placeholder: 'Numéro d’identifiant unique' },
  { key: 'rccm', label: 'RCCM', placeholder: 'RC/DLA/2024/B/1234' },
  { key: 'email', label: 'E-mail de facturation', placeholder: 'comptabilite@entreprise.cm' },
  { key: 'phone', label: 'Téléphone', placeholder: '+237 6 …' },
  { key: 'address', label: 'Adresse', multiline: true },
]

function BillingProfileForm({ profile, canEdit }: { profile: BillingProfile; canEdit: boolean }) {
  const toast = useToast()
  const update = useUpdateBillingProfile()
  const [form, setForm] = useState<ProfileForm>({
    legal_name: profile.legal_name,
    address: profile.address,
    niu: profile.niu,
    rccm: profile.rccm,
    email: profile.email,
    phone: profile.phone,
  })

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await update.mutateAsync(form)
      toast.success('Informations de facturation enregistrées : elles figureront sur vos prochaines factures.')
    } catch (error) {
      toast.error(extractErrorMessage(error, 'Impossible d’enregistrer ces informations.'))
    }
  }

  return (
    <form className="grid gap-4 sm:grid-cols-2" onSubmit={(e) => void submit(e)} noValidate>
      {PROFILE_FIELDS.map((field) => (
        <div key={field.key} className={clsx(field.multiline && 'sm:col-span-2')}>
          <label className="label" htmlFor={`billing-${field.key}`}>
            {field.label}
          </label>
          {field.multiline ? (
            <textarea
              id={`billing-${field.key}`}
              className="input min-h-[72px]"
              value={form[field.key]}
              disabled={!canEdit}
              onChange={(e) => setForm({ ...form, [field.key]: e.target.value })}
            />
          ) : (
            <input
              id={`billing-${field.key}`}
              className="input"
              type={field.key === 'email' ? 'email' : 'text'}
              placeholder={field.placeholder}
              value={form[field.key]}
              disabled={!canEdit}
              onChange={(e) => setForm({ ...form, [field.key]: e.target.value })}
            />
          )}
        </div>
      ))}
      {canEdit && (
        <div className="sm:col-span-2">
          <button type="submit" className="btn-primary" disabled={update.isPending}>
            {update.isPending && <Spinner />}
            Enregistrer
          </button>
        </div>
      )}
    </form>
  )
}

function BillingProfileSection({ canEdit }: { canEdit: boolean }) {
  const { data: profile, isLoading } = useBillingProfile()
  return (
    <section className="card">
      <div className="mb-5 flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
          <BuildingIcon className="h-5 w-5" />
        </span>
        <div>
          <h2 className="section-title">Informations de facturation</h2>
          <p className="text-xs text-slate-500">
            Reportées sur vos factures (raison sociale, NIU, RCCM).
            {!canEdit && ' Seuls les propriétaires et administrateurs peuvent les modifier.'}
          </p>
        </div>
      </div>
      {isLoading || !profile ? (
        <Skeleton className="h-40 rounded-xl" />
      ) : (
        <BillingProfileForm key={profile.updated_at ?? 'nouveau'} profile={profile} canEdit={canEdit} />
      )}
    </section>
  )
}

/* ---------------------------------------------------------------------------
 * Page
 * ------------------------------------------------------------------------- */

export default function BillingPage() {
  const toast = useToast()
  const { organization } = useAuth()
  const canManage = isAdminRole(organization?.my_role)
  const { data: subscription, isLoading: subscriptionLoading } = useSubscription()
  const { data: plans, isLoading: plansLoading } = usePlans()
  const cancelSubscription = useCancelSubscription()
  const resumeSubscription = useResumeSubscription()
  const [confirmCancel, setConfirmCancel] = useState(false)

  const sortedPlans = [...(plans ?? [])].sort((a, b) => a.max_reviews_per_month - b.max_reviews_per_month)
  const recommendedCode = sortedPlans.find((p) => p.code === 'pro')?.code ?? sortedPlans[1]?.code
  const endsOn = subscription?.current_period_end

  const handleCancel = async () => {
    try {
      const updated = await cancelSubscription.mutateAsync()
      toast.info(
        updated.cancel_at_period_end
          ? `Résiliation enregistrée : votre formule reste active jusqu’au ${formatDate(updated.current_period_end)}.`
          : 'Abonnement résilié.',
      )
    } catch (error) {
      toast.error(extractErrorMessage(error, 'Impossible de résilier l’abonnement.'))
    }
    setConfirmCancel(false)
  }

  const handleResume = async () => {
    try {
      await resumeSubscription.mutateAsync()
      toast.success('Résiliation annulée : votre abonnement continue.')
    } catch (error) {
      toast.error(extractErrorMessage(error, 'Impossible d’annuler la résiliation.'))
    }
  }

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Compte"
        title="Abonnement"
        subtitle="Votre formule, votre consommation et vos factures. Souscription et renouvellement avec notre équipe, sur WhatsApp."
        actions={<WhatsAppButton topic="billing" organizationName={organization?.name} label="Une question ? WhatsApp" />}
      />

      {!subscriptionLoading && <AccessAlert subscription={subscription ?? null} organizationName={organization?.name} />}

      {subscriptionLoading ? (
        <Skeleton className="h-60 rounded-3xl" />
      ) : subscription ? (
        <CurrentPlanCard
          subscription={subscription}
          organizationName={organization?.name}
          canManage={canManage}
          onCancel={() => setConfirmCancel(true)}
          onResume={() => void handleResume()}
          resuming={resumeSubscription.isPending}
        />
      ) : (
        <section className="card flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-slate-600">Choisissez une formule avec notre équipe : activation dès réception du règlement.</p>
          <WhatsAppButton topic="billing" organizationName={organization?.name} variant="primary" label={SUBSCRIBE_LABEL} />
        </section>
      )}

      <section>
        <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="section-title text-lg">Formules</h2>
            <p className="text-sm text-slate-500">Tarifs sur devis, selon la formule et la durée. Sans engagement.</p>
          </div>
        </div>
        <div className="mt-6 grid gap-6 md:grid-cols-3">
          {plansLoading && [0, 1, 2].map((i) => <Skeleton key={i} className="h-[420px] rounded-3xl" />)}
          {sortedPlans.map((plan) => (
            <PlanCard
              key={plan.id}
              plan={plan}
              isCurrentPlan={subscription?.plan.code === plan.code}
              recommended={plan.code === recommendedCode}
              organizationName={organization?.name}
            />
          ))}
        </div>
        <ol className="mt-8 grid gap-4 md:grid-cols-3">
          {HOW_IT_WORKS.map((step, index) => (
            <li key={step} className="flex gap-3 text-sm text-slate-600">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-semibold text-brand-700">
                {index + 1}
              </span>
              <span className="pt-0.5">{step}</span>
            </li>
          ))}
        </ol>
      </section>

      <InvoicesSection />

      <BillingProfileSection canEdit={canManage} />

      <Modal
        open={confirmCancel}
        onClose={() => setConfirmCancel(false)}
        title="Résilier l’abonnement ?"
        description={
          endsOn
            ? `Votre formule reste active jusqu’au ${formatDate(endsOn)}, puis ne sera pas renouvelée.`
            : 'Vous ne pourrez plus lancer de nouvelles revues.'
        }
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
          Les revues existantes restent consultables, et vous pouvez annuler la résiliation jusqu’à la fin de la période.
        </p>
      </Modal>
    </div>
  )
}
