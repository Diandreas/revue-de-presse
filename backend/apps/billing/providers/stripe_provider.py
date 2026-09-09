import logging

import stripe
from django.conf import settings

from ..models import Invoice, Subscription
from ..services import SubscriptionService
from .base import SubscriptionProvider

logger = logging.getLogger(__name__)

# Devises pour lesquelles Stripe n'utilise pas de sous-unité (le montant Stripe est
# déjà dans l'unité de base — ne PAS diviser par 100). XAF (franc CFA) y figure : c'est
# la devise par défaut de nos Plan, donc l'oubli casserait silencieusement les montants
# facturés dès qu'un plan Stripe en XAF serait utilisé.
STRIPE_ZERO_DECIMAL_CURRENCIES = {
    "bif", "clp", "djf", "gnf", "jpy", "kmf", "krw", "mga",
    "pyg", "rwf", "ugx", "vnd", "vuv", "xaf", "xof", "xpf",
}


def _stripe_amount_to_decimal(amount, currency):
    if (currency or "").lower() in STRIPE_ZERO_DECIMAL_CURRENCIES:
        return amount or 0
    return (amount or 0) / 100


class StripeProvider(SubscriptionProvider):
    def __init__(self):
        self.enabled = bool(settings.STRIPE_SECRET_KEY)
        if self.enabled:
            stripe.api_key = settings.STRIPE_SECRET_KEY

    def create_checkout(self, *, organization, plan, subscription):
        if not self.enabled:
            logger.warning("STRIPE_SECRET_KEY non configurée : retour d'une session Stripe factice.")
            return {
                "provider": "stripe",
                "mock": True,
                "checkout_url": None,
                "detail": "Stripe non configuré — fournissez STRIPE_SECRET_KEY pour activer le paiement carte.",
            }

        if not plan.stripe_price_id:
            raise ValueError(f"Le plan {plan.code} n'a pas de stripe_price_id configuré.")

        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
            success_url=f"{settings.FRONTEND_BASE_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_BASE_URL}/billing/cancel",
            metadata={"organization_id": str(organization.id), "subscription_id": str(subscription.id)},
        )
        return {"provider": "stripe", "mock": False, "checkout_url": session.url}

    def cancel(self, *, subscription):
        if self.enabled and subscription.provider_subscription_id:
            stripe.Subscription.delete(subscription.provider_subscription_id)

    def handle_webhook(self, *, payload, sig_header):
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
        event_type = event["type"]
        data = event["data"]["object"]

        if event_type == "checkout.session.completed":
            self._handle_checkout_completed(data)
        elif event_type == "invoice.paid":
            self._handle_invoice_paid(data)
        elif event_type == "invoice.payment_failed":
            self._handle_payment_failed(data)
        elif event_type == "customer.subscription.deleted":
            self._handle_subscription_deleted(data)
        else:
            logger.info("Événement Stripe ignoré : %s", event_type)
        return event

    def _handle_checkout_completed(self, data):
        subscription_pk = (data.get("metadata") or {}).get("subscription_id")
        if not subscription_pk:
            logger.warning("checkout.session.completed sans subscription_id en métadonnée.")
            return
        subscription = Subscription.objects.filter(pk=subscription_pk).first()
        if subscription is None:
            logger.warning("Abonnement introuvable pour checkout.session.completed : %s", subscription_pk)
            return
        SubscriptionService.activate(
            subscription=subscription,
            provider_customer_id=data.get("customer", "") or "",
            provider_subscription_id=data.get("subscription", "") or "",
        )

    def _handle_invoice_paid(self, data):
        from django.utils import timezone

        subscription = Subscription.objects.filter(provider_subscription_id=data.get("subscription", "")).first()
        if subscription is None:
            logger.warning("invoice.paid Stripe sans abonnement correspondant : %s", data.get("subscription"))
            return
        SubscriptionService.renew(subscription=subscription)
        currency = data.get("currency") or "xaf"
        Invoice.objects.update_or_create(
            provider=Subscription.Provider.STRIPE,
            provider_reference=data["id"],
            defaults={
                "organization": subscription.organization,
                "subscription": subscription,
                "amount": _stripe_amount_to_decimal(data.get("amount_paid"), currency),
                "currency": currency.upper(),
                "status": Invoice.Status.PAID,
                "period_start": subscription.current_period_start,
                "period_end": subscription.current_period_end,
                "paid_at": timezone.now(),
                "raw_payload": data,
            },
        )

    def _handle_payment_failed(self, data):
        subscription = Subscription.objects.filter(provider_subscription_id=data.get("subscription", "")).first()
        if subscription:
            SubscriptionService.mark_past_due(subscription=subscription)

    def _handle_subscription_deleted(self, data):
        subscription = Subscription.objects.filter(provider_subscription_id=data.get("id", "")).first()
        if subscription:
            SubscriptionService.cancel(subscription=subscription)
