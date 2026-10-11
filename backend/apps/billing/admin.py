"""Administration de la facturation. En mode manuel (BILLING_MODE=manual), c'est ici que
l'équipe active et prolonge les abonnements après un paiement reçu hors ligne :

- liste des abonnements : filtrer par statut / échéance, cocher, choisir éventuellement une
  formule dans la barre d'actions, puis « Activer / prolonger 1, 3 ou 12 mois » ;
- « Enregistrer un paiement » (lien de la liste ou bouton de la fiche) : crée la facture
  PAYÉE numérotée (RDP-AAAA-NNNN) et prolonge l'abonnement d'autant.
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .invoice_pdf import METHOD_LABELS, invoice_filename, render_invoice_pdf
from .invoicing import amounts_from_ht
from .models import BillingProfile, Invoice, Plan, Subscription
from .services import InvoiceError, InvoiceService, SubscriptionService

logger = logging.getLogger(__name__)


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "price_amount", "currency", "max_reviews_per_month", "max_seats", "is_active"]
    search_fields = ["name", "code"]


# --------------------------------------------------------------------------- abonnements


class SubscriptionActionForm(ActionForm):
    """Barre d'actions de la liste : formule (optionnelle) appliquée par les actions « prolonger »."""

    plan = forms.ModelChoiceField(
        queryset=Plan.objects.filter(is_active=True),
        required=False,
        label="Formule",
        empty_label="— garder la formule actuelle —",
    )


class ExpiryFilter(admin.SimpleListFilter):
    title = "échéance"
    parameter_name = "echeance"

    def lookups(self, request, model_admin):
        return [
            ("expired", "Échue"),
            ("7d", "Dans les 7 jours"),
            ("30d", "Dans les 30 jours"),
        ]

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == "expired":
            return queryset.filter(current_period_end__lt=now)
        if self.value() == "7d":
            return queryset.filter(current_period_end__gte=now, current_period_end__lte=now + timedelta(days=7))
        if self.value() == "30d":
            return queryset.filter(current_period_end__gte=now, current_period_end__lte=now + timedelta(days=30))
        return queryset


class RecordPaymentForm(forms.Form):
    plan = forms.ModelChoiceField(queryset=Plan.objects.filter(is_active=True), label="Formule payée")
    months = forms.TypedChoiceField(
        label="Durée payée",
        choices=[(1, "1 mois"), (3, "3 mois"), (6, "6 mois"), (12, "12 mois")],
        coerce=int,
        initial=1,
    )
    amount_ttc = forms.DecimalField(
        label="Montant encaissé (TTC)",
        min_value=Decimal("0"),
        max_digits=12,
        decimal_places=2,
        help_text="Montant réellement reçu, TVA comprise (prix « sur devis » : saisissez le montant convenu).",
    )
    method = forms.ChoiceField(label="Mode de règlement", choices=list(METHOD_LABELS.items()))
    reference = forms.CharField(
        label="Référence du paiement",
        required=False,
        max_length=255,
        help_text="N° de transaction Mobile Money, référence du virement, n° de chèque…",
    )
    note = forms.CharField(label="Note interne", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    extend = forms.BooleanField(
        label="Prolonger l'abonnement de la durée payée",
        required=False,
        initial=True,
        help_text="Décochez si l'abonnement a déjà été prolongé avec une action de la liste.",
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        "organization", "plan", "status", "current_period_end", "access_column",
        "cancel_at_period_end", "provider", "payment_link",
    ]
    list_filter = ["status", ExpiryFilter, "plan", "provider", "cancel_at_period_end"]
    search_fields = ["organization__name"]
    autocomplete_fields = ["organization"]
    list_select_related = ["organization", "plan"]
    ordering = ["current_period_end"]
    action_form = SubscriptionActionForm
    actions = ["extend_1_month", "extend_3_months", "extend_12_months"]
    change_form_template = "admin/billing/subscription/change_form.html"

    @admin.display(boolean=True, description="Accès")
    def access_column(self, obj):
        return SubscriptionService.grants_access(obj)

    @admin.display(description="Paiement")
    def payment_link(self, obj):
        url = reverse("admin:billing_subscription_record_payment", args=[obj.pk])
        return format_html('<a href="{}">Enregistrer un paiement</a>', url)

    def get_urls(self):
        custom = [
            path(
                "<uuid:subscription_id>/record-payment/",
                self.admin_site.admin_view(self.record_payment_view),
                name="billing_subscription_record_payment",
            ),
        ]
        return custom + super().get_urls()

    # ---- actions « Activer / prolonger »

    def _extend(self, request, queryset, months):
        plan = None
        plan_id = request.POST.get("plan")
        if plan_id:
            plan = Plan.objects.filter(pk=plan_id, is_active=True).first()
        count = 0
        for subscription in queryset.select_related("plan"):
            SubscriptionService.extend(
                subscription=subscription, months=months, plan=plan, provider=Subscription.Provider.MANUAL
            )
            count += 1
        suffix = f" sur la formule {plan.name}" if plan else ""
        self.message_user(
            request,
            f"{count} abonnement(s) activé(s) / prolongé(s) de {months} mois{suffix}. Pensez à enregistrer "
            "le paiement correspondant (facture).",
            messages.SUCCESS,
        )

    @admin.action(description="Activer / prolonger 1 mois", permissions=["change"])
    def extend_1_month(self, request, queryset):
        self._extend(request, queryset, 1)

    @admin.action(description="Activer / prolonger 3 mois", permissions=["change"])
    def extend_3_months(self, request, queryset):
        self._extend(request, queryset, 3)

    @admin.action(description="Activer / prolonger 12 mois", permissions=["change"])
    def extend_12_months(self, request, queryset):
        self._extend(request, queryset, 12)

    # ---- « Enregistrer un paiement »

    def record_payment_view(self, request, subscription_id):
        subscription = get_object_or_404(Subscription.objects.select_related("organization", "plan"), pk=subscription_id)
        if not self.has_change_permission(request, subscription):
            return redirect("admin:billing_subscription_changelist")
        if request.method == "POST":
            form = RecordPaymentForm(request.POST)
            if form.is_valid():
                data = form.cleaned_data
                invoice = InvoiceService.record_manual_payment(
                    subscription=subscription,
                    months=data["months"],
                    amount_ttc=data["amount_ttc"],
                    plan=data["plan"],
                    reference=data["reference"],
                    method=data["method"],
                    note=data["note"],
                    recorded_by=request.user,
                    extend=data["extend"],
                )
                subscription.refresh_from_db()
                self.message_user(
                    request,
                    f"Paiement enregistré : facture {invoice.number} ({invoice.amount:.0f} {invoice.currency} TTC). "
                    f"Abonnement actif jusqu'au {timezone.localtime(subscription.current_period_end):%d/%m/%Y}.",
                    messages.SUCCESS,
                )
                return redirect("admin:billing_subscription_change", subscription.pk)
        else:
            plan = subscription.plan
            form = RecordPaymentForm(
                initial={
                    "plan": plan,
                    "months": 1,
                    "amount_ttc": amounts_from_ht(plan.price_amount, currency=plan.currency)["amount"],
                    "method": "mobile_money",
                    "extend": True,
                }
            )
        context = {
            **self.admin_site.each_context(request),
            "title": f"Enregistrer un paiement — {subscription.organization}",
            "subscription": subscription,
            "form": form,
            "opts": self.model._meta,
            "base_from": SubscriptionService.extension_base(subscription),
        }
        return TemplateResponse(request, "admin/billing/subscription/record_payment.html", context)


# --------------------------------------------------------------------------- factures


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Factures : les virements (mode « online ») se valident ici — filtrer par statut
    « Justificatif à valider », ouvrir le justificatif, lancer « Valider » ou « Refuser »."""

    list_display = [
        "number", "buyer_name", "plan", "months", "amount", "currency", "status", "provider",
        "paid_at", "created_at", "pdf_link",
    ]
    list_filter = ["status", "provider", "plan"]
    search_fields = ["number", "buyer_name", "organization__name", "provider_reference"]
    autocomplete_fields = ["organization"]
    list_select_related = ["plan", "organization"]
    readonly_fields = ["number", "seller", "buyer", "reviewed_by", "created_at", "updated_at", "pdf_link"]
    actions = ["approve_bank_transfer", "reject_invoice"]

    @admin.display(description="PDF")
    def pdf_link(self, obj):
        if not obj.pk:
            return "—"
        return format_html('<a href="{}">Télécharger</a>', reverse("admin:billing_invoice_pdf", args=[obj.pk]))

    def get_urls(self):
        custom = [
            path("<uuid:invoice_id>/pdf/", self.admin_site.admin_view(self.pdf_view), name="billing_invoice_pdf"),
        ]
        return custom + super().get_urls()

    def has_delete_permission(self, request, obj=None):
        # Pièces comptables : on les annule (statut), on ne les supprime pas.
        return request.user.is_superuser

    def pdf_view(self, request, invoice_id):
        invoice = get_object_or_404(Invoice.objects.select_related("plan"), pk=invoice_id)
        try:
            pdf_bytes = render_invoice_pdf(invoice)
        except OSError:
            logger.exception("Génération du PDF de facture impossible.")
            self.message_user(request, "WeasyPrint n'est pas disponible sur ce serveur.", messages.ERROR)
            return redirect("admin:billing_invoice_change", invoice.pk)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{invoice_filename(invoice)}"'
        return response

    @admin.action(description="Valider le paiement (marquer payée + prolonger l'abonnement)")
    def approve_bank_transfer(self, request, queryset):
        count = 0
        for invoice in queryset.filter(status__in=[Invoice.Status.PENDING, Invoice.Status.PENDING_REVIEW]):
            try:
                InvoiceService.settle(invoice=invoice, reviewed_by=request.user)
                count += 1
            except InvoiceError as exc:
                self.message_user(request, f"{invoice.number} : {exc}", messages.WARNING)
        self.message_user(request, f"{count} facture(s) validée(s).")

    @admin.action(description="Refuser (justificatif non conforme, paiement non reçu)")
    def reject_invoice(self, request, queryset):
        count = 0
        for invoice in queryset.filter(status__in=[Invoice.Status.PENDING, Invoice.Status.PENDING_REVIEW]):
            InvoiceService.reject(invoice=invoice, reviewed_by=request.user, reason="Refusée depuis l'administration.")
            count += 1
        self.message_user(request, f"{count} facture(s) refusée(s).")


@admin.register(BillingProfile)
class BillingProfileAdmin(admin.ModelAdmin):
    list_display = ["organization", "legal_name", "niu", "rccm", "email", "phone"]
    search_fields = ["organization__name", "legal_name", "niu", "rccm"]
    autocomplete_fields = ["organization"]
