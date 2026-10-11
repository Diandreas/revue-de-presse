"""Le modèle écrit parfois le nom de catégorie de travers ; ces points saillants ne doivent
pas être jetés en silence (revue « réussie » mais passages sensibles manquants)."""
from types import SimpleNamespace as Cat

import pytest

from apps.ai_pipeline import tasks as pipeline_tasks
from apps.ai_pipeline.matching import match_category
from apps.ai_pipeline.mistral_client import FakeMistralClient
from apps.ai_pipeline.tasks import run_press_review_pipeline
from apps.press_review.models import DetectionCategory, PipelineStepRun, PressReviewJob, SourceDocument
from django.core.files.uploadedfile import SimpleUploadedFile
from tests.pdf_fixtures import make_minimal_pdf_bytes

CATEGORIES = [
    Cat(name="Risque juridique", type="legal_risk"),
    Cat(name="Point important", type="important_point"),
    Cat(name="Intox potentielle", type="intox"),
    Cat(name="Annonce concurrent", type="custom"),
]


@pytest.mark.parametrize(
    "written_by_the_model, expected",
    [
        ("Intox potentielle", "Intox potentielle"),  # exact
        ("intox potentielle", "Intox potentielle"),  # casse
        ("INTOX POTENTIELLE", "Intox potentielle"),
        ("risque_juridique", "Risque juridique"),  # snake_case (constaté en réel)
        ("Risque-juridique", "Risque juridique"),
        ("Risque juridiqué", "Risque juridique"),  # accent parasite
        ("into_x_potentielle", "Intox potentielle"),  # lettres mangées (constaté en réel)
        ("legal_risk", "Risque juridique"),  # le prompt affiche « type: legal_risk »
        ("intox", "Intox potentielle"),
        ("important_point", "Point important"),
        ("  Point   important ", "Point important"),
    ],
)
def test_match_category_tolerates_what_the_model_actually_writes(written_by_the_model, expected):
    assert match_category(written_by_the_model, CATEGORIES).name == expected


@pytest.mark.parametrize("nonsense", ["", None, "Catégorie totalement inventée", "Sport", "zzz"])
def test_match_category_does_not_classify_at_random(nonsense):
    assert match_category(nonsense, CATEGORIES) is None


def test_similar_but_different_categories_are_not_confused():
    assert match_category("Point important", CATEGORIES).name == "Point important"
    assert match_category("Annonce concurrent", CATEGORIES).name == "Annonce concurrent"
    assert match_category("Annonce concurrente", CATEGORIES).name == "Annonce concurrent"  # accord fautif


class _MangledNamesClient(FakeMistralClient):
    def complete_json(self, **kwargs):
        if kwargs.get("response_hint") == "highlight_detection":
            return {"highlights": [
                {"category_name": "into_x_potentielle", "excerpt": "une rumeur sans fondement", "explanation": "e"},
                {"category_name": "legal_risk", "excerpt": "propos diffamatoires visant le directeur", "explanation": "e"},
                {"category_name": "Catégorie inventée", "excerpt": "autre chose", "explanation": "e"},
            ]}
        return super().complete_json(**kwargs)


# Les citations sont vérifiées dans le texte source (grounding.py) : il doit les contenir.
ARTICLE_LINES = [
    "Un article de presse avec suffisamment de texte reel.",
    "Il relaie une rumeur sans fondement et des",
    "propos diffamatoires visant le directeur.",
]


@pytest.mark.django_db
def test_highlights_with_mangled_category_names_are_kept_and_the_rest_is_traced(organization, user, monkeypatch):
    DetectionCategory.objects.create(name="Intox potentielle", type="intox", is_active=True)
    DetectionCategory.objects.create(name="Risque juridique", type="legal_risk", is_active=True)
    monkeypatch.setattr(pipeline_tasks, "get_mistral_client", lambda: _MangledNamesClient())
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    SourceDocument.objects.create(
        organization=organization, job=job, uploaded_by=user,
        file=SimpleUploadedFile("a.pdf", make_minimal_pdf_bytes(ARTICLE_LINES), content_type="application/pdf"),
        original_filename="a.pdf", kind="pdf",
    )

    run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.REVIEW_READY
    kept = {h.category.name: h.excerpt for h in job.highlights.select_related("category")}
    assert kept == {
        "Intox potentielle": "une rumeur sans fondement",
        "Risque juridique": "propos diffamatoires visant le directeur",
    }
    step = PipelineStepRun.objects.get(job=job, step_name=PipelineStepRun.StepName.HIGHLIGHT_DETECTION)
    assert step.result_summary["unmatched_categories"] == ["Catégorie inventée"]  # tracé, pas jeté en silence
