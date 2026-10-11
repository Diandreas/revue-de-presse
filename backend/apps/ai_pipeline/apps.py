from django.apps import AppConfig


class AiPipelineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ai_pipeline"
    label = "ai_pipeline"
    verbose_name = "Pipeline IA"

    def ready(self):
        from . import checks  # noqa: F401 - enregistre les vérifications de configuration
