"""Maîtrise de la charge et du coût de l'IA : journal de chaque appel (AIUsage), totaux
mensuels dans l'admin, limiteur de débit global et par organisation, plafonds de taille
d'une revue selon la formule, et refus de livrer des revues factices en production."""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.ai_pipeline import mistral_client as mc
from apps.ai_pipeline import ratelimit
from apps.ai_pipeline import tasks as pipeline_tasks
from apps.ai_pipeline.checks import mistral_key_configured
from apps.ai_pipeline.errors import AIRateLimitBusyError, AIUnavailableError, describe_error, is_retryable_error
from apps.ai_pipeline.mistral_client import FakeMistralClient, MistralClient, get_mistral_client
from apps.ai_pipeline.models import AIUsage
from apps.ai_pipeline.ratelimit import acquire_ai_slot
from apps.ai_pipeline.tasks import run_press_review_pipeline
from apps.ai_pipeline.usage import ai_call_context, estimate_cost_usd, monthly_totals
from apps.billing.models import Subscription
from apps.press_review.models import PipelineStepRun, PressReviewJob, SourceDocument
from tests.factories import DetectionCategoryFactory, OrganizationFactory, PlanFactory, SubscriptionFactory
from tests.image_fixtures import make_image_bytes
from tests.pdf_fixtures import make_minimal_pdf_bytes, make_multipage_pdf_bytes

VALID_JSON = '{"summary": "Résumé.", "highlights": [], "journal": "LE JOUR", "rubrique": "generale", "resume": "Notice."}'


class _Chat:
    """`client.chat` du SDK Mistral : lève les erreurs prévues, puis répond avec `usage`."""

    def __init__(self, *, errors=(), content=VALID_JSON, usage=None):
        self.errors = list(errors)
        self.content = content
        self.usage = usage if usage is not None else SimpleNamespace(prompt_tokens=120, completion_tokens=30, total_tokens=150)
        self.calls = 0

    def complete(self, **kwargs):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=self.usage)


def _sdk_client(chat, model="ministral-8b-latest"):
    client = MistralClient(api_key="x", model=model)
    client._client = SimpleNamespace(chat=chat)
    return client


# --------------------------------------------------------------------------- journal des appels


@pytest.mark.django_db
def test_each_call_is_recorded_with_tokens_duration_and_who_consumed_it(organization, user):
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    client = _sdk_client(_Chat())

    with ai_call_context(organization_id=organization.id, job_id=job.id, step="CHUNKING_SUMMARIZATION"):
        client.complete_json(system_prompt="s", user_prompt="u")

    usage = AIUsage.objects.get()
    assert (usage.organization, usage.job, usage.step) == (organization, job, "CHUNKING_SUMMARIZATION")
    assert (usage.model, usage.operation, usage.succeeded) == ("ministral-8b-latest", "json", True)
    assert (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens) == (120, 30, 150)
    assert usage.duration_ms >= 0


@pytest.mark.django_db
def test_rate_limited_attempts_are_recorded_as_failures(organization, monkeypatch):
    monkeypatch.setattr(mc.time, "sleep", lambda _s: None)
    rate_limited = RuntimeError('API error occurred: Status 429. Body: {"type":"rate_limited"}')
    chat = _Chat(errors=[rate_limited, rate_limited])

    with ai_call_context(organization_id=organization.id):
        _sdk_client(chat).complete_json(system_prompt="s", user_prompt="u")

    assert chat.calls == 3
    assert list(AIUsage.objects.order_by("created_at").values_list("succeeded", "status_code")) == [
        (False, 429), (False, 429), (True, None),
    ]


@pytest.mark.django_db
def test_vision_calls_are_recorded_as_such(organization):
    chat = _Chat(content="Texte de la une.")

    _sdk_client(chat).transcribe_image(b"jpeg")

    assert AIUsage.objects.get().operation == "vision"


@pytest.mark.django_db
@override_settings(MISTRAL_HIGHLIGHT_MODEL="", MISTRAL_REVIEW_MODEL="")
def test_the_pipeline_attributes_every_call_to_the_job_and_its_step(organization, user, monkeypatch):
    DetectionCategoryFactory(organization=None, is_active=True)
    client = _sdk_client(_Chat())
    monkeypatch.setattr(pipeline_tasks, "get_mistral_client", lambda: client)
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    SourceDocument.objects.create(
        organization=organization, job=job, uploaded_by=user, original_filename="a.pdf", kind="pdf",
        file=SimpleUploadedFile("a.pdf", make_minimal_pdf_bytes(["Un article de presse avec du texte reel."])),
    )

    run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.REVIEW_READY, job.error_message
    steps = set(AIUsage.objects.filter(job=job, organization=organization).values_list("step", flat=True))
    assert steps == {"CHUNKING_SUMMARIZATION", "HIGHLIGHT_DETECTION", "REVIEW_DRAFTING"}


@pytest.mark.django_db
def test_a_tracking_failure_never_breaks_the_call(monkeypatch):
    def broken_create(**kwargs):
        raise RuntimeError("base indisponible")

    monkeypatch.setattr(AIUsage.objects, "create", broken_create)

    assert _sdk_client(_Chat()).complete_json(system_prompt="s", user_prompt="u")["summary"] == "Résumé."


# --------------------------------------------------------------------------- coût et admin


def test_cost_estimate_uses_indicative_prices_and_tolerates_unknown_models():
    assert estimate_cost_usd("ministral-8b-latest", 1_000_000, 1_000_000) == pytest.approx(0.20)
    assert estimate_cost_usd("ministral-8b-2410", 1_000_000, 0) == pytest.approx(0.10)  # version datée
    assert estimate_cost_usd("modele-inconnu", 1000, 1000) is None


@pytest.mark.django_db
@override_settings(AI_TOKEN_PRICES_USD={"modele-maison": [1, 2]})
def test_monthly_totals_per_organization(user):
    alpha, beta = OrganizationFactory(name="Alpha"), OrganizationFactory(name="Beta")
    job = PressReviewJob.objects.create(organization=alpha, created_by=user)
    AIUsage.objects.create(organization=alpha, job=job, model="ministral-8b-latest", prompt_tokens=600_000, completion_tokens=400_000)
    AIUsage.objects.create(organization=alpha, job=job, model="modele-maison", prompt_tokens=1_000_000, completion_tokens=0, succeeded=False)
    AIUsage.objects.create(organization=beta, model="modele-inconnu", prompt_tokens=10, completion_tokens=5)

    month = monthly_totals()[0]

    rows = {row["organization"]: row for row in month["rows"]}
    assert rows["Alpha"]["calls"] == 2 and rows["Alpha"]["failed"] == 1 and rows["Alpha"]["jobs"] == 1
    assert rows["Alpha"]["prompt_tokens"] == 1_600_000
    assert rows["Alpha"]["cost_usd"] == pytest.approx(0.10 + 1.0)
    assert rows["Beta"]["unpriced_models"] == {"modele-inconnu"}
    assert month["total"]["calls"] == 3


@pytest.mark.django_db
def test_staff_sees_the_monthly_totals_page_and_members_do_not(client, organization):
    AIUsage.objects.create(organization=organization, model="ministral-8b-latest", prompt_tokens=10, completion_tokens=5)
    url = reverse("admin:ai_pipeline_aiusage_monthly")

    client.force_login(User.objects.create_user(email="membre@example.com", password="x" * 12))
    assert client.get(url).status_code == 302  # renvoyé vers la connexion de l'admin

    client.force_login(User.objects.create_superuser(email="staff@example.com", password="x" * 12))
    response = client.get(url)
    assert response.status_code == 200
    assert organization.name in response.content.decode()
    changelist = client.get(reverse("admin:ai_pipeline_aiusage_changelist"))
    assert changelist.status_code == 200 and url in changelist.content.decode()


# --------------------------------------------------------------------------- limiteur de débit


@pytest.fixture
def limiter(settings):
    cache.clear()
    ratelimit._local_counters.clear()
    settings.AI_RATE_LIMIT_GLOBAL_PER_MINUTE = 3
    settings.AI_RATE_LIMIT_ORG_PER_MINUTE = 2
    settings.AI_RATE_LIMIT_MAX_WAIT_SECONDS = 0
    yield settings
    cache.clear()
    ratelimit._local_counters.clear()


def _acquire(organization_id, **kwargs):
    with ai_call_context(organization_id=organization_id):
        acquire_ai_slot(clock=lambda: 6_000_010.0, **kwargs)


def test_one_organization_cannot_take_the_whole_rate(limiter):
    _acquire("org-a")
    _acquire("org-a")
    with pytest.raises(AIRateLimitBusyError):
        _acquire("org-a")  # plafond par organisation (2/min) atteint
    _acquire("org-b")  # une autre entreprise passe encore
    with pytest.raises(AIRateLimitBusyError):
        _acquire("org-c")  # plafond global (3/min) atteint


def test_a_full_window_waits_for_the_next_minute_instead_of_failing(limiter):
    limiter.AI_RATE_LIMIT_MAX_WAIT_SECONDS = 90
    now = {"t": 6_000_010.0}  # 10 s après le début d'une fenêtre d'une minute
    waits = []

    def fake_sleep(seconds):
        waits.append(seconds)
        now["t"] += seconds

    for _ in range(3):
        with ai_call_context(organization_id="org-a"):
            acquire_ai_slot(clock=lambda: now["t"], sleep=fake_sleep)

    assert len(waits) == 1 and waits[0] == pytest.approx(50, abs=0.1)


def test_the_limiter_falls_back_to_a_local_counter_when_the_cache_is_down(limiter, monkeypatch):
    class _DownCaches:
        def __getitem__(self, alias):
            raise ConnectionError("Redis injoignable")

    monkeypatch.setattr(ratelimit, "caches", _DownCaches())

    _acquire("org-a")
    _acquire("org-a")
    with pytest.raises(AIRateLimitBusyError):
        _acquire("org-a")


def test_a_saturated_limiter_is_a_transient_error_retried_by_celery():
    exc = AIRateLimitBusyError("saturé")
    assert is_retryable_error(exc)
    assert "Limite de débit" in describe_error(exc)


@pytest.mark.django_db
def test_the_client_goes_through_the_limiter_before_calling_mistral(limiter):
    limiter.AI_RATE_LIMIT_ORG_PER_MINUTE = 1
    chat = _Chat()
    client = _sdk_client(chat)

    with ai_call_context(organization_id="org-a"):
        client.complete_json(system_prompt="s", user_prompt="u")
        with pytest.raises(AIRateLimitBusyError):
            client.complete_json(system_prompt="s", user_prompt="u")

    assert chat.calls == 1


# --------------------------------------------------------------------------- plafonds de la formule


@pytest.fixture
def starter_org(organization, settings):
    settings.AI_REVIEW_LIMITS = {"default": {"max_documents": 30, "max_pages": 80}, "starter": {"max_documents": 2, "max_pages": 3}}
    now = timezone.now()
    SubscriptionFactory(
        organization=organization, plan=PlanFactory(code="starter", name="Starter"), status=Subscription.Status.ACTIVE,
        current_period_start=now - timedelta(days=1), current_period_end=now + timedelta(days=29),
    )
    DetectionCategoryFactory(organization=None, is_active=True)
    return organization


def _upload(client, name, content, content_type):
    response = client.post(
        "/api/documents/", {"file": SimpleUploadedFile(name, content, content_type=content_type)}, format="multipart"
    )
    assert response.status_code == 201, response.data
    return response.data["id"]


def _photo(client, name="une.png"):
    return _upload(client, name, make_image_bytes(), "image/png")


def _pdf(client, name, pages):
    return _upload(client, name, make_multipage_pdf_bytes([[f"Page {i} du journal."] for i in range(pages)]), "application/pdf")


@pytest.mark.django_db
def test_too_many_documents_for_the_plan_is_refused_before_the_analysis(authenticated_client, starter_org):
    ids = [_photo(authenticated_client, f"p{i}.png") for i in range(3)]

    response = authenticated_client.post("/api/jobs/", {"document_ids": ids}, format="json")

    assert response.status_code == 400
    assert "Votre formule Starter permet d'analyser jusqu'à 2 documents par revue (3 sélectionnés)" in response.data["detail"]
    assert "contactez-nous" in response.data["detail"]
    assert not PressReviewJob.objects.exists()


@pytest.mark.django_db
def test_too_many_pages_for_the_plan_is_refused(authenticated_client, starter_org):
    ids = [_pdf(authenticated_client, "cahier.pdf", 3), _photo(authenticated_client)]

    response = authenticated_client.post("/api/jobs/", {"document_ids": ids}, format="json")

    assert response.status_code == 400
    assert "jusqu'à 3 pages par revue" in response.data["detail"] and "en compte 4" in response.data["detail"]


@pytest.mark.django_db
def test_a_pdf_longer_than_the_global_maximum_is_refused_by_name(authenticated_client, starter_org, settings):
    settings.AI_MAX_PDF_PAGES = 2
    starter_org.subscription.plan.code = "pro"  # pas de plafond de pages propre : défaut 80
    starter_org.subscription.plan.save()

    response = authenticated_client.post(
        "/api/jobs/", {"document_ids": [_pdf(authenticated_client, "annuaire.pdf", 3)]}, format="json"
    )

    assert response.status_code == 400
    assert "« annuaire.pdf » compte 3 pages" in response.data["detail"]


@pytest.mark.django_db
def test_a_review_within_the_plan_limits_starts(authenticated_client, starter_org, monkeypatch):
    monkeypatch.setattr(pipeline_tasks, "run_press_review_pipeline", lambda job_id: None)
    ids = [_pdf(authenticated_client, "une.pdf", 2), _photo(authenticated_client)]

    response = authenticated_client.post("/api/jobs/", {"document_ids": ids}, format="json")

    assert response.status_code == 201, response.data


# --------------------------------------------------------------------------- pas de revue factice en production


@override_settings(MISTRAL_API_KEY="", MISTRAL_ALLOW_FAKE_CLIENT=False)
def test_production_without_a_key_refuses_the_fake_client():
    with pytest.raises(AIUnavailableError):
        get_mistral_client()


@override_settings(MISTRAL_API_KEY="", MISTRAL_ALLOW_FAKE_CLIENT=None, DEBUG=True)
def test_the_fake_client_follows_debug_when_not_configured():
    assert isinstance(get_mistral_client(), FakeMistralClient)


@pytest.mark.django_db
@override_settings(MISTRAL_API_KEY="", MISTRAL_ALLOW_FAKE_CLIENT=False)
def test_a_review_fails_with_an_admin_message_instead_of_mock_content(organization, user):
    DetectionCategoryFactory(organization=None, is_active=True)
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    SourceDocument.objects.create(
        organization=organization, job=job, uploaded_by=user, original_filename="a.pdf", kind="pdf",
        file=SimpleUploadedFile("a.pdf", make_minimal_pdf_bytes(["Un article de presse avec du texte reel."])),
    )

    with pytest.raises(AIUnavailableError):
        run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.FAILED
    assert "clé Mistral manquante" in job.error_message and "administrateur" in job.error_message
    step = PipelineStepRun.objects.get(job=job, step_name=PipelineStepRun.StepName.CHUNKING_SUMMARIZATION)
    assert step.status == "failed"


def test_a_deploy_check_warns_when_the_key_is_missing():
    with override_settings(DEBUG=False, MISTRAL_API_KEY="", MISTRAL_ALLOW_FAKE_CLIENT=False):
        assert [w.id for w in mistral_key_configured()] == ["ai_pipeline.W001"]
    with override_settings(DEBUG=False, MISTRAL_API_KEY="sk-x", MISTRAL_ALLOW_FAKE_CLIENT=False):
        assert mistral_key_configured() == []
