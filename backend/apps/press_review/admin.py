from django.contrib import admin

from .models import DetectionCategory, GeneratedReview, Highlight, PipelineStepRun, PressReviewJob, SourceDocument


@admin.register(DetectionCategory)
class DetectionCategoryAdmin(admin.ModelAdmin):
    """Surface principale par laquelle le client affine les critères de détection
    (légal camerounais, points importants, intox) sans toucher au code."""

    list_display = ["name", "type", "organization", "is_active", "sort_order"]
    list_filter = ["type", "is_active"]
    search_fields = ["name", "description"]


class PipelineStepRunInline(admin.TabularInline):
    model = PipelineStepRun
    extra = 0
    readonly_fields = [
        "step_name", "status", "progress_percent", "result_summary", "error_message", "started_at", "finished_at",
    ]
    can_delete = False


class HighlightInline(admin.TabularInline):
    model = Highlight
    extra = 0
    readonly_fields = ["category", "excerpt", "explanation", "confidence", "page_number"]
    can_delete = False


@admin.register(PressReviewJob)
class PressReviewJobAdmin(admin.ModelAdmin):
    list_display = ["title", "organization", "status", "progress_percent", "created_at"]
    list_filter = ["status"]
    search_fields = ["title"]
    inlines = [PipelineStepRunInline, HighlightInline]


@admin.register(SourceDocument)
class SourceDocumentAdmin(admin.ModelAdmin):
    list_display = ["original_filename", "organization", "extraction_status", "requires_ocr", "created_at"]
    list_filter = ["extraction_status"]


@admin.register(GeneratedReview)
class GeneratedReviewAdmin(admin.ModelAdmin):
    list_display = ["job", "generated_at"]
