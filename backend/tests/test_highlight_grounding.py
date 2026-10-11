"""Points clés vérifiés avant d'arriver dans la revue : une citation inventée, paraphrasée,
réduite au nom du journal ou jugée peu sûre par le modèle ne doit jamais être livrée."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.ai_pipeline import tasks as pipeline_tasks
from apps.ai_pipeline.grounding import (
    REJECT_LOW_CONFIDENCE,
    REJECT_NEWSPAPER_NAME,
    REJECT_NOT_FOUND,
    REJECT_TOO_SHORT,
    check_highlight,
    excerpt_similarity,
    is_newspaper_name,
)
from apps.ai_pipeline.mistral_client import FakeMistralClient, MistralClient
from apps.ai_pipeline.tasks import run_press_review_pipeline
from apps.press_review.models import DetectionCategory, PipelineStepRun, PressReviewJob, SourceDocument
from tests.pdf_fixtures import make_minimal_pdf_bytes

# Texte tel que lu sur une photo : lettres mal lues (rn -> m), accents perdus, césure, [illisible].
OCR_TEXT = (
    "Le rninistre de la Cornmunication a annonce hier que le gouverne-\nment allait poursuivre "
    "les auteurs de fausses inforrnations [illisible] diffusées sur les reseaux sociaux. "
    "Selon nos sources, le directeur general de la societe aurait detourne pres de 2 milliards FCFA."
)


@pytest.mark.parametrize(
    "excerpt",
    [
        "Le ministre de la Communication a annoncé hier que le gouvernement allait poursuivre",  # OCR corrigé
        "les auteurs de fausses informations diffusées sur les réseaux sociaux",  # sans [illisible]
        "aurait détourné près de 2 milliards FCFA",  # accents rétablis
        "Le ministre de la Communication a annoncé … les auteurs de fausses informations",  # coupure
    ],
)
def test_a_real_quote_is_found_despite_ocr_noise(excerpt):
    assert excerpt_similarity(excerpt, OCR_TEXT) >= 0.88


@pytest.mark.parametrize(
    "excerpt",
    [
        "Le ministre de la Communication a déclaré hier que l'Etat allait poursuivre",  # paraphrase
        "le directeur général aurait volé près de 2 milliards FCFA",  # paraphrase
        "aurait détourné près de 5 milliards FCFA",  # chiffre inventé : rejeté d'office
        "Le Premier ministre a démissionné ce matin",  # inventé
        "Le ministre de la Communication a annoncé … la démission immédiate du Premier ministre",
    ],
)
def test_an_invented_or_paraphrased_quote_is_not_found(excerpt):
    assert excerpt_similarity(excerpt, OCR_TEXT) < 0.88


@pytest.mark.parametrize(
    "excerpt, expected",
    [
        ("CAMEROON TRIBUNE", True),
        ("Cameroun Tribune", True),
        ("LE JOUR N° 3456 du lundi 10 octobre 2026", True),
        ("Quotidien Mutations N° 5012", True),
        ("Le Messager accuse le ministre de fraude", False),
        ("Le gouvernement annonce une nouvelle loi", False),
    ],
)
def test_a_newspaper_masthead_is_not_a_key_point(excerpt, expected):
    assert is_newspaper_name(excerpt) is expected


def test_check_highlight_reasons():
    def check(excerpt, confidence=0.9):
        return check_highlight(excerpt=excerpt, confidence=confidence, source_text=OCR_TEXT)

    assert check("aurait détourné près de 2 milliards FCFA") is None
    assert check("2 milliards") == REJECT_TOO_SHORT
    assert check("CAMEROON TRIBUNE N° 12345") == REJECT_NEWSPAPER_NAME
    assert check("aurait détourné près de 2 milliards FCFA", confidence=0.3) == REJECT_LOW_CONFIDENCE
    # Confiance non fournie : on ne peut pas en juger, la vérification dans le texte suffit.
    assert check("aurait détourné près de 2 milliards FCFA", confidence=None) is None
    assert check("Le Premier ministre a démissionné ce matin") == REJECT_NOT_FOUND


@override_settings(HIGHLIGHT_MIN_CONFIDENCE=0.95, HIGHLIGHT_MIN_EXCERPT_WORDS=10)
def test_thresholds_are_configurable():
    assert check_highlight(excerpt="aurait détourné près de 2 milliards FCFA", confidence=0.9, source_text=OCR_TEXT) == (
        REJECT_TOO_SHORT
    )
    long_quote = "Le ministre de la Communication a annoncé hier que le gouvernement allait poursuivre"
    assert check_highlight(excerpt=long_quote, confidence=0.9, source_text=OCR_TEXT) == REJECT_LOW_CONFIDENCE


# --------------------------------------------------------------------------- pipeline

ARTICLE = [
    "Le ministre de la Communication a annonce hier des poursuites",
    "contre les auteurs de fausses informations sur les reseaux sociaux.",
    "La societe aurait detourne pres de 2 milliards FCFA selon nos sources.",
]


class _MixedQualityClient(FakeMistralClient):
    """Réponse réaliste : une bonne citation, et tout ce qu'un petit modèle renvoie aussi."""

    def complete_json(self, **kwargs):
        if kwargs.get("response_hint") == "highlight_detection":
            return {"highlights": [
                {"category_name": "Risque juridique", "excerpt": "La société aurait détourné près de 2 milliards FCFA",
                 "explanation": "Accusation de détournement", "confidence": 0.9},
                {"category_name": "Risque juridique", "excerpt": "La société aurait détourné près de 2 milliards FCFA",
                 "explanation": "Doublon", "confidence": 0.9},
                {"category_name": "Intox potentielle", "excerpt": "Le ministre a promis de fermer tous les journaux",
                 "explanation": "Inventé", "confidence": 0.95},
                {"category_name": "Point important", "excerpt": "CAMEROON TRIBUNE N° 12345 du lundi 10 octobre",
                 "confidence": 0.9},
                {"category_name": "Point important", "excerpt": "fausses informations", "confidence": 0.9},
                {"category_name": "Point important", "excerpt": "des poursuites contre les auteurs de fausses informations",
                 "explanation": "Peu sûr", "confidence": 0.2},
            ]}
        return super().complete_json(**kwargs)


def _job(organization, user):
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    SourceDocument.objects.create(
        organization=organization, job=job, uploaded_by=user, original_filename="une.pdf", kind="pdf",
        file=SimpleUploadedFile("une.pdf", make_minimal_pdf_bytes(ARTICLE), content_type="application/pdf"),
    )
    return job


def _categories():
    for name, kind in (("Risque juridique", "legal_risk"), ("Intox potentielle", "intox"), ("Point important", "important_point")):
        DetectionCategory.objects.create(name=name, type=kind, is_active=True)


@pytest.mark.django_db
def test_only_grounded_confident_key_points_are_saved_and_the_rest_is_traced(organization, user, monkeypatch):
    _categories()
    monkeypatch.setattr(pipeline_tasks, "get_mistral_client", lambda: _MixedQualityClient())
    job = _job(organization, user)

    run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.REVIEW_READY, job.error_message
    assert list(job.highlights.values_list("excerpt", flat=True)) == ["La société aurait détourné près de 2 milliards FCFA"]
    step = PipelineStepRun.objects.get(job=job, step_name=PipelineStepRun.StepName.HIGHLIGHT_DETECTION)
    assert step.result_summary["discarded_highlights"] == {
        "duplicate": 1, "not_found": 1, "newspaper_name": 1, "too_short": 1, "low_confidence": 1,
    }


@pytest.mark.django_db
def test_the_default_fake_client_cites_the_document_so_its_key_point_survives(organization, user):
    """Démo sans clé : l'extrait factice cite le texte réel, il n'est donc pas écarté."""
    DetectionCategory.objects.create(name="Point important", type="important_point", is_active=True)
    job = _job(organization, user)

    run_press_review_pipeline(str(job.id))

    highlight = job.highlights.get()
    assert highlight.excerpt.startswith("Le ministre de la Communication")
    assert "[MOCK]" in highlight.explanation


@pytest.mark.django_db
@override_settings(MISTRAL_API_KEY="sk-test", MISTRAL_MODEL="petit-modele", MISTRAL_HIGHLIGHT_MODEL="modele-fidele")
def test_highlight_detection_uses_the_faithful_model_at_temperature_zero(organization, user, monkeypatch):
    calls = []

    def fake_complete_json(self, *, system_prompt, user_prompt, response_hint=None, temperature=0.2):
        calls.append((response_hint, self.model, temperature))
        return FakeMistralClient().complete_json(
            system_prompt=system_prompt, user_prompt=user_prompt, response_hint=response_hint
        )

    monkeypatch.setattr(MistralClient, "complete_json", fake_complete_json)
    DetectionCategory.objects.create(name="Point important", type="important_point", is_active=True)
    job = _job(organization, user)

    run_press_review_pipeline(str(job.id))

    assert ("highlight_detection", "modele-fidele", 0.0) in calls
    assert ("chunk_summary", "petit-modele", 0.2) in calls
