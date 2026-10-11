"""Vérifications de configuration (`manage.py check`, lancé aussi par migrate / runserver)."""
from django.conf import settings
from django.core import checks


@checks.register(checks.Tags.compatibility)
def mistral_key_configured(app_configs=None, **kwargs):
    """Hors DEBUG, une clé Mistral absente sans client factice explicitement permis ferait
    échouer chaque revue : on le signale dès le déploiement plutôt qu'au premier client."""
    from .mistral_client import fake_client_allowed

    if settings.DEBUG or settings.MISTRAL_API_KEY or fake_client_allowed():
        return []
    return [
        checks.Warning(
            "MISTRAL_API_KEY est vide : toutes les revues échoueront (« service d'IA non configuré »).",
            hint="Renseignez MISTRAL_API_KEY dans le .env du serveur (ou MISTRAL_ALLOW_FAKE_CLIENT=true pour une démo).",
            id="ai_pipeline.W001",
        )
    ]
