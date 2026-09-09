import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Subscription
from .providers import get_provider
from .services import SubscriptionService

logger = logging.getLogger(__name__)


@shared_task
def request_monthly_mobile_money_renewals():
    """Les abonnements Mobile Money n'ont pas de prélèvement automatique réel : on
    émet une demande de collecte quelques jours avant l'échéance (voir CamPayProvider)."""
    upcoming = Subscription.objects.filter(
        provider=Subscription.Provider.MOBILE_MONEY,
        status=Subscription.Status.ACTIVE,
        current_period_end__lte=timezone.now() + timedelta(days=3),
        current_period_end__gt=timezone.now(),
    ).select_related("organization", "plan")

    provider = get_provider("mobile_money")
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
        except Exception:
            logger.exception("Échec de la demande de renouvellement Mobile Money pour %s", subscription.id)


@shared_task
def check_overdue_subscriptions():
    """Passe en `past_due` puis `canceled` les abonnements Mobile Money/virement dont
    la période de grâce est dépassée sans facture payée (Stripe gère son propre cycle
    via ses webhooks : on ne le touche pas ici)."""
    now = timezone.now()
    grace_by_provider = {
        Subscription.Provider.MOBILE_MONEY: timedelta(days=settings.SUBSCRIPTION_MOBILE_MONEY_GRACE_DAYS),
        Subscription.Provider.BANK_TRANSFER: timedelta(days=settings.SUBSCRIPTION_BANK_TRANSFER_GRACE_DAYS),
    }

    overdue = Subscription.objects.filter(
        status__in=[Subscription.Status.ACTIVE, Subscription.Status.PAST_DUE],
        provider__in=list(grace_by_provider),
        current_period_end__lt=now,
    )
    for subscription in overdue:
        grace = grace_by_provider[subscription.provider]
        if now > subscription.current_period_end + grace:
            SubscriptionService.cancel(subscription=subscription)
        elif subscription.status != Subscription.Status.PAST_DUE:
            SubscriptionService.mark_past_due(subscription=subscription)


@shared_task
def send_renewal_reminders():
    for days_before in settings.SUBSCRIPTION_RENEWAL_REMINDER_DAYS_BEFORE:
        target_date = (timezone.now() + timedelta(days=days_before)).date()
        subscriptions = Subscription.objects.filter(
            status=Subscription.Status.ACTIVE,
            provider__in=[Subscription.Provider.MOBILE_MONEY, Subscription.Provider.BANK_TRANSFER],
            current_period_end__date=target_date,
        ).select_related("organization", "plan")
        for subscription in subscriptions:
            _send_reminder_email(subscription, days_before)


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
                f"Le renouvellement de {subscription.organization.name} arrive à échéance le "
                f"{subscription.current_period_end:%d/%m/%Y}. Merci de procéder au paiement pour "
                "éviter une interruption de service."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=True,
        )
    except Exception:
        logger.exception("Échec de l'envoi du rappel de renouvellement pour %s", subscription.id)
