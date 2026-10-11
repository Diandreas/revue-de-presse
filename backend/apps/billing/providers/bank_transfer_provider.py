from ..models import Invoice, Subscription
from ..services import InvoiceService
from .base import SubscriptionProvider


class BankTransferProvider(SubscriptionProvider):
    """Aucune API externe : génère une facture, l'entreprise télécharge un
    justificatif de virement (InvoiceProofUploadView), un membre de l'équipe
    plateforme valide manuellement (InvoiceReviewView / action admin). Reflète
    l'usage B2B dominant au Cameroun pour les paiements récurrents inter-entreprises,
    plutôt qu'un prélèvement Mobile Money peu adapté à ce contexte.

    Réservé au mode « online » : en mode manuel, la vue de checkout refuse avant d'arriver ici."""

    def create_checkout(self, *, organization, plan, subscription):
        # Chaque clic créait une nouvelle facture en attente : on réutilise celle qui attend
        # déjà le virement pour la même formule.
        invoice = Invoice.objects.filter(
            subscription=subscription,
            plan=plan,
            provider=Subscription.Provider.BANK_TRANSFER,
            status=Invoice.Status.PENDING,
        ).first() or InvoiceService.create_for_plan(
            subscription=subscription, plan=plan, provider=Subscription.Provider.BANK_TRANSFER
        )
        return {
            "provider": "bank_transfer",
            "invoice_id": str(invoice.id),
            "invoice_number": invoice.number,
            "amount": str(invoice.amount),
            "currency": invoice.currency,
            "detail": (
                f"Effectuez le virement en indiquant la référence {invoice.number}, puis téléversez "
                "le justificatif sur cette facture pour validation."
            ),
        }

    def cancel(self, *, subscription):
        return None
