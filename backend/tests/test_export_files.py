"""Exports réellement générés (et pas seulement leur HTML) : l'export PDF a déjà cassé en
production (WeasyPrint + pydyf) sans qu'aucun test ne produise un vrai fichier.

WeasyPrint exige des bibliothèques système (Pango) absentes de certains postes Windows :
le test PDF est alors ignoré en local, mais la CI (REQUIRE_WEASYPRINT=1) le rend obligatoire."""
import os

import pytest
from django.utils import timezone

from apps.ai_pipeline.export import get_or_render_export
from apps.press_review.models import GeneratedReview, Highlight, PressReviewJob
from tests.factories import DetectionCategoryFactory, OrganizationFactory


def _require_weasyprint():
    try:
        import weasyprint  # noqa: F401
    except Exception as exc:  # OSError quand les libs natives manquent
        if os.environ.get("REQUIRE_WEASYPRINT"):
            pytest.fail(f"WeasyPrint inutilisable alors que REQUIRE_WEASYPRINT est défini : {exc}")
        pytest.skip(f"WeasyPrint indisponible sur ce poste : {exc}")


@pytest.fixture
def review(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    organization = OrganizationFactory(name="Groupe Médias Douala")
    job = PressReviewJob.objects.create(organization=organization, title="Revue du lundi", status="REVIEW_READY")
    category = DetectionCategoryFactory(name="Risque juridique", color="#DC2626")
    Highlight.objects.create(job=job, category=category, excerpt="Le directeur est accusé sans preuve", order=0)
    return GeneratedReview.objects.create(
        job=job,
        summary_markdown="# Synthèse\n\nLe **gouvernement** annonce une réforme.",
        generated_at=timezone.now(),
    )


def test_pdf_export_produces_a_real_pdf_file(review):
    _require_weasyprint()

    file_field = get_or_render_export(review, fmt="pdf")

    with file_field.open("rb") as handle:
        content = handle.read()
    assert content.startswith(b"%PDF")
    assert len(content) > 1000


def test_docx_export_produces_a_real_word_file(review):
    file_field = get_or_render_export(review, fmt="docx")

    with file_field.open("rb") as handle:
        assert handle.read(2) == b"PK"  # conteneur ZIP Office Open XML
