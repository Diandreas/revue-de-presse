from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

DEBUG = False

# La clé secrète signe les sessions, les jetons de connexion et les liens vers les fichiers
# clients : la production refuse de démarrer sans une vraie clé fournie par l'environnement.
# Générer : python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
PUBLIC_SECRET_KEYS = {"dev-insecure-key-change-me", "test-secret-key", "change-me", "changeme", "secret"}
SECRET_KEY = env("DJANGO_SECRET_KEY", default="")  # noqa: F405


def _require_strong_secret_key(value):
    if not value or value in PUBLIC_SECRET_KEYS or value.startswith("django-insecure"):
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY est absente ou publique : la production refuse de démarrer. "
            "Renseignez une clé aléatoire d'au moins 50 caractères dans le .env."
        )
    if len(value) < 50 or len(set(value)) < 5:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY est trop faible (au moins 50 caractères variés) : la production refuse de démarrer."
        )


_require_strong_secret_key(SECRET_KEY)

SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Derrière nginx : fichiers clients envoyés par nginx (X-Accel-Redirect, cf.
# ops/nginx/presse-media.conf) et IP du client lue dans X-Forwarded-For (1 proxy).
MEDIA_X_ACCEL_REDIRECT = env.bool("MEDIA_X_ACCEL_REDIRECT", default=True)  # noqa: F405
REST_FRAMEWORK = {**REST_FRAMEWORK, "NUM_PROXIES": env.int("DJANGO_NUM_PROXIES", default=1)}  # noqa: F405
