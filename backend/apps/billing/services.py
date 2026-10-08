"""Point d'entrée unique qui modifie Subscription/Invoice. Les vues, webhooks et
tâches Celery appellent ces méthodes — jamais les modèles directement."""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Plan, Subscription

logger = logging.getLogger(__name__)

NO_SUBSCRIPTION_MESSAGE = (
    "Aucun abonnement actif pour votre organisation. Choisissez une formule dans « Abonnement » "
    "pour lancer de nouvelles revues."
)
TRIAL_EXPIRED_MESSAGE = (
    "Votre essai gratuit est terminé. Choisissez une formule dans « Abonnement » pour continuer "
    "à générer des revues."
)
QUOTA_REACHED_MESSAGE = (
    "Quota atteint : {limit} revues sur cette période avec la formule {plan}. Passez à une "
    "formule supérieure dans « Abonnement » ou attendez le prochain renouvellement."
)


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
    def start_trial(*, organization):
        """Essai gratuit offert à la création d'une entreprise.

        Sans lui, un compte tout juste créé ne peut lancer aucune revue (403 « aucun
        abonnement actif ») tant qu'un paiement n'a pas été validé. Ne fait rien si l'essai
        est désactivé (TRIAL_DAYS=0), si l'organisation a déjà un abonnement, ou si aucun
        plan n'est configuré (ex : `seed_plans` pas encore exécuté)."""
        days = getattr(settings, "TRIAL_DAYS", 0)
        if days <= 0 or Subscription.objects.filter(organization=organization).exists():
            return None
        plan = (
            Plan.objects.filter(code=getattr(settings, "TRIAL_PLAN_CODE", ""), is_active=True).first()
            or Plan.objects.filter(is_active=True).order_by("price_amount").first()
        )
        if plan is None:
            logger.warning("Aucun plan actif : pas d'essai gratuit pour %s (lancez seed_plans).", organization)
            return None
        now = timezone.now()
        return Subscription.objects.create(
            organization=organization,
            plan=plan,
            # Aucun prestataire externe pendant l'essai : le virement est le seul fournisseur
            # sans appel d'API (annulation = no-op). Le choix réel se fait au paiement.
            provider=Subscription.Provider.BANK_TRANSFER,
            status=Subscription.Status.TRIALING,
            current_period_start=now,
            current_period_end=now + timedelta(days=days),
            metadata={"trial": True},
        )

    @staticmethod
    def grants_access(subscription):
        """Actif, ou essai pas encore expiré."""
        if subscription.status == Subscription.Status.ACTIVE:
            return True
        return subscription.status == Subscription.Status.TRIALING and (
            subscription.current_period_end is None or timezone.now() <= subscription.current_period_end
        )

    @staticmethod
    @transaction.atomic
    def request_plan_change(*, subscription, plan, provider):
        """Formule choisie au lancement d'un paiement.

        Tant que l'abonnement en cours donne accès au service, la nouvelle formule reste en
        attente (metadata.pending_plan_code) jusqu'à la confirmation du paiement : sinon un
        simple clic sur « Payer » (paiement abandonné, prestataire non configuré) suffisait
        à obtenir les quotas d'une formule supérieure."""
        metadata = dict(subscription.metadata or {})
        if SubscriptionService.grants_access(subscription):
            if subscription.plan_id == plan.id:
                metadata.pop("pending_plan_code", None)
            else:
                metadata["pending_plan_code"] = plan.code
        else:
            subscription.plan = plan
            subscription.provider = provider
            metadata.pop("pending_plan_code", None)
        subscription.metadata = metadata
        subscription.save(update_fields=["plan", "provider", "metadata", "updated_at"])
        return subscription

    @staticmethod
    def _apply_confirmed_payment(subscription, provider):
        metadata = dict(subscription.metadata or {})
        pending_code = metadata.pop("pending_plan_code", None)
        if pending_code:
            plan = Plan.objects.filter(code=pending_code).first()
            if plan is not None:
                subscription.plan = plan
        subscription.metadata = metadata
        if provider:
            subscription.provider = provider

    @staticmethod
    @transaction.atomic
    def activate(*, subscription, provider_customer_id="", provider_subscription_id="", period_end=None, provider=None):
        SubscriptionService._apply_confirmed_payment(subscription, provider)
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
    def renew(*, subscription, period_end=None, provider=None):
        SubscriptionService._apply_confirmed_payment(subscription, provider)
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
    def reviews_used(subscription):
        """Nombre de revues lancées sur la période en cours de l'abonnement."""
        from apps.press_review.models import PressReviewJob

        period_start = subscription.current_period_start or subscription.organization.created_at
        return PressReviewJob.objects.filter(
            organization=subscription.organization, created_at__gte=period_start
        ).count()

    @staticmethod
    def review_quota_denial(*, organization):
        """Raison lisible pour laquelle une nouvelle revue est refusée, ou None si autorisée."""
        subscription = getattr(organization, "subscription", None)
        if subscription is None or subscription.status not in (
            Subscription.Status.ACTIVE,
            Subscription.Status.TRIALING,
        ):
            return NO_SUBSCRIPTION_MESSAGE
        if not SubscriptionService.grants_access(subscription):
            return TRIAL_EXPIRED_MESSAGE
        limit = subscription.plan.max_reviews_per_month
        if SubscriptionService.reviews_used(subscription) >= limit:
            return QUOTA_REACHED_MESSAGE.format(limit=limit, plan=subscription.plan.name)
        return None

    @staticmethod
    def has_quota_for_new_review(*, organization):
        return SubscriptionService.review_quota_denial(organization=organization) is None
