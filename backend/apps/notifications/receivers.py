"""Branchements sur les autres apps, par signaux uniquement : ni le pipeline ni
l'inscription n'importent apps.notifications."""
import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import Organization
from apps.press_review.models import PressReviewJob
from apps.press_review.signals import job_status_changed

from . import services

logger = logging.getLogger(__name__)


@receiver(job_status_changed, dispatch_uid="notifications.job_status_changed")
def on_job_status_changed(sender, job, previous_status, new_status, **kwargs):
    """Déjà appelé après commit (cf. press_review.signals.announce_status_change)."""
    if new_status == PressReviewJob.Status.REVIEW_READY:
        services.notify_review_ready(job)
    elif new_status == PressReviewJob.Status.FAILED:
        services.notify_review_failed(job, previous_status)


@receiver(post_save, sender=Organization, dispatch_uid="notifications.organization_created")
def on_organization_created(sender, instance, created, raw=False, **kwargs):
    """Nouvelle entreprise (inscription en libre-service) -> alerte au staff, une fois
    l'inscription validée en base (propriétaire et essai compris)."""
    if not created or raw:
        return
    organization_id = instance.pk
    transaction.on_commit(lambda: services.notify_new_registration(organization_id), robust=True)
