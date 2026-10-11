"""Choix du module de settings par les points d'entrée (manage.py, wsgi, asgi, Celery).

Ordre de priorité :
1. la variable d'environnement DJANGO_SETTINGS_MODULE (PM2, Docker, launch.json…) ;
2. la ligne DJANGO_SETTINGS_MODULE du .env à la racine du dépôt (celui que lit
   config.settings.base) — en production : DJANGO_SETTINGS_MODULE=config.settings.prod ;
3. à défaut seulement, config.settings.dev, AVEC un avertissement sur stderr.

Le repli (3) garde le développement local sans configuration, mais ne peut plus passer
inaperçu ; et config.settings.dev refuse de démarrer derrière un vrai nom de domaine
(voir config.settings_guard)."""
import os
import re
import sys
from pathlib import Path

DEV_SETTINGS = "config.settings.dev"
ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"

_SETTINGS_LINE = re.compile(
    r"""^\s*(?:export\s+)?DJANGO_SETTINGS_MODULE\s*=\s*["']?([A-Za-z_][\w.]*)["']?\s*(?:\#.*)?$"""
)


def settings_module_from_env_file(path=ENV_FILE):
    """Valeur de DJANGO_SETTINGS_MODULE dans le .env (dernière occurrence), sinon None.
    Ne charge AUCUNE autre variable : c'est le rôle de config.settings.base."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    found = None
    for line in lines:
        match = _SETTINGS_LINE.match(line)
        if match:
            found = match.group(1)
    return found


def configure_settings_module(env_file=ENV_FILE):
    """Fixe os.environ["DJANGO_SETTINGS_MODULE"] s'il ne l'est pas encore ; renvoie la valeur."""
    current = os.environ.get("DJANGO_SETTINGS_MODULE")
    if current:
        return current
    module = settings_module_from_env_file(env_file)
    if not module:
        module = DEV_SETTINGS
        sys.stderr.write(
            "AVERTISSEMENT : DJANGO_SETTINGS_MODULE n'est défini ni dans l'environnement ni dans "
            f"le .env -> {DEV_SETTINGS} (développement). En production, définissez "
            "DJANGO_SETTINGS_MODULE=config.settings.prod.\n"
        )
    os.environ["DJANGO_SETTINGS_MODULE"] = module
    return module
