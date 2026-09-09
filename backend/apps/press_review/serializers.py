from rest_framework import serializers

from .models import DetectionCategory, GeneratedReview, Highlight, PipelineStepRun, PressReviewJob, SourceDocument

MAX_UPLOAD_SIZE_BYTES = 30 * 1024 * 1024  # 30 Mo


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
        is_pdf = f.content_type == "application/pdf" or f.name.lower().endswith(".pdf")
        if not is_pdf:
            raise serializers.ValidationError("Seuls les fichiers PDF sont acceptés.")
        if f.size > MAX_UPLOAD_SIZE_BYTES:
            raise serializers.ValidationError("Le fichier dépasse la taille maximale de 30 Mo.")
        return f


class SourceDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourceDocument
        fields = [
            "id", "file", "original_filename", "page_count",
            "requires_ocr", "extraction_status", "job", "created_at",
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
    class Meta:
        model = PressReviewJob
        fields = ["id", "title", "status", "progress_percent", "created_at", "completed_at"]
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

    class Meta:
        model = Highlight
        fields = ["id", "category", "excerpt", "explanation", "confidence", "page_number", "order", "source_document"]
        read_only_fields = fields


class GeneratedReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedReview
        fields = ["summary_markdown", "pdf_file", "docx_file", "generated_at"]
        read_only_fields = fields
