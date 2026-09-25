"""Extraction du texte des documents téléversés.

- PDF : texte natif d'abord (pdfplumber, rapide, gratuit et exact pour les PDF numériques) ;
  si le résultat est trop pauvre (coupure de presse scannée), chaque page est lue par le
  moteur d'OCR configuré (voir `ocr.py`).
- Image / photo (coupure de presse photographiée au téléphone) : lue directement par le
  moteur d'OCR configuré, après correction de l'orientation EXIF.
"""
import logging

import pdfplumber
from PIL import Image, ImageOps

from .errors import is_configuration_error, is_retryable_error
from .ocr import get_ocr_engine, pdf_pages_as_images

logger = logging.getLogger(__name__)

# Photos iPhone (.heic/.heif) : enregistre le décodeur si pillow-heif est installé.
try:  # pragma: no cover - dépend de l'environnement
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:  # noqa: BLE001
    logger.info("pillow-heif indisponible : les photos HEIC/HEIF ne pourront pas être analysées.")

MIN_CHARS_PER_PAGE_THRESHOLD = 20


def extract_text_from_pdf(file_path):
    """Retourne (text, page_count, requires_ocr). `text` concatène les pages avec un
    saut de page (\\f) pour permettre à chunking.py d'aligner les chunks sur les pages."""
    pages_text = _extract_digital_text(file_path)
    page_count = len(pages_text)

    if _needs_ocr(pages_text):
        logger.info("Texte natif insuffisant pour %s, bascule sur l'OCR.", file_path)
        pages_text = _ocr_pdf(file_path)
        requires_ocr = True
    else:
        requires_ocr = False

    return "\f".join(pages_text), page_count, requires_ocr


def extract_text_from_image(file_path):
    """Lecture d'une photo / d'un scan. Même contrat que extract_text_from_pdf :
    retourne (text, page_count=1, requires_ocr=True)."""
    engine = get_ocr_engine()
    with Image.open(file_path) as img:
        oriented = ImageOps.exif_transpose(img)  # respecte l'orientation des photos de téléphone
        text = engine.read_image(oriented)
    return text, 1, True


def _extract_digital_text(file_path):
    with pdfplumber.open(file_path) as pdf:
        return [(page.extract_text() or "") for page in pdf.pages]


def _needs_ocr(pages_text):
    if not pages_text:
        return True
    avg_chars = sum(len(p) for p in pages_text) / len(pages_text)
    return avg_chars < MIN_CHARS_PER_PAGE_THRESHOLD


def _ocr_pdf(file_path):
    engine = get_ocr_engine()
    texts = []
    for page_image in pdf_pages_as_images(file_path):
        try:
            texts.append(engine.read_image(page_image))
        except Exception as exc:
            # Panne de configuration ou erreur transitoire : ce n'est pas une page « vide »,
            # on remonte pour que la tâche échoue clairement / soit relancée plus tard.
            if is_configuration_error(exc) or is_retryable_error(exc):
                raise
            logger.exception("Échec OCR sur une page de %s", file_path)
            texts.append("")
    return texts
