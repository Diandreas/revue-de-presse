"""Plafonds de taille d'une revue selon la formule (documents et pages), vérifiés AVANT de
lancer l'analyse : une revue trop grosse est refusée avec un message clair au lieu de
saturer le débit IA partagé ou d'échouer au bout de vingt minutes.

Réglages (`AI_REVIEW_LIMITS`, par code de formule, « default » pour les autres) :
    {"default": {"max_documents": 40, "max_pages": 80}, "starter": {...}, ...}
et `AI_MAX_PDF_PAGES` : longueur maximale d'UN PDF (garde-fou mémoire / coût, appliqué
aussi pendant l'extraction). 0 = pas de limite.

Une photo compte pour une page ; un PDF pour son nombre de pages.
"""
import logging

import pdfplumber
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_REVIEW_LIMITS = {"max_documents": 40, "max_pages": 80}
DEFAULT_MAX_PDF_PAGES = 100

CONTACT_HINT = "Répartissez-les sur plusieurs revues, ou contactez-nous pour une formule adaptée à vos volumes."


def max_pdf_pages():
    value = getattr(settings, "AI_MAX_PDF_PAGES", None)
    return DEFAULT_MAX_PDF_PAGES if value is None else int(value)


def _plan_of(organization):
    subscription = getattr(organization, "subscription", None)  # OneToOne inverse : None si absent
    return getattr(subscription, "plan", None)


def review_limits(organization):
    """{"plan": nom de la formule, "max_documents": n, "max_pages": n} (0 = illimité)."""
    configured = getattr(settings, "AI_REVIEW_LIMITS", None) or {}
    limits = {**DEFAULT_REVIEW_LIMITS, **(configured.get("default") or {})}
    plan = _plan_of(organization)
    if plan is not None:
        limits.update(configured.get(plan.code) or {})
    return {"plan": plan.name if plan is not None else "", **limits}


def count_pdf_pages(path):
    """Nombre de pages (lecture de la structure seulement, sans rendu), None si illisible."""
    try:
        with pdfplumber.open(path) as pdf:
            return len(pdf.pages)
    except Exception:  # noqa: BLE001 - fichier corrompu : l'extraction le signalera
        logger.warning("Nombre de pages illisible pour %s.", path, exc_info=True)
        return None


def document_pages(document):
    if document.kind != "pdf":
        return 1
    if document.page_count:
        return document.page_count
    return count_pdf_pages(document.file.path) or 1


def too_many_pages_message(filename, pages, limit):
    return (
        f"« {filename} » compte {pages} pages : un même PDF est limité à {limit} pages. "
        "Découpez-le (par exemple un fichier par journal) avant de l'analyser."
    )


def review_size_denial(*, organization, document_ids):
    """Raison lisible pour laquelle cette sélection dépasse les plafonds de la formule, ou None."""
    from apps.press_review.models import SourceDocument

    limits = review_limits(organization)
    formula = f"Votre formule {limits['plan']}" if limits["plan"] else "Votre formule"
    count = len({str(i) for i in document_ids})
    if limits["max_documents"] and count > limits["max_documents"]:
        return (
            f"{formula} permet d'analyser jusqu'à {limits['max_documents']} documents par revue "
            f"({count} sélectionnés). {CONTACT_HINT}"
        )

    documents = SourceDocument.objects.filter(id__in=document_ids, organization=organization, job__isnull=True)
    pages_by_document = [(document, document_pages(document)) for document in documents]
    per_pdf = max_pdf_pages()
    for document, pages in pages_by_document:
        if per_pdf and document.kind == "pdf" and pages > per_pdf:
            return too_many_pages_message(document.original_filename, pages, per_pdf)
    total_pages = sum(pages for _document, pages in pages_by_document)
    if limits["max_pages"] and total_pages > limits["max_pages"]:
        return (
            f"{formula} permet d'analyser jusqu'à {limits['max_pages']} pages par revue (une photo "
            f"compte pour une page ; cette sélection en compte {total_pages}). {CONTACT_HINT}"
        )
    return None
