import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Subscription
from .providers import get_provider
from .services import SubscriptionService, billing_is_manual

logger = logging.getLogger(__name__)

# Abonnements dont l'échéance est suivie ici (Stripe gère son propre cycle via ses webhooks).
SELF_MANAGED_PROVIDERS = [
    Subscription.Provider.MOBILE_MONEY,
    Subscription.Provider.BANK_TRANSFER,
    Subscription.Provider.MANUAL,
]


@shared_task
def request_monthly_mobile_money_renewals():
    """Les abonnements Mobile Money n'ont pas de prélèvement automatique réel : on
    émet une demande de collecte quelques jours avant l'échéance (voir CamPayProvider).
    En mode manuel, aucune demande de paiement n'est envoyée : l'équipe renouvelle."""
    if billing_is_manual():
        logger.info("Facturation manuelle : aucune relance Mobile Money automatique.")
        return 0
    upcoming = Subscription.objects.filter(
        provider=Subscription.Provider.MOBILE_MONEY,
        status=Subscription.Status.ACTIVE,
        cancel_at_period_end=False,
        current_period_end__lte=timezone.now() + timedelta(days=3),
        current_period_end__gt=timezone.now(),
    ).select_related("organization", "plan")

    provider = get_provider("mobile_money")
    requested = 0
    for subscription in upcoming:
        phone = (subscription.metadata or {}).get("phone_number")
        if not phone:
            logger.warning("Abonnement %s sans numéro Mobile Money enregistré, relance impossible.", subscription.id)
            continue
        try:
            provider.create_checkout(
                organization=subscription.organization,
                plan=subscription.plan,
                subscription=subscription,
                phone_number=phone,
            )
            requested += 1
        except Exception:
            logger.exception("Échec de la demande de renouvellement Mobile Money pour %s", subscription.id)
    return requested


@shared_task
def check_overdue_subscriptions():
    """Fait suivre aux abonnements échus les mêmes règles que SubscriptionService.grants_access :

    - période terminée et résiliation demandée -> `canceled` ;
    - période terminée sans renouvellement -> `past_due` (« en retard ») : l'accès reste
      ouvert BILLING_GRACE_DAYS jours, puis grants_access le ferme d'après la date.

    L'abonnement n'est jamais résilié d'office : l'équipe le prolonge depuis l'admin dès
    réception du paiement."""
    now = timezone.now()
    expired = Subscription.objects.filter(
        status__in=[Subscription.Status.ACTIVE, Subscription.Status.PAST_DUE],
        provider__in=SELF_MANAGED_PROVIDERS,
        current_period_end__lt=now,
    )
    for subscription in expired:
        if subscription.cancel_at_period_end:
            SubscriptionService.cancel(subscription=subscription)
        elif subscription.status != Subscription.Status.PAST_DUE:
            SubscriptionService.mark_past_due(subscription=subscription)


@shared_task
def send_renewal_reminders():
    for days_before in settings.SUBSCRIPTION_RENEWAL_REMINDER_DAYS_BEFORE:
        target_date = (timezone.now() + timedelta(days=days_before)).date()
        subscriptions = Subscription.objects.filter(
            status=Subscription.Status.ACTIVE,
            cancel_at_period_end=False,
            provider__in=SELF_MANAGED_PROVIDERS,
            current_period_end__date=target_date,
        ).select_related("organization", "plan")
        for subscription in subscriptions:
            _send_reminder_email(subscription, days_before)


def _renewal_instructions():
    if billing_is_manual():
        contact = getattr(settings, "BILLING_CONTACT_WHATSAPP", "")
        return f"Contactez-nous sur WhatsApp au {contact} pour le renouveler sans interruption de service."
    return "Merci de procéder au paiement pour éviter une interruption de service."


def _send_reminder_email(subscription, days_before):
    recipients = list(
        subscription.organization.memberships.filter(role__in=["owner", "admin"]).values_list(
            "user__email", flat=True
        )
    )
    if not recipients:
        return
    try:
        send_mail(
            subject=f"Votre abonnement Revue de Presse expire dans {days_before} jour(s)",
            message=(
                f"L'abonnement de {subscription.organization.name} arrive à échéance le "
                f"{timezone.localtime(subscription.current_period_end):%d/%m/%Y}. {_renewal_instructions()}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=True,
        )
    except Exception:
        logger.exception("Échec de l'envoi du rappel de renouvellement pour %s", subscription.id)
