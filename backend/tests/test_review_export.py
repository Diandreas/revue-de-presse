import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.ai_pipeline.tasks import run_press_review_pipeline
from apps.press_review.models import PressReviewJob, SourceDocument
from tests.factories import DetectionCategoryFactory
from tests.pdf_fixtures import make_minimal_pdf_bytes


def _create_ready_job(organization, user, title="Job export"):
    DetectionCategoryFactory(organization=None, is_active=True)
    pdf_bytes = make_minimal_pdf_bytes(["Un article de presse avec du texte reel."])
    job = PressReviewJob.objects.create(organization=organization, created_by=user, title=title)
    SourceDocument.objects.create(
        organization=organization,
        job=job,
        uploaded_by=user,
        file=SimpleUploadedFile("article.pdf", pdf_bytes, content_type="application/pdf"),
        original_filename="article.pdf",
    )
    run_press_review_pipeline(str(job.id))
    job.refresh_from_db()
    return job


@pytest.mark.django_db
def test_export_docx_returns_a_downloadable_url(authenticated_client, organization, user):
    """Régression : le paramètre de requête s'appelait `format`, qui entre en collision
    avec la négociation de contenu de DRF (réservé au choix du renderer) — DRF répondait
    404 avant même d'atteindre le code de la vue, pour CHAQUE appel à cet endpoint."""
    job = _create_ready_job(organization, user)
    assert job.status == "REVIEW_READY"

    response = authenticated_client.get(f"/api/jobs/{job.id}/review/export/?export_format=docx")

    assert response.status_code == 200, response.data
    assert response.data["url"].endswith(".docx")


@pytest.mark.django_db
def test_export_defaults_to_pdf_format_name_in_validation_error(authenticated_client, organization, user):
    job = _create_ready_job(organization, user)

    response = authenticated_client.get(f"/api/jobs/{job.id}/review/export/?export_format=exe")

    assert response.status_code == 400
    assert "export_format" in response.data["detail"]


@pytest.mark.django_db
def test_export_before_review_ready_returns_404(authenticated_client, organization, user):
    job = PressReviewJob.objects.create(organization=organization, created_by=user)

    response = authenticated_client.get(f"/api/jobs/{job.id}/review/export/?export_format=docx")

    assert response.status_code == 404
