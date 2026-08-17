"""Tâches Celery du pipeline. Chaque tâche : (1) fait transitionner le job vers
l'étape qu'elle exécute, (2) fait le travail, (3) marque l'étape réussie/échouée.

Aucun `link_error` : si une tâche lève, la `chain` Celery n'invoque naturellement pas
la tâche suivante (elle n'est déclenchée que par le succès de la précédente), et
chaque tâche gère elle-même le passage du job en FAILED avant de re-lever — donc
l'état en base reste toujours cohérent sans dépendre de la sémantique fragile des
callbacks d'erreur Celery."""
import logging

from celery import chain, shared_task
from django.db.models import Q
from django.utils import timezone

from apps.press_review.models import (
    DetectionCategory,
    GeneratedReview,
    Highlight,
    PipelineStepRun,
    PressReviewJob,
)
from apps.press_review.services.pipeline import (
    InvalidTransition,
    mark_step_result,
    start_step,
    transition_job,
    update_step_progress,
)

from .chunking import chunk_document_text
from .extraction import extract_text_from_pdf
from .mistral_client import get_mistral_client
from .prompts import build_chunk_summary_prompt, build_highlight_detection_prompt, build_review_drafting_prompt
from .schemas import ChunkSummaryResult, HighlightDetectionResult, ReviewDraftResult

logger = logging.getLogger(__name__)


def run_press_review_pipeline(job_id):
    chain(
        task_extract_text.s(job_id),
        task_chunk_and_summarize.s(),
        task_detect_highlights.s(),
        task_draft_review.s(),
    ).apply_async()


def _fail_job(job, step_name, exc):
    logger.exception("Échec de l'étape %s pour le job %s", step_name, job.id)
    mark_step_result(job, step_name, result=PipelineStepRun.Status.FAILED, error_message=str(exc))
    try:
        transition_job(job, PressReviewJob.Status.FAILED, error_message=str(exc))
    except InvalidTransition:
        pass  # le job est déjà FAILED (ex : erreur détectée ailleurs) — rien à faire.


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def task_extract_text(self, job_id):
    job = PressReviewJob.objects.get(pk=job_id)
    step_name = PipelineStepRun.StepName.TEXT_EXTRACTION
    try:
        transition_job(job, PressReviewJob.Status.TEXT_EXTRACTION)
        start_step(job, step_name)

        documents = list(job.documents.all())
        for document in documents:
            text, page_count, requires_ocr = extract_text_from_pdf(document.file.path)
            document.extracted_text = text
            document.page_count = page_count
            document.requires_ocr = requires_ocr
            document.extraction_status = document.ExtractionStatus.DONE
            document.save(
                update_fields=["extracted_text", "page_count", "requires_ocr", "extraction_status", "updated_at"]
            )

        mark_step_result(job, step_name, result=PipelineStepRun.Status.SUCCEEDED)
    except Exception as exc:
        _fail_job(job, step_name, exc)
        raise
    return str(job.id)


@shared_task(bind=True, max_retries=2)
def task_chunk_and_summarize(self, job_id):
    job = PressReviewJob.objects.get(pk=job_id)
    step_name = PipelineStepRun.StepName.CHUNKING_SUMMARIZATION
    try:
        transition_job(job, PressReviewJob.Status.CHUNKING_SUMMARIZATION)
        start_step(job, step_name)
        client = get_mistral_client()

        documents_payload = []
        flat_chunks = []  # (index dans documents_payload, TextChunk)
        for document in job.documents.all():
            documents_payload.append({"document_id": str(document.id), "chunks": []})
            for chunk in chunk_document_text(document.extracted_text):
                flat_chunks.append((len(documents_payload) - 1, chunk))

        total = len(flat_chunks)
        update_step_progress(job, step_name, chunks_done=0, chunks_total=max(total, 1))

        for i, (doc_index, chunk) in enumerate(flat_chunks, start=1):
            system_prompt, user_prompt = build_chunk_summary_prompt(chunk.text)
            raw = client.complete_json(
                system_prompt=system_prompt, user_prompt=user_prompt, response_hint="chunk_summary"
            )
            summary = ChunkSummaryResult.model_validate(raw).summary
            documents_payload[doc_index]["chunks"].append(
                {
                    "text": chunk.text,
                    "summary": summary,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                }
            )
            update_step_progress(job, step_name, chunks_done=i, chunks_total=total)

        update_step_progress(
            job, step_name, chunks_done=total, chunks_total=max(total, 1), extra={"documents": documents_payload}
        )
        mark_step_result(job, step_name, result=PipelineStepRun.Status.SUCCEEDED)
    except Exception as exc:
        _fail_job(job, step_name, exc)
        raise
    return str(job.id)


@shared_task(bind=True, max_retries=2)
def task_detect_highlights(self, job_id):
    job = PressReviewJob.objects.get(pk=job_id)
    step_name = PipelineStepRun.StepName.HIGHLIGHT_DETECTION
    try:
        transition_job(job, PressReviewJob.Status.HIGHLIGHT_DETECTION)
        start_step(job, step_name)
        client = get_mistral_client()

        # Un retry relance tout le pipeline depuis l'extraction : sans ce nettoyage,
        # des highlights détectés lors d'une tentative précédente (avant un échec sur
        # une étape ultérieure) seraient dupliqués en plus des nouveaux.
        Highlight.objects.filter(job=job).delete()

        chunking_step = PipelineStepRun.objects.get(
            job=job, step_name=PipelineStepRun.StepName.CHUNKING_SUMMARIZATION
        )
        documents_payload = chunking_step.result_summary.get("documents", [])
        documents_by_index = list(job.documents.all())

        categories = list(
            DetectionCategory.objects.filter(
                Q(organization=job.organization) | Q(organization__isnull=True), is_active=True
            )
        )
        if not categories:
            raise ValueError(
                "Aucune catégorie de détection active pour cette organisation. "
                "Exécutez `seed_default_categories` ou configurez-en via l'admin."
            )
        categories_by_name = {c.name: c for c in categories}

        flat_chunks = [
            (doc_index, chunk)
            for doc_index, doc_payload in enumerate(documents_payload)
            for chunk in doc_payload["chunks"]
        ]
        total = len(flat_chunks)
        update_step_progress(job, step_name, chunks_done=0, chunks_total=max(total, 1))

        order = 0
        for i, (doc_index, chunk) in enumerate(flat_chunks, start=1):
            system_prompt, user_prompt = build_highlight_detection_prompt(chunk["text"], categories)
            raw = client.complete_json(
                system_prompt=system_prompt, user_prompt=user_prompt, response_hint="highlight_detection"
            )
            parsed = HighlightDetectionResult.model_validate(raw)
            document = documents_by_index[doc_index] if doc_index < len(documents_by_index) else None

            for item in parsed.highlights:
                category = categories_by_name.get(item.category_name)
                if category is None:
                    logger.warning("Catégorie inconnue renvoyée par Mistral : %s", item.category_name)
                    continue
                Highlight.objects.create(
                    job=job,
                    source_document=document,
                    category=category,
                    excerpt=item.excerpt,
                    explanation=item.explanation,
                    confidence=item.confidence,
                    page_number=chunk.get("page_start"),
                    order=order,
                )
                order += 1

            update_step_progress(job, step_name, chunks_done=i, chunks_total=total)

        mark_step_result(job, step_name, result=PipelineStepRun.Status.SUCCEEDED)
    except Exception as exc:
        _fail_job(job, step_name, exc)
        raise
    return str(job.id)


@shared_task(bind=True, max_retries=2)
def task_draft_review(self, job_id):
    job = PressReviewJob.objects.get(pk=job_id)
    step_name = PipelineStepRun.StepName.REVIEW_DRAFTING
    try:
        transition_job(job, PressReviewJob.Status.REVIEW_DRAFTING)
        start_step(job, step_name)
        client = get_mistral_client()

        chunking_step = PipelineStepRun.objects.get(
            job=job, step_name=PipelineStepRun.StepName.CHUNKING_SUMMARIZATION
        )
        documents_payload = chunking_step.result_summary.get("documents", [])
        chunk_summaries = [c["summary"] for doc in documents_payload for c in doc["chunks"]]
        document_titles = [d.original_filename for d in job.documents.all()]

        highlights_payload = [
            {"category_name": h.category.name, "excerpt": h.excerpt, "explanation": h.explanation}
            for h in Highlight.objects.filter(job=job).select_related("category")
        ]

        system_prompt, user_prompt = build_review_drafting_prompt(
            document_titles=document_titles, chunk_summaries=chunk_summaries, highlights=highlights_payload
        )
        raw = client.complete_json(
            system_prompt=system_prompt, user_prompt=user_prompt, response_hint="review_drafting"
        )
        parsed = ReviewDraftResult.model_validate(raw)

        GeneratedReview.objects.update_or_create(
            job=job, defaults={"summary_markdown": parsed.summary_markdown, "generated_at": timezone.now()}
        )

        mark_step_result(job, step_name, result=PipelineStepRun.Status.SUCCEEDED)
        transition_job(job, PressReviewJob.Status.REVIEW_READY)
    except Exception as exc:
        _fail_job(job, step_name, exc)
        raise
    return str(job.id)
