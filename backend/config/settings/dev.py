from .base import *  # noqa: F401,F403

DEBUG = True

INSTALLED_APPS += ["django_extensions"] if env.bool("DJANGO_USE_EXTENSIONS", default=False) else []  # noqa: F405

# Documentation de l'API ouverte à tous en local.
SPECTACULAR_SETTINGS = {  # noqa: F405
    **SPECTACULAR_SETTINGS,  # noqa: F405
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
}

# Le REDIS_URL du .env vise souvent l'hôte Docker « redis », injoignable hors Docker : en
# local la limitation de débit garde ses compteurs en mémoire (un seul processus).
if not env.bool("DJANGO_DEV_REDIS_CACHE", default=False):  # noqa: F405
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "presse"}}
