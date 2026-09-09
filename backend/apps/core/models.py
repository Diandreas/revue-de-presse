import uuid

from django.db import models


class TimeStampedModel(models.Model):
    """Base abstraite : clé primaire UUID + horodatage. Utilisée par tous les modèles
    de domaine pour éviter les ID séquentiels devinables entre organisations."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
