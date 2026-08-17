"""Extraction du texte des PDF téléversés. Stratégie : texte natif d'abord
(pdfplumber, rapide et fiable pour les PDF numériques) ; si le résultat est trop
pauvre (coupure de presse scannée), bascule sur l'OCR (pdf2image + pytesseract)."""
import logging

import pdfplumber
import pytesseract
from pdf2image import convert_from_path

logger = logging.getLogger(__name__)

MIN_CHARS_PER_PAGE_THRESHOLD = 20
OCR_LANGUAGES = "fra"


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


def _extract_digital_text(file_path):
    with pdfplumber.open(file_path) as pdf:
        return [(page.extract_text() or "") for page in pdf.pages]


def _needs_ocr(pages_text):
    if not pages_text:
        return True
    avg_chars = sum(len(p) for p in pages_text) / len(pages_text)
    return avg_chars < MIN_CHARS_PER_PAGE_THRESHOLD


def _ocr_pdf(file_path, lang=OCR_LANGUAGES):
    images = convert_from_path(file_path)
    texts = []
    for image in images:
        try:
            texts.append(pytesseract.image_to_string(image, lang=lang))
        except Exception:
            logger.exception("Échec OCR sur une page de %s", file_path)
            texts.append("")
    return texts
