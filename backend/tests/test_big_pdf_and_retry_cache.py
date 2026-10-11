"""Gros PDF lus page par page (une seule page en mémoire), plafond de pages par PDF, et
relances économes : ni les pages déjà lues, ni les résumés, ni les points clés déjà
obtenus ne sont redemandés à l'IA."""
from collections import Counter

import pytesseract
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.ai_pipeline import ocr
from apps.ai_pipeline import tasks as pipeline_tasks
from apps.ai_pipeline.mistral_client import FakeMistralClient
from apps.ai_pipeline.tasks import run_press_review_pipeline
from apps.press_review.models import DetectionCategory, Highlight, PressReviewJob, SourceDocument
from tests.pdf_fixtures import make_multipage_pdf_bytes


@pytest.fixture
def rendered_pages(monkeypatch):
    """Simule Poppler : une image par appel, et note les pages demandées à chaque appel."""
    calls = []

    def fake_convert(path, dpi=200, first_page=None, last_page=None, **kwargs):
        calls.append((first_page, last_page))
        return [Image.new("RGB", (50, 50), "white")]

    monkeypatch.setattr(ocr, "convert_from_path", fake_convert)
    return calls


def _scanned_pdf_job(organization, user, pages, name="scan.pdf"):
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    SourceDocument.objects.create(
        organization=organization, job=job, uploaded_by=user, original_filename=name, kind="pdf",
        file=SimpleUploadedFile(name, make_multipage_pdf_bytes([[] for _ in range(pages)]), content_type="application/pdf"),
    )
    return job


def _ocr_pages(monkeypatch, *, fail_on=None):
    """Tesseract simulé : « Texte de la page N » ; `fail_on` = n° d'appel qui lève un 429."""
    state = {"n": 0}

    def fake_ocr(*args, **kwargs):
        state["n"] += 1
        if state["n"] == fail_on:
            raise RuntimeError("Status 429 rate_limited")
        return f"Texte OCR de la page numero {state['n']} du journal.\f"  # Tesseract finit par \f

    monkeypatch.setattr(pytesseract, "image_to_string", fake_ocr)
    return state


@pytest.mark.django_db
def test_a_scanned_pdf_is_rendered_one_page_at_a_time(organization, user, monkeypatch, rendered_pages):
    DetectionCategory.objects.create(name="Point important", type="important_point", is_active=True)
    _ocr_pages(monkeypatch)
    job = _scanned_pdf_job(organization, user, pages=3)

    run_press_review_pipeline(str(job.id))

    assert rendered_pages == [(1, 1), (2, 2), (3, 3)]
    document = job.documents.get()
    assert document.extraction_status == "done" and document.page_count == 3 and document.requires_ocr
    pages = document.extracted_text.split("\f")
    assert len(pages) == 3 and pages[2].startswith("Texte OCR de la page numero 3")  # \f de Tesseract neutralisé


@pytest.mark.django_db
def test_a_pdf_over_the_page_maximum_is_flagged_without_failing_the_other_documents(
    organization, user, monkeypatch, rendered_pages, settings
):
    settings.AI_MAX_PDF_PAGES = 2
    DetectionCategory.objects.create(name="Point important", type="important_point", is_active=True)
    _ocr_pages(monkeypatch)
    job = _scanned_pdf_job(organization, user, pages=3, name="annuaire.pdf")
    SourceDocument.objects.create(
        organization=organization, job=job, uploaded_by=user, original_filename="une.pdf", kind="pdf",
        file=SimpleUploadedFile("une.pdf", make_multipage_pdf_bytes([["Un article de presse avec du texte reel."]])),
    )

    run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.REVIEW_READY, job.error_message
    too_long = job.documents.get(original_filename="annuaire.pdf")
    assert too_long.extraction_status == "failed"
    assert "« annuaire.pdf » compte 3 pages" in too_long.extraction_error
    assert rendered_pages == []  # refusé avant tout rendu / appel d'OCR


@pytest.mark.django_db
def test_a_retry_resumes_the_ocr_where_the_rate_limit_stopped_it(
    authenticated_client, organization, user, monkeypatch, rendered_pages
):
    DetectionCategory.objects.create(name="Point important", type="important_point", is_active=True)
    _ocr_pages(monkeypatch, fail_on=2)  # 429 sur la page 2
    job = _scanned_pdf_job(organization, user, pages=3)

    with pytest.raises(RuntimeError):
        run_press_review_pipeline(str(job.id))

    document = job.documents.get()
    assert document.extraction_status == "pending"  # pas « illisible » : ce n'est pas sa faute
    assert document.extracted_text.startswith("Texte OCR de la page numero 1")  # page 1 conservée
    rendered_pages.clear()

    response = authenticated_client.post(f"/api/jobs/{job.id}/retry/")

    assert response.data["status"] == "REVIEW_READY", response.data
    assert rendered_pages == [(2, 2), (3, 3)]  # la page 1 n'est ni re-rendue ni relue
    assert len(job.documents.get().extracted_text.split("\f")) == 3


class _CountingClient(FakeMistralClient):
    def __init__(self):
        super().__init__()
        self.calls = Counter()

    def complete_json(self, **kwargs):
        self.calls[kwargs.get("response_hint")] += 1
        return super().complete_json(**kwargs)


def _ready_job(organization, user, client, monkeypatch):
    monkeypatch.setattr(pipeline_tasks, "get_mistral_client", lambda: client)
    DetectionCategory.objects.create(name="Point important", type="important_point", is_active=True)
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    for index in range(2):
        SourceDocument.objects.create(
            organization=organization, job=job, uploaded_by=user, position=index, original_filename=f"{index}.pdf",
            kind="pdf", file=SimpleUploadedFile(
                f"{index}.pdf", make_multipage_pdf_bytes([[f"Article {index} : le gouvernement annonce une reforme."]])
            ),
        )
    run_press_review_pipeline(str(job.id))
    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.REVIEW_READY, job.error_message
    return job


def _fail_and_retry(client, job):
    """« Réessayer » après une panne survenue à la fin du pipeline."""
    PressReviewJob.objects.filter(pk=job.pk).update(status=PressReviewJob.Status.FAILED)
    client.post(f"/api/jobs/{job.id}/retry/")
    job.refresh_from_db()


@pytest.mark.django_db
def test_a_retry_does_not_ask_the_ai_again_for_summaries_key_points_or_notices(
    authenticated_client, organization, user, monkeypatch
):
    client = _CountingClient()
    job = _ready_job(organization, user, client, monkeypatch)
    assert client.calls == Counter(chunk_summary=2, highlight_detection=2, press_entry=2)
    highlights_before = Highlight.objects.filter(job=job).count()
    assert highlights_before == 2  # un point clé (cité tel quel) par document
    client.calls.clear()

    _fail_and_retry(authenticated_client, job)

    assert job.status == PressReviewJob.Status.REVIEW_READY, job.error_message
    assert client.calls == Counter()  # aucun appel IA : tout vient des résultats déjà obtenus
    assert Highlight.objects.filter(job=job).count() == highlights_before  # recréés, pas dupliqués


@pytest.mark.django_db
def test_changed_detection_categories_invalidate_only_the_key_points(
    authenticated_client, organization, user, monkeypatch
):
    client = _CountingClient()
    job = _ready_job(organization, user, client, monkeypatch)
    DetectionCategory.objects.create(name="Annonce concurrent", type="custom", is_active=True)
    client.calls.clear()

    _fail_and_retry(authenticated_client, job)

    assert client.calls == Counter(highlight_detection=2)  # le prompt a changé : on redemande
