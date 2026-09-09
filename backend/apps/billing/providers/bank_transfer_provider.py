from datetime import timedelta

from django.utils import timezone

from ..models import Invoice, Subscription
from .base import SubscriptionProvider


class BankTransferProvider(SubscriptionProvider):
    """Aucune API externe : génère une facture, l'entreprise télécharge un
    justificatif de virement (InvoiceProofUploadView), un membre de l'équipe
    plateforme valide manuellement (InvoiceReviewView / action admin). Reflète
    l'usage B2B dominant au Cameroun pour les paiements récurrents inter-entreprises,
    plutôt qu'un prélèvement Mobile Money peu adapté à ce contexte."""

    def create_checkout(self, *, organization, plan, subscription):
        invoice = Invoice.objects.create(
            organization=organization,
            subscription=subscription,
            provider=Subscription.Provider.BANK_TRANSFER,
            amount=plan.price_amount,
            currency=plan.currency,
            status=Invoice.Status.PENDING,
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30),
        )
        return {
            "provider": "bank_transfer",
            "invoice_id": str(invoice.id),
            "amount": str(plan.price_amount),
            "currency": plan.currency,
            "detail": "Effectuez le virement puis téléversez le justificatif sur cette facture pour validation.",
        }

    def cancel(self, *, subscription):
        return None
