"""Quoi envoyer, à qui et quand. Les receivers (signaux) et les tâches planifiées
appellent ces fonctions ; l'envoi effectif passe par emails.queue_email.

Paiements gérés à la main : aucun e-mail n'affiche de prix. Le client est invité à
contacter l'équipe sur WhatsApp, et le staff à contacter le client."""
import logging
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.utils import timezone

from .emails import Email, admin_url, frontend_url, queue_email, staff_recipients, whatsapp_url
from .models import NotificationLog, NotificationPreference

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- utilitaires


def _date(moment):
    return timezone.localtime(moment).strftime("%d/%m/%Y")


def _relative_day(moment, now):
    days = (timezone.localtime(moment).date() - timezone.localtime(now).date()).days
    if days <= 0:
        return "aujourd'hui"
    if days == 1:
        return "demain"
    return f"dans {days} jours"


def _greeting(user):
    name = (getattr(user, "full_name", "") or "").strip()
    return f"Bonjour {name}," if name else "Bonjour,"


def _org_managers(organization):
    """Propriétaires et administrateurs actifs d'une organisation."""
    from apps.accounts.models import Membership

    return [
        membership.user
        for membership in organization.memberships.select_related("user").filter(
            role__in=[Membership.Role.OWNER, Membership.Role.ADMIN], user__is_active=True
        )
    ]


def _owner_label(organization):
    from apps.accounts.models import Membership

    membership = (
        organization.memberships.select_related("user").filter(role=Membership.Role.OWNER).order_by("created_at").first()
    )
    if membership is None:
        return "propriétaire non renseigné"
    user = membership.user
    return f"{user.full_name} <{user.email}>" if user.full_name else user.email


def _job_title(job):
    return job.title or "Revue de presse"


def _review_link(job):
    return frontend_url(f"/jobs/{job.pk}")


OPT_OUT_FOOTER = (
    "Vous recevez cet e-mail car vous avez lancé cette revue. Vous pouvez désactiver ces "
    "e-mails dans Paramètres : {url}"
)


# --------------------------------------------------------------------------- revues


def _job_recipient(job):
    user = job.created_by
    if user is None or not user.is_active or not user.email:
        return None
    if not NotificationPreference.wants_review_updates(user):
        logger.info("Revue %s : %s a désactivé les e-mails de revue.", job.pk, user.email)
        return None
    return user


def review_ready_email(job):
    documents = list(job.documents.all())
    unreadable = sum(1 for document in documents if document.extraction_status == "failed")
    paragraphs = [
        f"Votre revue « {_job_title(job)} » ({job.organization.name}) est prête. Vous pouvez la "
        "relire, la télécharger en PDF ou en Word et la partager.",
        f"{len(documents)} document(s) analysé(s), {job.highlights.count()} point(s) clé(s) détecté(s).",
    ]
    if unreadable:
        paragraphs.append(
            f"Attention : {unreadable} document(s) n'ont pas pu être lus (photo floue, page vide) et "
            "ne figurent pas dans la revue."
        )
    return Email(
        subject=f"Votre revue de presse est prête : {_job_title(job)}",
        greeting=_greeting(job.created_by),
        paragraphs=paragraphs,
        action_label="Ouvrir la revue",
        action_url=_review_link(job),
        footer=OPT_OUT_FOOTER.format(url=frontend_url("/settings")),
    )


def review_failed_email(job):
    paragraphs = [f"La revue « {_job_title(job)} » ({job.organization.name}) n'a pas pu être générée."]
    if job.error_message:
        paragraphs.append(f"Motif : {job.error_message}")
    paragraphs.append(
        "Ouvrez la revue puis cliquez sur « Réessayer ». Si le problème persiste, écrivez-nous sur "
        f"WhatsApp au {settings.SUPPORT_WHATSAPP_NUMBER}."
    )
    return Email(
        subject=f"Échec de la revue « {_job_title(job)} »",
        greeting=_greeting(job.created_by),
        paragraphs=paragraphs,
        action_label="Ouvrir la revue",
        action_url=_review_link(job),
        footer=OPT_OUT_FOOTER.format(url=frontend_url("/settings")),
    )


def _status_label(status):
    from apps.press_review.models import PressReviewJob

    try:
        return PressReviewJob.Status(status).label
    except ValueError:
        return status or "inconnue"


def staff_job_failed_email(job, previous_status):
    creator = job.created_by.email if job.created_by else "inconnu"
    return Email(
        subject=f"[Revue de Presse] Revue en échec — {job.organization.name}",
        paragraphs=["Une revue vient de passer en échec. Le client a été prévenu par e-mail (sauf désactivation)."],
        items=[
            f"Organisation : {job.organization.name}",
            f"Revue : {_job_title(job)} (lancée par {creator})",
            f"Étape au moment de l'échec : {_status_label(previous_status)}",
            f"Motif : {job.error_message or 'non précisé'}",
        ],
        action_label="Voir la revue dans l'admin",
        action_url=admin_url(f"press_review/pressreviewjob/{job.pk}/change/"),
    )


def notify_review_ready(job):
    user = _job_recipient(job)
    if user is not None:
        queue_email(to=[user.email], email=review_ready_email(job))


def notify_review_failed(job, previous_status=""):
    user = _job_recipient(job)
    if user is not None:
        queue_email(to=[user.email], email=review_failed_email(job))
    if settings.STAFF_NOTIFY_JOB_FAILURES:
        queue_email(to=staff_recipients(), email=staff_job_failed_email(job, previous_status))


# --------------------------------------------------------------------------- inscription


def new_registration_email(organization):
    subscription = getattr(organization, "subscription", None)
    if subscription is not None and subscription.status == "trialing" and subscription.current_period_end:
        trial = f"Essai gratuit jusqu'au {_date(subscription.current_period_end)} (formule {subscription.plan.name})"
    else:
        trial = "Aucun essai gratuit en cours"
    return Email(
        subject=f"[Revue de Presse] Nouvelle inscription : {organization.name}",
        paragraphs=[
            "Une nouvelle entreprise vient de s'inscrire. Pensez à la contacter pour l'accompagner "
            "pendant son essai."
        ],
        items=[
            f"Entreprise : {organization.name}",
            f"Propriétaire : {_owner_label(organization)}",
            trial,
            f"Inscrite le : {_date(organization.created_at)}",
        ],
        action_label="Voir l'entreprise dans l'admin",
        action_url=admin_url(f"accounts/organization/{organization.pk}/change/"),
    )


def notify_new_registration(organization_id):
    from apps.accounts.models import Organization

    organization = Organization.objects.filter(pk=organization_id).first()
    if organization is None:
        return False
    return queue_email(to=staff_recipients(), email=new_registration_email(organization))


# --------------------------------------------------------------------------- abonnements


def trial_ending_email(subscription, user, now):
    organization = subscription.organization
    message = quote(f"Bonjour, je souhaite continuer Revue de Presse après l'essai (entreprise : {organization.name}).")
    return Email(
        subject=f"Votre essai gratuit Revue de Presse se termine {_relative_day(subscription.current_period_end, now)}",
        greeting=_greeting(user),
        paragraphs=[
            f"L'essai gratuit de {organization.name} se termine le {_date(subscription.current_period_end)} "
            f"({_relative_day(subscription.current_period_end, now)}).",
            "Pour continuer à générer vos revues sans interruption, contactez-nous sur WhatsApp au "
            f"{settings.SUPPORT_WHATSAPP_NUMBER} : nous vous proposons la formule adaptée à votre volume "
            "(tarif sur devis) et activons votre abonnement directement.",
        ],
        action_label="Nous écrire sur WhatsApp",
        action_url=f"{whatsapp_url()}?text={message}",
    )


def send_trial_ending_reminders(*, now):
    """Rappel unique (NotificationLog) aux owners/admins des essais finissant dans les
    TRIAL_REMINDER_DAYS_BEFORE jours. Renvoie le nombre d'organisations prévenues."""
    from apps.billing.models import Subscription

    horizon = now + timedelta(days=settings.TRIAL_REMINDER_DAYS_BEFORE)
    ending = Subscription.objects.filter(
        status=Subscription.Status.TRIALING, current_period_end__gt=now, current_period_end__lte=horizon
    ).select_related("organization", "plan")
    sent = 0
    for subscription in ending:
        key = f"{subscription.pk}:{timezone.localtime(subscription.current_period_end).date().isoformat()}"
        if not NotificationLog.claim("trial_ending", key):
            continue
        for user in _org_managers(subscription.organization):
            queue_email(to=[user.email], email=trial_ending_email(subscription, user, now))
        sent += 1
    return sent


def _renewal_line(subscription, now):
    end = subscription.current_period_end
    kind = "essai" if subscription.status == "trialing" else "abonnement"
    if subscription.status == "past_due":
        kind = "abonnement en retard de paiement"
    when = f"fin le {_date(end)}" if end >= now else f"terminé le {_date(end)}"
    return (
        f"{subscription.organization.name} — {kind} {subscription.plan.name} — {when} — "
        f"{_owner_label(subscription.organization)} — "
        f"{admin_url(f'billing/subscription/{subscription.pk}/change/')}"
    )


def staff_renewal_digest_email(subscriptions, now):
    return Email(
        subject=f"[Revue de Presse] {len(subscriptions)} client(s) à contacter pour le renouvellement",
        paragraphs=[
            "Paiements gérés manuellement : contactez ces clients (WhatsApp, téléphone) pour leur "
            "renouvellement, puis prolongez l'abonnement dans l'admin une fois le paiement reçu.",
        ],
        items=[_renewal_line(subscription, now) for subscription in subscriptions],
        action_label="Tous les abonnements",
        action_url=admin_url("billing/subscription/"),
    )


def subscriptions_to_renew(*, now):
    """Essais et abonnements qui se terminent dans STAFF_RENEWAL_ALERT_DAYS jours, ou qui
    se sont terminés depuis moins longtemps (à relancer en priorité)."""
    from apps.billing.models import Subscription

    window = timedelta(days=settings.STAFF_RENEWAL_ALERT_DAYS)
    return list(
        Subscription.objects.filter(
            status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING, Subscription.Status.PAST_DUE],
            current_period_end__gte=now - window,
            current_period_end__lte=now + window,
        )
        .select_related("organization", "plan")
        .order_by("current_period_end")
    )


def send_staff_renewal_digest(*, now):
    """Un récapitulatif par jour au plus, seulement s'il y a quelqu'un à contacter."""
    subscriptions = subscriptions_to_renew(now=now)
    if not subscriptions:
        return 0
    if not NotificationLog.claim("staff_renewal_digest", timezone.localtime(now).date().isoformat()):
        return 0
    queue_email(to=staff_recipients(), email=staff_renewal_digest_email(subscriptions, now))
    return len(subscriptions)
