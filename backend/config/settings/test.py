from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "test-secret-key"

DATABASES["default"] = env.db(  # noqa: F405
    "DATABASE_URL", default="postgres://revue:revue@localhost:5432/revue_de_presse_test"
)

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

# Les tests ne doivent JAMAIS appeler un service externe réel — même si le .env
# partagé à la racine (utilisé aussi par le serveur de dev) contient de vraies clés.
# Sans ça : quota Mistral consommé par la suite de tests, flakiness (rate limiting),
# risque d'appels Stripe/CamPay réels pendant `pytest`.
MISTRAL_API_KEY = ""
STRIPE_SECRET_KEY = ""
CAMPAY_APP_USERNAME = ""
CAMPAY_APP_PASSWORD = ""

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

MEDIA_ROOT = BASE_DIR / "test_mediafiles"  # noqa: F405
