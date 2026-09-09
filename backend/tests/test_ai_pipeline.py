from django.conf import settings
from django.test import override_settings

from apps.ai_pipeline.chunking import chunk_document_text
from apps.ai_pipeline.extraction import _needs_ocr
from apps.ai_pipeline.mistral_client import FakeMistralClient, MistralClient, get_mistral_client


def test_test_settings_never_hold_real_external_credentials():
    """Garde-fou : la suite de tests ne doit jamais appeler une vraie API externe
    payante (Mistral, Stripe, CamPay), même si le .env partagé à la racine (utilisé
    aussi par le serveur de dev) contient de vraies clés — cf. config/settings/test.py.
    Sans ce garde-fou, une clé Mistral réelle dans .env rend `pytest` flaky (rate
    limiting) et consomme du quota facturé à chaque run."""
    assert settings.MISTRAL_API_KEY == ""
    assert settings.STRIPE_SECRET_KEY == ""
    assert settings.CAMPAY_APP_USERNAME == ""


def test_needs_ocr_true_for_empty_pages():
    assert _needs_ocr(["", "", ""]) is True


def test_needs_ocr_true_for_no_pages():
    assert _needs_ocr([]) is True


def test_needs_ocr_false_for_dense_native_text():
    dense_page = "Ceci est un article de presse camerounais avec suffisamment de texte natif. " * 3
    assert _needs_ocr([dense_page, dense_page]) is False


def test_chunk_document_text_handles_empty_string():
    assert chunk_document_text("") == []
    assert chunk_document_text("   ") == []


def test_chunk_document_text_splits_on_size_and_tracks_pages():
    text = "\f".join(["a" * 100] * 5)  # 5 "pages"
    chunks = chunk_document_text(text, target_chars=250)

    assert len(chunks) >= 2
    assert chunks[0].page_start == 1
    assert chunks[-1].page_end == 5
    # Chaque page ne doit apparaître que dans un seul chunk (pas de chevauchement).
    covered_pages = [p for c in chunks for p in range(c.page_start, c.page_end + 1)]
    assert covered_pages == sorted(covered_pages)
    assert len(covered_pages) == len(set(covered_pages))


@override_settings(MISTRAL_API_KEY="")
def test_get_mistral_client_returns_fake_when_key_blank():
    assert isinstance(get_mistral_client(), FakeMistralClient)


@override_settings(MISTRAL_API_KEY="sk-real-key")
def test_get_mistral_client_returns_real_client_when_key_present():
    assert type(get_mistral_client()) is MistralClient


def test_fake_mistral_client_highlight_detection_shape():
    result = FakeMistralClient().complete_json(system_prompt="", user_prompt="", response_hint="highlight_detection")
    assert "highlights" in result
    assert result["highlights"][0]["category_name"] == "Point important"


def test_fake_mistral_client_review_drafting_shape():
    result = FakeMistralClient().complete_json(system_prompt="", user_prompt="", response_hint="review_drafting")
    assert "summary_markdown" in result
    assert "MOCK" in result["summary_markdown"]
