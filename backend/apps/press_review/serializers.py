from rest_framework import serializers

from apps.core.uploads import SOURCE_DOCUMENT_TYPES, VerifiedFileField

from .models import DetectionCategory, GeneratedReview, Highlight, PipelineStepRun, PressReviewJob, SourceDocument

MAX_UPLOAD_SIZE_BYTES = 30 * 1024 * 1024  # 30 Mo


def classify_upload_kind(uploaded_file):
    """Retourne 'pdf' ou 'image' d'après le type DÉTECTÉ par SourceDocumentUploadSerializer
    (jamais d'après le nom ou le Content-Type déclarés par le navigateur)."""
    if uploaded_file.file_type.is_image:
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
    # Type réel lu dans les octets (cf. apps.core.uploads) ; le fichier validé porte
    # `original_name` (nom choisi par l'utilisateur) et l'extension du type détecté.
    file = VerifiedFileField(
        allowed_types=SOURCE_DOCUMENT_TYPES,
        max_size=MAX_UPLOAD_SIZE_BYTES,
        formats_message="Formats acceptés : PDF, ou photo (JPG, PNG, WebP, HEIC).",
    )


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
            "documents_count", "highlights_count", "created_by",
        ]
        read_only_fields = fields


class PressReviewJobDetailSerializer(serializers.ModelSerializer):
    step_runs = PipelineStepRunSerializer(many=True, read_only=True)
    documents = SourceDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = PressReviewJob
        fields = [
            "id", "title", "status", "progress_percent", "error_message",
            "started_at", "completed_at", "created_at", "step_runs", "documents", "created_by",
        ]
        read_only_fields = fields


class JobCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    document_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False, max_length=50)


class HighlightSerializer(serializers.ModelSerializer):
    category = DetectionCategorySerializer(read_only=True)

    class Meta:
        model = Highlight
        fields = [
            "id", "category", "excerpt", "explanation", "confidence", "page_number", "order", "source_document",
            "hidden",
        ]
        read_only_fields = fields


class GeneratedReviewSerializer(serializers.ModelSerializer):
    # Rubriques résolues (titre, couleur, pictogramme) ; null pour les revues antérieures
    # au format « revue de presse », que le frontend affiche alors en Markdown.
    structured = serializers.SerializerMethodField()
    # Relecture (cf. services/editing.py) : revue corrigée à la main, par qui et quand ;
    # catalogue des rubriques pour déplacer une notice vers une rubrique encore vide.
    is_edited = serializers.BooleanField(read_only=True)
    edited_by_name = serializers.SerializerMethodField()
    rubriques = serializers.SerializerMethodField()

    class Meta:
        model = GeneratedReview
        fields = [
            "summary_markdown", "structured", "pdf_file", "docx_file", "generated_at",
            "is_edited", "edited_at", "edited_by_name", "rubriques",
        ]
        read_only_fields = fields

    def get_structured(self, obj):
        from apps.ai_pipeline.press_format import present

        return present(obj.structured)

    def get_edited_by_name(self, obj):
        user = obj.edited_by
        return (user.full_name or user.email) if user else None

    def get_rubriques(self, obj):
        from apps.ai_pipeline.press_format import RUBRIQUES

        return [{key: rubrique[key] for key in ("key", "title", "color", "icon")} for rubrique in RUBRIQUES]
