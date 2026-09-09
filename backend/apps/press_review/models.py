import uuid
from pathlib import PurePosixPath

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.accounts.models import Organization
from apps.core.models import TimeStampedModel

# Django's FileField défaut à max_length=100 pour la colonne "name" ; nos chemins
# organizations/<uuid>/.../<uuid>... le dépassent facilement (SuspiciousFileOperation
# à l'upload). On garde le nom original uniquement dans un champ dédié (ex:
# original_filename) et on ne met qu'un UUID + l'extension dans le chemin de stockage.
FILE_PATH_MAX_LENGTH = 255


def _safe_suffix(filename, default=""):
    suffix = PurePosixPath(filename).suffix
    return suffix[:10] if suffix else default


def source_document_upload_path(instance, filename):
    ext = _safe_suffix(filename, ".pdf")
    return f"organizations/{instance.organization_id}/source_documents/{uuid.uuid4()}{ext}"


def generated_review_upload_path(instance, filename):
    ext = _safe_suffix(filename)
    return f"organizations/{instance.job.organization_id}/reviews/{instance.job_id}{ext}"


class DetectionCategory(TimeStampedModel):
    """Catégorie de détection éditable (légal/point important/intox/autre). C'est
    l'unique point d'entrée du contenu "critères" injecté dans les prompts Mistral :
    aucun texte de loi n'est codé en dur, le client affine ces lignes via l'admin."""

    class Type(models.TextChoices):
        LEGAL_RISK = "legal_risk", "Risque juridique"
        IMPORTANT_POINT = "important_point", "Point important"
        INTOX = "intox", "Intox potentielle"
        CUSTOM = "custom", "Autre"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="detection_categories",
        null=True,
        blank=True,
        help_text="Vide = catégorie globale visible par toutes les organisations.",
    )
    name = models.CharField(max_length=150)
    type = models.CharField(max_length=30, choices=Type.choices, default=Type.CUSTOM)
    description = models.TextField(blank=True)
    prompt_hint = models.TextField(
        blank=True,
        help_text="Injecté verbatim dans les prompts Mistral pour guider la détection.",
    )
    keywords = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    color = models.CharField(max_length=7, default="#6B7280", help_text="Couleur hex pour l'affichage frontend.")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "Detection categories"

    def __str__(self):
        return self.name


class SourceDocument(TimeStampedModel):
    class ExtractionStatus(models.TextChoices):
        PENDING = "pending", "En attente"
        DONE = "done", "Terminée"
        FAILED = "failed", "Échouée"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="source_documents")
    job = models.ForeignKey(
        "PressReviewJob", on_delete=models.CASCADE, related_name="documents", null=True, blank=True
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="uploaded_documents"
    )
    file = models.FileField(upload_to=source_document_upload_path, max_length=FILE_PATH_MAX_LENGTH)
    original_filename = models.CharField(max_length=255)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    requires_ocr = models.BooleanField(null=True, blank=True)
    extracted_text = models.TextField(blank=True)
    extraction_status = models.CharField(
        max_length=20, choices=ExtractionStatus.choices, default=ExtractionStatus.PENDING
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.original_filename


class PressReviewJob(TimeStampedModel):
    class Status(models.TextChoices):
        UPLOADED = "UPLOADED", "Téléversé"
        TEXT_EXTRACTION = "TEXT_EXTRACTION", "Extraction du texte"
        CHUNKING_SUMMARIZATION = "CHUNKING_SUMMARIZATION", "Découpage & résumé"
        HIGHLIGHT_DETECTION = "HIGHLIGHT_DETECTION", "Détection des points saillants"
        REVIEW_DRAFTING = "REVIEW_DRAFTING", "Rédaction de la revue"
        REVIEW_READY = "REVIEW_READY", "Revue prête"
        EXPORTED = "EXPORTED", "Exportée"
        FAILED = "FAILED", "Échouée"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="press_review_jobs")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_jobs"
    )
    title = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.UPLOADED)
    progress_percent = models.PositiveSmallIntegerField(default=0)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title or f"Job {self.id}"


class PipelineStepRun(TimeStampedModel):
    class StepName(models.TextChoices):
        TEXT_EXTRACTION = "TEXT_EXTRACTION", "Extraction du texte"
        CHUNKING_SUMMARIZATION = "CHUNKING_SUMMARIZATION", "Découpage & résumé"
        HIGHLIGHT_DETECTION = "HIGHLIGHT_DETECTION", "Détection des points saillants"
        REVIEW_DRAFTING = "REVIEW_DRAFTING", "Rédaction de la revue"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        RUNNING = "running", "En cours"
        SUCCEEDED = "succeeded", "Réussie"
        FAILED = "failed", "Échouée"

    job = models.ForeignKey(PressReviewJob, on_delete=models.CASCADE, related_name="step_runs")
    step_name = models.CharField(max_length=30, choices=StepName.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    progress_percent = models.PositiveSmallIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    result_summary = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["job", "step_name"], name="unique_step_per_job"),
        ]

    def __str__(self):
        return f"{self.job_id} · {self.step_name} ({self.status})"


class Highlight(TimeStampedModel):
    job = models.ForeignKey(PressReviewJob, on_delete=models.CASCADE, related_name="highlights")
    source_document = models.ForeignKey(
        SourceDocument, on_delete=models.SET_NULL, null=True, blank=True, related_name="highlights"
    )
    category = models.ForeignKey(DetectionCategory, on_delete=models.PROTECT, related_name="highlights")
    excerpt = models.TextField()
    explanation = models.TextField(blank=True)
    confidence = models.FloatField(null=True, blank=True)
    page_number = models.PositiveIntegerField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"{self.category.name}: {self.excerpt[:40]}"


class GeneratedReview(TimeStampedModel):
    job = models.OneToOneField(PressReviewJob, on_delete=models.CASCADE, related_name="review")
    summary_markdown = models.TextField(blank=True)
    pdf_file = models.FileField(
        upload_to=generated_review_upload_path, null=True, blank=True, max_length=FILE_PATH_MAX_LENGTH
    )
    docx_file = models.FileField(
        upload_to=generated_review_upload_path, null=True, blank=True, max_length=FILE_PATH_MAX_LENGTH
    )
    generated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Revue pour job {self.job_id}"
