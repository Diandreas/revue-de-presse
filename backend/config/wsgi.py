from django.core.wsgi import get_wsgi_application

from config.bootstrap import configure_settings_module

# Pas de repli silencieux sur config.settings.dev en production : voir config/bootstrap.py.
configure_settings_module()

application = get_wsgi_application()
