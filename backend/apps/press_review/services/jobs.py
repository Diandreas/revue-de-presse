from django.db import transaction
from django.utils import timezone

from ..models import PressReviewJob, SourceDocument

_MONTHS_FR = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)


def default_job_title(moment=None):
    """« Revue de presse du 8 octobre 2026 » — indépendant de la locale du serveur."""
    day = timezone.localtime(moment or timezone.now())
    return f"Revue de presse du {day.day} {_MONTHS_FR[day.month - 1]} {day.year}"


@transaction.atomic
def create_press_review_job(*, organization, created_by, document_ids, title=""):
    """Regroupe des documents déjà téléversés (job=null) dans un nouveau job. Un
    document ne peut appartenir qu'à un seul job — le queryset filtre `job__isnull=True`
    pour empêcher qu'un même PDF soit réutilisé silencieusement dans deux revues."""
    documents = list(
        SourceDocument.objects.select_for_update().filter(
            id__in=document_ids, organization=organization, job__isnull=True
        )
    )
    if not documents:
        raise ValueError("Aucun document valide fourni.")
    if len(documents) != len(set(document_ids)):
        raise ValueError("Certains documents sont introuvables, déjà utilisés, ou n'appartiennent pas à votre organisation.")

    job = PressReviewJob.objects.create(
        organization=organization,
        created_by=created_by,
        # Sans titre, la liste des revues devient vite illisible (« Revue sans titre » x N).
        title=(title or "").strip() or default_job_title(),
    )
    # L'ordre de `document_ids` est l'ordre de lecture voulu par l'utilisateur.
    rank = {str(document_id): index for index, document_id in enumerate(document_ids)}
    for document in documents:
        document.job = job
        document.position = rank[str(document.id)]
    SourceDocument.objects.bulk_update(documents, ["job", "position"])
    return job, sorted(documents, key=lambda d: d.position)
