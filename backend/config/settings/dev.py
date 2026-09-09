from .base import *  # noqa: F401,F403

DEBUG = True

INSTALLED_APPS += ["django_extensions"] if env.bool("DJANGO_USE_EXTENSIONS", default=False) else []  # noqa: F405
