"""Signaux du domaine « revue de presse ».

`job_status_changed` est émis APRÈS COMMIT à chaque changement de statut d'un job
(arguments : job, previous_status, new_status). Les e-mails « revue prête / échec »
(apps.notifications) s'y abonnent : la machine à états ne connaît aucun destinataire."""
import logging

from django.db import transaction
from django.dispatch import Signal

logger = logging.getLogger(__name__)

job_status_changed = Signal()


def announce_status_change(job, previous_status):
    new_status = job.status

    def _send():
        # send_robust : un destinataire en panne (SMTP, broker) ne casse jamais le pipeline.
        for receiver, result in job_status_changed.send_robust(
            sender=type(job), job=job, previous_status=previous_status, new_status=new_status
        ):
            if isinstance(result, Exception):
                logger.error("Abonné %r de job_status_changed en échec : %s", receiver, result)

    transaction.on_commit(_send)
