"""Machine à états du pipeline de génération de revue de presse.

Un seul point d'entrée modifie `PressReviewJob.status` : `transition_job`. Les tâches
Celery (apps.ai_pipeline.tasks) ne touchent jamais `job.status` directement."""
from django.db import transaction
from django.utils import timezone

from ..models import PipelineStepRun, PressReviewJob

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
    allowed = ALLOWED_TRANSITIONS.get(job.status, [])
    if new_status not in allowed:
        raise InvalidTransition(f"Impossible de passer de {job.status} à {new_status}.")

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

    job.save(update_fields=["status", "progress_percent", "started_at", "completed_at", "error_message", "updated_at"])
    return job


def start_step(job, step_name):
    step, _created = PipelineStepRun.objects.get_or_create(job=job, step_name=step_name)
    step.status = PipelineStepRun.Status.RUNNING
    if step.started_at is None:
        step.started_at = timezone.now()
    step.save(update_fields=["status", "started_at", "updated_at"])
    return step


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
    step.save(update_fields=["status", "finished_at", "error_message", "updated_at"])
    return step
