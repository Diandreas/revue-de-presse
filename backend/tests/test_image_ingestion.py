from datetime import timedelta

import pytesseract
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.ai_pipeline import extraction
from apps.ai_pipeline.tasks import run_press_review_pipeline
from apps.billing.models import Subscription
from apps.press_review.models import PressReviewJob, SourceDocument
from tests.factories import DetectionCategoryFactory, SubscriptionFactory
from tests.image_fixtures import make_image_bytes
from tests.pdf_fixtures import make_minimal_pdf_bytes


@pytest.fixture(autouse=True)
def _stub_ocr(monkeypatch):
    """Le binaire `tesseract` n'est pas garanti présent en local ; on stub l'OCR pour
    des tests hermétiques et déterministes (comme on stub Mistral via FakeMistralClient)."""
    monkeypatch.setattr(
        pytesseract,
        "image_to_string",
        lambda *args, **kwargs: "Texte OCR simule d'une coupure de presse camerounaise.",
    )


def _add_document(job, organization, user, *, name, content, kind):
    return SourceDocument.objects.create(
        organization=organization,
        job=job,
        uploaded_by=user,
        file=SimpleUploadedFile(name, content, content_type="image/png" if kind == "image" else "application/pdf"),
        original_filename=name,
        kind=kind,
    )


@pytest.mark.django_db
def test_upload_image_is_accepted_and_classified_as_image(authenticated_client):
    response = authenticated_client.post(
        "/api/documents/",
        {"file": SimpleUploadedFile("coupure.png", make_image_bytes(), content_type="image/png")},
        format="multipart",
    )
    assert response.status_code == 201, response.data
    assert response.data["kind"] == "image"


@pytest.mark.django_db
def test_upload_pdf_still_classified_as_pdf(authenticated_client):
    response = authenticated_client.post(
        "/api/documents/",
        {"file": SimpleUploadedFile("article.pdf", make_minimal_pdf_bytes(["Texte."]), content_type="application/pdf")},
        format="multipart",
    )
    assert response.status_code == 201, response.data
    assert response.data["kind"] == "pdf"


@pytest.mark.django_db
def test_upload_rejects_unsupported_file_type(authenticated_client):
    response = authenticated_client.post(
        "/api/documents/",
        {"file": SimpleUploadedFile("notes.txt", b"bonjour", content_type="text/plain")},
        format="multipart",
    )
    assert response.status_code == 400


def test_extract_text_from_image_returns_a_single_ocr_page(tmp_path):
    path = tmp_path / "coupure.png"
    path.write_bytes(make_image_bytes())

    text, page_count, requires_ocr = extraction.extract_text_from_image(str(path))

    assert page_count == 1
    assert requires_ocr is True
    assert "coupure de presse" in text.lower()


@pytest.mark.django_db
def test_full_pipeline_with_only_an_image(organization, user):
    DetectionCategoryFactory(organization=None, is_active=True)
    job = PressReviewJob.objects.create(organization=organization, created_by=user, title="Revue photo")
    _add_document(job, organization, user, name="coupure.jpg", content=make_image_bytes(fmt="JPEG"), kind="image")

    run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == "REVIEW_READY"
    doc = job.documents.get()
    assert doc.extraction_status == "done"
    assert doc.requires_ocr is True


@pytest.mark.django_db
def test_mixed_pdf_and_image_job_completes(organization, user):
    DetectionCategoryFactory(organization=None, is_active=True)
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    _add_document(job, organization, user, name="a.pdf", content=make_minimal_pdf_bytes(["Un article natif de presse avec suffisamment de texte."]), kind="pdf")
    _add_document(job, organization, user, name="b.png", content=make_image_bytes(), kind="image")

    run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == "REVIEW_READY"
    assert {d.kind for d in job.documents.all()} == {"pdf", "image"}
    # Les DEUX documents ont vraiment été lus (le test passait avant même si le PDF échouait).
    assert {d.extraction_status for d in job.documents.all()} == {"done"}


@pytest.mark.django_db
def test_one_unreadable_document_does_not_fail_the_whole_job(organization, user):
    DetectionCategoryFactory(organization=None, is_active=True)
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    _add_document(job, organization, user, name="ok.png", content=make_image_bytes(), kind="image")
    _add_document(job, organization, user, name="broken.png", content=b"pas vraiment une image", kind="image")

    run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == "REVIEW_READY"
    statuses = {d.original_filename: d.extraction_status for d in job.documents.all()}
    assert statuses == {"ok.png": "done", "broken.png": "failed"}


@pytest.mark.django_db
def test_job_creation_returns_cleanly_when_pipeline_fails_synchronously(
    authenticated_client, organization, monkeypatch
):
    """Régression : en mode eager, une exception du pipeline (ex: API Mistral qui
    renvoie 403 'tier_not_allowed') remontait en 500 HTML brut sur POST /api/jobs/ au
    lieu de renvoyer le job marqué FAILED (que le frontend sait afficher + Réessayer)."""
    DetectionCategoryFactory(organization=None, is_active=True)
    SubscriptionFactory(
        organization=organization,
        status=Subscription.Status.ACTIVE,
        current_period_start=timezone.now() - timedelta(days=1),
    )

    class _BoomClient:
        def complete_json(self, **kwargs):
            raise RuntimeError("Mistral API error occurred: Status 403 tier_not_allowed")

    monkeypatch.setattr("apps.ai_pipeline.tasks.get_mistral_client", lambda: _BoomClient())

    pdf = make_minimal_pdf_bytes(["Un article de presse avec suffisamment de texte reel."])
    upload = authenticated_client.post(
        "/api/documents/",
        {"file": SimpleUploadedFile("a.pdf", pdf, content_type="application/pdf")},
        format="multipart",
    )
    response = authenticated_client.post(
        "/api/jobs/", {"title": "x", "document_ids": [upload.data["id"]]}, format="json"
    )

    assert response.status_code == 201, response.data
    assert response.data["status"] == "FAILED"
    # C'est bien l'erreur Mistral qui a fait échouer la revue (et non l'extraction).
    assert "Aucun document" not in response.data["error_message"]
    assert response.data["error_message"]


@pytest.mark.django_db
def test_job_fails_when_no_document_can_be_extracted(organization, user):
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    _add_document(job, organization, user, name="broken.png", content=b"garbage", kind="image")

    # En mode eager (CELERY_TASK_EAGER_PROPAGATES), la tâche re-lève après avoir marqué
    # le job en échec — comportement voulu pour le monitoring/retry Celery réel.
    with pytest.raises(Exception):
        run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == "FAILED"
    assert "Aucun document" in job.error_message
