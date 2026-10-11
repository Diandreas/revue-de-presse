from django.core.exceptions import ImproperlyConfigured

from config.sentry import init_sentry, read_revision

from .base import *  # noqa: F401,F403

DEBUG = False

SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 7
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# La valeur de repli de base.py est publique (dépôt) : en production elle permettrait de
# forger des sessions et des jetons. On refuse de démarrer sans vraie clé.
if not env("DJANGO_SECRET_KEY", default="") or SECRET_KEY == "dev-insecure-key-change-me":  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY doit être défini (valeur longue et aléatoire) en production.")

# --- Supervision : Sentry (facultatif, actif seulement si SENTRY_DSN est défini) ---
# Initialisé ici (et non dans base.py) : jamais d'envoi depuis les tests ni le poste de dev.
SENTRY_DSN = env("SENTRY_DSN", default="")  # noqa: F405
init_sentry(
    dsn=SENTRY_DSN,
    environment=env("SENTRY_ENVIRONMENT", default="production"),  # noqa: F405
    release=env("SENTRY_RELEASE", default="") or read_revision(BASE_DIR),  # noqa: F405
    traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0),  # noqa: F405
)
