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

# Celery lit CELERY_BROKER_URL et CELERY_RESULT_BACKEND DIRECTEMENT dans l'environnement,
# avec priorité sur les settings Django — et django-environ y injecte ceux du .env (hôte
# Docker `redis`). Sans ce forçage, un test qui démarre un vrai worker tenterait de
# joindre Redis (broker ET backend de résultats).
import os  # noqa: E402

os.environ["CELERY_BROKER_URL"] = CELERY_BROKER_URL
os.environ["CELERY_RESULT_BACKEND"] = CELERY_RESULT_BACKEND

# Les tests ne doivent JAMAIS appeler un service externe réel — même si le .env
# partagé à la racine (utilisé aussi par le serveur de dev) contient de vraies clés.
# Sans ça : quota Mistral consommé par la suite de tests, flakiness (rate limiting),
# risque d'appels Stripe/CamPay réels pendant `pytest`.
MISTRAL_API_KEY = ""
MISTRAL_ALLOW_FAKE_CLIENT = True  # DEBUG=False ici : le client factice doit être explicitement permis
# Limiteur de débit IA coupé : ses compteurs (cache mémoire) survivraient d'un test à l'autre.
# tests/test_ai_cost_control.py le teste explicitement.
AI_RATE_LIMIT_GLOBAL_PER_MINUTE = 0
AI_RATE_LIMIT_ORG_PER_MINUTE = 0
OCR_ENGINE = "tesseract"  # jamais d'appel Mistral pour lire une image en test (les tests stubent pytesseract)
STRIPE_SECRET_KEY = ""
CAMPAY_APP_USERNAME = ""
CAMPAY_APP_PASSWORD = ""

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

MEDIA_ROOT = BASE_DIR / "test_mediafiles"  # noqa: F405
