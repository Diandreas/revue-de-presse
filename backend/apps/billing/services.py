"""Point d'entrée unique qui modifie Subscription/Invoice. Les vues, webhooks et
tâches Celery appellent ces méthodes — jamais les modèles directement."""
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Subscription

logger = logging.getLogger(__name__)


def _default_period_end():
    return timezone.now() + timedelta(days=30)


class SubscriptionService:
    @staticmethod
    @transaction.atomic
    def start_subscription(*, organization, plan, provider):
        subscription, _created = Subscription.objects.update_or_create(
            organization=organization,
            defaults={"plan": plan, "provider": provider, "status": Subscription.Status.INCOMPLETE},
        )
        return subscription

    @staticmethod
    @transaction.atomic
    def activate(*, subscription, provider_customer_id="", provider_subscription_id="", period_end=None):
        subscription.status = Subscription.Status.ACTIVE
        if provider_customer_id:
            subscription.provider_customer_id = provider_customer_id
        if provider_subscription_id:
            subscription.provider_subscription_id = provider_subscription_id
        subscription.current_period_start = timezone.now()
        subscription.current_period_end = period_end or _default_period_end()
        subscription.save()
        return subscription

    @staticmethod
    @transaction.atomic
    def renew(*, subscription, period_end=None):
        subscription.status = Subscription.Status.ACTIVE
        subscription.current_period_start = timezone.now()
        subscription.current_period_end = period_end or _default_period_end()
        subscription.save()
        return subscription

    @staticmethod
    @transaction.atomic
    def mark_past_due(*, subscription):
        subscription.status = Subscription.Status.PAST_DUE
        subscription.save(update_fields=["status", "updated_at"])
        return subscription

    @staticmethod
    @transaction.atomic
    def cancel(*, subscription):
        subscription.status = Subscription.Status.CANCELED
        subscription.save(update_fields=["status", "updated_at"])
        return subscription

    @staticmethod
    def has_quota_for_new_review(*, organization):
        subscription = getattr(organization, "subscription", None)
        if subscription is None or subscription.status not in (
            Subscription.Status.ACTIVE,
            Subscription.Status.TRIALING,
        ):
            return False

        from apps.press_review.models import PressReviewJob

        period_start = subscription.current_period_start or organization.created_at
        count = PressReviewJob.objects.filter(organization=organization, created_at__gte=period_start).count()
        return count < subscription.plan.max_reviews_per_month
