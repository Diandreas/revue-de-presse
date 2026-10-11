"""Tâches Celery du pipeline, exécutées en arrière-plan par un worker.

Chaque tâche : (1) fait entrer le job dans l'étape qu'elle exécute (idempotent, voir
`enter_step`), (2) fait le travail en publiant sa progression, (3) marque l'étape
réussie / échouée.

Aucun `link_error` : si une tâche lève, la `chain` Celery n'invoque naturellement pas la
tâche suivante (elle n'est déclenchée que par le succès de la précédente), et chaque
tâche gère elle-même le passage du job en FAILED avant de re-lever — l'état en base
reste donc cohérent sans dépendre de la sémantique fragile des callbacks d'erreur.

Erreurs transitoires (rate limit 429, indisponibilité 5xx, timeout réseau) : la tâche
n'échoue pas, elle est relancée plus tard par Celery (`_handle_step_error`), sans que
l'utilisateur ait à cliquer sur « Réessayer ».

Relances économes : un appel IA déjà fait n'est pas refait. Pages OCR déjà lues (sur le
document), résumés et points clés (par prompt, dans le résultat de l'étape), notices (par
document) : une relance reprend là où la tentative précédente s'était arrêtée.

Chaque étape déclare son organisation / sa revue (`ai_call_context`) : le limiteur de
débit par organisation et la mesure du coût (AIUsage) s'appuient dessus."""
import hashlib
import logging
from collections import Counter

from celery import chain, shared_task
from django.conf import settings
from pydantic import ValidationError
from django.db.models import Q
from django.utils import timezone

from apps.press_review.models import (
    DetectionCategory,
    GeneratedReview,
    Highlight,
    PipelineStepRun,
    PressReviewJob,
    SourceDocument,
)
from apps.press_review.services.pipeline import (
    InvalidTransition,
    enter_step,
    mark_step_result,
    note_step_retry,
    transition_job,
    update_step_progress,
)

from .chunking import chunk_document_text
from .errors import DocumentRejectedError, describe_error, is_configuration_error, is_retryable_error
from .extraction import PAGE_SEPARATOR, extract_text_from_image, extract_text_from_pdf
from .grounding import check_highlight, normalized_words
from .matching import match_category
from .mistral_client import MistralClient, complete_structured, get_mistral_client
from .media import UNIDENTIFIED_PREFIX
from .press_format import DEFAULT_RUBRIQUE, build_structured, country_label, long_french_date, match_rubrique, to_markdown
from .prompts import build_chunk_summary_prompt, build_highlight_detection_prompt, build_press_entry_prompt
from .schemas import ChunkSummaryResult, HighlightDetectionResult, PressEntryResult
from .usage import ai_call_context

logger = logging.getLogger(__name__)

MAX_STEP_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 45  # 45 s, 90 s, 135 s : laisse le temps à un rate limit de retomber
MIN_EXTRACTED_CHARS = 15  # en-deçà (hors espaces), on considère qu'aucun texte n'a été lu


def run_press_review_pipeline(job_id):
    chain(
        task_extract_text.s(job_id),
        task_chunk_and_summarize.s(),
        task_detect_highlights.s(),
        task_draft_review.s(),
    ).apply_async()


def _ordered_documents(job):
    """Documents dans l'ordre de lecture de la revue (cf. SourceDocument.Meta.ordering :
    rang choisi par l'utilisateur, puis ordre d'upload)."""
    return list(job.documents.all())


def _step_context(job, step_name):
    return ai_call_context(organization_id=job.organization_id, job_id=job.id, step=step_name)


def _prompt_key(client, system_prompt, user_prompt):
    """Empreinte d'un appel IA (modèle + prompts) : même empreinte = même réponse attendue,
    inutile de la redemander lors d'une relance."""
    material = "\0".join((str(getattr(client, "model", "") or ""), system_prompt, user_prompt))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def _fail_job(job, step_name, exc, *, retried=False):
    logger.exception("Échec de l'étape %s pour le job %s", step_name, job.id)
    message = describe_error(exc, retried=retried)
    mark_step_result(job, step_name, result=PipelineStepRun.Status.FAILED, error_message=message)
    try:
        transition_job(job, PressReviewJob.Status.FAILED, error_message=message)
    except InvalidTransition:
        pass  # le job est déjà FAILED (ex : erreur détectée ailleurs) — rien à faire.


def _handle_step_error(task, job, step_name, exc):
    """Erreur transitoire -> on programme une nouvelle tentative (lève `Retry`) ; le job
    reste dans l'étape en cours. Sinon (ou tentatives épuisées) -> échec définitif du
    job, puis l'appelant re-lève l'exception d'origine.

    Pas de retry en mode eager (dev/tests sans worker) : aucun ordonnanceur n'y honorera
    le délai, et Celery y propage `Retry` à l'appelant — le job resterait bloqué en cours
    de route sans jamais repartir. On échoue donc tout de suite, avec un message clair."""
    can_retry = not task.request.is_eager and task.request.retries < task.max_retries
    if can_retry and is_retryable_error(exc):
        attempt = task.request.retries + 1
        delay = RETRY_BASE_DELAY_SECONDS * attempt
        logger.warning(
            "Étape %s (job %s) : erreur transitoire, nouvelle tentative %s/%s dans %ss : %s",
            step_name, job.id, attempt, task.max_retries, delay, exc,
        )
        note_step_retry(job, step_name, attempt=attempt, delay_seconds=delay, reason=describe_error(exc))
        raise task.retry(exc=exc, countdown=delay)
    _fail_job(job, step_name, exc, retried=task.request.retries > 0)


def _ocr_pages_already_read(document):
    """Pages d'un PDF scanné lues lors d'une tentative interrompue (rate limit à la page 30
    sur 50) : gardées sur le document, encore « en attente », pour ne pas les relire."""
    if (
        document.extraction_status != SourceDocument.ExtractionStatus.PENDING
        or not document.requires_ocr
        or not document.extracted_text
    ):
        return []
    return document.extracted_text.split(PAGE_SEPARATOR)


def _ocr_progress_saver(document):
    def save(pages_text):
        document.extracted_text = PAGE_SEPARATOR.join(pages_text)
        document.requires_ocr = True
        document.save(update_fields=["extracted_text", "requires_ocr", "updated_at"])

    return save


def _extract_document(document):
    path = document.file.path
    if document.kind == SourceDocument.Kind.IMAGE:
        return extract_text_from_image(path)
    return extract_text_from_pdf(
        path,
        display_name=document.original_filename,
        ocr_pages_done=_ocr_pages_already_read(document),
        on_ocr_page=_ocr_progress_saver(document),
    )


def _has_enough_text(text):
    return len("".join((text or "").split())) >= MIN_EXTRACTED_CHARS


@shared_task(bind=True, max_retries=MAX_STEP_RETRIES)
def task_extract_text(self, job_id):
    job = PressReviewJob.objects.get(pk=job_id)
    step_name = PipelineStepRun.StepName.TEXT_EXTRACTION
    with _step_context(job, step_name):
        try:
            enter_step(job, PressReviewJob.Status.TEXT_EXTRACTION, step_name)

            documents = _ordered_documents(job)
            total = len(documents)
            update_step_progress(
                job, step_name, chunks_done=0, chunks_total=max(total, 1),
                extra={"unit": "documents", "documents_total": total, "documents_failed": 0},
            )

            succeeded = 0
            for index, document in enumerate(documents, start=1):
                if document.extraction_status == SourceDocument.ExtractionStatus.DONE and document.extracted_text:
                    # Déjà lu lors d'une tentative précédente (relance après erreur transitoire ou
                    # « Réessayer ») : on ne relit pas — l'OCR par l'API se paie et est limité.
                    succeeded += 1
                    update_step_progress(
                        job, step_name, chunks_done=index, chunks_total=max(total, 1),
                        extra={"documents_failed": index - succeeded},
                    )
                    continue

                error = ""
                text, page_count, requires_ocr = "", None, None
                try:
                    text, page_count, requires_ocr = _extract_document(document)
                    if not _has_enough_text(text):
                        error = "Aucun texte lisible détecté dans ce fichier."
                except DocumentRejectedError as exc:
                    error = exc.user_message[:255]  # ex : PDF trop long — message destiné au client
                except Exception as exc:
                    # Configuration du serveur (OCR absent, clé refusée, modèle fermé à l'offre) ou
                    # erreur transitoire (429/5xx/réseau) : ce n'est PAS la faute de ce fichier. On
                    # remonte -> le job échoue avec un message d'administrateur, ou l'étape est
                    # relancée plus tard (voir `_handle_step_error`).
                    if is_configuration_error(exc) or is_retryable_error(exc):
                        raise
                    # Une photo floue / un fichier corrompu ne doit pas faire échouer toute la
                    # revue : on marque ce document en échec (avec la raison) et on continue.
                    logger.exception(
                        "Échec de l'extraction du document %s (%s)", document.id, document.original_filename
                    )
                    error = "Fichier illisible ou corrompu."

                if error:
                    document.extraction_status = SourceDocument.ExtractionStatus.FAILED
                    document.extraction_error = error
                    document.extracted_text = ""
                else:
                    document.extraction_status = SourceDocument.ExtractionStatus.DONE
                    document.extraction_error = ""
                    document.extracted_text = text
                    document.page_count = page_count
                    document.requires_ocr = requires_ocr
                    succeeded += 1
                document.save(
                    update_fields=[
                        "extracted_text", "page_count", "requires_ocr",
                        "extraction_status", "extraction_error", "updated_at",
                    ]
                )

                update_step_progress(
                    job, step_name, chunks_done=index, chunks_total=max(total, 1),
                    extra={"documents_failed": index - succeeded},
                )

            if succeeded == 0:
                reasons = " ; ".join(f"{d.original_filename} : {d.extraction_error}" for d in documents)
                raise RuntimeError(f"Aucun document n'a pu être analysé. {reasons}"[:500])

            mark_step_result(job, step_name, result=PipelineStepRun.Status.SUCCEEDED)
        except Exception as exc:
            _handle_step_error(self, job, step_name, exc)
            raise
    return str(job.id)


@shared_task(bind=True, max_retries=MAX_STEP_RETRIES)
def task_chunk_and_summarize(self, job_id):
    job = PressReviewJob.objects.get(pk=job_id)
    step_name = PipelineStepRun.StepName.CHUNKING_SUMMARIZATION
    with _step_context(job, step_name):
        try:
            step = enter_step(job, PressReviewJob.Status.CHUNKING_SUMMARIZATION, step_name)
            client = get_mistral_client()
            # Résumés déjà obtenus lors d'une tentative précédente, par empreinte de prompt.
            cache = dict((step.result_summary or {}).get("summary_cache") or {})

            documents_payload = []
            flat_chunks = []  # (index dans documents_payload, TextChunk)
            for document in _ordered_documents(job):
                if document.extraction_status != SourceDocument.ExtractionStatus.DONE:
                    continue  # fichier illisible / sans texte : déjà signalé à l'extraction
                documents_payload.append({"document_id": str(document.id), "chunks": []})
                for chunk in chunk_document_text(document.extracted_text):
                    flat_chunks.append((len(documents_payload) - 1, chunk))

            total = len(flat_chunks)
            update_step_progress(job, step_name, chunks_done=0, chunks_total=max(total, 1), extra={"unit": "extraits"})

            for i, (doc_index, chunk) in enumerate(flat_chunks, start=1):
                system_prompt, user_prompt = build_chunk_summary_prompt(chunk.text)
                key = _prompt_key(client, system_prompt, user_prompt)
                summary = cache.get(key)
                extra = None
                if summary is None:
                    summary = complete_structured(
                        client, schema=ChunkSummaryResult, system_prompt=system_prompt,
                        user_prompt=user_prompt, response_hint="chunk_summary",
                    ).summary
                    cache[key] = summary
                    extra = {"summary_cache": cache}
                documents_payload[doc_index]["chunks"].append(
                    {
                        "text": chunk.text,
                        "summary": summary,
                        "page_start": chunk.page_start,
                        "page_end": chunk.page_end,
                    }
                )
                update_step_progress(job, step_name, chunks_done=i, chunks_total=total, extra=extra)

            update_step_progress(
                job, step_name, chunks_done=total, chunks_total=max(total, 1), extra={"documents": documents_payload}
            )
            mark_step_result(job, step_name, result=PipelineStepRun.Status.SUCCEEDED)
        except Exception as exc:
            _handle_step_error(self, job, step_name, exc)
            raise
    return str(job.id)


def _highlight_client():
    """Détection des points clés : modèle le plus fidèle disponible (`MISTRAL_HIGHLIGHT_MODEL`,
    ministral-14b par défaut) — les citations doivent être exactes."""
    client = get_mistral_client()
    model = getattr(settings, "MISTRAL_HIGHLIGHT_MODEL", "")
    if type(client) is MistralClient and model:
        client = MistralClient(model=model)
    return client


def _detect_chunk_highlights(client, system_prompt, user_prompt):
    """Points clés bruts (dicts) renvoyés par le modèle pour un extrait."""
    parsed = complete_structured(
        client, schema=HighlightDetectionResult, system_prompt=system_prompt,
        user_prompt=user_prompt, response_hint="highlight_detection",
        temperature=getattr(settings, "HIGHLIGHT_TEMPERATURE", 0.0),
    )
    return [item.model_dump() for item in parsed.highlights]


@shared_task(bind=True, max_retries=MAX_STEP_RETRIES)
def task_detect_highlights(self, job_id):
    job = PressReviewJob.objects.get(pk=job_id)
    step_name = PipelineStepRun.StepName.HIGHLIGHT_DETECTION
    with _step_context(job, step_name):
        try:
            step = enter_step(job, PressReviewJob.Status.HIGHLIGHT_DETECTION, step_name)
            client = _highlight_client()
            # Réponses brutes déjà obtenues lors d'une tentative précédente (par empreinte de
            # prompt) : les filtres ci-dessous sont rejoués, pas l'appel IA.
            cache = dict((step.result_summary or {}).get("detection_cache") or {})

            # Un retry (manuel ou automatique) relance l'étape depuis le début : sans ce
            # nettoyage, des highlights détectés lors d'une tentative précédente seraient
            # dupliqués en plus des nouveaux.
            Highlight.objects.filter(job=job).delete()

            chunking_step = PipelineStepRun.objects.get(
                job=job, step_name=PipelineStepRun.StepName.CHUNKING_SUMMARIZATION
            )
            documents_payload = chunking_step.result_summary.get("documents", [])
            documents_by_id = {str(d.id): d for d in job.documents.all()}

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

            flat_chunks = [
                (doc_payload["document_id"], chunk)
                for doc_payload in documents_payload
                for chunk in doc_payload["chunks"]
            ]
            total = len(flat_chunks)
            update_step_progress(job, step_name, chunks_done=0, chunks_total=max(total, 1), extra={"unit": "extraits"})

            order = 0
            unmatched = set()
            discarded = Counter()  # points clés écartés, par raison (cf. grounding.py)
            seen = set()
            unreadable_chunks = 0
            last_parse_error = None
            for i, (document_id, chunk) in enumerate(flat_chunks, start=1):
                system_prompt, user_prompt = build_highlight_detection_prompt(chunk["text"], categories)
                key = _prompt_key(client, system_prompt, user_prompt)
                items = cache.get(key)
                extra = None
                if items is None:
                    try:
                        items = _detect_chunk_highlights(client, system_prompt, user_prompt)
                    except ValidationError as exc:
                        last_parse_error = exc
                        # Les points clés sont une annexe : une réponse illisible sur UN extrait (même
                        # après la relance corrective) ne doit pas faire échouer une revue de 27
                        # documents. On l'écarte, c'est tracé, et l'étape échoue seulement si aucun
                        # extrait n'a pu être analysé.
                        logger.warning("Points clés illisibles pour un extrait du job %s : extrait ignoré.", job.id)
                        unreadable_chunks += 1
                        update_step_progress(job, step_name, chunks_done=i, chunks_total=total)
                        continue
                    cache[key] = items
                    extra = {"detection_cache": cache}
                document = documents_by_id.get(document_id)

                for item in items:
                    category = match_category(item.get("category_name"), categories)
                    if category is None:
                        # Rien de plausible : on ne classe pas au hasard, mais on ne jette pas en
                        # silence non plus — c'est tracé (log + résumé de l'étape).
                        logger.warning("Catégorie inconnue renvoyée par Mistral : %r", item.get("category_name"))
                        unmatched.add(item.get("category_name"))
                        continue
                    excerpt = item.get("excerpt") or ""
                    # Citation introuvable dans le texte, trop courte, nom du journal ou jugée
                    # peu sûre par le modèle lui-même : écartée avant d'arriver dans la revue.
                    reason = check_highlight(excerpt=excerpt, confidence=item.get("confidence"), source_text=chunk["text"])
                    if reason is None:
                        identity = (document_id, category.pk, " ".join(normalized_words(excerpt)))
                        reason = "duplicate" if identity in seen else None
                        seen.add(identity)
                    if reason:
                        discarded[reason] += 1
                        continue
                    Highlight.objects.create(
                        job=job,
                        source_document=document,
                        category=category,
                        excerpt=excerpt,
                        explanation=item.get("explanation") or "",
                        confidence=item.get("confidence"),
                        page_number=chunk.get("page_start"),
                        order=order,
                    )
                    order += 1

                update_step_progress(job, step_name, chunks_done=i, chunks_total=total, extra=extra)

            if total and unreadable_chunks == total:
                raise last_parse_error
            # Toujours réécrit : une relance ne doit pas afficher les écarts de la tentative précédente.
            update_step_progress(
                job, step_name, chunks_done=total, chunks_total=max(total, 1),
                extra={
                    "unmatched_categories": sorted(unmatched),
                    "unreadable_chunks": unreadable_chunks,
                    "discarded_highlights": dict(discarded),
                },
            )
            mark_step_result(job, step_name, result=PipelineStepRun.Status.SUCCEEDED)
        except Exception as exc:
            _handle_step_error(self, job, step_name, exc)
            raise
    return str(job.id)


@shared_task(bind=True, max_retries=MAX_STEP_RETRIES)
def task_draft_review(self, job_id):
    """Rédige la revue au format « revue de presse » : une notice par journal (nom, titre de
    la une, résumé), rangée dans sa rubrique — cf. press_format.

    Un appel IA par document, mis en cache dans le résultat de l'étape : une nouvelle
    tentative (rate limit, « Réessayer ») reprend là où l'étape s'était arrêtée au lieu de
    tout refaire sur une revue de 27 photos."""
    job = PressReviewJob.objects.get(pk=job_id)
    step_name = PipelineStepRun.StepName.REVIEW_DRAFTING
    with _step_context(job, step_name):
        try:
            step = enter_step(job, PressReviewJob.Status.REVIEW_DRAFTING, step_name)
            client = get_mistral_client()
            if type(client) is MistralClient and settings.MISTRAL_REVIEW_MODEL:
                client = MistralClient(model=settings.MISTRAL_REVIEW_MODEL)

            chunking_step = PipelineStepRun.objects.get(
                job=job, step_name=PipelineStepRun.StepName.CHUNKING_SUMMARIZATION
            )
            summaries_by_document = {
                doc["document_id"]: [c.get("summary", "") for c in doc["chunks"]]
                for doc in chunking_step.result_summary.get("documents", [])
            }
            documents = [
                d for d in _ordered_documents(job) if d.extraction_status == SourceDocument.ExtractionStatus.DONE
            ]
            cache = dict((step.result_summary or {}).get("entries") or {})
            total = len(documents)
            update_step_progress(
                job, step_name, chunks_done=len([d for d in documents if str(d.id) in cache]),
                chunks_total=max(total, 1), extra={"unit": "journaux"},
            )

            for i, document in enumerate(documents, start=1):
                key = str(document.id)
                if key in cache:
                    continue
                summaries = summaries_by_document.get(key, [])
                system_prompt, user_prompt = build_press_entry_prompt(
                    filename=document.original_filename, text=document.extracted_text, chunk_summaries=summaries
                )
                try:
                    parsed = complete_structured(
                        client, schema=PressEntryResult, system_prompt=system_prompt,
                        user_prompt=user_prompt, response_hint="press_entry", temperature=0.1,
                    )
                    entry = {
                        "source": parsed.journal.upper(),
                        "rubrique": match_rubrique(parsed.rubrique),
                        "headline": parsed.titre,
                        "summary": parsed.resume,
                    }
                except ValidationError:
                    # Notice illisible même après relance : on garde au moins les résumés du
                    # document plutôt que de perdre toute la revue.
                    logger.warning("Notice illisible pour %s (job %s) : résumés bruts.", document.original_filename, job.id)
                    entry = {"source": "", "rubrique": DEFAULT_RUBRIQUE, "headline": "", "summary": " ".join(summaries)}
                if not entry["source"]:
                    # Pas le nom de fichier (« WhatsApp Image 2026-10-09 at… ») : illisible dans
                    # une revue diffusée ; le n° renvoie à l'onglet « Documents ».
                    kind = "photo" if document.kind == SourceDocument.Kind.IMAGE else "document"
                    entry["source"] = f"{UNIDENTIFIED_PREFIX} ({kind} n° {i})"
                entry["documents"] = [document.original_filename]
                entry["document_ids"] = [key]
                cache[key] = entry
                update_step_progress(job, step_name, chunks_done=len(cache), chunks_total=max(total, 1), extra={"entries": cache})

            structured = build_structured(
                entries=[{**cache[str(d.id)], "document_ids": [str(d.id)]} for d in documents if str(d.id) in cache],
                country=country_label(job.organization.country),
                date_label=long_french_date(job.created_at),
            )
            if not any(section["entries"] for section in structured["sections"]):
                raise ValueError("Aucun document lisible : impossible de rédiger la revue de presse.")

            # Nouvelle rédaction -> les exports déjà générés (ancienne version) sont périmés.
            previous = GeneratedReview.objects.filter(job=job).first()
            if previous is not None:
                for stale in (previous.pdf_file, previous.docx_file):
                    if stale:
                        stale.delete(save=False)
            GeneratedReview.objects.update_or_create(
                job=job,
                defaults={
                    "summary_markdown": to_markdown(structured),
                    "structured": structured,
                    "generated_at": timezone.now(),
                    "pdf_file": None,
                    "docx_file": None,
                },
            )

            mark_step_result(job, step_name, result=PipelineStepRun.Status.SUCCEEDED)
            transition_job(job, PressReviewJob.Status.REVIEW_READY)
        except Exception as exc:
            _handle_step_error(self, job, step_name, exc)
            raise
    return str(job.id)
