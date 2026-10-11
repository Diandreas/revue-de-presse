"""Point d'entrée unique qui modifie Subscription/Invoice. Les vues, webhooks, tâches Celery
et actions d'administration appellent ces méthodes — jamais les modèles directement."""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .invoicing import add_months, amounts_from_ht, amounts_from_ttc
from .models import Invoice, Plan, Subscription

logger = logging.getLogger(__name__)

NO_SUBSCRIPTION_MESSAGE = (
    "Aucun abonnement actif pour votre organisation. Contactez notre équipe (WhatsApp, page "
    "« Abonnement ») pour souscrire et lancer de nouvelles revues."
)
TRIAL_EXPIRED_MESSAGE = (
    "Votre essai gratuit est terminé. Contactez notre équipe (WhatsApp, page « Abonnement ») "
    "pour souscrire et continuer à générer des revues."
)
SUBSCRIPTION_EXPIRED_MESSAGE = (
    "Votre abonnement est arrivé à échéance. Contactez notre équipe (WhatsApp, page "
    "« Abonnement ») pour le renouveler."
)
QUOTA_REACHED_MESSAGE = (
    "Quota atteint : {limit} revues ce mois-ci avec la formule {plan}. Contactez notre équipe "
    "(page « Abonnement ») pour passer à une formule supérieure, ou attendez le mois suivant."
)
MANUAL_BILLING_MESSAGE = (
    "Le paiement en ligne n'est pas disponible : notre équipe active et renouvelle les abonnements. "
    "Contactez-nous sur WhatsApp au {contact} (page « Abonnement »)."
)


class InvoiceError(ValueError):
    """Opération impossible sur une facture (déjà traitée, montant insuffisant…)."""


def billing_is_manual():
    """Mode manuel (défaut) : aucun paiement en ligne, l'équipe active les abonnements dans
    l'admin. Toute valeur autre que « online » est traitée comme manuelle (repli sûr)."""
    return getattr(settings, "BILLING_MODE", "manual") != "online"


def manual_billing_message():
    return MANUAL_BILLING_MESSAGE.format(contact=getattr(settings, "BILLING_CONTACT_WHATSAPP", ""))


def _default_period_end():
    return timezone.now() + timedelta(days=30)


def _grace():
    return timedelta(days=max(0, getattr(settings, "BILLING_GRACE_DAYS", 0)))


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

    # ------------------------------------------------------------------ accès

    @staticmethod
    def access_until(subscription):
        """Date jusqu'à laquelle l'abonnement ouvre le service (None = sans échéance connue).

        Un essai s'arrête exactement à sa date de fin ; une période payée garde l'accès
        BILLING_GRACE_DAYS jours de plus, le temps que l'équipe enregistre le renouvellement."""
        end = subscription.current_period_end
        if end is None:
            return None
        if subscription.status == Subscription.Status.TRIALING:
            return end
        return end + _grace()

    @staticmethod
    def grants_access(subscription, now=None):
        """Essai non expiré, ou période payée (active / en retard) délai de grâce compris."""
        status = subscription.status
        if status not in (Subscription.Status.ACTIVE, Subscription.Status.PAST_DUE, Subscription.Status.TRIALING):
            return False
        until = SubscriptionService.access_until(subscription)
        if until is None:
            # Sans échéance enregistrée (données anciennes, Stripe) : l'état fait foi.
            return status != Subscription.Status.PAST_DUE
        return (now or timezone.now()) <= until

    # ------------------------------------------------------------------ changements de formule

    @staticmethod
    @transaction.atomic
    def request_plan_change(*, subscription, plan, provider):
        """Formule choisie au lancement d'un paiement (mode « online »).

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
        """Renouvellement piloté par Stripe (qui gère lui-même ses périodes)."""
        SubscriptionService._apply_confirmed_payment(subscription, provider)
        subscription.status = Subscription.Status.ACTIVE
        subscription.current_period_start = timezone.now()
        subscription.current_period_end = period_end or _default_period_end()
        subscription.save()
        return subscription

    @staticmethod
    def extension_base(subscription, now=None):
        """Point de départ d'une prolongation : la fin de la période en cours si elle n'est
        pas encore passée (le client ne perd aucun jour payé), sinon maintenant."""
        now = now or timezone.now()
        end = subscription.current_period_end
        return end if end is not None and end > now else now

    @staticmethod
    @transaction.atomic
    def extend(*, subscription, months, plan=None, provider=None, now=None):
        """Active ou prolonge l'abonnement de `months` mois depuis max(maintenant, fin de
        période). Utilisé par l'équipe (admin) et au règlement d'une facture."""
        if months < 1:
            raise ValueError("La durée doit être d'au moins un mois.")
        now = now or timezone.now()
        base = SubscriptionService.extension_base(subscription, now)
        if base == now or subscription.current_period_start is None:
            # Période échue (ou première activation) : nouvelle période à partir de maintenant.
            subscription.current_period_start = now
        subscription.current_period_end = add_months(base, months)
        metadata = dict(subscription.metadata or {})
        if plan is not None:
            subscription.plan = plan
            if metadata.get("pending_plan_code") == plan.code:
                metadata.pop("pending_plan_code")
        subscription.metadata = metadata
        if provider:
            subscription.provider = provider
        subscription.status = Subscription.Status.ACTIVE
        subscription.cancel_at_period_end = False
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
        subscription.cancel_at_period_end = False
        subscription.save(update_fields=["status", "cancel_at_period_end", "updated_at"])
        return subscription

    @staticmethod
    @transaction.atomic
    def request_cancellation(*, subscription):
        """Résiliation demandée par le client : une période payée en cours va jusqu'à son
        terme (cancel_at_period_end), puis check_overdue_subscriptions la clôt. Un essai,
        un abonnement en retard ou sans échéance est résilié tout de suite."""
        end = subscription.current_period_end
        if subscription.status == Subscription.Status.ACTIVE and end is not None and end > timezone.now():
            subscription.cancel_at_period_end = True
            subscription.save(update_fields=["cancel_at_period_end", "updated_at"])
            return subscription
        return SubscriptionService.cancel(subscription=subscription)

    @staticmethod
    @transaction.atomic
    def resume(*, subscription):
        """Annule une résiliation programmée (tant que la période n'est pas terminée)."""
        if subscription.status != Subscription.Status.ACTIVE or not subscription.cancel_at_period_end:
            raise ValueError("Aucune résiliation programmée à annuler.")
        subscription.cancel_at_period_end = False
        subscription.save(update_fields=["cancel_at_period_end", "updated_at"])
        return subscription

    # ------------------------------------------------------------------ quota

    @staticmethod
    def usage_window_start(subscription, now=None):
        """Début du mois de quota en cours. Le quota est mensuel : une période payée de 3 ou
        12 mois est découpée en tranches d'un mois à partir de current_period_start."""
        start = subscription.current_period_start or subscription.organization.created_at
        now = now or timezone.now()
        if start >= now:
            return start
        months = (now.year - start.year) * 12 + (now.month - start.month)
        window = add_months(start, months)
        if window > now:
            window = add_months(start, months - 1)
        return window

    @staticmethod
    def reviews_used(subscription):
        """Nombre de revues lancées sur le mois de quota en cours."""
        from apps.press_review.models import PressReviewJob

        return PressReviewJob.objects.filter(
            organization=subscription.organization,
            created_at__gte=SubscriptionService.usage_window_start(subscription),
        ).count()

    @staticmethod
    def review_quota_denial(*, organization):
        """Raison lisible pour laquelle une nouvelle revue est refusée, ou None si autorisée."""
        subscription = getattr(organization, "subscription", None)
        if subscription is None:
            return NO_SUBSCRIPTION_MESSAGE
        if not SubscriptionService.grants_access(subscription):
            if subscription.status == Subscription.Status.TRIALING:
                return TRIAL_EXPIRED_MESSAGE
            if subscription.status in (Subscription.Status.ACTIVE, Subscription.Status.PAST_DUE):
                return SUBSCRIPTION_EXPIRED_MESSAGE
            return NO_SUBSCRIPTION_MESSAGE
        limit = subscription.plan.max_reviews_per_month
        if SubscriptionService.reviews_used(subscription) >= limit:
            return QUOTA_REACHED_MESSAGE.format(limit=limit, plan=subscription.plan.name)
        return None

    @staticmethod
    def has_quota_for_new_review(*, organization):
        return SubscriptionService.review_quota_denial(organization=organization) is None


# ---------------------------------------------------------------------- places (membres)


def seats_used(organization):
    """Places occupées : membres + invitations en attente encore valables."""
    from apps.accounts.models import Invitation, Membership

    members = Membership.objects.filter(organization=organization).count()
    pending = Invitation.objects.filter(
        organization=organization, status=Invitation.Status.PENDING, expires_at__gt=timezone.now()
    ).count()
    return members + pending


def seats_limit(organization):
    """Nombre de membres permis par la formule, None sans abonnement (aucune limite connue)."""
    subscription = Subscription.objects.filter(organization=organization).select_related("plan").first()
    return subscription.plan.max_seats if subscription else None


def seats_available(organization, *, exclude_invitation=None):
    """Places encore libres selon la formule (jamais négatif), None sans abonnement.

    À l'acceptation d'une invitation, passer `exclude_invitation` : l'invitation acceptée
    occupe déjà une place dans le décompte et ne doit pas se bloquer elle-même."""
    limit = seats_limit(organization)
    if limit is None:
        return None
    used = seats_used(organization)
    if exclude_invitation is not None and exclude_invitation.status == "pending" and not exclude_invitation.is_expired:
        used -= 1
    return max(0, limit - used)


# ---------------------------------------------------------------------- factures


class InvoiceService:
    @staticmethod
    def create_for_plan(*, subscription, plan, provider, months=1, provider_reference="", raw_payload=None):
        """Facture en attente (proforma) pour `months` mois de `plan` au prix catalogue HT."""
        now = timezone.now()
        base = SubscriptionService.extension_base(subscription, now)
        return Invoice.objects.create(
            organization=subscription.organization,
            subscription=subscription,
            plan=plan,
            months=months,
            provider=provider,
            provider_reference=provider_reference,
            currency=plan.currency,
            status=Invoice.Status.PENDING,
            period_start=base,
            period_end=add_months(base, months),
            raw_payload=raw_payload or {},
            **amounts_from_ht(plan.price_amount * months, currency=plan.currency),
        )

    @staticmethod
    def _locked_open_invoice(invoice):
        invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
        if invoice.status not in (Invoice.Status.PENDING, Invoice.Status.PENDING_REVIEW):
            raise InvoiceError("Cette facture n'est pas en attente de paiement.")
        return invoice

    @staticmethod
    def check_amount(invoice):
        """Refuse une facture dont le montant HT ne couvre pas la formule payée (prix
        modifié entre-temps, facture saisie à la main avec une erreur…)."""
        plan = invoice.plan
        if plan is None:
            return
        expected = plan.price_amount * invoice.months
        paid = invoice.amount_ht if invoice.amount_ht is not None else invoice.amount
        if paid < expected:
            raise InvoiceError(
                f"Montant insuffisant : {paid:.0f} {invoice.currency} HT facturés pour {expected:.0f} "
                f"{invoice.currency} HT attendus ({plan.name}, {invoice.months} mois). Vérifiez avant de valider."
            )

    @staticmethod
    @transaction.atomic
    def settle(*, invoice, reviewed_by=None, check_amount=True):
        """Marque payée une facture en attente et prolonge l'abonnement de `invoice.months`
        mois sur la formule de la facture (`invoice.plan`)."""
        invoice = InvoiceService._locked_open_invoice(invoice)
        subscription = invoice.subscription
        if subscription is None:
            raise InvoiceError("Cette facture n'est rattachée à aucun abonnement.")
        if check_amount:
            InvoiceService.check_amount(invoice)
        invoice.status = Invoice.Status.PAID
        invoice.paid_at = timezone.now()
        if reviewed_by is not None:
            invoice.reviewed_by = reviewed_by
        invoice.save(update_fields=["status", "paid_at", "reviewed_by", "updated_at"])
        if invoice.plan is None:
            # Facture antérieure à l'enregistrement de la formule : ancien comportement.
            SubscriptionService._apply_confirmed_payment(subscription, None)
        SubscriptionService.extend(
            subscription=subscription, months=invoice.months, plan=invoice.plan, provider=invoice.provider
        )
        return invoice

    @staticmethod
    @transaction.atomic
    def reject(*, invoice, reviewed_by=None, reason=""):
        """Refuse un justificatif / une facture en attente, sans toucher à l'abonnement."""
        invoice = InvoiceService._locked_open_invoice(invoice)
        invoice.status = Invoice.Status.FAILED
        if reviewed_by is not None:
            invoice.reviewed_by = reviewed_by
        if reason:
            invoice.notes = f"{invoice.notes}\n{reason}".strip() if invoice.notes else reason
        invoice.save(update_fields=["status", "reviewed_by", "notes", "updated_at"])
        return invoice

    @staticmethod
    @transaction.atomic
    def record_manual_payment(
        *,
        subscription,
        months,
        amount_ttc,
        plan=None,
        reference="",
        method="",
        note="",
        recorded_by=None,
        extend=True,
    ):
        """Paiement reçu hors ligne (Mobile Money, virement, espèces…) : crée une facture
        PAYÉE numérotée et, par défaut, prolonge l'abonnement d'autant."""
        plan = plan or subscription.plan
        now = timezone.now()
        if extend:
            period_start = SubscriptionService.extension_base(subscription, now)
            period_end = add_months(period_start, months)
        else:
            period_start = subscription.current_period_start or now
            period_end = subscription.current_period_end or add_months(period_start, months)
        invoice = Invoice.objects.create(
            organization=subscription.organization,
            subscription=subscription,
            plan=plan,
            months=months,
            provider=Subscription.Provider.MANUAL,
            provider_reference=reference,
            currency=plan.currency,
            status=Invoice.Status.PAID,
            period_start=period_start,
            period_end=period_end,
            paid_at=now,
            reviewed_by=recorded_by,
            notes=note,
            raw_payload={"method": method} if method else {},
            **amounts_from_ttc(amount_ttc, currency=plan.currency),
        )
        if extend:
            SubscriptionService.extend(
                subscription=subscription, months=months, plan=plan, provider=Subscription.Provider.MANUAL, now=now
            )
        return invoice
