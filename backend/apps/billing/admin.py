from django.contrib import admin
from django.utils import timezone

from .models import Invoice, Plan, Subscription
from .services import SubscriptionService


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "price_amount", "currency", "max_reviews_per_month", "max_seats", "is_active"]
    search_fields = ["name", "code"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["organization", "plan", "provider", "status", "current_period_end"]
    list_filter = ["provider", "status"]
    autocomplete_fields = ["organization"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Les virements bancaires (usage B2B dominant au Cameroun) se valident ici : filtrer
    par statut "Justificatif à valider", ouvrir le justificatif, lancer l'action ci-dessous."""

    list_display = ["organization", "provider", "amount", "currency", "status", "created_at"]
    list_filter = ["provider", "status"]
    autocomplete_fields = ["organization"]
    actions = ["approve_bank_transfer"]

    @admin.action(description="Valider le virement (marquer payé + renouveler l'abonnement)")
    def approve_bank_transfer(self, request, queryset):
        count = 0
        for invoice in queryset.filter(status=Invoice.Status.PENDING_REVIEW):
            invoice.status = Invoice.Status.PAID
            invoice.paid_at = timezone.now()
            invoice.reviewed_by = request.user
            invoice.save(update_fields=["status", "paid_at", "reviewed_by", "updated_at"])
            SubscriptionService.renew(subscription=invoice.subscription)
            count += 1
        self.message_user(request, f"{count} facture(s) validée(s).")
