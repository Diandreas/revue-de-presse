from django.core.exceptions import ImproperlyConfigured

from config.settings_guard import public_hosts

from .base import *  # noqa: F401,F403

DEBUG = True

INSTALLED_APPS += ["django_extensions"] if env.bool("DJANGO_USE_EXTENSIONS", default=False) else []  # noqa: F405

# DEBUG=True derrière un vrai domaine = traces d'erreur (et secrets) exposées : on refuse
# de démarrer. Échappatoire volontaire (tunnel ngrok de test…) : la variable ci-dessous.
_public = public_hosts(ALLOWED_HOSTS)  # noqa: F405
if _public and not env.bool("DJANGO_ALLOW_DEV_SETTINGS_ON_PUBLIC_HOSTS", default=False):  # noqa: F405
    raise ImproperlyConfigured(
        f"config.settings.dev (DEBUG=True) chargé pour un domaine public ({', '.join(_public)}). "
        "En production : DJANGO_SETTINGS_MODULE=config.settings.prod (variable d'environnement ou .env)."
    )
