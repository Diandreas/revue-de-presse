"""Une revue de 27 photos échouait entièrement (3 fois de suite) parce que le modèle avait
renvoyé UN point clé à l'extrait vide : les points clés sont une annexe, un élément ou un
extrait illisible ne doit pas faire perdre toute la revue."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.ai_pipeline import tasks as pipeline_tasks
from apps.ai_pipeline.mistral_client import FakeMistralClient
from apps.ai_pipeline.prompts import unwrap_source
from apps.ai_pipeline.schemas import HighlightDetectionResult
from apps.ai_pipeline.tasks import run_press_review_pipeline
from apps.press_review.models import DetectionCategory, PipelineStepRun, PressReviewJob, SourceDocument
from tests.pdf_fixtures import make_minimal_pdf_bytes


def test_items_without_excerpt_are_dropped_instead_of_rejecting_the_answer():
    result = HighlightDetectionResult.model_validate({"highlights": [
        {"category_name": "Intox potentielle", "excerpt": "une rumeur", "explanation": "e"},
        {"category_name": "Point important", "excerpt": "", "explanation": "rien"},  # constaté en réel
        {"category_name": "Point important", "excerpt": None},
        {"category_name": "Point important", "excerpt": "   "},
    ]})

    assert [h.excerpt for h in result.highlights] == ["une rumeur"]


def _job_with_documents(organization, user, count):
    job = PressReviewJob.objects.create(organization=organization, created_by=user)
    for index in range(count):
        SourceDocument.objects.create(
            organization=organization, job=job, uploaded_by=user, position=index,
            file=SimpleUploadedFile(
                f"{index}.pdf", make_minimal_pdf_bytes([f"Article {index} avec suffisamment de texte reel."]),
                content_type="application/pdf",
            ),
            original_filename=f"{index}.pdf", kind="pdf",
        )
    return job


class _OneUnreadableChunkClient(FakeMistralClient):
    """Le 2e extrait renvoie deux fois une réponse inexploitable (avant et après relance).
    Les autres citent leur extrait tel quel (les citations sont vérifiées dans le texte)."""

    def __init__(self):
        self.calls = 0

    def complete_json(self, **kwargs):
        if kwargs.get("response_hint") == "highlight_detection":
            self.calls += 1
            if self.calls in (2, 3):
                return {"highlights": "Aucun point clé."}  # texte au lieu d'une liste
            excerpt = unwrap_source(kwargs["user_prompt"])
            return {"highlights": [{"category_name": "Intox potentielle", "excerpt": excerpt}]}
        return super().complete_json(**kwargs)


@pytest.mark.django_db
def test_one_unreadable_chunk_does_not_fail_the_whole_review(organization, user, monkeypatch):
    DetectionCategory.objects.create(name="Intox potentielle", type="intox", is_active=True)
    client = _OneUnreadableChunkClient()
    monkeypatch.setattr(pipeline_tasks, "get_mistral_client", lambda: client)
    job = _job_with_documents(organization, user, 3)

    run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.REVIEW_READY, job.error_message
    assert job.highlights.count() == 2
    step = PipelineStepRun.objects.get(job=job, step_name=PipelineStepRun.StepName.HIGHLIGHT_DETECTION)
    assert step.result_summary["unreadable_chunks"] == 1


class _AlwaysUnreadableClient(FakeMistralClient):
    def complete_json(self, **kwargs):
        if kwargs.get("response_hint") == "highlight_detection":
            return {"highlights": "Aucun point clé."}
        return super().complete_json(**kwargs)


@pytest.mark.django_db
def test_review_still_fails_clearly_when_no_chunk_can_be_read(organization, user, monkeypatch):
    DetectionCategory.objects.create(name="Intox potentielle", type="intox", is_active=True)
    monkeypatch.setattr(pipeline_tasks, "get_mistral_client", lambda: _AlwaysUnreadableClient())
    job = _job_with_documents(organization, user, 2)

    with pytest.raises(Exception):
        run_press_review_pipeline(str(job.id))

    job.refresh_from_db()
    assert job.status == PressReviewJob.Status.FAILED
    assert "format inattendu" in job.error_message
