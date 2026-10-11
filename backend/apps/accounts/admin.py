from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils import timezone
from django.utils.html import format_html

from .models import Invitation, Membership, Organization, User
from .services import password_reset_expiry, password_reset_url


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["-date_joined"]
    list_display = ["email", "full_name", "is_staff", "is_active", "date_joined", "terms_version"]
    search_fields = ["email", "full_name"]
    readonly_fields = ["accepted_terms_at", "terms_version", "sessions_revoked_at"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Informations", {"fields": ("full_name",)}),
        ("Droits", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Conditions et sessions", {"fields": ("accepted_terms_at", "terms_version", "sessions_revoked_at")}),
        ("Dates", {"fields": ("last_login",)}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "full_name", "password1", "password2")}),
    )
    filter_horizontal = ("groups", "user_permissions")
    actions = ["generate_password_reset_links"]

    @admin.action(description="Générer un lien de réinitialisation du mot de passe (à transmettre)")
    def generate_password_reset_links(self, request, queryset):
        """Tant que l'e-mail n'est pas configuré : le staff transmet le lien (WhatsApp…) au
        lieu d'un mot de passe en clair. Lien à usage unique, invalidé par une connexion."""
        expires_label = timezone.localtime(password_reset_expiry()).strftime("%d/%m/%Y %H:%M")
        for user in queryset:
            reset_url = password_reset_url(user)
            self.message_user(
                request,
                format_html(
                    "{} : <a href='{}'>{}</a> (valable jusqu'au {})", user.email, reset_url, reset_url, expires_label
                ),
                level=messages.INFO,
            )


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["user"]


class ClosedOrganizationFilter(admin.SimpleListFilter):
    title = "fermeture"
    parameter_name = "fermee"

    def lookups(self, request, model_admin):
        return [("oui", "Fermées"), ("non", "Actives")]

    def queryset(self, request, queryset):
        if self.value() == "oui":
            return queryset.filter(closed_at__isnull=False)
        if self.value() == "non":
            return queryset.filter(closed_at__isnull=True)
        return queryset


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "contact_phone", "country", "created_at", "closed_at"]
    list_filter = [ClosedOrganizationFilter]
    search_fields = ["name", "slug", "contact_phone"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["closed_at", "closed_by", "closure_reason"]
    inlines = [MembershipInline]
    actions = ["grant_trial", "reopen"]

    @admin.action(description="Offrir l'essai gratuit (organisations sans abonnement)")
    def grant_trial(self, request, queryset):
        # Import tardif : billing dépend des modèles de accounts.
        from apps.billing.services import SubscriptionService

        for organization in queryset:
            subscription = SubscriptionService.start_trial(organization=organization)
            if subscription is None:
                self.message_user(
                    request,
                    f"{organization} : pas d'essai (abonnement existant, essai désactivé ou aucune formule).",
                    level=messages.WARNING,
                )
            else:
                self.message_user(
                    request,
                    f"{organization} : essai {subscription.plan.name} jusqu'au "
                    f"{subscription.current_period_end:%d/%m/%Y}.",
                )

    @admin.action(description="Rouvrir les organisations fermées")
    def reopen(self, request, queryset):
        count = queryset.filter(closed_at__isnull=False).update(closed_at=None, closed_by=None, closure_reason="")
        self.message_user(request, f"{count} organisation(s) rouverte(s).")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["organization", "user", "role", "created_at"]
    list_filter = ["role"]
    autocomplete_fields = ["organization", "user"]


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ["email", "organization", "role", "status", "expires_at"]
    list_filter = ["status", "role"]
    search_fields = ["email"]
