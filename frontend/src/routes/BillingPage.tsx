import { useRef, useState } from 'react'
import { extractErrorMessage } from '../api/client'
import { InvoiceStatusBadge, SubscriptionStatusBadge } from '../components/StatusBadge'
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

function formatAmount(amount: string, currency: string) {
  const value = Number(amount)
  return `${new Intl.NumberFormat('fr-FR').format(value)} ${currency}`
}

function formatDate(value: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium' }).format(new Date(value))
}

export default function BillingPage() {
  const { data: subscription } = useSubscription()
  const { data: plans, isLoading: plansLoading } = usePlans()
  const { data: invoices } = useInvoices()

  const checkoutStripe = useCheckoutStripe()
  const checkoutMobileMoney = useCheckoutMobileMoney()
  const checkoutBankTransfer = useCheckoutBankTransfer()
  const cancelSubscription = useCancelSubscription()
  const uploadProof = useUploadInvoiceProof()

  const [selectedPlan, setSelectedPlan] = useState<string | null>(null)
  const [phoneNumber, setPhoneNumber] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionResult, setActionResult] = useState<string | null>(null)
  const proofFileInputRef = useRef<HTMLInputElement>(null)
  const [proofInvoiceId, setProofInvoiceId] = useState<string | null>(null)

  const handleStripe = async (planCode: string) => {
    setActionError(null)
    try {
      const result = await checkoutStripe.mutateAsync(planCode)
      if (result.checkout_url) {
        window.location.href = result.checkout_url
      } else {
        setActionResult(result.detail ?? 'Stripe non configuré.')
      }
    } catch (error) {
      setActionError(extractErrorMessage(error, 'Échec du paiement par carte.'))
    }
  }

  const handleMobileMoney = async (planCode: string) => {
    setActionError(null)
    setActionResult(null)
    if (!phoneNumber) {
      setActionError('Renseignez un numéro Mobile Money.')
      return
    }
    try {
      const result = await checkoutMobileMoney.mutateAsync({ planCode, phoneNumber })
      setActionResult(result.detail ?? `Demande de paiement envoyée au ${phoneNumber}.`)
    } catch (error) {
      setActionError(extractErrorMessage(error, 'Échec de la demande Mobile Money.'))
    }
  }

  const handleBankTransfer = async (planCode: string) => {
    setActionError(null)
    setActionResult(null)
    try {
      const result = await checkoutBankTransfer.mutateAsync(planCode)
      setActionResult(result.detail ?? 'Facture créée — téléversez votre justificatif ci-dessous une fois le virement effectué.')
    } catch (error) {
      setActionError(extractErrorMessage(error, 'Impossible de générer la facture.'))
    }
  }

  const handleProofUpload = async (invoiceId: string, file: File) => {
    setActionError(null)
    try {
      await uploadProof.mutateAsync({ invoiceId, file })
      setActionResult('Justificatif envoyé — en attente de validation par notre équipe.')
    } catch (error) {
      setActionError(extractErrorMessage(error, 'Échec de l’envoi du justificatif.'))
    }
  }

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900">Abonnement</h1>
      <p className="mt-1 text-sm text-slate-500">Gérez le plan et le moyen de paiement de votre organisation.</p>

      <div className="card mt-6">
        <h2 className="text-sm font-semibold text-slate-900">Abonnement actuel</h2>
        {subscription ? (
          <div className="mt-3 flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-800">
                {subscription.plan.name} — {formatAmount(subscription.plan.price_amount, subscription.plan.currency)} / mois
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Période en cours jusqu&apos;au {formatDate(subscription.current_period_end)}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <SubscriptionStatusBadge status={subscription.status} />
              {subscription.status === 'active' && (
                <button
                  type="button"
                  className="btn-danger"
                  disabled={cancelSubscription.isPending}
                  onClick={() => void cancelSubscription.mutate()}
                >
                  Annuler
                </button>
              )}
            </div>
          </div>
        ) : (
          <p className="mt-2 text-sm text-slate-500">Aucun abonnement actif. Choisissez un plan ci-dessous.</p>
        )}
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        {plansLoading && <p className="text-sm text-slate-500">Chargement des plans…</p>}
        {plans?.map((plan) => (
          <div key={plan.id} className="card">
            <p className="text-sm font-semibold text-slate-900">{plan.name}</p>
            <p className="mt-1 text-lg font-semibold text-brand-600">{formatAmount(plan.price_amount, plan.currency)}</p>
            <p className="text-xs text-slate-500">par mois</p>
            <ul className="mt-3 space-y-1 text-xs text-slate-600">
              <li>{plan.max_reviews_per_month} revues / mois</li>
              <li>{plan.max_seats} membres</li>
            </ul>
            <button
              type="button"
              className="btn-secondary mt-4 w-full"
              onClick={() => setSelectedPlan(selectedPlan === plan.code ? null : plan.code)}
            >
              {selectedPlan === plan.code ? 'Fermer' : 'Choisir ce plan'}
            </button>

            {selectedPlan === plan.code && (
              <div className="mt-4 space-y-3 border-t border-slate-100 pt-4">
                <button type="button" className="btn-primary w-full" onClick={() => void handleStripe(plan.code)}>
                  Payer par carte (Stripe)
                </button>

                <div>
                  <label className="label">Numéro Mobile Money</label>
                  <input
                    className="input"
                    placeholder="6XXXXXXXX"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                  />
                  <button
                    type="button"
                    className="btn-secondary mt-2 w-full"
                    onClick={() => void handleMobileMoney(plan.code)}
                  >
                    Payer par Mobile Money
                  </button>
                </div>

                <button
                  type="button"
                  className="btn-secondary w-full"
                  onClick={() => void handleBankTransfer(plan.code)}
                >
                  Payer par virement bancaire
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      {actionError && <p className="mt-4 text-sm text-red-600">{actionError}</p>}
      {actionResult && <p className="mt-4 text-sm text-green-700">{actionResult}</p>}

      <div className="card mt-6">
        <h2 className="text-sm font-semibold text-slate-900">Factures</h2>
        <div className="mt-3 space-y-2">
          {invoices?.length === 0 && <p className="text-sm text-slate-500">Aucune facture pour l’instant.</p>}
          {invoices?.map((invoice) => (
            <div key={invoice.id} className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2">
              <div>
                <p className="text-sm text-slate-800">{formatAmount(invoice.amount, invoice.currency)}</p>
                <p className="text-xs text-slate-500">{formatDate(invoice.created_at)}</p>
              </div>
              <div className="flex items-center gap-3">
                <InvoiceStatusBadge status={invoice.status} />
                {invoice.provider === 'bank_transfer' && invoice.status === 'pending' && (
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => {
                      setProofInvoiceId(invoice.id)
                      proofFileInputRef.current?.click()
                    }}
                  >
                    Envoyer le justificatif
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
        <input
          ref={proofFileInputRef}
          type="file"
          accept="application/pdf,image/*"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file && proofInvoiceId) void handleProofUpload(proofInvoiceId, file)
            e.target.value = ''
          }}
        />
      </div>
    </div>
  )
}
