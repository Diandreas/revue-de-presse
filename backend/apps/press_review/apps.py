from django.apps import AppConfig


class PressReviewConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.press_review"
    label = "press_review"
    verbose_name = "Revues de presse"

    def ready(self):
        from . import signals  # noqa: F401 — branche l'effacement des fichiers (post_delete)
