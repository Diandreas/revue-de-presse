import logging
import uuid

import requests
from django.conf import settings

from ..invoicing import amounts_from_ht
from ..models import Invoice, Subscription
from ..services import InvoiceService
from .base import SubscriptionProvider

logger = logging.getLogger(__name__)


class CamPayProvider(SubscriptionProvider):
    """Mobile Money (MTN MoMo + Orange Money) via l'agrégateur CamPay. Il n'existe pas
    de prélèvement récurrent réel côté Mobile Money : on émet une demande de collecte
    mensuelle (voir billing.tasks.request_monthly_mobile_money_renewals) et on attend
    la confirmation par webhook."""

    def __init__(self):
        self.enabled = bool(settings.CAMPAY_APP_USERNAME and settings.CAMPAY_APP_PASSWORD)
        self.base_url = settings.CAMPAY_BASE_URL.rstrip("/")

    def _get_token(self):
        response = requests.post(
            f"{self.base_url}/token/",
            data={"username": settings.CAMPAY_APP_USERNAME, "password": settings.CAMPAY_APP_PASSWORD},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()["token"]

    def create_checkout(self, *, organization, plan, subscription, phone_number=None):
        if not self.enabled:
            logger.warning("Identifiants CamPay non configurés : retour d'une collecte factice.")
            return {
                "provider": "mobile_money",
                "mock": True,
                "reference": None,
                "detail": "Mobile Money non configuré — fournissez les identifiants CamPay pour l'activer.",
            }
        if not phone_number:
            raise ValueError("Un numéro de téléphone Mobile Money est requis.")

        reference = f"sub-{subscription.id}-{uuid.uuid4().hex[:8]}"
        # Prix catalogue HT -> montant TTC réellement demandé au client.
        amount_ttc = amounts_from_ht(plan.price_amount, currency="XAF")["amount"]
        token = self._get_token()
        response = requests.post(
            f"{self.base_url}/collect/",
            headers={"Authorization": f"Token {token}"},
            json={
                "amount": str(int(amount_ttc)),
                "currency": "XAF",
                "from": phone_number,
                "description": f"Abonnement {plan.name} — Revue de Presse",
                "external_reference": reference,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        InvoiceService.create_for_plan(
            subscription=subscription,
            plan=plan,
            provider=Subscription.Provider.MOBILE_MONEY,
            provider_reference=reference,
            raw_payload=data,
        )
        return {
            "provider": "mobile_money",
            "mock": False,
            "reference": reference,
            "operator_reference": data.get("reference"),
        }

    def cancel(self, *, subscription):
        # CamPay n'a pas de notion d'abonnement récurrent à annuler côté serveur : on
        # se contente d'arrêter les relances (SubscriptionService.cancel suffit).
        return None

    def handle_webhook(self, *, payload):
        reference = str(payload.get("external_reference") or "").strip()
        if not reference:
            logger.warning("Webhook CamPay sans référence : ignoré.")
            return None
        # Seule une facture Mobile Money encore en attente peut être soldée par CamPay (une
        # facture de virement ou déjà payée ne doit jamais l'être), et une seule fois.
        invoice = (
            Invoice.objects.filter(
                provider=Subscription.Provider.MOBILE_MONEY,
                provider_reference=reference,
                status=Invoice.Status.PENDING,
            )
            .select_related("subscription")
            .first()
        )
        if invoice is None:
            logger.warning("Webhook CamPay sans facture en attente correspondante : %s", reference)
            return None

        invoice.raw_payload = payload
        invoice.save(update_fields=["raw_payload", "updated_at"])
        if payload.get("status") == "SUCCESSFUL":
            # Montant encaissé par l'opérateur : pas de contrôle face au prix catalogue actuel.
            return InvoiceService.settle(invoice=invoice, check_amount=False)
        return InvoiceService.reject(invoice=invoice, reason=f"Paiement Mobile Money refusé ({payload.get('status')}).")
