from django.db import models

from apps.accounts.models import Organization
from apps.core.models import TimeStampedModel


class AIUsage(TimeStampedModel):
    """Un appel au service d'IA (Mistral), réussi ou non : qui l'a consommé (organisation,
    revue, étape), avec quel modèle, combien de jetons et en combien de temps.

    Écrit par `usage.record_ai_call` à chaque appel du SDK (cf. mistral_client) ; sert au
    suivi du coût par client et par mois dans l'admin (« Totaux mensuels »). Les liens sont
    en SET_NULL : supprimer une revue ou une organisation ne fait pas disparaître le coût
    déjà engagé."""

    class Operation(models.TextChoices):
        JSON = "json", "Analyse de texte (JSON)"
        JSON_REPAIR = "json_repair", "Correction d'un JSON invalide"
        VISION = "vision", "Lecture d'une image (OCR)"

    organization = models.ForeignKey(
        Organization, on_delete=models.SET_NULL, null=True, blank=True, related_name="ai_usages"
    )
    job = models.ForeignKey(
        "press_review.PressReviewJob", on_delete=models.SET_NULL, null=True, blank=True, related_name="ai_usages"
    )
    step = models.CharField(max_length=30, blank=True, help_text="Étape du pipeline (vide hors pipeline).")
    operation = models.CharField(max_length=20, choices=Operation.choices, default=Operation.JSON)
    model = models.CharField(max_length=100)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(default=0)
    succeeded = models.BooleanField(default=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Code HTTP en cas d'échec.")
    error = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "appel IA"
        verbose_name_plural = "appels IA (usage et coût)"
        indexes = [models.Index(fields=["organization", "created_at"], name="aiusage_org_created_idx")]

    def __str__(self):
        return f"{self.model} · {self.step or '-'} · {self.total_tokens} jetons"
