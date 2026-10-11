from django.contrib import admin

from .models import NotificationLog, NotificationPreference


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "email_review_updates", "updated_at")
    list_filter = ("email_review_updates",)
    search_fields = ("user__email",)


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("kind", "key", "created_at")
    list_filter = ("kind",)
    search_fields = ("key",)
    readonly_fields = ("kind", "key", "created_at")
