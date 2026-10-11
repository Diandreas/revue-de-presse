"""Moteurs de lecture (OCR) des photos et des PDF scannés.

Deux moteurs interchangeables, choisis par `settings.OCR_ENGINE` :

- **mistral** : un modèle de vision de Mistral lit l'image côté serveur (appel API). Aucune
  dépendance système à installer (ni Tesseract, ni ses données de langue), et une bien
  meilleure lecture des photos de journaux (rotation, flou, colonnes) — mesuré à 99,5–100 %
  de fidélité sur une photo tournée et floutée. Les images sont envoyées à Mistral, le même
  prestataire que l'analyse du texte : pas de nouveau tiers.
- **tesseract** : OCR local (binaire Tesseract + données `fra`). Fonctionne hors ligne mais
  lit nettement moins bien les photos.
- **auto** (défaut) : `mistral` si `MISTRAL_API_KEY` est renseignée, sinon `tesseract`.

Contrat commun : `engine.read_image(pil_image) -> str` (texte, "" si rien de lisible). Une
panne de configuration (moteur absent, clé refusée…) lève `OcrUnavailableError` ou une
erreur d'API : elle n'est JAMAIS convertie en texte vide.
"""
import io
import logging

import pytesseract
from django.conf import settings
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFInfoNotInstalledError
from PIL import ImageOps

from .errors import OcrUnavailableError
from .mistral_client import get_mistral_client

logger = logging.getLogger(__name__)

TESSERACT_LANGUAGES = "fra"
MAX_TESSERACT_EDGE = 3000  # px : au-delà, Tesseract est lent sans gain de qualité
MAX_VISION_EDGE = 2000  # px : suffisant pour un journal, limite le poids envoyé et le coût
VISION_JPEG_QUALITY = 85
PDF_RENDER_DPI = 200  # défaut de pdf2image : lisible pour l'OCR, ~12 Mo par page A4 en mémoire

# Messages Tesseract signalant un problème d'installation (données de langue absentes)
# et non un problème propre à l'image traitée.
_TESSERACT_SETUP_MARKERS = ("Failed loading language", "Error opening data file", "Could not initialize tesseract")


def _limit_edge(image, max_edge):
    longest = max(image.size)
    if longest <= max_edge:
        return image
    scale = max_edge / longest
    return image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))))


class TesseractEngine:
    name = "tesseract"

    def read_image(self, image):
        prepared = ImageOps.autocontrast(_limit_edge(image.convert("L"), MAX_TESSERACT_EDGE))
        try:
            return pytesseract.image_to_string(prepared, lang=TESSERACT_LANGUAGES)
        except pytesseract.TesseractNotFoundError as exc:
            raise OcrUnavailableError("Tesseract n'est pas installé ou introuvable dans le PATH.") from exc
        except pytesseract.TesseractError as exc:
            if any(marker in str(exc) for marker in _TESSERACT_SETUP_MARKERS):
                raise OcrUnavailableError(
                    f"Données de langue OCR « {TESSERACT_LANGUAGES} » manquantes : {exc}"
                ) from exc
            raise


class MistralVisionEngine:
    name = "mistral-vision"

    def read_image(self, image):
        buffer = io.BytesIO()
        _limit_edge(image.convert("RGB"), MAX_VISION_EDGE).save(buffer, format="JPEG", quality=VISION_JPEG_QUALITY)
        # Les erreurs d'API (429/5xx = transitoires, 401/403/quota 0 = configuration) sont
        # laissées remonter telles quelles : tasks.py sait les traiter différemment.
        return get_mistral_client().transcribe_image(buffer.getvalue())


def get_ocr_engine():
    choice = (getattr(settings, "OCR_ENGINE", "auto") or "auto").strip().lower()
    if choice == "auto":
        choice = "mistral" if settings.MISTRAL_API_KEY else "tesseract"
    if choice == "mistral":
        if not settings.MISTRAL_API_KEY:
            raise OcrUnavailableError(
                "OCR_ENGINE=mistral mais MISTRAL_API_KEY est vide.",
                user_message=(
                    "La lecture des photos par l'IA n'est pas configurée sur le serveur (clé Mistral "
                    "manquante). Contactez l'administrateur de la plateforme."
                ),
            )
        return MistralVisionEngine()
    if choice == "tesseract":
        return TesseractEngine()
    raise OcrUnavailableError(f"OCR_ENGINE inconnu : « {choice} » (valeurs : auto, mistral, tesseract).")


def iter_pdf_page_images(file_path, *, page_count, first_page=1, dpi=PDF_RENDER_DPI):
    """Pages d'un PDF scanné rendues en images UNE PAR UNE (nécessite Poppler) : une seule
    page en mémoire à la fois. Convertir tout le PDF d'un coup (ancienne version) chargeait
    toutes les pages — plusieurs Go pour un PDF de quelques centaines de pages, sur un VPS
    partagé. Produit (numéro de page, image) ; l'image est fermée après usage."""
    for number in range(first_page, page_count + 1):
        try:
            images = convert_from_path(file_path, dpi=dpi, first_page=number, last_page=number)
        except PDFInfoNotInstalledError as exc:
            raise OcrUnavailableError("Poppler (pdftoppm) n'est pas installé ou introuvable dans le PATH.") from exc
        for image in images:
            try:
                yield number, image
            finally:
                image.close()
