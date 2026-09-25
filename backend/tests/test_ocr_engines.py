"""Lecture des photos par Mistral (vision) côté serveur, choix du moteur, classification
des erreurs d'API (quota à 0 ≠ rate limit passager) et réponses IA mal formatées."""
import base64
import io
from types import SimpleNamespace

import pytest
import pytesseract
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.ai_pipeline import mistral_client as mc
from apps.ai_pipeline import ocr
from apps.ai_pipeline import tasks as pipeline_tasks
from apps.ai_pipeline.errors import (
    OcrUnavailableError,
    describe_error,
    is_configuration_error,
    is_quota_blocked,
    is_retryable_error,
)
from apps.ai_pipeline.mistral_client import FakeMistralClient, MistralClient, complete_structured
from apps.ai_pipeline.schemas import ChunkSummaryResult, HighlightDetectionResult, HighlightItem, ReviewDraftResult
from apps.ai_pipeline.tasks import run_press_review_pipeline
from apps.press_review.models import PressReviewJob, SourceDocument
from pydantic import ValidationError
from tests.factories import DetectionCategoryFactory
from tests.image_fixtures import make_image_bytes

VISION_TEXT = "CAMEROUN TRIBUNE. Le gouvernement annonce une reforme de la loi sur la cybersecurite."


class _ApiError(Exception):
    """Ressemble à mistralai.models.SDKError : status_code + headers HTTP."""

    def __init__(self, status_code, headers=None):
        super().__init__(f"API error occurred: Status {status_code}")
        self.status_code = status_code
        self.headers = headers or {}


QUOTA_ZERO = {"x-ratelimit-limit-req-minute": "0", "x-ratelimit-remaining-req-minute": "0"}
QUOTA_OK = {"x-ratelimit-limit-req-minute": "60", "x-ratelimit-remaining-req-minute": "0"}


class _StubVisionClient:
    """Faux client Mistral côté `ocr` : enregistre les images reçues."""

    def __init__(self, text=VISION_TEXT, error=None):
        self.text, self.error, self.received = text, error, []

    def transcribe_image(self, jpeg_bytes, **kwargs):
        self.received.append(jpeg_bytes)
        if self.error:
            raise self.error
        return self.text


def _use_mistral_ocr(settings, monkeypatch, client):
    settings.OCR_ENGINE = "mistral"
    settings.MISTRAL_API_KEY = "test-key"
    monkeypatch.setattr(ocr, "get_mistral_client", lambda: client)
    # L'analyse du texte reste factice : on ne teste ici que la lecture des images.
    monkeypatch.setattr(pipeline_tasks, "get_mistral_client", lambda: FakeMistralClient())


def _image_job(organization, user, *names, content=None):
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    for name in names:
        SourceDocument.objects.create(
            organization=organization, job=job, uploaded_by=user,
            file=SimpleUploadedFile(name, content or make_image_bytes(), content_type="image/png"),
            original_filename=name, kind=SourceDocument.Kind.IMAGE,
        )
    return job


# --- choix du moteur ------------------------------------------------------------------


def test_auto_engine_uses_tesseract_without_api_key(settings):
    settings.OCR_ENGINE, settings.MISTRAL_API_KEY = "auto", ""
    assert isinstance(ocr.get_ocr_engine(), ocr.TesseractEngine)


def test_auto_engine_uses_mistral_vision_when_a_key_is_configured(settings):
    settings.OCR_ENGINE, settings.MISTRAL_API_KEY = "auto", "k"
    assert isinstance(ocr.get_ocr_engine(), ocr.MistralVisionEngine)


def test_explicit_mistral_engine_without_key_is_a_setup_error(settings):
    settings.OCR_ENGINE, settings.MISTRAL_API_KEY = "mistral", ""
    with pytest.raises(OcrUnavailableError) as exc:
        ocr.get_ocr_engine()
    assert "clé Mistral" in describe_error(exc.value)


def test_unknown_engine_is_rejected(settings):
    settings.OCR_ENGINE = "magie"
    with pytest.raises(OcrUnavailableError):
        ocr.get_ocr_engine()


# --- le moteur Mistral vision ---------------------------------------------------------


def test_vision_engine_sends_a_reasonably_sized_jpeg(monkeypatch):
    stub = _StubVisionClient()
    monkeypatch.setattr(ocr, "get_mistral_client", lambda: stub)
    big_rgba = Image.new("RGBA", (5000, 3000), (240, 240, 240, 255))  # ex : capture d'écran / PNG avec alpha

    text = ocr.MistralVisionEngine().read_image(big_rgba)

    assert text == VISION_TEXT
    sent = Image.open(io.BytesIO(stub.received[0]))
    assert sent.format == "JPEG" and sent.mode == "RGB"
    assert max(sent.size) <= ocr.MAX_VISION_EDGE  # photo 4K réduite : payload et coût maîtrisés


def test_client_transcribe_image_calls_the_vision_model_strictly():
    calls = {}

    def _complete(**kwargs):
        calls.update(kwargs)
        message = SimpleNamespace(content="  " + VISION_TEXT + "  ")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = MistralClient(api_key="k", model="analysis-model")
    client._client = SimpleNamespace(chat=SimpleNamespace(complete=_complete))

    text = client.transcribe_image(b"\xff\xd8fake-jpeg", model="vision-model")

    assert text == VISION_TEXT
    assert calls["model"] == "vision-model" and calls["temperature"] == 0  # fidélité : pas de créativité
    parts = calls["messages"][0]["content"]
    assert parts[0]["type"] == "text" and "EXACTEMENT" in parts[0]["text"]
    assert parts[1]["image_url"].startswith("data:image/jpeg;base64,")
    assert base64.b64decode(parts[1]["image_url"].split(",", 1)[1]) == b"\xff\xd8fake-jpeg"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("```\nLe texte de la photo\n```", "Le texte de la photo"),
        ("```text\nLe texte de la photo\n```", "Le texte de la photo"),
        ("[aucun texte]", ""),
        ("  [Aucun texte].  ", ""),
        ("Texte normal", "Texte normal"),
    ],
)
def test_transcription_cleanup(raw, expected):
    assert mc._clean_transcription(raw) == expected


def test_fake_client_never_fabricates_a_transcription():
    with pytest.raises(OcrUnavailableError):
        FakeMistralClient().transcribe_image(b"jpeg")


# --- quota à 0 (offre) vs vrai rate limit (passager) -----------------------------------


def test_zero_quota_429_is_permanent_a_configuration_problem():
    exc = _ApiError(429, QUOTA_ZERO)
    assert is_quota_blocked(exc)
    assert not is_retryable_error(exc)  # attendre ne servirait à rien
    assert is_configuration_error(exc)
    assert "quota de 0" in describe_error(exc) and "MISTRAL_VISION_MODEL" in describe_error(exc)


def test_regular_429_stays_transient():
    exc = _ApiError(429, QUOTA_OK)
    assert not is_quota_blocked(exc)
    assert is_retryable_error(exc) and not is_configuration_error(exc)


def test_backoff_does_not_waste_time_retrying_a_zero_quota(monkeypatch):
    sleeps, calls = [], {"n": 0}
    monkeypatch.setattr(mc.time, "sleep", sleeps.append)

    def _complete(**kwargs):
        calls["n"] += 1
        raise _ApiError(429, QUOTA_ZERO)

    client = MistralClient(api_key="k", model="m")
    client._client = SimpleNamespace(chat=SimpleNamespace(complete=_complete))

    with pytest.raises(_ApiError):
        client.complete_json(system_prompt="", user_prompt="")

    assert calls["n"] == 1 and sleeps == []


# --- réponses IA mal formatées ---------------------------------------------------------


def test_schemas_accept_the_shapes_small_models_actually_return():
    assert ChunkSummaryResult.model_validate({"summary": ["Phrase un.", "Phrase deux."]}).summary == "Phrase un. Phrase deux."
    as_object = ChunkSummaryResult.model_validate({"summary": {"faits": "Une loi.", "sources": ["A", "B"]}}).summary
    assert "faits : Une loi." in as_object and "sources : A B" in as_object
    item = HighlightItem.model_validate(
        {"category_name": "Intox", "excerpt": "x", "explanation": ["a", "b"], "confidence": "80%"}
    )
    assert item.explanation == "a b" and item.confidence == 0.8
    assert HighlightItem.model_validate({"category_name": "c", "excerpt": "x", "confidence": "n/a"}).confidence is None
    assert len(HighlightDetectionResult.model_validate({"highlights": {"category_name": "c", "excerpt": "x"}}).highlights) == 1
    md = ReviewDraftResult.model_validate({"summary_markdown": ["# Titre", "Corps"]}).summary_markdown
    assert md == "# Titre\n\nCorps"


def test_empty_values_are_still_rejected():
    for bad in ({"summary": ""}, {"summary": []}, {}):
        with pytest.raises(ValidationError):
            ChunkSummaryResult.model_validate(bad)


class _ScriptedClient:
    def __init__(self, *responses):
        self.responses, self.prompts = list(responses), []

    def complete_json(self, *, system_prompt, user_prompt, response_hint=None, **kwargs):
        self.prompts.append(user_prompt)
        return self.responses.pop(0)


def test_structured_call_retries_once_with_a_corrective_prompt():
    client = _ScriptedClient({"summary": ""}, {"summary": "Un résumé correct."})

    result = complete_structured(
        client, schema=ChunkSummaryResult, system_prompt="s", user_prompt="Résume ceci", response_hint="chunk_summary"
    )

    assert result.summary == "Un résumé correct." and len(client.prompts) == 2
    assert "ATTENTION" in client.prompts[1] and "Résume ceci" in client.prompts[1]


def test_structured_call_gives_up_after_one_corrective_retry():
    client = _ScriptedClient({"summary": ""}, {"nope": 1})
    with pytest.raises(ValidationError):
        complete_structured(client, schema=ChunkSummaryResult, system_prompt="s", user_prompt="u")
    assert len(client.prompts) == 2
    assert "format inattendu" in describe_error(ValidationError.from_exception_data("x", []))


# --- intégration pipeline : photos lues par Mistral -----------------------------------


@pytest.mark.django_db
def test_pipeline_reads_photos_with_mistral_vision(organization, user, settings, monkeypatch):
    DetectionCategoryFactory(organization=None, is_active=True)
    stub = _StubVisionClient()
    _use_mistral_ocr(settings, monkeypatch, stub)
    job = _image_job(organization, user, "p1.png", "p2.png")

    run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.REVIEW_READY
    assert len(stub.received) == 2  # une lecture par photo
    for doc in job.documents.all():  # la SORTIE est vérifiée, pas seulement le statut
        assert doc.extracted_text == VISION_TEXT and doc.requires_ocr is True


@pytest.mark.django_db
def test_zero_quota_on_the_vision_model_fails_the_job_without_blaming_the_photos(
    organization, user, settings, monkeypatch
):
    _use_mistral_ocr(settings, monkeypatch, _StubVisionClient(error=_ApiError(429, QUOTA_ZERO)))
    job = _image_job(organization, user, "p1.png")

    with pytest.raises(Exception):
        run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.FAILED
    assert "quota de 0" in job.error_message
    assert job.documents.get().extraction_status == "pending"  # ce n'est pas la faute de la photo


@pytest.mark.django_db
def test_transient_error_while_reading_a_photo_is_not_reported_as_an_unreadable_file(
    organization, user, settings, monkeypatch
):
    _use_mistral_ocr(settings, monkeypatch, _StubVisionClient(error=_ApiError(429, QUOTA_OK)))
    job = _image_job(organization, user, "p1.png")

    with pytest.raises(Exception):  # mode eager : pas de relance différée, échec immédiat et clair
        run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.FAILED and "Limite de débit" in job.error_message
    assert job.documents.get().extraction_status == "pending"


@pytest.mark.django_db
def test_bad_request_on_one_photo_only_flags_that_photo(organization, user, settings, monkeypatch):
    DetectionCategoryFactory(organization=None, is_active=True)
    stub = _StubVisionClient()
    _use_mistral_ocr(settings, monkeypatch, stub)
    job = _image_job(organization, user, "ok.png")
    SourceDocument.objects.create(  # fichier corrompu : PIL ne sait pas l'ouvrir
        organization=organization, job=job, uploaded_by=user,
        file=SimpleUploadedFile("cassee.png", b"pas une image", content_type="image/png"),
        original_filename="cassee.png", kind=SourceDocument.Kind.IMAGE,
    )

    run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.REVIEW_READY
    statuses = {d.original_filename: d.extraction_status for d in job.documents.all()}
    assert statuses == {"ok.png": "done", "cassee.png": "failed"}
    assert len(stub.received) == 1  # la photo cassée n'a même pas été envoyée à l'API


@pytest.mark.django_db
def test_documents_already_read_are_not_read_again_on_a_rerun(organization, user, monkeypatch):
    """Une relance (erreur transitoire ou « Réessayer ») ne doit pas repayer l'OCR des
    documents déjà lus : chaque lecture par l'API est facturée et limitée."""
    DetectionCategoryFactory(organization=None, is_active=True)
    calls = {"n": 0}

    def _ocr(*args, **kwargs):
        calls["n"] += 1
        return "Texte relu pour la deuxieme photo du lot."

    monkeypatch.setattr(pytesseract, "image_to_string", _ocr)
    job = _image_job(organization, user, "deja_lue.png", "a_lire.png")
    done = job.documents.get(original_filename="deja_lue.png")
    done.extraction_status, done.extracted_text = "done", "Texte deja lu lors de la tentative precedente."
    done.save()

    run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.REVIEW_READY
    assert calls["n"] == 1  # seule la photo restante a été lue
    assert job.documents.get(original_filename="deja_lue.png").extracted_text.startswith("Texte deja lu")


def test_schemas_accept_a_bare_value_at_the_json_root():
    """Constaté en réel avec ministral-8b : `[{"category_name": ...}]` à la racine au lieu de
    `{"highlights": [...]}`, y compris à la relance corrective -> tout le job échouait."""
    bare_list = [{"category_name": "Risque juridique", "excerpt": "fausses informations", "confidence": 0.85}]
    result = HighlightDetectionResult.model_validate(bare_list)
    assert [h.category_name for h in result.highlights] == ["Risque juridique"]
    assert result.highlights[0].confidence == 0.85

    renamed = {"points_saillants": [{"category_name": "Intox potentielle", "excerpt": "rumeur"}]}
    assert len(HighlightDetectionResult.model_validate(renamed).highlights) == 1

    assert HighlightDetectionResult.model_validate([]).highlights == []
    assert ChunkSummaryResult.model_validate(["Phrase un.", "Phrase deux."]).summary == "Phrase un. Phrase deux."
    assert ReviewDraftResult.model_validate("# Revue\n\nCorps").summary_markdown.startswith("# Revue")


def test_schemas_accept_the_object_wrapped_in_a_list():
    """Réponse réelle de ministral-8b au prompt de détection : `[{"highlights": [...]}]`."""
    wrapped = [{"highlights": [
        {"category_name": "Risque juridique", "excerpt": "peines alourdies", "explanation": "e", "confidence": 0.8},
        {"category_name": "Intox potentielle", "excerpt": "rumeur de fraude", "explanation": "e", "confidence": 0.9},
    ]}]
    result = HighlightDetectionResult.model_validate(wrapped)
    assert [h.category_name for h in result.highlights] == ["Risque juridique", "Intox potentielle"]

    two_wrappers = [{"highlights": [{"category_name": "a", "excerpt": "x"}]}, {"highlights": [{"category_name": "b", "excerpt": "y"}]}]
    assert len(HighlightDetectionResult.model_validate(two_wrappers).highlights) == 2

    assert ChunkSummaryResult.model_validate([{"summary": "Un résumé."}]).summary == "Un résumé."
    assert ReviewDraftResult.model_validate([{"summary_markdown": "# T"}]).summary_markdown == "# T"
