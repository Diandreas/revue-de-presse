"""L'annexe « Points clés » (PDF, Word) et le panneau des points clés citent le JOURNAL dont
provient chaque passage, plus le nom du fichier téléversé (« WhatsApp Image… »)."""
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from docx import Document

from apps.ai_pipeline import tasks as pipeline_tasks
from apps.ai_pipeline.attribution import newspaper_names
from apps.ai_pipeline.export import _build_pdf_html, _render_docx
from apps.ai_pipeline.mistral_client import FakeMistralClient
from apps.ai_pipeline.press_format import build_structured
from apps.ai_pipeline.tasks import run_press_review_pipeline
from apps.press_review.models import DetectionCategory, GeneratedReview, Highlight, PressReviewJob, SourceDocument
from tests.pdf_fixtures import make_minimal_pdf_bytes

WHATSAPP = "WhatsApp Image 2026-10-09 at 08.12.33.jpeg"
PAPERS = {"Texte de la une du quotidien gouvernemental.": "Cameroon Tribune", "Texte de la une du quotidien Le Jour.": "Le Jour"}


class _PapersClient(FakeMistralClient):
    """Notice : le journal dépend du texte de la page ; points clés : la 1re phrase citée."""

    def complete_json(self, **kwargs):
        if kwargs.get("response_hint") == "press_entry":
            text = next(t for t in PAPERS if t in kwargs["user_prompt"])
            return {"journal": PAPERS[text], "rubrique": "generale", "titre": "", "resume": "Notice."}
        return super().complete_json(**kwargs)


def _job(organization, user, texts, filename=WHATSAPP):
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    for index, text in enumerate(texts):
        SourceDocument.objects.create(
            organization=organization, job=job, uploaded_by=user, position=index, original_filename=filename,
            kind="pdf", file=SimpleUploadedFile("page.pdf", make_minimal_pdf_bytes([text])),
        )
    return job


@pytest.fixture
def ready_job(organization, user, monkeypatch):
    DetectionCategory.objects.create(name="Point important", type="important_point", is_active=True)
    monkeypatch.setattr(pipeline_tasks, "get_mistral_client", lambda: _PapersClient())
    # Deux photos au MÊME nom de fichier : seuls les ids permettent de les distinguer.
    job = _job(organization, user, list(PAPERS))
    run_press_review_pipeline(str(job.id))
    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.REVIEW_READY, job.error_message
    assert job.highlights.count() == 2
    return job


@pytest.mark.django_db
def test_each_document_is_attributed_to_its_newspaper(ready_job):
    tribune, le_jour = ready_job.documents.all()

    assert newspaper_names(ready_job) == {str(tribune.id): "CAMEROON TRIBUNE", str(le_jour.id): "LE JOUR"}


@pytest.mark.django_db
def test_pdf_and_docx_annex_cite_the_newspaper_not_the_file_name(ready_job, settings, tmp_path):
    html = _build_pdf_html(ready_job.review)
    annex = html[html.index("Points clés détectés"):]
    assert "<p class='src'>CAMEROON TRIBUNE · page 1</p>" in annex
    assert "<p class='src'>LE JOUR · page 1</p>" in annex
    assert "WhatsApp" not in annex

    settings.MEDIA_ROOT = tmp_path
    _render_docx(ready_job.review)
    ready_job.review.refresh_from_db()
    texts = [p.text for p in Document(io.BytesIO(ready_job.review.docx_file.read())).paragraphs]
    assert "CAMEROON TRIBUNE · page 1" in texts and not any("WhatsApp" in t for t in texts)


@pytest.mark.django_db
def test_highlights_api_gives_the_newspaper_name(authenticated_client, ready_job):
    response = authenticated_client.get(f"/api/jobs/{ready_job.id}/highlights/")

    assert response.status_code == 200
    assert sorted(h["source_name"] for h in response.data) == ["CAMEROON TRIBUNE", "LE JOUR"]


@pytest.mark.django_db
def test_a_corrected_notice_name_is_what_the_annex_shows(ready_job):
    """La revue (notices) prime sur le cache de rédaction : une correction de la notice se
    retrouve dans l'annexe."""
    review = ready_job.review
    for section in review.structured["sections"]:
        for entry in section["entries"]:
            if entry["source"] == "LE JOUR":
                entry["source"] = "LE MESSAGER"
    review.save()

    assert "LE MESSAGER" in newspaper_names(ready_job).values()


@pytest.mark.django_db
def test_reviews_without_document_ids_fall_back_to_unique_file_names(organization, user):
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    document = SourceDocument.objects.create(
        organization=organization, job=job, original_filename="une.jpg", kind="image", file="x/une.jpg"
    )
    structured = build_structured(entries=[{"source": "Mutations", "summary": "s", "documents": ["une.jpg"]}])
    GeneratedReview.objects.create(job=job, structured=structured)

    assert newspaper_names(job) == {str(document.id): "MUTATIONS"}


@pytest.mark.django_db
def test_legacy_reviews_keep_the_file_name(organization, user):
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    document = SourceDocument.objects.create(
        organization=organization, job=job, original_filename="cameroon-tribune.pdf", kind="pdf", file="x/a.pdf"
    )
    category = DetectionCategory.objects.create(name="Point important", type="important_point")
    Highlight.objects.create(job=job, category=category, source_document=document, excerpt="Un extrait cité ici", page_number=2)
    review = GeneratedReview.objects.create(job=job, summary_markdown="# Revue")

    assert "cameroon-tribune.pdf · page 2" in _build_pdf_html(review)
