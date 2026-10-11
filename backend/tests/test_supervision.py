"""Supervision : /api/health/ (base, Redis, worker) et surveillance des revues bloquées."""
import os
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.core import health
from apps.press_review.models import PipelineStepRun, PressReviewJob
from apps.press_review.services.pipeline import start_step, transition_job
from apps.press_review.services.watchdog import fail_stuck_jobs
from config.celery import app as celery_app


@pytest.fixture(autouse=True)
def _clear_health_cache():
    cache.delete(health.WORKER_CACHE_KEY)
    yield
    cache.delete(health.WORKER_CACHE_KEY)


# --------------------------------------------------------------------------- /api/health/


@pytest.mark.django_db
def test_health_is_ok_in_eager_mode_and_skips_the_worker(api_client):
    response = api_client.get("/api/health/")

    assert response.status_code == 200
    assert response.data == {"status": "ok", "checks": {"database": "ok", "redis": "skipped", "worker": "skipped"}}


@pytest.fixture
def redis_broker(settings, monkeypatch):
    """Simule la prod : broker Redis, worker séparé (sans contacter de vrai Redis)."""
    settings.CELERY_TASK_ALWAYS_EAGER = False
    settings.CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"
    monkeypatch.setattr(health, "check_redis", lambda: health.OK)


@pytest.mark.django_db
def test_health_reports_a_live_worker(api_client, redis_broker, monkeypatch):
    calls = []

    def _ping(**kwargs):
        calls.append(kwargs)
        return [{"celery@vps": {"ok": "pong"}}]

    monkeypatch.setattr(celery_app.control, "ping", _ping)

    first = api_client.get("/api/health/")
    second = api_client.get("/api/health/")

    assert first.status_code == 200 and first.data["checks"]["worker"] == "ok"
    assert second.status_code == 200
    assert len(calls) == 1  # réponse mise en cache : pas de diffusion sur le broker à chaque appel
    assert calls[0]["limit"] == 1


@pytest.mark.django_db
def test_health_is_degraded_when_no_worker_answers(api_client, redis_broker, monkeypatch):
    monkeypatch.setattr(celery_app.control, "ping", lambda **kwargs: [])

    response = api_client.get("/api/health/")

    assert response.status_code == 503
    assert response.data["status"] == "degraded"
    assert response.data["checks"] == {"database": "ok", "redis": "ok", "worker": "error"}


@pytest.mark.django_db
def test_redis_down_is_an_error_and_the_worker_is_not_pinged(api_client, settings, monkeypatch):
    settings.CELERY_TASK_ALWAYS_EAGER = False
    settings.CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"

    def _redis_down():
        raise ConnectionError("Connection refused")

    def _ping(**kwargs):
        raise AssertionError("le worker ne doit pas être sondé quand Redis est injoignable")

    monkeypatch.setattr(health, "check_redis", _redis_down)
    monkeypatch.setattr(celery_app.control, "ping", _ping)

    response = api_client.get("/api/health/")

    assert response.status_code == 503
    assert response.data == {"status": "error", "checks": {"database": "ok", "redis": "error", "worker": "error"}}


@pytest.mark.django_db
def test_health_never_leaks_error_details(api_client, monkeypatch):
    def _db_down():
        raise RuntimeError("password authentication failed for user revue")

    monkeypatch.setattr(health, "check_database", _db_down)

    response = api_client.get("/api/health/")

    assert response.status_code == 503
    assert response.data["status"] == "error"
    assert "password" not in response.content.decode()


@pytest.mark.skipif(not os.environ.get("CI_REDIS_URL"), reason="Redis réel seulement en CI (service GitHub Actions)")
def test_redis_check_against_a_real_redis(settings):
    settings.CELERY_BROKER_URL = os.environ["CI_REDIS_URL"]

    assert health.check_redis() == health.OK


# --------------------------------------------------------------------------- revues bloquées


def _age(job, minutes):
    """Recule l'horodatage du job et de ses étapes (update() ne touche pas auto_now)."""
    moment = timezone.now() - timedelta(minutes=minutes)
    PressReviewJob.objects.filter(pk=job.pk).update(updated_at=moment)
    PipelineStepRun.objects.filter(job=job).update(updated_at=moment)


def _running_job(organization, user, status=PressReviewJob.Status.HIGHLIGHT_DETECTION):
    job = PressReviewJob.objects.create(organization=organization, created_by=user, title="Revue bloquée")
    for step in (
        PressReviewJob.Status.TEXT_EXTRACTION,
        PressReviewJob.Status.CHUNKING_SUMMARIZATION,
        PressReviewJob.Status.HIGHLIGHT_DETECTION,
    ):
        transition_job(job, step)
        if step == status:
            break
    start_step(job, status)
    return job


@pytest.mark.django_db
def test_job_without_progress_is_failed_so_that_retry_works(authenticated_client, organization, user):
    job = _running_job(organization, user)
    _age(job, 45)

    failed = fail_stuck_jobs(older_than=timedelta(minutes=30))

    job.refresh_from_db()
    assert [j.pk for j in failed] == [job.pk]
    assert job.status == PressReviewJob.Status.FAILED
    assert "30 minutes" in job.error_message and "Réessayer" in job.error_message
    step = job.step_runs.get(step_name=PipelineStepRun.StepName.HIGHLIGHT_DETECTION)
    assert step.status == PipelineStepRun.Status.FAILED

    response = authenticated_client.post(f"/api/jobs/{job.pk}/retry/")
    assert response.status_code == 200  # « Réessayer » accepté (il exige FAILED)


@pytest.mark.django_db
def test_recent_progress_keeps_the_job_running(organization, user):
    quiet_job = _running_job(organization, user)
    _age(quiet_job, 10)
    busy_step_job = _running_job(organization, user)
    _age(busy_step_job, 45)
    # Une étape en pause de relance automatique a bougé récemment : le job vit encore.
    PipelineStepRun.objects.filter(job=busy_step_job).update(updated_at=timezone.now() - timedelta(minutes=2))

    assert fail_stuck_jobs(older_than=timedelta(minutes=30)) == []
    for job in (quiet_job, busy_step_job):
        job.refresh_from_db()
        assert job.status == PressReviewJob.Status.HIGHLIGHT_DETECTION


@pytest.mark.django_db
def test_job_never_picked_up_by_a_worker_is_failed_too(organization, user):
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    _age(job, 120)

    fail_stuck_jobs(older_than=timedelta(minutes=30))

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.FAILED


@pytest.mark.django_db
def test_finished_jobs_are_never_touched(organization, user):
    ready = PressReviewJob.objects.create(organization=organization, created_by=user, status=PressReviewJob.Status.REVIEW_READY)
    failed = PressReviewJob.objects.create(
        organization=organization, created_by=user, status=PressReviewJob.Status.FAILED, error_message="Avant"
    )
    _age(ready, 500)
    _age(failed, 500)

    assert fail_stuck_jobs(older_than=timedelta(minutes=30)) == []
    failed.refresh_from_db()
    assert failed.error_message == "Avant"


@pytest.mark.django_db
def test_watchdog_task_uses_the_configured_delay(organization, user, settings):
    from apps.notifications.tasks import fail_stuck_jobs as watchdog_task

    settings.PIPELINE_STUCK_AFTER_MINUTES = 60
    job = _running_job(organization, user)
    _age(job, 45)

    assert watchdog_task.apply().get() == []
    _age(job, 90)
    assert watchdog_task.apply().get() == [str(job.pk)]


@pytest.mark.django_db
def test_stuck_job_failure_notifies_its_creator(organization, user, settings, django_capture_on_commit_callbacks):
    from django.core import mail

    settings.STAFF_NOTIFICATION_EMAILS = ["staff@revue.test"]
    job = _running_job(organization, user)
    _age(job, 45)

    with django_capture_on_commit_callbacks(execute=True):
        fail_stuck_jobs(older_than=timedelta(minutes=30))

    assert {tuple(message.to) for message in mail.outbox} == {(user.email,), ("staff@revue.test",)}


def test_celery_requeues_tasks_of_a_killed_worker(settings):
    assert settings.CELERY_TASK_ACKS_LATE is True
    assert settings.CELERY_TASK_REJECT_ON_WORKER_LOST is True
