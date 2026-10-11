from django.core.asgi import get_asgi_application

from config.bootstrap import configure_settings_module

# Pas de repli silencieux sur config.settings.dev en production : voir config/bootstrap.py.
configure_settings_module()

application = get_asgi_application()
