"""Relecture de la revue avant diffusion : corriger les notices (journal, titre de la une,
résumé), les réordonner ou les changer de rubrique, en supprimer, modifier le titre et la
date ; masquer ou reclasser un point clé ; supprimer une revue.

Règles communes :
- la version rédigée par l'IA est mise de côté à la première correction
  (`GeneratedReview.original_structured`) pour pouvoir la restaurer ;
- toute modification du contenu exporté vide le cache des exports (PDF / Word), sinon le
  client téléchargerait l'ancienne version ;
- les messages d'erreur sont renvoyés tels quels à l'utilisateur : ils disent quelle
  notice corriger et pourquoi.
"""
import re

from django.db import transaction
from django.utils import timezone

from ..models import GeneratedReview, Highlight, PipelineStepRun, PressReviewJob, SourceDocument

MAX_TITLE_LENGTH = 255
MAX_SOURCE_LENGTH = 150
MAX_HEADLINE_LENGTH = 300
MAX_SUMMARY_LENGTH = 5000
MAX_DATE_LABEL_LENGTH = 100
MAX_COUNTRY_LENGTH = 60
MAX_ENTRIES = 200
MAX_DOCUMENTS_PER_ENTRY = 50
MAX_DOCUMENT_NAME_LENGTH = 255

# Une revue ne se corrige qu'une fois rédigée ; on ne supprime pas une revue en cours
# d'analyse (un worker écrit encore dedans).
EDITABLE_STATUSES = (PressReviewJob.Status.REVIEW_READY, PressReviewJob.Status.EXPORTED)
DELETABLE_STATUSES = (*EDITABLE_STATUSES, PressReviewJob.Status.FAILED)

NOT_EDITABLE_MESSAGE = "La revue ne peut être modifiée qu'une fois prête."
LEGACY_REVIEW_MESSAGE = (
    "Cette revue a été rédigée avant le format « revue de presse » : seul son titre peut être modifié."
)
NOT_DELETABLE_MESSAGE = "Une revue en cours d'analyse ne peut pas être supprimée : attendez la fin de l'analyse."
CONFLICT_MESSAGE = "La revue a été modifiée entre-temps par un autre membre. Rechargez la page pour voir sa version."

_UNSET = object()  # « paramètre non fourni » (None est une valeur valide)


class ReviewEditError(ValueError):
    """Correction refusée : le message s'affiche tel quel à l'utilisateur."""


class ReviewEditConflict(Exception):
    """La revue a changé depuis que l'utilisateur l'a ouverte (deux relecteurs en même temps)."""


# --------------------------------------------------------------------------- exports


def invalidate_exports(review, *, save=True):
    """Vide le cache des exports : le prochain téléchargement régénère le PDF / Word.

    Les anciens fichiers ne sont effacés du disque qu'une fois la transaction validée (une
    correction annulée ne doit pas perdre l'export encore valable)."""
    stale = [(field.storage, field.name) for field in (review.pdf_file, review.docx_file) if field]
    review.pdf_file = None
    review.docx_file = None
    if save:
        review.save(update_fields=["pdf_file", "docx_file", "updated_at"])
    for storage, name in stale:
        transaction.on_commit(lambda storage=storage, name=name: storage.delete(name), robust=True)


def invalidate_job_exports(job):
    review = GeneratedReview.objects.filter(job=job).first()
    if review is not None and (review.pdf_file or review.docx_file):
        invalidate_exports(review)


# --------------------------------------------------------------------------- validation


def _text(value, *, where, label, max_length):
    """Texte d'un champ, espaces et retours à la ligne ramenés à un espace : chaque notice
    est un seul paragraphe dans la revue diffusée (Word, PDF, WhatsApp)."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ReviewEditError(f"{where} : {label} doit être du texte.")
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) > max_length:
        raise ReviewEditError(f"{where} : {label} ne doit pas dépasser {max_length} caractères.")
    return text


def _documents(value, *, where):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_DOCUMENTS_PER_ENTRY:
        raise ReviewEditError(f"{where} : liste de documents invalide.")
    if not all(isinstance(name, str) and len(name) <= MAX_DOCUMENT_NAME_LENGTH for name in value):
        raise ReviewEditError(f"{where} : liste de documents invalide.")
    return list(value)


def _normalize_entry(entry, *, where):
    from apps.ai_pipeline.press_format import clean_headline

    if not isinstance(entry, dict):
        raise ReviewEditError(f"{where} : notice invalide.")
    source = _text(entry.get("source"), where=where, label="le nom du journal", max_length=MAX_SOURCE_LENGTH)
    headline = clean_headline(
        _text(entry.get("headline"), where=where, label="le titre de la une", max_length=MAX_HEADLINE_LENGTH)
    )
    summary = _text(entry.get("summary"), where=where, label="le résumé", max_length=MAX_SUMMARY_LENGTH)
    if not source:
        raise ReviewEditError(f"{where} : le nom du journal est obligatoire.")
    if not headline and not summary:
        raise ReviewEditError(f"{where} ({source.upper()}) : indiquez le titre de la une ou un résumé.")
    return {
        # Les noms de journaux sont en capitales dans la revue (« ▶ CAMEROON TRIBUNE »).
        "source": source.upper(),
        "headline": headline,
        "summary": summary,
        "documents": _documents(entry.get("documents"), where=where),
    }


def normalize_sections(sections):
    """Rubriques envoyées par l'éditeur -> rubriques stockées (`structured["sections"]`).

    L'ordre des notices DANS une rubrique est celui choisi par l'utilisateur ; les rubriques
    restent dans l'ordre de la charte (press_format.RUBRIQUES) et une rubrique vidée
    disparaît, comme dans une revue rédigée par l'IA."""
    from apps.ai_pipeline.press_format import RUBRIQUE_BY_KEY, RUBRIQUES

    if not isinstance(sections, list):
        raise ReviewEditError("Les rubriques de la revue sont invalides.")
    entries_by_key = {}
    for section in sections:
        if not isinstance(section, dict):
            raise ReviewEditError("Les rubriques de la revue sont invalides.")
        key = section.get("key")
        rubrique = RUBRIQUE_BY_KEY.get(key) if isinstance(key, str) else None
        if rubrique is None:
            raise ReviewEditError(f"Rubrique inconnue : « {key} ».")
        if key in entries_by_key:
            raise ReviewEditError(f"La rubrique « {rubrique['title']} » apparaît deux fois.")
        entries = section.get("entries")
        if not isinstance(entries, list):
            raise ReviewEditError(f"Rubrique « {rubrique['title']} » : liste de notices invalide.")
        entries_by_key[key] = [
            _normalize_entry(entry, where=f"{rubrique['title']}, notice {position}")
            for position, entry in enumerate(entries, start=1)
        ]

    total = sum(len(entries) for entries in entries_by_key.values())
    if total == 0:
        raise ReviewEditError("La revue doit contenir au moins une notice.")
    if total > MAX_ENTRIES:
        raise ReviewEditError(f"La revue ne peut pas dépasser {MAX_ENTRIES} notices.")
    return [{"key": r["key"], "entries": entries_by_key[r["key"]]} for r in RUBRIQUES if entries_by_key.get(r["key"])]


def _normalize_label(value, *, label, max_length):
    return _text(value, where="En-tête de la revue", label=label, max_length=max_length)


def normalize_title(value):
    title = _text(value, where="Titre", label="le titre", max_length=MAX_TITLE_LENGTH)
    if not title:
        raise ReviewEditError("Le titre de la revue ne peut pas être vide.")
    return title


# --------------------------------------------------------------------------- revue


@transaction.atomic
def rename_job(job, title):
    """Renomme une revue. Le titre figure sous le bandeau des exports : ils sont périmés."""
    job.title = normalize_title(title)
    job.save(update_fields=["title", "updated_at"])
    invalidate_job_exports(job)
    return job


def _save_markdown(review):
    from apps.ai_pipeline.press_format import to_markdown

    review.summary_markdown = to_markdown(review.structured)


def _check_version(review, expected_edited_at):
    """Verrou optimiste : `expected_edited_at` = date de la dernière correction connue du
    client (None pour une revue jamais corrigée). Absent = pas de contrôle."""
    if expected_edited_at is _UNSET:
        return
    if review.edited_at != expected_edited_at:
        raise ReviewEditConflict(CONFLICT_MESSAGE)


@transaction.atomic
def update_review(review, *, user, changes, expected_edited_at=_UNSET):
    """Applique une correction. `changes` : sous-ensemble de {title, date_label, country,
    sections} (valeurs brutes de la requête, validées ici). Retourne la revue à jour."""
    review = GeneratedReview.objects.select_for_update().select_related("job").get(pk=review.pk)
    job = review.job
    if job.status not in EDITABLE_STATUSES:
        raise ReviewEditError(NOT_EDITABLE_MESSAGE)
    _check_version(review, expected_edited_at)

    from apps.ai_pipeline.press_format import FORMAT_VERSION

    content_keys = {"date_label", "country", "sections"} & set(changes)
    if content_keys and (review.structured or {}).get("format") != FORMAT_VERSION:
        raise ReviewEditError(LEGACY_REVIEW_MESSAGE)

    if "title" in changes:
        job.title = normalize_title(changes["title"])
        job.save(update_fields=["title", "updated_at"])

    if content_keys:
        structured = dict(review.structured)
        if "date_label" in changes:
            structured["date_label"] = _normalize_label(
                changes["date_label"], label="la date", max_length=MAX_DATE_LABEL_LENGTH
            )
        if "country" in changes:
            structured["country"] = _normalize_label(
                changes["country"], label="le pays", max_length=MAX_COUNTRY_LENGTH
            ).upper()
        if "sections" in changes:
            structured["sections"] = normalize_sections(changes["sections"])
            # L'ordre choisi par l'utilisateur prime désormais sur le classement automatique
            # des journaux (press_format.present).
            structured["manual_order"] = True
        if not review.original_structured:
            review.original_structured = review.structured
        review.structured = structured
        review.edited_at = timezone.now()
        review.edited_by = user
        _save_markdown(review)

    # Le titre figure aussi sous le bandeau des exports : tout changement les périme.
    invalidate_exports(review, save=False)
    review.save()
    return review


@transaction.atomic
def restore_original_review(review):
    """Revient à la version rédigée par l'IA (les corrections manuelles sont perdues)."""
    review = GeneratedReview.objects.select_for_update().select_related("job").get(pk=review.pk)
    if review.job.status not in EDITABLE_STATUSES:
        raise ReviewEditError(NOT_EDITABLE_MESSAGE)
    if not review.original_structured:
        raise ReviewEditError("Cette revue n'a pas été modifiée : il n'y a rien à restaurer.")
    review.structured = review.original_structured
    review.original_structured = {}
    review.edited_at = None
    review.edited_by = None
    _save_markdown(review)
    invalidate_exports(review, save=False)
    review.save()
    return review


# --------------------------------------------------------------------------- points clés


@transaction.atomic
def update_highlight(highlight, *, changes):
    """`changes` : {hidden: bool} et/ou {category: DetectionCategory déjà validée}."""
    fields = []
    if "hidden" in changes and changes["hidden"] != highlight.hidden:
        highlight.hidden = changes["hidden"]
        fields.append("hidden")
    if "category" in changes and changes["category"].pk != highlight.category_id:
        highlight.category = changes["category"]
        fields.append("category")
    if fields:
        highlight.save(update_fields=[*fields, "updated_at"])
        # L'annexe « Points clés détectés » des exports a changé.
        invalidate_job_exports(highlight.job)
    return highlight


# --------------------------------------------------------------------------- suppression


def can_delete_job(job, user, *, is_org_admin):
    return is_org_admin or (job.created_by_id is not None and job.created_by_id == user.pk)


@transaction.atomic
def delete_press_review_job(job):
    """Supprime une revue à la demande du client : documents source, revue, points clés et
    fichiers (effacés du disque après validation, cf. signals.py).

    La ligne PressReviewJob est conservée sans contenu (`deleted_at`) : la revue reste
    décomptée du quota de la période (billing.SubscriptionService.reviews_used) — sinon
    supprimer puis relancer une revue contournerait la limite de la formule."""
    job = PressReviewJob.objects.select_for_update().get(pk=job.pk)
    if job.deleted_at is not None:
        return job
    if job.status not in DELETABLE_STATUSES:
        raise ReviewEditError(NOT_DELETABLE_MESSAGE)
    Highlight.objects.filter(job=job).delete()
    GeneratedReview.objects.filter(job=job).delete()
    SourceDocument.objects.filter(job=job).delete()
    PipelineStepRun.objects.filter(job=job).delete()
    job.title = ""
    job.error_message = ""
    job.deleted_at = timezone.now()
    job.save(update_fields=["title", "error_message", "deleted_at", "updated_at"])
    return job
