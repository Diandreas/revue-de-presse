"""Comportement de l'analyse *en arrière-plan* : progression par document, ordre de
lecture, tolérance aux fichiers sans texte, relance automatique des erreurs
transitoires, et mise en file qui échoue (broker injoignable)."""
import time
from datetime import timedelta
from types import SimpleNamespace

import pytesseract
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.ai_pipeline import ocr
from apps.ai_pipeline import tasks as pipeline_tasks
from apps.ai_pipeline.errors import describe_error, is_retryable_error
from apps.ai_pipeline.mistral_client import FakeMistralClient
from apps.ai_pipeline.tasks import MAX_STEP_RETRIES, _handle_step_error, run_press_review_pipeline
from apps.billing.models import Subscription
from apps.press_review.models import PipelineStepRun, PressReviewJob, SourceDocument
from apps.press_review.services.pipeline import enter_step, transition_job
from tests.factories import DetectionCategoryFactory, SubscriptionFactory
from tests.image_fixtures import make_image_bytes
from tests.pdf_fixtures import make_minimal_pdf_bytes

OCR_TEXT = "Texte OCR simule d'une coupure de presse camerounaise."


@pytest.fixture(autouse=True)
def _stub_ocr(monkeypatch):
    monkeypatch.setattr(pytesseract, "image_to_string", lambda *a, **k: OCR_TEXT)


def _add_image(job, organization, user, name, *, created_at=None):
    doc = SourceDocument.objects.create(
        organization=organization,
        job=job,
        uploaded_by=user,
        file=SimpleUploadedFile(name, make_image_bytes(), content_type="image/png"),
        original_filename=name,
        kind=SourceDocument.Kind.IMAGE,
    )
    if created_at is not None:
        SourceDocument.objects.filter(pk=doc.pk).update(created_at=created_at)
    return doc


def _subscribe(organization):
    SubscriptionFactory(
        organization=organization,
        status=Subscription.Status.ACTIVE,
        current_period_start=timezone.now() - timedelta(days=1),
    )


def _upload_pdf(client):
    pdf = make_minimal_pdf_bytes(["Un article de presse avec suffisamment de texte reel."])
    return client.post(
        "/api/documents/",
        {"file": SimpleUploadedFile("a.pdf", pdf, content_type="application/pdf")},
        format="multipart",
    ).data["id"]


class _RateLimitedClient(FakeMistralClient):
    """Lève un 429 sur les `fail_times` premiers appels, puis répond normalement."""

    def __init__(self, fail_times):
        super().__init__()
        self.fail_times = fail_times
        self.calls = 0

    def complete_json(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError('API error occurred: Status 429. Body: {"type":"rate_limited"}')
        return super().complete_json(**kwargs)


# --- progression & lecture méthodique des documents ----------------------------------


@pytest.mark.django_db
def test_extraction_reports_progress_per_document(organization, user):
    DetectionCategoryFactory(organization=None, is_active=True)
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    for name in ("p1.png", "p2.png", "p3.png"):
        _add_image(job, organization, user, name)

    run_press_review_pipeline(str(job.id))

    step = PipelineStepRun.objects.get(job=job, step_name=PipelineStepRun.StepName.TEXT_EXTRACTION)
    assert step.result_summary["unit"] == "documents"
    assert step.result_summary["chunks_done"] == step.result_summary["chunks_total"] == 3
    assert step.result_summary["documents_failed"] == 0


@pytest.mark.django_db
def test_documents_are_read_in_upload_order(organization, user):
    """Régression : Meta.ordering était -created_at, donc la dernière photo téléversée
    était analysée (et présentée dans la revue) en premier."""
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    now = timezone.now()
    _add_image(job, organization, user, "troisieme.png", created_at=now)
    _add_image(job, organization, user, "premiere.png", created_at=now - timedelta(minutes=2))
    _add_image(job, organization, user, "deuxieme.png", created_at=now - timedelta(minutes=1))

    assert [d.original_filename for d in job.documents.all()] == ["premiere.png", "deuxieme.png", "troisieme.png"]


@pytest.mark.django_db
def test_photo_without_readable_text_is_flagged_but_does_not_fail_the_job(organization, user, monkeypatch):
    DetectionCategoryFactory(organization=None, is_active=True)
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    _add_image(job, organization, user, "lisible.png", created_at=timezone.now() - timedelta(minutes=1))
    _add_image(job, organization, user, "paysage.png", created_at=timezone.now())

    calls = {"n": 0}

    def _ocr(*args, **kwargs):
        calls["n"] += 1
        return OCR_TEXT if calls["n"] == 1 else "   \n "  # 2e photo : aucun texte

    monkeypatch.setattr(pytesseract, "image_to_string", _ocr)

    run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.REVIEW_READY
    by_name = {d.original_filename: d for d in job.documents.all()}
    assert by_name["lisible.png"].extraction_status == "done"
    assert by_name["paysage.png"].extraction_status == "failed"
    assert "Aucun texte" in by_name["paysage.png"].extraction_error
    step = PipelineStepRun.objects.get(job=job, step_name=PipelineStepRun.StepName.TEXT_EXTRACTION)
    assert step.result_summary["documents_failed"] == 1


@pytest.mark.django_db
def test_job_error_lists_the_reason_for_each_unreadable_file(organization, user, monkeypatch):
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    _add_image(job, organization, user, "vide.png")
    monkeypatch.setattr(pytesseract, "image_to_string", lambda *a, **k: "")

    with pytest.raises(Exception):
        run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.FAILED
    assert "vide.png" in job.error_message and "Aucun texte" in job.error_message


# --- erreurs transitoires : relance automatique en arrière-plan ----------------------


@pytest.mark.django_db
def test_rate_limit_in_eager_mode_fails_immediately_with_a_readable_message(
    authenticated_client, organization, monkeypatch
):
    DetectionCategoryFactory(organization=None, is_active=True)
    _subscribe(organization)
    client = _RateLimitedClient(fail_times=10**6)
    monkeypatch.setattr(pipeline_tasks, "get_mistral_client", lambda: client)

    response = authenticated_client.post(
        "/api/jobs/", {"title": "x", "document_ids": [_upload_pdf(authenticated_client)]}, format="json"
    )

    assert response.status_code == 201, response.data
    assert response.data["status"] == "FAILED"
    # Mode eager (pas de worker pour honorer un délai) : pas de relance, échec immédiat.
    assert client.calls == 1
    assert "Limite de débit" in response.data["error_message"]
    assert "rate_limited" not in response.data["error_message"]  # pas de JSON brut côté client


@pytest.mark.django_db
def test_non_transient_error_is_not_retried(authenticated_client, organization, monkeypatch):
    DetectionCategoryFactory(organization=None, is_active=True)
    _subscribe(organization)
    calls = {"n": 0}

    class _ForbiddenClient:
        def complete_json(self, **kwargs):
            calls["n"] += 1
            raise RuntimeError('Status 403. Body: {"type":"tier_not_allowed"}')

    monkeypatch.setattr(pipeline_tasks, "get_mistral_client", lambda: _ForbiddenClient())

    response = authenticated_client.post(
        "/api/jobs/", {"title": "x", "document_ids": [_upload_pdf(authenticated_client)]}, format="json"
    )

    assert response.data["status"] == "FAILED"
    assert calls["n"] == 1  # réessayer ne changerait rien : on échoue tout de suite
    assert "MISTRAL_MODEL" in response.data["error_message"]


def test_error_classification():
    class _HttpError(Exception):
        def __init__(self, status_code):
            super().__init__(f"Status {status_code}")
            self.status_code = status_code

    assert is_retryable_error(_HttpError(429))
    assert is_retryable_error(_HttpError(503))
    assert is_retryable_error(TimeoutError())
    assert not is_retryable_error(_HttpError(403))
    assert not is_retryable_error(ValueError("catégories manquantes"))
    assert "Limite de débit" in describe_error(_HttpError(429))
    assert describe_error(ValueError("message métier")) == "message métier"


# --- mise en file : le job ne doit jamais rester bloqué sans erreur visible ---------


@pytest.mark.django_db
def test_job_creation_returns_immediately_when_the_pipeline_runs_in_the_background(
    authenticated_client, organization, monkeypatch
):
    """Simule un worker qui n'a pas encore pris la tâche : la requête rend la main tout
    de suite avec un job UPLOADED (l'interface suit ensuite la progression par polling)."""
    _subscribe(organization)
    monkeypatch.setattr(pipeline_tasks, "run_press_review_pipeline", lambda job_id: None)

    response = authenticated_client.post(
        "/api/jobs/", {"title": "x", "document_ids": [_upload_pdf(authenticated_client)]}, format="json"
    )

    assert response.status_code == 201, response.data
    assert response.data["status"] == "UPLOADED"
    assert response.data["step_runs"] == []


@pytest.mark.django_db
def test_unreachable_broker_marks_the_job_failed_instead_of_leaving_it_stuck(
    authenticated_client, organization, monkeypatch
):
    _subscribe(organization)

    def _broker_down(job_id):
        raise ConnectionError("Error 10061 connecting to localhost:6379")

    monkeypatch.setattr(pipeline_tasks, "run_press_review_pipeline", _broker_down)

    response = authenticated_client.post(
        "/api/jobs/", {"title": "x", "document_ids": [_upload_pdf(authenticated_client)]}, format="json"
    )

    assert response.status_code == 201, response.data
    assert response.data["status"] == "FAILED"
    assert "file de tâches" in response.data["error_message"]


@pytest.mark.django_db
def test_retry_moves_the_job_out_of_failed_immediately_so_polling_continues(
    authenticated_client, organization, user, monkeypatch
):
    """Régression (async) : un job resté FAILED jusqu'à ce que le worker prenne la tâche
    arrêtait le polling du frontend, qui ne suit que les statuts « actifs »."""
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    transition_job(job, PressReviewJob.Status.TEXT_EXTRACTION)
    transition_job(job, PressReviewJob.Status.FAILED, error_message="ancienne erreur")
    monkeypatch.setattr(pipeline_tasks, "run_press_review_pipeline", lambda job_id: None)

    response = authenticated_client.post(f"/api/jobs/{job.id}/retry/")

    assert response.status_code == 200, response.data
    assert response.data["status"] == "TEXT_EXTRACTION"
    assert response.data["error_message"] == ""


@pytest.mark.django_db
def test_enter_step_is_idempotent_so_celery_can_rerun_a_step(organization, user):
    job = PressReviewJob.objects.create(organization=organization, created_by=user)

    enter_step(job, PressReviewJob.Status.TEXT_EXTRACTION, PipelineStepRun.StepName.TEXT_EXTRACTION)
    enter_step(job, PressReviewJob.Status.TEXT_EXTRACTION, PipelineStepRun.StepName.TEXT_EXTRACTION)

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.TEXT_EXTRACTION
    assert job.step_runs.count() == 1


# --- logique de relance (déterministe, sans worker) -----------------------------------


class _Scheduled(Exception):
    """Ce que `task.retry(...)` lève quand Celery programme une nouvelle tentative."""

    def __init__(self, countdown):
        super().__init__(f"retry in {countdown}s")
        self.countdown = countdown


class _FakeTask:
    max_retries = MAX_STEP_RETRIES

    def __init__(self, *, retries=0, is_eager=False):
        self.request = SimpleNamespace(retries=retries, is_eager=is_eager)

    def retry(self, *, exc, countdown):
        return _Scheduled(countdown)


def _job_in_extraction(organization, user):
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    enter_step(job, PressReviewJob.Status.TEXT_EXTRACTION, PipelineStepRun.StepName.TEXT_EXTRACTION)
    return job


@pytest.mark.django_db
def test_transient_error_schedules_a_retry_and_keeps_the_job_running(organization, user):
    job = _job_in_extraction(organization, user)
    step_name = PipelineStepRun.StepName.TEXT_EXTRACTION

    with pytest.raises(_Scheduled) as scheduled:
        _handle_step_error(_FakeTask(retries=0), job, step_name, RuntimeError("Status 429 rate_limited"))

    assert scheduled.value.countdown == pipeline_tasks.RETRY_BASE_DELAY_SECONDS  # 1re relance
    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.TEXT_EXTRACTION  # toujours en cours, pas FAILED
    retry = PipelineStepRun.objects.get(job=job, step_name=step_name).result_summary["retry"]
    assert retry["attempt"] == 1 and "Limite de débit" in retry["reason"]  # visible dans l'interface


@pytest.mark.django_db
def test_retry_delay_grows_with_each_attempt(organization, user):
    job = _job_in_extraction(organization, user)

    with pytest.raises(_Scheduled) as scheduled:
        _handle_step_error(
            _FakeTask(retries=2), job, PipelineStepRun.StepName.TEXT_EXTRACTION, RuntimeError("Status 503")
        )

    assert scheduled.value.countdown == pipeline_tasks.RETRY_BASE_DELAY_SECONDS * 3


@pytest.mark.django_db
def test_exhausted_retries_fail_the_job_with_a_message_mentioning_the_retries(organization, user):
    job = _job_in_extraction(organization, user)

    _handle_step_error(
        _FakeTask(retries=MAX_STEP_RETRIES), job, PipelineStepRun.StepName.TEXT_EXTRACTION,
        RuntimeError("Status 429 rate_limited"),
    )

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.FAILED
    assert "relancée automatiquement" in job.error_message


@pytest.mark.django_db
def test_eager_mode_never_schedules_a_retry(organization, user):
    job = _job_in_extraction(organization, user)

    _handle_step_error(
        _FakeTask(is_eager=True), job, PipelineStepRun.StepName.TEXT_EXTRACTION, RuntimeError("Status 429")
    )

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.FAILED


# --- VRAI worker Celery (thread + broker mémoire) : l'analyse tourne bien en arrière-plan


@pytest.fixture
def background_worker(monkeypatch, settings):
    """Démarre un vrai worker Celery dans un thread : les tâches sont publiées sur un
    broker (mémoire) et exécutées HORS de la requête, exactement comme en production."""
    from celery.contrib.testing.worker import start_worker

    from config.celery import app

    monkeypatch.setattr(pipeline_tasks, "RETRY_BASE_DELAY_SECONDS", 0)  # pas d'attente en test
    # NB : `app.conf.task_always_eager = False` est sans effet (Celery relit la valeur,
    # préfixée CELERY_, dans les settings Django) — on passe donc par les settings.
    settings.CELERY_TASK_ALWAYS_EAGER = False
    assert app.conf.task_always_eager is False
    with start_worker(app, pool="solo", perform_ping_check=False, loglevel="ERROR", shutdown_timeout=20):
        yield


def _wait_for_terminal_status(job, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job.refresh_from_db()
        if job.status in (PressReviewJob.Status.REVIEW_READY, PressReviewJob.Status.FAILED):
            return job.status
        time.sleep(0.1)
    raise AssertionError(f"Le job est resté en {job.status} après {timeout}s (worker bloqué ?)")


@pytest.mark.django_db(transaction=True)
def test_real_worker_runs_the_whole_pipeline_in_the_background(background_worker, organization, user):
    DetectionCategoryFactory(organization=None, is_active=True)
    job = PressReviewJob.objects.create(organization=organization, created_by=user, title="Revue photos")
    for name in ("p1.png", "p2.png", "p3.png"):
        _add_image(job, organization, user, name)

    started = time.monotonic()
    run_press_review_pipeline(str(job.id))
    dispatch_seconds = time.monotonic() - started

    assert dispatch_seconds < 2  # la mise en file rend la main tout de suite
    assert _wait_for_terminal_status(job) == PressReviewJob.Status.REVIEW_READY
    assert [s.status for s in job.step_runs.order_by("created_at")] == ["succeeded"] * 4
    assert job.review.summary_markdown


@pytest.mark.django_db(transaction=True)
def test_real_worker_retries_a_rate_limit_by_itself_until_it_succeeds(
    background_worker, organization, user, monkeypatch
):
    DetectionCategoryFactory(organization=None, is_active=True)
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    _add_image(job, organization, user, "coupure.png")
    client = _RateLimitedClient(fail_times=2)
    monkeypatch.setattr(pipeline_tasks, "get_mistral_client", lambda: client)

    run_press_review_pipeline(str(job.id))

    assert _wait_for_terminal_status(job) == PressReviewJob.Status.REVIEW_READY  # sans « Réessayer »
    assert client.calls > 2
    assert all("retry" not in step.result_summary for step in job.step_runs.all())


@pytest.mark.django_db(transaction=True)
def test_real_worker_gives_up_after_the_max_retries_and_marks_the_job_failed(
    background_worker, organization, user, monkeypatch
):
    DetectionCategoryFactory(organization=None, is_active=True)
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    _add_image(job, organization, user, "coupure.png")
    client = _RateLimitedClient(fail_times=10**6)
    monkeypatch.setattr(pipeline_tasks, "get_mistral_client", lambda: client)

    run_press_review_pipeline(str(job.id))

    assert _wait_for_terminal_status(job) == PressReviewJob.Status.FAILED
    assert client.calls == MAX_STEP_RETRIES + 1  # 1 tentative + N relances automatiques
    assert "relancée automatiquement" in job.error_message


# --- OCR : une panne SERVEUR ne doit jamais passer pour « la photo est vide » ----------


@pytest.mark.django_db
def test_missing_ocr_engine_fails_the_job_loudly_instead_of_blaming_the_files(organization, user, monkeypatch):
    """Régression : TesseractNotFoundError était avalée -> texte vide silencieux ; le
    job « réussissait » avec 0 extrait, ou accusait chaque photo d'être sans texte."""
    import pytesseract

    def _no_tesseract(*args, **kwargs):
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "image_to_string", _no_tesseract)
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    _add_image(job, organization, user, "a.png")
    _add_image(job, organization, user, "b.png")

    with pytest.raises(Exception):
        run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.FAILED
    assert "OCR" in job.error_message and "administrateur" in job.error_message
    # Aucune photo n'est marquée « illisible » : ce n'est pas leur faute.
    assert {d.extraction_status for d in job.documents.all()} == {"pending"}


@pytest.mark.django_db
def test_missing_ocr_language_data_is_reported_as_a_server_setup_problem(organization, user, monkeypatch):
    import pytesseract

    def _no_lang(*args, **kwargs):
        raise pytesseract.TesseractError(1, "Failed loading language 'fra'")

    monkeypatch.setattr(pytesseract, "image_to_string", _no_lang)
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    _add_image(job, organization, user, "a.png")

    with pytest.raises(Exception):
        run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.FAILED
    assert "OCR" in job.error_message


@pytest.mark.django_db
def test_tesseract_error_specific_to_one_image_only_affects_that_image(organization, user, monkeypatch):
    import pytesseract

    DetectionCategoryFactory(organization=None, is_active=True)
    calls = {"n": 0}

    def _second_image_is_bad(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise pytesseract.TesseractError(1, "Image too small to scale")
        return OCR_TEXT

    monkeypatch.setattr(pytesseract, "image_to_string", _second_image_is_bad)
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    _add_image(job, organization, user, "ok.png", created_at=timezone.now() - timedelta(minutes=1))
    _add_image(job, organization, user, "mauvaise.png", created_at=timezone.now())

    run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.REVIEW_READY
    by_name = {d.original_filename: d for d in job.documents.all()}
    assert by_name["ok.png"].extraction_status == "done"
    assert by_name["mauvaise.png"].extraction_status == "failed"
    assert "illisible" in by_name["mauvaise.png"].extraction_error


@pytest.mark.django_db
def test_missing_poppler_for_a_scanned_pdf_is_reported_as_a_server_setup_problem(
    organization, user, monkeypatch
):
    from pdf2image.exceptions import PDFInfoNotInstalledError

    def _no_poppler(*args, **kwargs):
        raise PDFInfoNotInstalledError("Unable to get page count. Is poppler installed and in PATH?")

    monkeypatch.setattr(ocr, "convert_from_path", _no_poppler)
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    SourceDocument.objects.create(
        organization=organization,
        job=job,
        uploaded_by=user,
        file=SimpleUploadedFile("scan.pdf", make_minimal_pdf_bytes([""]), content_type="application/pdf"),
        original_filename="scan.pdf",
        kind=SourceDocument.Kind.PDF,
    )

    with pytest.raises(Exception):
        run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.FAILED
    assert "OCR" in job.error_message
