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


class DeletedFilter(admin.SimpleListFilter):
    title = "suppression"
    parameter_name = "supprimee"

    def lookups(self, request, model_admin):
        return [("non", "Visibles"), ("oui", "Supprimées par le client")]

    def queryset(self, request, queryset):
        if self.value() == "non":
            return queryset.filter(deleted_at__isnull=True)
        if self.value() == "oui":
            return queryset.filter(deleted_at__isnull=False)
        return queryset


@admin.register(PressReviewJob)
class PressReviewJobAdmin(admin.ModelAdmin):
    # Une revue « supprimée » n'a plus de contenu : la ligne reste pour le décompte du quota.
    list_display = ["title", "organization", "status", "progress_percent", "created_at", "deleted_at"]
    list_filter = ["status", DeletedFilter]
    search_fields = ["title"]
    inlines = [PipelineStepRunInline, HighlightInline]


@admin.register(SourceDocument)
class SourceDocumentAdmin(admin.ModelAdmin):
    list_display = ["original_filename", "organization", "extraction_status", "requires_ocr", "created_at"]
    list_filter = ["extraction_status"]


@admin.register(GeneratedReview)
class GeneratedReviewAdmin(admin.ModelAdmin):
    list_display = ["job", "generated_at", "edited_at", "edited_by"]
    readonly_fields = ["original_structured", "edited_at", "edited_by"]
