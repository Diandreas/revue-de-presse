"""Surveillance des revues bloquées « en cours ».

Un worker tué en plein traitement (redémarrage, manque de mémoire), une tâche perdue par
le broker ou un worker arrêté laissent un job dans un statut actif pour toujours : le
frontend continue de sonder et « Réessayer » reste impossible (il exige FAILED). Cette
fonction, appelée par une tâche périodique (apps.notifications.tasks.fail_stuck_jobs),
passe en FAILED les jobs sans AUCUNE progression depuis `older_than`."""
import logging

from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from ..models import PipelineStepRun, PressReviewJob
from .pipeline import mark_dispatch_failed, mark_step_result, transition_job

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = (
    PressReviewJob.Status.UPLOADED,
    PressReviewJob.Status.TEXT_EXTRACTION,
    PressReviewJob.Status.CHUNKING_SUMMARIZATION,
    PressReviewJob.Status.HIGHLIGHT_DETECTION,
    PressReviewJob.Status.REVIEW_DRAFTING,
)

STUCK_MESSAGE = (
    "Le traitement s'est interrompu : aucune progression depuis {minutes} minutes (serveur "
    "redémarré ou surchargé). Cliquez sur « Réessayer » pour relancer la revue."
)


def stuck_jobs(*, older_than, now=None):
    """Jobs actifs dont ni le job ni aucune étape n'a bougé depuis `older_than`
    (les étapes notent aussi les pauses de relance automatique)."""
    cutoff = (now or timezone.now()) - older_than
    return (
        PressReviewJob.objects.filter(status__in=ACTIVE_STATUSES, updated_at__lt=cutoff)
        .annotate(last_step_activity=Max("step_runs__updated_at"))
        .filter(Q(last_step_activity__isnull=True) | Q(last_step_activity__lt=cutoff))
    )


def fail_stuck_jobs(*, older_than, now=None):
    """Passe les jobs bloqués en FAILED (avec un message invitant à réessayer) et renvoie
    la liste des jobs traités. Le passage en FAILED émet job_status_changed (e-mails)."""
    now = now or timezone.now()
    cutoff = now - older_than
    message = STUCK_MESSAGE.format(minutes=int(older_than.total_seconds() // 60))
    failed = []
    for candidate in stuck_jobs(older_than=older_than, now=now):
        with transaction.atomic():
            job = PressReviewJob.objects.select_for_update().get(pk=candidate.pk)
            # Revérifié sous verrou : un worker a pu reprendre la main entre-temps.
            if (
                job.status not in ACTIVE_STATUSES
                or job.updated_at >= cutoff
                or job.step_runs.filter(updated_at__gte=cutoff).exists()
            ):
                continue
            for step in job.step_runs.filter(status=PipelineStepRun.Status.RUNNING):
                mark_step_result(job, step.step_name, result=PipelineStepRun.Status.FAILED, error_message=message)
            if job.status == PressReviewJob.Status.UPLOADED:
                # Jamais pris par un worker : même traitement qu'une mise en file ratée.
                job = mark_dispatch_failed(job, message)
            else:
                job = transition_job(job, PressReviewJob.Status.FAILED, error_message=message)
        logger.error("Revue %s bloquée sans progression depuis %s : passée en échec.", job.pk, older_than)
        failed.append(job)
    return failed
