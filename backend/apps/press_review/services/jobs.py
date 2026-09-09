from django.db import transaction

from ..models import PressReviewJob, SourceDocument


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

    job = PressReviewJob.objects.create(organization=organization, created_by=created_by, title=title)
    SourceDocument.objects.filter(id__in=[d.id for d in documents]).update(job=job)
    return job, documents
