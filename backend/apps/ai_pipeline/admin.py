from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.urls import path

from .models import AIUsage
from .usage import estimate_cost_usd, monthly_totals


@admin.register(AIUsage)
class AIUsageAdmin(admin.ModelAdmin):
    """Journal des appels IA, en lecture seule, et totaux mensuels par organisation (bouton
    « Totaux mensuels par organisation ») pour suivre le coût de chaque client."""

    change_list_template = "admin/ai_pipeline/aiusage/change_list.html"
    list_display = [
        "created_at", "organization", "job", "step", "operation", "model",
        "prompt_tokens", "completion_tokens", "duration_ms", "succeeded", "estimated_cost",
    ]
    list_filter = ["succeeded", "operation", "step", "model", ("created_at", admin.DateFieldListFilter)]
    search_fields = ["organization__name", "model", "job__title"]
    list_select_related = ["organization", "job"]
    date_hierarchy = "created_at"
    readonly_fields = [field.name for field in AIUsage._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Coût estimé ($)")
    def estimated_cost(self, obj):
        cost = estimate_cost_usd(obj.model, obj.prompt_tokens, obj.completion_tokens)
        return "—" if cost is None else f"{cost:.5f}"

    def get_urls(self):
        monthly = path(
            "totaux-mensuels/",
            self.admin_site.admin_view(self.monthly_totals_view),
            name="ai_pipeline_aiusage_monthly",
        )
        return [monthly, *super().get_urls()]

    def monthly_totals_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        context = {
            **self.admin_site.each_context(request),
            "title": "Consommation d'IA par organisation et par mois",
            "opts": self.model._meta,
            "months": monthly_totals(months=12),
        }
        return TemplateResponse(request, "admin/ai_pipeline/aiusage/monthly_totals.html", context)
