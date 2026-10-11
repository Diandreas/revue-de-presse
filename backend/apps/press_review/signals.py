"""Effacement des fichiers sur le disque quand leur ligne disparaît (suppression d'une revue
depuis l'appli, d'un document non rattaché, ou depuis l'admin Django) : sans ça, documents
source et exports resteraient sur le serveur indéfiniment.

L'effacement attend la validation de la transaction : une suppression annulée ne doit pas
laisser une ligne qui pointe vers un fichier disparu."""
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import GeneratedReview, SourceDocument


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
