"""Signaux du domaine « revue de presse ».

- `job_status_changed` est émis APRÈS COMMIT à chaque changement de statut d'un job
  (arguments : job, previous_status, new_status). Les e-mails « revue prête / échec »
  (apps.notifications) s'y abonnent : la machine à états ne connaît aucun destinataire.
- Effacement des fichiers sur le disque quand leur ligne disparaît (suppression d'une revue
  depuis l'appli, d'un document non rattaché, ou depuis l'admin Django), après validation
  de la transaction : une suppression annulée ne doit pas laisser une ligne qui pointe vers
  un fichier disparu."""
import logging

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import Signal, receiver

from .models import GeneratedReview, SourceDocument

logger = logging.getLogger(__name__)

job_status_changed = Signal()


def announce_status_change(job, previous_status):
    new_status = job.status

    def _send():
        # send_robust : un destinataire en panne (SMTP, broker) ne casse jamais le pipeline.
        for receiver_, result in job_status_changed.send_robust(
            sender=type(job), job=job, previous_status=previous_status, new_status=new_status
        ):
            if isinstance(result, Exception):
                logger.error("Abonné %r de job_status_changed en échec : %s", receiver_, result)

    transaction.on_commit(_send)


def _delete_file_on_commit(field_file):
    if not field_file:
        return
    storage, name = field_file.storage, field_file.name
    transaction.on_commit(lambda: storage.delete(name), robust=True)


@receiver(post_delete, sender=SourceDocument, dispatch_uid="press_review_delete_source_document_file")
def delete_source_document_file(sender, instance, **kwargs):
    _delete_file_on_commit(instance.file)


@receiver(post_delete, sender=GeneratedReview, dispatch_uid="press_review_delete_review_exports")
def delete_review_export_files(sender, instance, **kwargs):
    _delete_file_on_commit(instance.pdf_file)
    _delete_file_on_commit(instance.docx_file)
