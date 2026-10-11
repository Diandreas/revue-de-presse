"""Machine à états du pipeline de génération de revue de presse.

Un seul point d'entrée modifie `PressReviewJob.status` : `transition_job`. Les tâches
Celery (apps.ai_pipeline.tasks) ne touchent jamais `job.status` directement."""
from django.db import transaction
from django.utils import timezone

from ..models import PipelineStepRun, PressReviewJob
from ..signals import announce_status_change

ALLOWED_TRANSITIONS = {
    PressReviewJob.Status.UPLOADED: [PressReviewJob.Status.TEXT_EXTRACTION],
    PressReviewJob.Status.TEXT_EXTRACTION: [
        PressReviewJob.Status.CHUNKING_SUMMARIZATION,
        PressReviewJob.Status.FAILED,
    ],
    PressReviewJob.Status.CHUNKING_SUMMARIZATION: [
        PressReviewJob.Status.HIGHLIGHT_DETECTION,
        PressReviewJob.Status.FAILED,
    ],
    PressReviewJob.Status.HIGHLIGHT_DETECTION: [
        PressReviewJob.Status.REVIEW_DRAFTING,
        PressReviewJob.Status.FAILED,
    ],
    PressReviewJob.Status.REVIEW_DRAFTING: [
        PressReviewJob.Status.REVIEW_READY,
        PressReviewJob.Status.FAILED,
    ],
    PressReviewJob.Status.REVIEW_READY: [PressReviewJob.Status.EXPORTED],
    PressReviewJob.Status.FAILED: [PressReviewJob.Status.TEXT_EXTRACTION],
}

# Poids (%) de chaque étape dans la progression globale. Somme = 95 ; les 5% restants
# sont crédités au passage à REVIEW_READY (finalisation).
STEP_WEIGHTS = {
    PressReviewJob.Status.TEXT_EXTRACTION: 15,
    PressReviewJob.Status.CHUNKING_SUMMARIZATION: 25,
    PressReviewJob.Status.HIGHLIGHT_DETECTION: 35,
    PressReviewJob.Status.REVIEW_DRAFTING: 20,
}
_STEP_ORDER = list(STEP_WEIGHTS.keys())


class InvalidTransition(Exception):
    pass


def _completed_weight(status):
    if status not in _STEP_ORDER:
        return 0
    idx = _STEP_ORDER.index(status)
    return sum(STEP_WEIGHTS[s] for s in _STEP_ORDER[:idx])


@transaction.atomic
def transition_job(job, new_status, *, error_message=""):
    job = PressReviewJob.objects.select_for_update().get(pk=job.pk)
    previous_status = job.status
    allowed = ALLOWED_TRANSITIONS.get(previous_status, [])
    if new_status not in allowed:
        raise InvalidTransition(f"Impossible de passer de {previous_status} à {new_status}.")

    job.status = new_status
    if new_status == PressReviewJob.Status.REVIEW_READY:
        job.progress_percent = 100
        job.completed_at = timezone.now()
    else:
        job.progress_percent = _completed_weight(new_status)

    if new_status == PressReviewJob.Status.TEXT_EXTRACTION and job.started_at is None:
        job.started_at = timezone.now()
    if new_status == PressReviewJob.Status.FAILED:
        job.error_message = error_message
    elif previous_status == PressReviewJob.Status.FAILED:
        job.error_message = ""  # le job repart : l'ancienne erreur n'a plus lieu d'être

    job.save(update_fields=["status", "progress_percent", "started_at", "completed_at", "error_message", "updated_at"])
    announce_status_change(job, previous_status)  # e-mails « revue prête / échec », après commit
    return job


def enter_step(job, job_status, step_name):
    """Passe le job dans l'étape `job_status` puis démarre son PipelineStepRun.

    Idempotent : quand Celery relance une étape après une erreur transitoire, le job est
    déjà dans cet état — on ne re-transitionne pas (TEXT_EXTRACTION -> TEXT_EXTRACTION
    est une transition invalide) mais on réarme l'étape."""
    current = PressReviewJob.objects.values_list("status", flat=True).get(pk=job.pk)
    if current != job_status:
        transition_job(job, job_status)
    return start_step(job, step_name)


def start_step(job, step_name):
    """(Ré)arme une étape au début d'une tentative — la première, un retry automatique
    après erreur transitoire, ou un `Réessayer` manuel : efface donc les traces de la
    tentative précédente (fin, erreur, pause de retry) pour ne pas afficher d'état périmé."""
    step, _created = PipelineStepRun.objects.get_or_create(job=job, step_name=step_name)
    step.status = PipelineStepRun.Status.RUNNING
    if step.started_at is None:
        step.started_at = timezone.now()
    step.finished_at = None
    step.error_message = ""
    step.progress_percent = 0
    result_summary = dict(step.result_summary or {})
    result_summary.pop("retry", None)
    step.result_summary = result_summary
    step.save(
        update_fields=[
            "status", "started_at", "finished_at", "error_message",
            "progress_percent", "result_summary", "updated_at",
        ]
    )
    return step


def note_step_retry(job, step_name, *, attempt, delay_seconds, reason):
    """Rend visible (polling du frontend) qu'une étape est en pause avant une nouvelle
    tentative automatique : sans ça, un job en attente d'un rate limit paraît figé."""
    step, _created = PipelineStepRun.objects.get_or_create(job=job, step_name=step_name)
    result_summary = dict(step.result_summary or {})
    result_summary["retry"] = {"attempt": attempt, "next_in_seconds": delay_seconds, "reason": reason[:200]}
    step.result_summary = result_summary
    step.status = PipelineStepRun.Status.RUNNING
    step.save(update_fields=["status", "result_summary", "updated_at"])


def mark_dispatch_failed(job, message):
    """Le pipeline n'a jamais pu être mis en file (ex : broker Celery injoignable).

    Aucune tâche ne tournera donc jamais `_fail_job` : sans ceci le job resterait bloqué
    à UPLOADED pour toujours, sans erreur visible. On le passe explicitement en FAILED
    (statut d'où `Réessayer` sait repartir)."""
    # États dans lesquels la vue laisse le job juste avant la mise en file : UPLOADED
    # (création), TEXT_EXTRACTION (« Réessayer » : la vue le repasse en extraction pour
    # que le polling continue), FAILED. Tout autre état = une tâche a déjà pris la main.
    startable = (
        PressReviewJob.Status.UPLOADED,
        PressReviewJob.Status.TEXT_EXTRACTION,
        PressReviewJob.Status.FAILED,
    )
    with transaction.atomic():
        job = PressReviewJob.objects.select_for_update().get(pk=job.pk)
        if job.status not in startable:
            return job
        previous_status = job.status
        job.status = PressReviewJob.Status.FAILED
        job.error_message = message
        job.save(update_fields=["status", "error_message", "updated_at"])
        announce_status_change(job, previous_status)
    return job


def update_step_progress(job, step_name, *, chunks_done=None, chunks_total=None, extra=None):
    """Met à jour la progression fine à l'intérieur d'une étape (ex: chunk N/M traité)
    et recalcule job.progress_percent en conséquence — une vraie barre de progression
    incrémentale, pas juste "étape N/5"."""
    step, _created = PipelineStepRun.objects.get_or_create(job=job, step_name=step_name)
    step.status = PipelineStepRun.Status.RUNNING
    if step.started_at is None:
        step.started_at = timezone.now()

    result_summary = dict(step.result_summary or {})
    if chunks_total is not None:
        result_summary["chunks_total"] = chunks_total
    if chunks_done is not None:
        result_summary["chunks_done"] = chunks_done
    if extra:
        result_summary.update(extra)
    step.result_summary = result_summary

    total = result_summary.get("chunks_total") or 0
    done = result_summary.get("chunks_done") or 0
    fraction = min(done, total) / total if total else 0.0
    step.progress_percent = int(fraction * 100)
    step.save(update_fields=["status", "started_at", "result_summary", "progress_percent", "updated_at"])

    base = _completed_weight(step_name)
    weight = STEP_WEIGHTS.get(step_name, 0)
    job.progress_percent = min(99, int(base + weight * fraction))
    job.save(update_fields=["progress_percent", "updated_at"])
    return step


def mark_step_result(job, step_name, *, result, error_message=""):
    step, _created = PipelineStepRun.objects.get_or_create(job=job, step_name=step_name)
    step.status = result
    step.finished_at = timezone.now()
    if error_message:
        step.error_message = error_message
    result_summary = dict(step.result_summary or {})
    if result == PipelineStepRun.Status.SUCCEEDED and result_summary.pop("retry", None) is not None:
        step.result_summary = result_summary  # la pause de retry est terminée
    step.save(update_fields=["status", "finished_at", "error_message", "result_summary", "updated_at"])
    return step
