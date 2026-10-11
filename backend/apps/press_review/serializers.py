import os

from rest_framework import serializers

from .models import DetectionCategory, GeneratedReview, Highlight, PipelineStepRun, PressReviewJob, SourceDocument

MAX_UPLOAD_SIZE_BYTES = 30 * 1024 * 1024  # 30 Mo

PDF_CONTENT_TYPE = "application/pdf"
IMAGE_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/tiff", "image/bmp", "image/gif", "image/heic", "image/heif",
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp", ".gif", ".heic", ".heif"}


def _upload_extension(uploaded_file):
    return os.path.splitext(uploaded_file.name or "")[1].lower()


def classify_upload_kind(uploaded_file):
    """Retourne 'pdf' ou 'image'. Suppose que validate_file a déjà validé le type."""
    ext = _upload_extension(uploaded_file)
    if uploaded_file.content_type in IMAGE_CONTENT_TYPES or ext in IMAGE_EXTENSIONS:
        return SourceDocument.Kind.IMAGE
    return SourceDocument.Kind.PDF


class DetectionCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = DetectionCategory
        fields = [
            "id", "name", "type", "description", "prompt_hint",
            "keywords", "color", "is_active", "sort_order", "organization",
        ]
        read_only_fields = ["id", "organization"]


class SourceDocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, f):
        ext = _upload_extension(f)
        is_pdf = f.content_type == PDF_CONTENT_TYPE or ext == ".pdf"
        is_image = f.content_type in IMAGE_CONTENT_TYPES or ext in IMAGE_EXTENSIONS
        if not (is_pdf or is_image):
            raise serializers.ValidationError(
                "Formats acceptés : PDF, ou photo (JPG, PNG, WebP, TIFF, HEIC)."
            )
        if f.size > MAX_UPLOAD_SIZE_BYTES:
            raise serializers.ValidationError("Le fichier dépasse la taille maximale de 30 Mo.")
        return f


class SourceDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourceDocument
        fields = [
            "id", "file", "original_filename", "kind", "page_count",
            "requires_ocr", "extraction_status", "extraction_error", "job", "created_at",
        ]
        read_only_fields = fields


class PipelineStepRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = PipelineStepRun
        fields = [
            "step_name", "status", "progress_percent",
            "result_summary", "error_message", "started_at", "finished_at",
        ]
        read_only_fields = fields


class PressReviewJobListSerializer(serializers.ModelSerializer):
    # Annotés par JobListCreateView.get_queryset (0 si le serializer est utilisé ailleurs).
    documents_count = serializers.IntegerField(read_only=True, default=0)
    highlights_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = PressReviewJob
        fields = [
            "id", "title", "status", "progress_percent", "created_at", "completed_at",
            "documents_count", "highlights_count",
        ]
        read_only_fields = fields


class PressReviewJobDetailSerializer(serializers.ModelSerializer):
    step_runs = PipelineStepRunSerializer(many=True, read_only=True)
    documents = SourceDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = PressReviewJob
        fields = [
            "id", "title", "status", "progress_percent", "error_message",
            "started_at", "completed_at", "created_at", "step_runs", "documents",
        ]
        read_only_fields = fields


class JobCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    document_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False, max_length=50)


class HighlightSerializer(serializers.ModelSerializer):
    category = DetectionCategorySerializer(read_only=True)
    # Journal dont provient le point clé (« CAMEROON TRIBUNE »), null si inconnu : fourni par
    # la vue dans le contexte `source_names` (cf. ai_pipeline.attribution).
    source_name = serializers.SerializerMethodField()

    class Meta:
        model = Highlight
        fields = [
            "id", "category", "excerpt", "explanation", "confidence", "page_number", "order", "source_document",
            "source_name",
        ]
        read_only_fields = fields

    def get_source_name(self, obj):
        names = self.context.get("source_names") or {}
        return names.get(str(obj.source_document_id)) if obj.source_document_id else None


class GeneratedReviewSerializer(serializers.ModelSerializer):
    # Rubriques résolues (titre, couleur, pictogramme) ; null pour les revues antérieures
    # au format « revue de presse », que le frontend affiche alors en Markdown.
    structured = serializers.SerializerMethodField()

    class Meta:
        model = GeneratedReview
        fields = ["summary_markdown", "structured", "pdf_file", "docx_file", "generated_at"]
        read_only_fields = fields

    def get_structured(self, obj):
        from apps.ai_pipeline.press_format import present

        return present(obj.structured)
