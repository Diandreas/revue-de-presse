"""Extraction du texte des documents téléversés.

- PDF : texte natif d'abord (pdfplumber, rapide, gratuit et exact pour les PDF numériques) ;
  si le résultat est trop pauvre (coupure de presse scannée), chaque page est lue par le
  moteur d'OCR configuré (voir `ocr.py`), une page à la fois.
- Image / photo (coupure de presse photographiée au téléphone) : lue directement par le
  moteur d'OCR configuré, après correction de l'orientation EXIF.

Un PDF de plus de `AI_MAX_PDF_PAGES` pages est refusé (`DocumentRejectedError`) : le
document est marqué en échec avec un message clair, la revue continue avec les autres.
"""
import logging

import pdfplumber
from PIL import Image, ImageOps

from .errors import DocumentRejectedError, is_configuration_error, is_retryable_error
from .limits import max_pdf_pages, too_many_pages_message
from .ocr import get_ocr_engine, iter_pdf_page_images

logger = logging.getLogger(__name__)

# Photos iPhone (.heic/.heif) : enregistre le décodeur si pillow-heif est installé.
try:  # pragma: no cover - dépend de l'environnement
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:  # noqa: BLE001
    logger.info("pillow-heif indisponible : les photos HEIC/HEIF ne pourront pas être analysées.")

MIN_CHARS_PER_PAGE_THRESHOLD = 20
PAGE_SEPARATOR = "\f"


def extract_text_from_pdf(file_path, *, display_name=None, ocr_pages_done=(), on_ocr_page=None):
    """Retourne (text, page_count, requires_ocr). `text` concatène les pages avec un
    saut de page (\\f) pour permettre à chunking.py d'aligner les chunks sur les pages.

    OCR d'un PDF scanné, page par page :
    - `ocr_pages_done` : textes des premières pages déjà lues lors d'une tentative
      interrompue (rate limit à la page 30 sur 50) — elles ne sont pas relues (ni payées) ;
    - `on_ocr_page(pages_text)` : appelé après chaque nouvelle page lue, pour que
      l'appelant mémorise la progression."""
    pages_text = _extract_digital_text(file_path, display_name=display_name)
    page_count = len(pages_text)

    if _needs_ocr(pages_text):
        logger.info("Texte natif insuffisant pour %s, bascule sur l'OCR.", file_path)
        pages_text = _ocr_pdf(file_path, page_count=page_count, pages_done=ocr_pages_done, on_page=on_ocr_page)
        requires_ocr = True
    else:
        requires_ocr = False

    return PAGE_SEPARATOR.join(pages_text), page_count, requires_ocr


def extract_text_from_image(file_path):
    """Lecture d'une photo / d'un scan. Même contrat que extract_text_from_pdf :
    retourne (text, page_count=1, requires_ocr=True)."""
    engine = get_ocr_engine()
    with Image.open(file_path) as img:
        oriented = ImageOps.exif_transpose(img)  # respecte l'orientation des photos de téléphone
        text = engine.read_image(oriented)
    return text, 1, True


def _extract_digital_text(file_path, *, display_name=None):
    with pdfplumber.open(file_path) as pdf:
        page_count = len(pdf.pages)
        limit = max_pdf_pages()
        if limit and page_count > limit:
            raise DocumentRejectedError(
                f"PDF de {page_count} pages (maximum {limit}) : {file_path}",
                user_message=too_many_pages_message(display_name or "Ce PDF", page_count, limit),
            )
        texts = []
        for page in pdf.pages:
            texts.append(page.extract_text() or "")
            page.close()  # libère le cache de la page : mémoire bornée sur les gros PDF
        return texts


def _needs_ocr(pages_text):
    if not pages_text:
        return True
    avg_chars = sum(len(p) for p in pages_text) / len(pages_text)
    return avg_chars < MIN_CHARS_PER_PAGE_THRESHOLD


def _ocr_pdf(file_path, *, page_count, pages_done=(), on_page=None):
    texts = list(pages_done)[:page_count]
    if len(texts) >= page_count:
        return texts
    engine = get_ocr_engine()
    for _number, page_image in iter_pdf_page_images(file_path, page_count=page_count, first_page=len(texts) + 1):
        try:
            text = engine.read_image(page_image)
        except Exception as exc:
            # Panne de configuration ou erreur transitoire : ce n'est pas une page « vide »,
            # on remonte pour que la tâche échoue clairement / soit relancée plus tard.
            if is_configuration_error(exc) or is_retryable_error(exc):
                raise
            logger.exception("Échec OCR sur une page de %s", file_path)
            text = ""
        # Tesseract termine chaque page par un saut de page : il décalerait la numérotation
        # des pages (séparateur de pages du texte stocké).
        texts.append((text or "").replace(PAGE_SEPARATOR, "\n"))
        if on_page is not None:
            on_page(list(texts))
    return texts
