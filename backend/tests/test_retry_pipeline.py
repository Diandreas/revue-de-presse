import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.press_review.models import Highlight, PressReviewJob, SourceDocument
from apps.press_review.services.pipeline import transition_job
from tests.factories import DetectionCategoryFactory
from tests.pdf_fixtures import make_minimal_pdf_bytes


@pytest.mark.django_db
def test_retry_reruns_the_full_pipeline_without_invalid_transition(authenticated_client, organization, user):
    """Régression : JobRetryView transitionnait le job vers TEXT_EXTRACTION elle-même
    AVANT d'appeler la tâche Celery, qui tente la même transition et échoue
    (TEXT_EXTRACTION -> TEXT_EXTRACTION est invalide). En mode eager, ça remontait un 500
    au lieu de relancer proprement le pipeline."""
    DetectionCategoryFactory(organization=None, is_active=True)

    pdf_bytes = make_minimal_pdf_bytes(["Un article de presse avec du texte reel."])
    job = PressReviewJob.objects.create(organization=organization, created_by=user, title="Job en échec")
    SourceDocument.objects.create(
        organization=organization,
        job=job,
        uploaded_by=user,
        file=SimpleUploadedFile("article.pdf", pdf_bytes, content_type="application/pdf"),
        original_filename="article.pdf",
    )
    transition_job(job, PressReviewJob.Status.TEXT_EXTRACTION)
    transition_job(job, PressReviewJob.Status.FAILED, error_message="Panne réseau simulée")

    response = authenticated_client.post(f"/api/jobs/{job.id}/retry/")

    assert response.status_code == 200, response.data
    assert response.data["status"] == "REVIEW_READY"
    assert all(step["status"] == "succeeded" for step in response.data["step_runs"])


@pytest.mark.django_db
def test_retry_clears_stale_highlights_before_regenerating(authenticated_client, organization, user):
    """Régression : task_detect_highlights ne vidait pas les Highlight existants avant
    d'en recréer — un retry après un échec survenu APRÈS la détection (ex: pendant la
    rédaction) aurait dupliqué les points saillants au lieu de les régénérer proprement."""
    DetectionCategoryFactory(organization=None, is_active=True)

    pdf_bytes = make_minimal_pdf_bytes(["Un article de presse avec du texte reel."])
    job = PressReviewJob.objects.create(organization=organization, created_by=user, title="Job en échec")
    SourceDocument.objects.create(
        organization=organization,
        job=job,
        uploaded_by=user,
        file=SimpleUploadedFile("article.pdf", pdf_bytes, content_type="application/pdf"),
        original_filename="article.pdf",
    )
    transition_job(job, PressReviewJob.Status.TEXT_EXTRACTION)
    transition_job(job, PressReviewJob.Status.FAILED, error_message="Panne simulée après détection")

    stale_category = DetectionCategoryFactory(organization=None, is_active=True, name="Catégorie périmée")
    Highlight.objects.create(job=job, category=stale_category, excerpt="Ancien extrait périmé", order=0)

    response = authenticated_client.post(f"/api/jobs/{job.id}/retry/")

    assert response.status_code == 200, response.data
    remaining_excerpts = list(Highlight.objects.filter(job=job).values_list("excerpt", flat=True))
    assert "Ancien extrait périmé" not in remaining_excerpts


@pytest.mark.django_db
def test_retry_on_non_failed_job_returns_404(authenticated_client, organization, user):
    job = PressReviewJob.objects.create(organization=organization, created_by=user, status=PressReviewJob.Status.UPLOADED)

    response = authenticated_client.post(f"/api/jobs/{job.id}/retry/")

    assert response.status_code == 404
