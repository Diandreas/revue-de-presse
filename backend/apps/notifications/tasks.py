"""Tâches Celery : envoi d'e-mails avec réessais, rappels planifiés et surveillance.

Les tâches périodiques sont créées par la migration 0002 (django-celery-beat, planning
modifiable ensuite dans /admin/django_celery_beat/)."""
import logging
import smtplib
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from . import services

logger = logging.getLogger(__name__)

EMAIL_MAX_RETRIES = 5
EMAIL_RETRY_BASE_SECONDS = 60  # 1, 2, 4, 8, 16 min : laisse au fournisseur SMTP le temps de revenir
# Refus définitifs : réessayer ne changerait rien (adresse inexistante…).
PERMANENT_SMTP_ERRORS = (smtplib.SMTPRecipientsRefused,)


def deliver_email(*, to, subject, text, html="", reply_to=None):
    """Envoi SMTP synchrone (lève en cas d'échec)."""
    message = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=list(to),
        reply_to=list(reply_to or []) or None,
    )
    if html:
        message.attach_alternative(html, "text/html")
    message.send(fail_silently=False)


def deliver_or_retry(task, payload):
    """Corps de `send_email`, séparé pour être testé avec une fausse tâche.

    Erreur SMTP/réseau -> nouvelle tentative avec délai croissant (lève `Retry`). Refus
    définitif, tentatives épuisées ou mode eager (dev/tests : aucun ordonnanceur ne
    rejouerait la tâche, et l'exception remonterait dans la requête ou le pipeline) ->
    erreur journalisée avec la trace, puis False. Jamais d'échec silencieux."""
    subject, to = payload["subject"], payload["to"]
    try:
        deliver_email(**payload)
    except Exception as exc:
        attempt = task.request.retries + 1
        retryable = not isinstance(exc, PERMANENT_SMTP_ERRORS)
        if retryable and not task.request.is_eager and task.request.retries < task.max_retries:
            delay = EMAIL_RETRY_BASE_SECONDS * 2**task.request.retries
            logger.warning(
                "E-mail « %s » à %s non envoyé (tentative %s/%s), nouvel essai dans %ss : %s",
                subject, to, attempt, task.max_retries + 1, delay, exc,
            )
            raise task.retry(exc=exc, countdown=delay)
        logger.error(
            "E-mail « %s » à %s définitivement non envoyé (%s tentative(s)).", subject, to, attempt, exc_info=True
        )
        return False
    logger.info("E-mail « %s » envoyé à %s", subject, to)
    return True


@shared_task(bind=True, max_retries=EMAIL_MAX_RETRIES)
def send_email(self, *, to, subject, text, html="", reply_to=None):
    """Envoie un e-mail transactionnel (texte + HTML), avec réessais espacés."""
    return deliver_or_retry(self, {"to": to, "subject": subject, "text": text, "html": html, "reply_to": reply_to})


@shared_task
def fail_stuck_jobs():
    """Toutes les 10 min : revues sans progression depuis PIPELINE_STUCK_AFTER_MINUTES -> FAILED."""
    from apps.press_review.services.watchdog import fail_stuck_jobs as _fail_stuck_jobs

    failed = _fail_stuck_jobs(older_than=timedelta(minutes=settings.PIPELINE_STUCK_AFTER_MINUTES))
    return [str(job.pk) for job in failed]


@shared_task
def send_trial_ending_reminders():
    """Chaque jour : rappel au propriétaire J-TRIAL_REMINDER_DAYS_BEFORE avant la fin de l'essai."""
    return services.send_trial_ending_reminders(now=timezone.now())


@shared_task
def send_staff_renewal_digest():
    """Chaque matin : liste au staff des clients à contacter (paiements manuels)."""
    return services.send_staff_renewal_digest(now=timezone.now())
