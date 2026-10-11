from celery import Celery

from .bootstrap import configure_settings_module

# Pas de repli silencieux sur config.settings.dev en production : voir config/bootstrap.py.
configure_settings_module()

app = Celery("revue_de_presse")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
