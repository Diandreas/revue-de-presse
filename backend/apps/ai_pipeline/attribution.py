"""Nom du journal dont provient chaque document d'une revue.

L'annexe « Points clés » et le panneau des points clés de l'application citaient le nom du
fichier (« WhatsApp Image 2026-10-09 at 08.12.33.jpeg »), illisible pour la direction qui
reçoit la revue. Le journal de chaque document est connu une fois la revue rédigée :

1. notices de la revue (`GeneratedReview.structured`) : `document_ids` (revues récentes),
   sinon le nom de fichier quand il est unique dans la revue — c'est aussi ce qui reflétera
   une éventuelle correction manuelle d'une notice ;
2. à défaut, le cache de l'étape de rédaction (une notice par id de document).

Un document sans journal identifié garde son libellé « JOURNAL NON IDENTIFIÉ (photo n° 3) ».
"""
from collections import Counter

from . import media


def _review_of(job):
    return getattr(job, "review", None)  # OneToOne inverse : None si la revue n'existe pas


def newspaper_names(job, review=None):
    """{id de document (str) : nom du journal à afficher}."""
    from apps.press_review.models import PipelineStepRun

    review = review if review is not None else _review_of(job)
    documents = list(job.documents.all())
    filename_counts = Counter(d.original_filename for d in documents)
    id_by_unique_filename = {d.original_filename: str(d.id) for d in documents if filename_counts[d.original_filename] == 1}

    names = {}
    structured = (getattr(review, "structured", None) or {}) if review is not None else {}
    for section in structured.get("sections") or []:
        for entry in section.get("entries") or []:
            source = media.display_name(entry.get("source"))
            if not source:
                continue
            for document_id in entry.get("document_ids") or []:
                names.setdefault(str(document_id), source)
            for filename in entry.get("documents") or []:
                document_id = id_by_unique_filename.get(filename)
                if document_id:
                    names.setdefault(document_id, source)

    drafting = (
        PipelineStepRun.objects.filter(job=job, step_name=PipelineStepRun.StepName.REVIEW_DRAFTING)
        .values_list("result_summary", flat=True)
        .first()
    )
    for document_id, entry in ((drafting or {}).get("entries") or {}).items():
        source = media.display_name((entry or {}).get("source"))
        if source:
            names.setdefault(str(document_id), source)
    return names


def source_label(highlight, names):
    """« CAMEROON TRIBUNE · page 2 » ; nom du fichier seulement pour une revue ancienne dont
    le journal est inconnu."""
    document = highlight.source_document
    if document is None:
        return ""
    label = names.get(str(document.id)) or document.original_filename
    if highlight.page_number and document.kind == "pdf":
        label += f" · page {highlight.page_number}"
    return label
