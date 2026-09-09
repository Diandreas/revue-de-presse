import pytest

from apps.press_review.models import PipelineStepRun, PressReviewJob
from apps.press_review.services.pipeline import InvalidTransition, start_step, transition_job, update_step_progress
from tests.factories import OrganizationFactory


@pytest.mark.django_db
def test_transition_job_follows_allowed_path():
    org = OrganizationFactory()
    job = PressReviewJob.objects.create(organization=org, title="Test")
    assert job.status == PressReviewJob.Status.UPLOADED

    job = transition_job(job, PressReviewJob.Status.TEXT_EXTRACTION)

    assert job.status == PressReviewJob.Status.TEXT_EXTRACTION
    assert job.progress_percent == 0
    assert job.started_at is not None


@pytest.mark.django_db
def test_transition_job_rejects_invalid_jump():
    org = OrganizationFactory()
    job = PressReviewJob.objects.create(organization=org, title="Test")

    with pytest.raises(InvalidTransition):
        transition_job(job, PressReviewJob.Status.REVIEW_READY)


@pytest.mark.django_db
def test_transition_job_to_failed_records_error_message():
    org = OrganizationFactory()
    job = PressReviewJob.objects.create(organization=org, status=PressReviewJob.Status.TEXT_EXTRACTION)

    job = transition_job(job, PressReviewJob.Status.FAILED, error_message="boom")

    assert job.status == PressReviewJob.Status.FAILED
    assert job.error_message == "boom"


@pytest.mark.django_db
def test_failed_job_can_be_retried_from_text_extraction():
    org = OrganizationFactory()
    job = PressReviewJob.objects.create(organization=org, status=PressReviewJob.Status.FAILED)

    job = transition_job(job, PressReviewJob.Status.TEXT_EXTRACTION)

    assert job.status == PressReviewJob.Status.TEXT_EXTRACTION


@pytest.mark.django_db
def test_update_step_progress_computes_job_percent_within_step_band():
    org = OrganizationFactory()
    job = PressReviewJob.objects.create(
        organization=org, status=PressReviewJob.Status.HIGHLIGHT_DETECTION, progress_percent=40
    )

    update_step_progress(job, PipelineStepRun.StepName.HIGHLIGHT_DETECTION, chunks_done=0, chunks_total=4)
    job.refresh_from_db()
    assert job.progress_percent == 40  # 0/4 traités -> juste la base de l'étape

    update_step_progress(job, PipelineStepRun.StepName.HIGHLIGHT_DETECTION, chunks_done=2, chunks_total=4)
    job.refresh_from_db()
    # base 40 + poids 35 * 0.5 = 57.5 -> 57 (int())
    assert job.progress_percent == 57

    step = PipelineStepRun.objects.get(job=job, step_name=PipelineStepRun.StepName.HIGHLIGHT_DETECTION)
    assert step.status == PipelineStepRun.Status.RUNNING
    assert step.progress_percent == 50


@pytest.mark.django_db
def test_update_step_progress_does_not_crash_when_only_total_is_known():
    # Régression : un premier appel qui ne fixe que chunks_total (chunks_done encore
    # jamais renseigné) ne doit pas lever de TypeError (min(None, total)).
    org = OrganizationFactory()
    job = PressReviewJob.objects.create(organization=org, status=PressReviewJob.Status.HIGHLIGHT_DETECTION)
    start_step(job, PipelineStepRun.StepName.HIGHLIGHT_DETECTION)

    update_step_progress(job, PipelineStepRun.StepName.HIGHLIGHT_DETECTION, chunks_total=5)

    step = PipelineStepRun.objects.get(job=job, step_name=PipelineStepRun.StepName.HIGHLIGHT_DETECTION)
    assert step.progress_percent == 0
