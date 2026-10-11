"""Contrôles de sécurité lancés par `python manage.py check --deploy` (avant chaque mise
en production) : ils signalent une configuration qui affaiblirait les protections."""
from django.conf import settings
from django.core.checks import Tags, Warning, register
from rest_framework.settings import api_settings


@register(Tags.security, deploy=True)
def check_security_settings(app_configs, **kwargs):
    warnings = []
    if settings.ADMIN_URL == "admin/":
        warnings.append(
            Warning(
                "L'administration Django est servie sur /admin/, le premier chemin essayé par les robots.",
                hint="Définissez DJANGO_ADMIN_URL avec un chemin difficile à deviner (ex. gestion-7f3k9q/).",
                id="core.W001",
            )
        )
    if "LocMemCache" in settings.CACHES["default"]["BACKEND"]:
        warnings.append(
            Warning(
                "Le cache est local à chaque processus : la limitation de débit n'est pas partagée "
                "entre les workers gunicorn.",
                hint="Définissez REDIS_URL (ex. redis://127.0.0.1:6379/2).",
                id="core.W002",
            )
        )
    if not settings.MEDIA_X_ACCEL_REDIRECT:
        warnings.append(
            Warning(
                "Les fichiers clients sont envoyés par Django lui-même (un worker est bloqué par téléchargement).",
                hint="Activez MEDIA_X_ACCEL_REDIRECT et l'emplacement nginx de ops/nginx/presse-media.conf.",
                id="core.W003",
            )
        )
    if api_settings.NUM_PROXIES is None:
        warnings.append(
            Warning(
                "DJANGO_NUM_PROXIES n'est pas défini : derrière nginx, l'IP du client utilisée par la "
                "limitation de débit peut être falsifiée via X-Forwarded-For.",
                hint="Définissez DJANGO_NUM_PROXIES=1 (nginx seul), 2 derrière un CDN comme Cloudflare.",
                id="core.W004",
            )
        )
    return warnings
