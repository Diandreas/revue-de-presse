"""Sentry (facultatif) : erreurs Django ET Celery remontées avec leur contexte.

Activé seulement si SENTRY_DSN est défini (config.settings.prod). Sans le paquet
sentry-sdk (requirements/prod.txt), on avertit au lieu d'empêcher le démarrage."""
import sys
from pathlib import Path


def read_revision(base_dir):
    """Commit déployé (fichier REVISION écrit par ops/deploy/deploy.sh), sinon ""."""
    try:
        return (Path(base_dir) / "REVISION").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def init_sentry(*, dsn, environment="production", release="", traces_sample_rate=0.0):
    """Renvoie True si Sentry a été initialisé."""
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.django import DjangoIntegration
    except ImportError:
        # Le logging de Django n'est pas encore configuré à ce stade : stderr direct.
        sys.stderr.write("AVERTISSEMENT : SENTRY_DSN est défini mais sentry-sdk n'est pas installé.\n")
        return False
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release or None,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=traces_sample_rate,
        # Pas d'e-mails, d'IP ni de corps de requête (documents clients) chez un tiers.
        send_default_pii=False,
        max_request_body_size="never",
    )
    return True
