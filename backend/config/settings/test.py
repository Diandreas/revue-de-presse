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
OCR_ENGINE = "tesseract"  # jamais d'appel Mistral pour lire une image en test (les tests stubent pytesseract)
STRIPE_SECRET_KEY = ""
STRIPE_WEBHOOK_SECRET = ""
CAMPAY_APP_USERNAME = ""
CAMPAY_APP_PASSWORD = ""
CAMPAY_WEBHOOK_SECRET = ""

# Facturation : valeurs figées, indépendantes du .env de la machine (les tests du mode
# « online » le réactivent explicitement).
BILLING_MODE = "manual"
BILLING_GRACE_DAYS = 3
BILLING_VAT_RATE = "19.25"
BILLING_INVOICE_PREFIX = "RDP"
BILLING_SELLER_NAME = "Revue de Presse SARL"
BILLING_SELLER_ADDRESS = "Douala, Cameroun"
BILLING_SELLER_RCCM = "RC/DLA/2026/B/0001"
BILLING_SELLER_NIU = "M012600000001A"
BILLING_SELLER_EMAIL = "facturation@example.com"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

MEDIA_ROOT = BASE_DIR / "test_mediafiles"  # noqa: F405

# Sécurité : jamais de Redis réel (compteurs de limitation vidés avant chaque test, cf.
# conftest.py), fichiers servis par Django, valeurs indépendantes du .env partagé.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "presse-tests"}}
MEDIA_X_ACCEL_REDIRECT = False
ADMIN_URL = "admin/"
REST_FRAMEWORK = {**REST_FRAMEWORK, "NUM_PROXIES": None}  # noqa: F405
